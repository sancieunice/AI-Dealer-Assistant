# Forecasting Results

Offline demand forecasting for **Part B** of the assignment. This module does **not** run inside the dealer chatbot — it answers a different question: *how many units will we sell next week?*

---

## Validation setup

| | |
|---|---|
| **Data** | `sales_history.csv` — 30 SKUs, 78 weekly rows each |
| **Train** | All weeks before the final 4 |
| **Test** | Most recent 4 weeks (chronological holdout — no random split) |
| **Leakage control** | Baseline uses `shift(1)` before rolling mean; Prophet fits on train only |

We never shuffle time series. Random train/test splits would leak future demand into past features and inflate scores artificially.

---

## Results

| Model | MAE | MAPE |
|-------|-----|------|
| 4-week moving average (baseline) | **7.858** | **32.09%** |
| Prophet per-SKU + `promo_flag` | **5.805** | **26.59%** |

Prophet reduces mean absolute error by about **26%** vs the baseline on the holdout window.

---

## Why we used Prophet

A simple moving average is the right **baseline** — every ops team understands it, it is fast, and it needs no tuning. But it lags when:

- Marketing runs a **promo week** (`promo_flag = 1`)
- Demand has **weekly seasonality** (service centres busier certain months)
- SKUs have **different demand shapes** (fast-moving brake pads vs slow mirror stock)

Prophet handles dated rows, trend, seasonality, and known event flags (promotions). We fit **one model per SKU** because a chain lube and a brake disc do not share the same demand curve.

We did **not** use the chat LLM for forecasting — language models are poor at numeric time-series extrapolation from tabular history. Prophet (or similar classical/structural models) is the standard tool for this job.

---

## Where Prophet fits in the real world

In industry, forecasting usually looks like this:

```text
Historical sales DB  →  nightly batch job (Prophet / ARIMA / custom)  →  forecast table  →  ERP / dashboard
```

Examples:

- **Auto parts distributors** — reorder points, warehouse pick capacity, promo stocking
- **Retail** — SKU-level purchase orders, safety stock
- **Ops planning** — staffing and capacity from predicted transaction volume

The customer-facing chat assistant reads **current** catalogue stock. Prophet reads **historical** sales to plan **future** stock. Same business, different pipeline — which is how this repo is structured.

---

## Model choice summary

| | Baseline | Prophet |
|---|----------|---------|
| Interpretability | Excellent | Good (trend + seasonality components) |
| Promo handling | Lags spikes | Uses `promo_flag` regressor |
| Compute | Trivial | Higher (30 separate fits) |
| When to use | Short history, quick sanity check | Promo-sensitive SKUs, seasonality |

For SKUs with very little history, the moving average remains a sensible production fallback.

---

## How to rerun

```bash
python -m forecasting.evaluate
```

Optional plot for README / `screenshots/forecasting.png`:

```bash
python -c "from forecasting.plots import plot_forecast; print(plot_forecast(sku='BRK-1042'))"
```

Outputs: `forecasting/forecast_results.csv`, `forecasting/prophet_results.csv`, and this file.
