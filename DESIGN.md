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
