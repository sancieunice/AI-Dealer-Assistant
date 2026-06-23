# VIKMO Dealer Assistant

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![LangGraph](https://img.shields.io/badge/LangGraph-Agent-green.svg)](https://github.com/langchain-ai/langgraph)
[![Eval](https://img.shields.io/badge/Eval-20%2F20-brightgreen.svg)](eval/results.md)

Production-style conversational AI for automotive dealers — RAG over a live parts catalogue, structured tool calling, multi-turn memory, guardrails, and a full evaluation suite. Includes demand forecasting (Prophet vs baseline) as Part B.

**Repo:** [github.com/sancieunice/AI-Dealer-Assistant](https://github.com/sancieunice/AI-Dealer-Assistant) · **Author:** [sancieunice](https://github.com/sancieunice) · **Docs:** [DESIGN.md](DESIGN.md) · **Eval:** [eval/results.md](eval/results.md)

---

## What it does

Dealers talk in plain language. The assistant:

- **Finds parts** from a ~600-SKU catalogue (RAG + metadata filters)
- **Checks stock and prices** via structured tools — never guessed
- **Creates orders** with Pydantic validation and confirmation flow
- **Remembers context** across turns ("which one is cheapest?" → "order 5 units")
- **Refuses off-topic requests** (weather, jokes, unsupported makes like Ferrari)
- **Forecasts demand** per SKU using historical sales (Part B bonus — separate from chat)

---

## Architecture at a glance

```text
React UI (localhost:3000)
        ↓
Flask API (server.py)
        ↓
LangGraph pipeline
  guardrails → entities → clarification → retrieval → tools → generation
        ↓
ChromaDB + sentence-transformers          catalogue.csv (ground truth)
        ↓
Tools: check_stock | find_parts_by_vehicle | create_order
```

The chat assistant and the forecasting module share the same repo but **do not share a runtime path**. Prophet reads `sales_history.csv`; the dealer bot reads `catalogue.csv`. That separation is intentional — you would not retrain a forecast model on every chat message.

---

## Screenshots

Add PNGs to `screenshots/` and they render here automatically:

<p align="center">
  <img src="screenshots/home.png" alt="Chat home" width="45%" />
  <img src="screenshots/retrieval.png" alt="Product search" width="45%" />
</p>

<p align="center">
  <img src="screenshots/order.png" alt="Order flow" width="45%" />
  <img src="screenshots/guardrail.png" alt="Guardrails" width="45%" />
</p>

See [screenshots/README.md](screenshots/README.md) for capture instructions.

---

## Tech stack

| Layer | Choice |
|-------|--------|
| Frontend | React (Vite) |
| API | Flask |
| Agent | LangGraph `StateGraph` |
| Vector store | ChromaDB (persistent, cosine HNSW) |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` |
| LLM | Groq `llama-3.1-8b-instant` (optional — works without API key) |
| Validation | Pydantic v2 |
| Forecasting | pandas + Prophet |
| Alt UI | Streamlit (`ui/app.py`) |

---

## Setup

### Backend + dependencies

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

Create `.env` (see `.env.example`):

```bash
GROQ_API_KEY=your_key_here      # optional — deterministic fallback without it
GROQ_MODEL=llama-3.1-8b-instant
```

### Run

```bash
# Terminal 1 — API
python server.py

# Terminal 2 — React UI
cd frontend
npm install
npm run dev
```

Open **http://localhost:3000**

**Windows shortcut:** double-click `start.bat` (starts backend + frontend in separate terminals).

Streamlit alternative: `streamlit run ui/app.py`

**First run:** the backend downloads the embedding model (~90 MB) and builds the Chroma index from `catalogue.csv`. This takes 1–2 minutes and creates local `models/` and `chroma/` folders (not committed — see `.gitignore`).

### Evaluation & forecasting

```bash
python -m eval.run_eval              # → eval/results.md
python -m forecasting.evaluate       # → forecasting/results.md
```

---

## Example queries

Try these in the chat UI:

```text
I need tyres
→ Which vehicle model do you need tyres for?

Do you have brake pads for Bajaj Pulsar 150?
→ Lists matching brake parts with SKU, price, stock

Check stock for BRK-1042
→ 43 units, INR 2,470 (from catalogue)

What's the cheapest chain lube you stock?
→ Grounded cheapest SKU from retrieval

Order 10 units for ABC Motors        (after discussing a part)
→ Order draft with line total

What's the weather today?
→ Polite refusal — out of domain
```

**Multi-turn:**

```text
Show tyres for Royal Enfield Himalayan
→ Product list

which one is the cheapest
→ Cheapest tube/tyre with price

how many in stock?
→ Stock for the part you were just discussing
```

---

## Evaluation results (summary)

We treat the assistant like a small product, not a demo script. There is a **20-case regression suite** covering happy paths, ambiguity, guardrails, hallucination traps, and multi-turn flows.

| Metric | Score | What it means |
|--------|-------|---------------|
| **Cases passed** | **20/20** | Every scenario behaves as specified |
| **Route accuracy** | **1.00** | Correct path: clarify, retrieve, refuse, or tool |
| **Tool accuracy** | **1.00** | Right tool invoked when data must come from catalogue |
| **Grounding accuracy** | **1.00** | Answers cite real SKUs, prices, or stock |
| **Clarification accuracy** | **1.00** | Ambiguous queries ask the right follow-up |
| **Retrieval hit rate@3** | **0.78** | Relevant product in top 3 for ~78% of retrieval queries |
| **MRR** | **0.78** | Relevant doc tends to appear early in the ranked list |

Retrieval is intentionally harder to perfect than routing — a query like "chain lube" can legitimately match several SKUs. We measure it anyway so we know when embedding or reranking drifts.

**Full report:** [eval/results.md](eval/results.md) · **Methodology:** [DESIGN.md#evaluation-methodology](DESIGN.md#evaluation-methodology)

---

## Forecasting (Part B — separate from chat)

Prophet is **not** inside the LangGraph loop. It runs offline on `sales_history.csv` to predict next-week demand per SKU.

| Model | MAE | MAPE |
|-------|-----|------|
| 4-week moving average (baseline) | 7.86 | 32.1% |
| Prophet per-SKU + `promo_flag` | **5.81** | **26.6%** |

Why Prophet? Promo weeks spike sales in ways a simple average lags behind. Prophet handles seasonality and known promotion flags without leaking future data into training.

**Details:** [forecasting/results.md](forecasting/results.md) · **Design rationale:** [DESIGN.md#forecasting-part-b](DESIGN.md#forecasting-part-b)

---

## Repository structure

Only source, data, and docs are committed — no secrets, caches, or local runtime files.

```text
AI-Dealer-Assistant/
├── assistant/              # LangGraph agent, RAG, tools, memory, guardrails
│   ├── tools/
│   └── schemas/
├── frontend/               # React chat UI
├── eval/                   # Test cases, metrics, results
├── forecasting/            # Baseline + Prophet (Part B)
├── screenshots/            # UI captures (add before sharing)
├── ui/                     # Streamlit alternative
├── catalogue.csv           # ~600 SKUs — retrieval corpus
├── sales_history.csv       # 30 SKUs × 78 weeks — forecasting data
├── server.py               # Flask API
├── requirements.txt
├── .env.example            # Copy to .env (optional Groq key)
├── start.bat / start.sh    # Quick start scripts
├── README.md               # Overview (GitHub landing page)
└── DESIGN.md               # Architecture & engineering decisions
```

**Not in the repo** (recreated locally): `.env`, `chroma/`, `models/`, `orders.json`, `frontend/node_modules/`, `.venv/`

---

## Further reading

- **[DESIGN.md](DESIGN.md)** — architecture, retrieval, tools, memory, guardrails, evaluation methodology, Prophet rationale
- **[eval/results.md](eval/results.md)** — latest metrics and failure analysis
- **[forecasting/results.md](forecasting/results.md)** — baseline vs Prophet comparison

---

## License

MIT — feel free to use for learning and portfolio review.
