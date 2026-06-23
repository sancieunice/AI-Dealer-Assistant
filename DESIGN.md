# Design Document

How the VIKMO Dealer Assistant is built and why I made the choices I did.

## Overview

```text
React / Streamlit
       ↓
Flask (server.py)
       ↓
LangGraph: guardrails → entities → clarification → retrieval → tools → generation
       ↓
ChromaDB + catalogue.csv
```

The assistant runs as a single-pass graph — not a ReAct loop. Each user message goes through the nodes once and returns a response.

## LangGraph flow

1. **Guardrails** — reject clearly off-topic input (weather, jokes).
2. **Entity extraction** — pull vehicle, category, SKU, quantity, dealer, and intent from the message and memory.
3. **Clarification** — if vehicle or category is missing, ask before searching.
4. **Retrieval** — fetch relevant products from ChromaDB.
5. **Tools** — call `check_stock`, `find_parts_by_vehicle`, or `create_order` when needed.
6. **Generation** — Groq formats the answer, or a deterministic fallback if no API key is set.

I used rule-based intent routing instead of LLM function calling. It is easier to debug and I can run the eval suite without depending on an API.

## Retrieval

I used ChromaDB because the catalogue has around 600 SKUs. Passing all of them to the model would not scale.

Each product row becomes one document:

```text
SKU: BRK-1042 | Name: Brake Disc Rotor — Bajaj Dominar 400 | Category: Brakes | ...
```

Metadata filters narrow results by vehicle, category, brand, and SKU. Vector search fills in when filters alone are not enough. A simple reranker boosts lexical overlap and in-stock items.

Embeddings: `all-MiniLM-L6-v2`. Index is stored in `chroma/` and rebuilt when the catalogue row count changes.

## Tools

| Tool | When it runs |
|------|--------------|
| `check_stock` | User asks about stock for a known SKU |
| `find_parts_by_vehicle` | User asks for parts for a vehicle (+ optional category) |
| `create_order` | User wants to place an order |

Orders go through Pydantic validation. The tool checks stock against the catalogue and returns errors like "BRK-1042 has only 43 units in stock" instead of inventing numbers.

## Memory

The assistant keeps conversation history and slots: vehicle, category, brand, SKU, quantity, dealer, and `focus_sku` (the product being discussed).

This allows follow-ups like "which one is cheapest?" or "order 5 units" without repeating the full context.

When the user starts a fresh search ("show brake pads for Pulsar"), stale order/stock slots are cleared so old SKUs do not leak into new queries.

## Guardrails

- Off-topic questions get a short refusal.
- Unsupported makes (Ferrari, BMW, etc.) are refused — the catalogue only covers listed vehicles.
- Retrieved docs are filtered so a brake query does not return unrelated categories.
- If nothing matches, the assistant says so instead of recommending random products.
- Prices and stock always come from the catalogue or tool output, not from the model's memory.

## Evaluation

I wrote 20 test cases in `eval/test_cases.json`: happy paths, ambiguous queries, guardrails, multi-turn flows, and a Ferrari hallucination trap.

Run with:

```bash
python -m eval.run_eval
```

**Latest:** 20/20 passed. Route, tool, grounding, and clarification accuracy are all 1.0. Retrieval hit rate@3 is 0.78 — some broad queries legitimately match several SKUs.

Multi-turn cases replay prior turns so slot memory is actually tested, not just single messages.

## Failure analysis

These are real issues I hit while building:

**"What's the cheapest chain lube you stock?" asked for a vehicle.**

The word "stock" in "you stock?" triggered the stock-check intent. I split catalogue-browsing phrases ("do you stock") from stock-lookup phrases ("check stock", "how many in stock").

**Context loss after clarification.**

```
User: Need tyres
Assistant: Which vehicle?
User: Royal Enfield Himalayan
```

Early versions sometimes lost the tyre category when the user only gave the vehicle on the next turn. Slot memory now merges category from the previous turn.

**"How many in stock?" after a failed order forgot the SKU.**

The user was discussing BRK-1042, tried to order 46 units (only 43 available), then asked about stock. The assistant asked "which SKU?" because `focus_sku` was wiped after the order turn and bare stock questions were not treated as follow-ups. Fixed with `is_stock_followup()` and remembering the SKU after every order attempt.

**"Which one is cheapest" after a tyre search returned nothing.**

A strict keyword filter removed valid Tube products. Pricing follow-ups now skip that filter and sort by price over the already-retrieved set.

**Wrong order on typo ("order fereari").**

Stale `focus_sku` from a previous search combined with any "order" keyword. Added unsupported-make detection and stricter rules for when a bare "order N units" counts as a follow-up.

**Tool ran but UI showed no products.**

`find_parts_by_vehicle` output was in tool traces but not copied to `retrieved_docs`, which is what the React UI reads. Synced tool output into state after execution.

Most bugs were routing and memory — not retrieval quality. The eval suite with multi-turn replay is what caught them.

## Forecasting (Part B)

Prophet is **not** inside the chatbot. It runs offline on `sales_history.csv`.

I compared:
- **Baseline:** 4-week moving average with `shift(1)` so the current week is never included in its own forecast.
- **Prophet:** one model per SKU, trained only on the train window, with `promo_flag` as a regressor.

Train/test split is chronological — last 4 weeks held out. No random split (that would leak future data).

| Model | MAE |
|-------|-----|
| 4-week moving average | 7.86 |
| Prophet per-SKU | 5.81 |

Prophet does better on promo weeks where the moving average lags. The baseline is still useful for SKUs with very little history.

## What I would improve next

- **Session storage** — currently in-memory; would use Redis for production.
- **QLoRA fine-tuning** — only for reply wording, not for facts. Routing and tools would stay as they are. I would train a small LoRA adapter on grounded conversation examples and reject it if the 20/20 eval suite regresses.
- **Hybrid retrieval** — BM25 + vectors for better SKU keyword matching.

## Known limits

- Entity extraction is rule-based. Unusual part names outside my alias list may miss category detection.
- Sessions do not survive a server restart.
- With Groq enabled, phrasing can vary slightly even at low temperature. Eval runs primarily against the deterministic path.
