# Design Document

This document explains the key engineering decisions behind the VIKMO Dealer Assistant and demand forecasting module.

## Architecture Overview

```text
User (React / Streamlit / API)
        |
        v
DealerAssistant (LangGraph StateGraph)
        |
        +--> Guardrails        (domain check, refuse off-topic)
        +--> Entity extraction (vehicle, category, SKU, intent)
        +--> Clarification     (ask for missing vehicle/category)
        +--> Retrieval         (ChromaDB vector search + metadata filters + rerank)
        +--> Tools             (check_stock, find_parts_by_vehicle, create_order)
        +--> Generation        (Groq LLM or deterministic grounded formatter)
        |
        v
Grounded answer + tool traces + order summary
```

The graph is a **single-pass DAG**, not a ReAct loop. Intent routing is deterministic (regex + catalogue vocabulary), which keeps latency predictable and makes evaluation reproducible without an API key.

## Retrieval Approach

### Why one document per SKU (no chunking)

The catalogue is structured tabular data (~600 rows). Each row becomes one retrieval document:

```text
SKU: BRK-1042 | Name: Brake Disc Rotor — Bajaj Dominar 400 | Category: Brakes |
Brand: Brembo | Vehicle: Bajaj Dominar 400 | Price INR: 2470 | Stock: 43 | ...
```

Chunking long prose is unnecessary here; row-level indexing gives precise SKU-level retrieval and clean metadata filtering.

### Embedding and indexing

- **Model:** `sentence-transformers/all-MiniLM-L6-v2` (384-dim, fast, good for short product text)
- **Store:** ChromaDB persistent collection with cosine HNSW
- **Cache:** Model weights cached under `models/`; index persisted under `chroma/`
- **Rebuild:** Index rebuilds automatically when catalogue row count changes

### Retrieval pipeline

1. **Entity extraction** pulls vehicle, category, brand, SKU, product keyword from the user message and slot memory.
2. **Metadata filters** narrow Chroma queries (`vehicle_fitment`, `category`, `brand`, `sku`).
3. **Vector search** retrieves top-20 candidates when filters alone are insufficient.
4. **Reranking** boosts lexical overlap, metadata matches, and in-stock items.
5. **SKU shortcut** bypasses vector search when a SKU is known.

### Why this scales beyond prompt-stuffing

600 SKUs × ~100 tokens each ≈ 60K tokens — too large for reliable in-context use. Retrieval returns only the top 3–12 relevant rows, keeping prompts small and grounded.

## Tool Design

| Tool | Trigger | Input | Output |
|------|---------|-------|--------|
| `check_stock` | Intent `check_stock` + SKU | `{sku}` | `{sku, name, stock, available, price_inr}` |
| `find_parts_by_vehicle` | Intent `find_parts` + vehicle | `{vehicle, category?}` | `[{sku, name, category, brand, price_inr, stock}]` |
| `create_order` | Intent `create_order` + resolvable payload | Pydantic `Order` | `{dealer, status, items[], total_inr, errors[]}` |

### How the model decides to call tools

Tools are **not** invoked via LLM function-calling. Intent is inferred heuristically:

- Order verbs (`order`, `buy`, `place`) → `create_order`
- Stock phrases (`check stock`, `availability`) → `check_stock` (but not "do you stock" catalogue browsing)
- Vehicle + fitment phrases (`parts for`, `do you have`, `show`) → `find_parts_by_vehicle`
- Everything else → search + retrieval

This trades agentic flexibility for **reliability and testability** — the assignment prioritises correct tool invocation over open-ended reasoning.

### Structured order output

`create_order` validates input through Pydantic:

```python
class OrderItem(BaseModel):
    sku: str
    quantity: int = Field(gt=0)

class Order(BaseModel):
    dealer: str = Field(..., min_length=2)
    items: list[OrderItem] = Field(..., min_length=1)
```

The tool checks stock availability and returns a typed summary — never free-text order JSON.

## Prompt Design and Guardrails

### System prompt rules

- Answer **only** from retrieved products and tool outputs
- Never invent prices, stock levels, or SKUs
- Ask clarifying questions when vehicle or category is missing
- Refuse non-automotive requests politely

### Guardrail layers

1. **Domain gate:** Keyword set (`brake`, `tyre`, `order`, `stock`, brand names, etc.) plus conversation history and filled slots
2. **Clarification gate:** Blocks retrieval until vehicle/category/SKU is sufficient
3. **Doc relevance filter:** Drops retrieved docs whose category/vehicle doesn't match extracted entities
4. **Deterministic fallbacks:** Cheapest-query formatter and product-list formatter when LLM is disabled
5. **Empty-retrieval guard:** Returns "couldn't find any matching products" instead of hallucinating

### Anti-hallucination strategy

Grounding is enforced at three levels: retrieval constraints, tool outputs with catalogue lookups, and prompt instructions. When Groq is enabled, temperature is 0.1 and the context block includes explicit slots and retrieved rows.

## Conversation Handling

`ConversationMemory` persists slots across turns:

| Slot | Example |
|------|---------|
| `vehicle` | Bajaj Pulsar 150 |
| `category` | Brakes |
| `product_keyword` | brake pad |
| `sku` | BRK-1042 |
| `quantity` | 10 |
| `dealer` | ABC Motors |

Follow-up queries like "which one is the cheapest" reuse slots from the previous turn. Pricing follow-ups skip strict product-keyword filtering so category-level results (e.g. tubes vs tyres) are not over-narrowed.

## Evaluation Methodology

### Why we evaluate this way

A conversational assistant can *sound* correct while being wrong — wrong SKU, wrong price, wrong tool, or a confident answer with no catalogue backing. We split evaluation into two layers:

1. **Retrieval quality** — did we fetch the right products before the LLM ever spoke?
2. **Behaviour quality** — did the graph route correctly, call the right tool, stay grounded, and clarify when it should?

That mirrors how production teams ship assistants: retrieval regressions and behaviour regressions are different failure modes and need different metrics.

### Eval set (`eval/test_cases.json`)

**20 cases** across seven categories:

| Category | Count | What we are testing |
|----------|-------|---------------------|
| Happy path | 6 | Search, stock, order, cheapest query |
| Ambiguous | 4 | Missing vehicle, Duke/Pulsar model ambiguity |
| Out of domain | 2 | Weather, jokes |
| Hallucination | 1 | Unsupported make (Ferrari) — must refuse, not invent parts |
| Multi-turn | 4 | Clarify → search; search → cheapest → stock → order |
| Tool chaining | 1 | Cheapest follow-up then stock check on same SKU |
| Context / guardrails | 2 | Pricing follow-ups, unsupported-make orders |

Each case asserts route, optional tool name, retrieval relevance terms, and substrings the answer must contain. Multi-turn cases replay prior user/assistant turns so slot memory is actually exercised — not just single-shot prompts.

### Metrics

| Metric | Definition | Why it matters |
|--------|------------|----------------|
| Hit Rate@3 | Top-3 docs include a row matching all relevant terms | Dealer sees the right part in the first screen of results |
| MRR | Reciprocal rank of first relevant doc | Penalises burying the correct SKU on page 2 |
| Context precision | Share of top-k docs that are relevant | Measures noise in the context window |
| Route accuracy | Graph took clarify / retrieve / refuse / tool path as expected | Wrong route → wrong behaviour even with good retrieval |
| Tool accuracy | Expected tool appears in traces | Stock and orders must come from structured lookups |
| Grounding accuracy | Answer cites catalogue-backed SKU, price, or stock | Catches hallucinations and vague replies |
| Clarification accuracy | Ambiguous input triggers a useful question | Better than guessing vehicle or category |
| Overall success | All per-case checks pass | Single number for CI-style regression |

**Latest run:** [eval/results.md](eval/results.md) — **20/20 passed**, behaviour metrics at **1.0**, retrieval hit rate **0.78**.

Retrieval at 0.78 is honest: some queries ("chain lube", broad category terms) have several valid SKUs. Perfect hit rate would mean over-fitting the eval set. We still track it so embedding or reranker changes do not silently regress.

### Failure analysis — what broke in development and how eval caught it

These are real bugs found while building, not hypothetical rows:

| Query / scenario | Symptom | Root cause | Fix |
|------------------|---------|------------|-----|
| "What's the cheapest chain lube you stock?" | Asked for vehicle instead of searching | `"stock"` in `"you stock?"` triggered `check_stock` intent | Split catalogue-browsing phrases from stock-lookup phrases |
| "Order 10 units of BRK-1042 for ABC Motors" | Dealer parsed as `"10 units of..."` | First `for` clause captured instead of dealer name | Take last valid `for <name>`; reject numeric/SKU fragments |
| "which one is cheapest" after tyre search | No products returned | Keyword filter removed valid matches (Tube vs tyre) | Skip keyword filter on pricing follow-ups |
| "how many in stock?" after failed order | "Which vehicle or SKU?" | `focus_sku` wiped after order turn; stock follow-up not contextual | `is_stock_followup()` + preserve SKU after order success/failure |
| "can you order fereari" (typo) | Ordered wrong SKU from stale context | Stale `focus_sku` + loose order intent | Unsupported-make detection; focused-order follow-up rules |
| "place order for 46 units" (over stock) | UI showed BRK-1042 but next turn lost it | Order failure path did not refresh slot memory | `_remember_order_sku()` after every order attempt |
| Ferrari parts request | Could hallucinate exotic inventory | No guard for unsupported OEMs | `detect_unsupported_make()` → polite refusal |
| `find_parts_by_vehicle` in UI | Empty product cards | Tool output not copied to `retrieved_docs` | Sync tool results into state for UI and eval |

The pattern: **most production bugs here were state and routing bugs, not embedding bugs.** Evaluation with multi-turn replay is what exposed them.

### What would still break in production

- Part names outside `PRODUCT_HINTS` / `CATEGORY_ALIASES` may miss category extraction
- LLM mode (Groq enabled) adds non-determinism despite low temperature — CI runs primarily on deterministic path
- In-memory sessions do not survive server restart — would need Redis/DB for horizontal scale
- No hybrid BM25 + vector retrieval yet — keyword-heavy SKU queries rely on metadata shortcut

## Forecasting (Part B)

### Where Prophet lives in this project

**Important:** Prophet is **not** called from the chat assistant. There is no "forecast demand" tool in LangGraph.

```text
sales_history.csv  →  forecasting/evaluate.py  →  per-SKU Prophet models  →  results.md / plots
catalogue.csv      →  assistant/retrieval.py   →  ChromaDB                 →  dealer chat
```

The two pipelines share a repo because both answer dealer operations questions — *what to sell today* (chat) vs *what to stock next month* (forecast). In a real deployment they would feed the same dashboard but stay separate services so model retraining does not block live chat latency.

### The business problem

Dealers over-stock slow movers and under-stock promo SKUs. Given 78 weeks of weekly `units_sold` for 30 SKUs (with `promo_flag` spikes), predict demand for the **next 4 weeks** and compare approaches fairly.

### Validation scheme

```text
|<-------- Train (74 weeks) -------->|<-- Test (4 weeks) -->|
```

- Cutoff: last 4 unique dates in `sales_history.csv`
- Train: all rows before cutoff
- Test: rows on or after cutoff
- Metrics: MAE and MAPE on test rows only — no random shuffling (time series respect order)

### Leakage prevention

**Baseline (4-week moving average):**

```python
group["forecast"] = group["units_sold"].shift(1).rolling(window=4).mean()
```

`shift(1)` ensures week *t* never sees week *t* actuals. We concatenate train+test only to keep the rolling window continuous; **scoring** uses test keys only.

**Prophet:** Each SKU gets its own model, fit **only** on train rows. Test-window `promo_flag` values are passed in as a regressor — promotions are known in advance in this dataset, which matches real planning (marketing calendar → warehouse prep).

### Why Prophet (and why not just use the chat LLM)?

| Approach | Role here |
|----------|-----------|
| **4-week moving average** | Simple, interpretable baseline every ops team understands |
| **Prophet** | Captures weekly seasonality + promo lifts that averages smooth away |
| **LLM / RAG** | Wrong tool — language models do not reliably forecast numeric demand from tabular history |

We chose Prophet because:

1. **Promo spikes** — moving average lags after a promotion; Prophet's regressor reacts when `promo_flag=1`
2. **Per-SKU heterogeneity** — brake pads and chain lube have different seasonality; one global model would blur that
3. **Interpretability** — stakeholders can see trend + seasonality components; important for supply-chain buy-in
4. **Industry fit** — Prophet (and successors like NeuralProphet) are common for retail/intermittent demand when you have dated rows and known events

### Where Prophet is used in the real world

Prophet-style forecasting shows up wherever teams need **explainable short-horizon demand** without building a full ML platform:

- **Retail & e-commerce** — SKU-level reorder quantities, safety stock, warehouse labour planning
- **Auto parts distributors** — exactly this domain: thousands of SKUs, promo weeks, slow movers
- **Finance ops** — cash-flow and transaction volume with holiday seasonality
- **Capacity planning** — call-centre staffing, server scaling from daily active users

It is usually **not** embedded inside a customer-facing chatbot. It runs on a schedule (nightly/weekly), writes forecasts to a database, and dashboards or ERP systems consume them. This project mirrors that: offline batch job, results in `forecasting/results.md`, optional plots in `screenshots/`.

### Results

See [forecasting/results.md](forecasting/results.md).

| Model | MAE | MAPE |
|-------|-----|------|
| 4-week moving average | 7.858 | 32.09% |
| Prophet per-SKU | **5.805** | **26.59%** |

Prophet wins on MAE (~26% lower error). The baseline remains the right fallback for SKUs with very short history or when you need zero dependencies — production systems often ship baseline first, add Prophet where error reduction pays for complexity.

### Complexity justification

One moving average is easy to explain in a stand-up. Prophet costs more CPU and tuning but pays back on promo-sensitive SKUs. We rejected a single global model because demand shapes differ too much across part categories.

## Production Considerations

| Concern | Current state | Production next step |
|---------|--------------|---------------------|
| Session storage | In-memory per server process | Redis or PostgreSQL session store |
| Order persistence | `orders.json` on confirm | ERP / OMS integration |
| Auth | None | Dealer API keys or OAuth |
| Observability | Print logging | Structured logs + tracing (LangSmith) |
| Scaling | Single Flask worker | Gunicorn + horizontal scaling behind load balancer |
| Index updates | Rebuild on row-count change | Incremental Chroma upserts on catalogue sync |

## Development Challenges — What Broke and How We Fixed It

Most of this project did not fail on embeddings or model size. It failed on **conversation state** — the boring stuff that separates a demo from something you could put in front of a dealer.

### The pattern we kept hitting

```text
User says something reasonable
    → routing picks the wrong intent
    → OR slots from turn N pollute turn N+1
    → assistant looks "dumb" even though retrieval was fine
```

Our eval suite with **multi-turn replay** is what caught these. Single-shot tests would have passed while the UI felt broken.

### Issue 1 — One word broke routing

**Symptom:** *"What's the cheapest chain lube you stock?"* → assistant asked for a vehicle.

**Cause:** The substring `"stock"` in `"you stock?"` matched stock-lookup intent, not catalogue browsing.

**Fix:** Split phrase lists — `CATALOGUE_STOCK_PHRASES` ("do you stock", "you carry") vs `STOCK_PHRASES` ("check stock", "how many in stock").

**Lesson:** Intent routing is lexical surgery. One false positive matters.

---

### Issue 2 — Slot memory amnesia

**Symptom:** User discusses BRK-1042, tries to order 46 units (only 43 in stock), then asks *"how many in stock?"* → *"Which vehicle or SKU should I look up?"*

**Cause:** Two bugs stacked:
1. After an order turn, `focus_sku` was copied to `sku` but then **deleted** by slot cleanup because `focus_sku` was not kept in entities.
2. Stock follow-ups like *"how many in stock?"* were not treated as contextual — they don't say *"it"*, so the reference resolver never fired.

**Fix:** `is_stock_followup()`, `_remember_order_sku()` after every order attempt, and preserve both `sku` + `focus_sku` on focused follow-ups.

**Lesson:** Production assistants fail on **pronoun resolution and implicit references**, not on vector search quality.

---

### Issue 3 — Stale context caused wrong orders

**Symptom:** *"can you order fereari"* (typo) still drafted an order for a completely different SKU from a prior turn.

**Cause:** Any message containing `"order"` triggered `create_order` while `focus_sku` and `quantity` were still in memory from an earlier search.

**Fix:** `is_focused_order_followup()` — only treat bare *"order 6 units"* as an order when it clearly continues the current product. `detect_unsupported_make()` clears transaction slots for Ferrari/BMW/etc.

**Lesson:** **Guardrails + slot clearing on topic shift** matter as much as RAG grounding.

---

### Issue 4 — Over-filtering retrieval on follow-ups

**Symptom:** After a tyre search, *"which one is cheapest"* returned nothing.

**Cause:** `product_keyword=tyre` filtered out valid **Tube** products that were correct for the vehicle.

**Fix:** Skip strict keyword filtering on pricing follow-ups; rank by price over the vehicle + category set already retrieved.

**Lesson:** Follow-up queries need **different retrieval rules** than fresh searches.

---

### Issue 5 — UI showed data the graph forgot

**Symptom:** `find_parts_by_vehicle` ran successfully but React showed empty product cards.

**Cause:** Tool output lived in `tool_traces` but was never copied to `retrieved_docs` (what the API returns to the frontend).

**Fix:** Sync tool results into state after execution.

**Lesson:** Agent graphs have **multiple consumers** (LLM, UI, eval) — state must be explicit.

---

### What we learned (the honest summary)

| Layer | How often it broke | What fixed it |
|-------|-------------------|---------------|
| Routing / intent | Often | Tighter phrase rules + eval |
| Slot memory | Often | `focus_sku`, follow-up detectors, cleanup logic |
| Retrieval | Sometimes | Metadata filters, reranker tuning |
| LLM phrasing | Rarely (when Groq enabled) | Prompt + temperature 0.1; deterministic fallback |

This is worth saying in an interview: **we did not fine-tune our way out of broken memory.** We instrumented, reproduced in eval, and fixed the graph.

---

## Future Improvement — QLoRA Fine-Tuning for Smoother Dialogue

### What the LLM does today (and does not do)

```text
Rule-based graph  →  decides WHAT to do (search / stock / order / clarify / refuse)
Groq Llama 3.1    →  decides HOW to say it (wording only)
Catalogue + tools →  source of truth for prices, stock, SKUs
```

Without `GROQ_API_KEY`, the assistant uses a **deterministic formatter** — correct and grounded, but robotic. With Groq, replies read more naturally but can still feel template-like on multi-turn flows.

**QLoRA fine-tuning would improve the generation layer only** — not routing, not tool choice, not retrieval. That separation is deliberate and production-appropriate.

### Why QLoRA specifically

| Approach | Fit for this project |
|----------|---------------------|
| Full fine-tune | Expensive, overkill for ~600 SKUs |
| Prompt engineering only | Fast, already used — hits a ceiling on tone/consistency |
| **QLoRA** | Low VRAM (~1× 8B model on a single GPU), fast iteration, easy to swap adapters |

QLoRA (Quantized Low-Rank Adaptation) trains small adapter matrices on top of a frozen base model (e.g. Llama 3.1 8B). You get custom conversational style without retraining 8B parameters.

### What we would fine-tune for

**Target behaviours** (not facts — facts stay in tools/RAG):

- Natural clarification tone: *"Got it — which vehicle is this for?"* vs rigid templates
- Smooth multi-turn transitions: acknowledging prior context without repeating full product lists
- Consistent dealer-facing voice: concise, professional, no markdown dumps
- Graceful refusals and stock errors: *"BRK-1042 only has 43 units — want me to draft an order for 43 instead?"*

**What we would NOT fine-tune into the model:**

- Prices, stock counts, SKUs (stay in catalogue + tools)
- Tool selection (stay rule-based or move to LLM function-calling later with eval gates)
- Vehicle compatibility (stay in metadata filters)

### Proposed training pipeline

```text
1. Collect seed data
   ├── Export 20 eval multi-turn flows as JSONL
   ├── Synthetic expansion: catalogue rows → (user query, grounded assistant reply) pairs
   └── Human review or LLM-as-judge for grounding violations

2. Format as instruction tuning
   {
     "system": "<same grounding rules as prompts.py>",
     "context": "<retrieved docs + tool output + slots>",
     "user": "how many in stock?",
     "assistant": "BRK-1042 (Brake Disc Rotor) has 43 units at INR 2,470."
   }

3. Train QLoRA adapter (e.g. rank=16, alpha=32)
   ├── Base: meta-llama/Llama-3.1-8B-Instruct
   ├── Framework: Hugging Face PEFT + bitsandbytes (4-bit)
   └── Loss: standard causal LM on assistant tokens only

4. Evaluate BEFORE merging
   ├── Existing eval suite must stay 20/20 on routing/tools/grounding
   ├── Add generation rubric: fluency, brevity, context acknowledgment
   └── Reject adapter if grounding accuracy drops

5. Deploy adapter behind same graph
   └── Replace GroqGenerator call with local vLLM/Ollama + LoRA weights
```

### Why this would impress reviewers (if explained correctly)

Saying *"I'd fine-tune with QLoRA"* alone is generic. What stands out is explaining **where** it fits:

> "We fixed correctness with the graph and eval first. QLoRA is the next step for **UX polish** — how the assistant speaks — while keeping prices and stock in tools so we never train hallucinations into the model."

That shows you understand the industry pattern: **RAG + tools for facts, fine-tuning for form.**

### Risks to mention (shows maturity)

- Fine-tuning on too little data → overfits eval phrasing, fails on new dealers
- Training on LLM-generated labels without grounding checks → silent hallucination drift
- Coupling generation to routing before eval is green → debugging becomes impossible

**Recommendation for this codebase:** ship with current architecture for the assignment; add QLoRA only after freezing the 20-case eval suite as a regression gate.

---

## Future Improvements (summary)

| Priority | Item | Impact |
|----------|------|--------|
| High | Session store (Redis) | Survive restarts, horizontal scale |
| High | Hybrid BM25 + vector retrieval | Better SKU keyword recall |
| Medium | QLoRA generation adapter | Smoother multi-turn dialogue |
| Medium | LLM function-calling (with eval gate) | More flexible tool routing |
| Low | Cross-encoder reranker | Retrieval precision on broad queries |
