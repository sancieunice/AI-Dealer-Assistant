# Screenshots

Add UI captures here and reference them from the root `README.md`.

Suggested files:

| File | What to capture |
|------|-----------------|
| `home.png` | Empty chat with quick suggestions |
| `retrieval.png` | Product search with product cards |
| `order.png` | Order draft ready for confirmation |
| `clarification.png` | "I need tyres" → vehicle clarification |
| `guardrail.png` | Off-topic refusal (e.g. weather) |
| `forecasting.png` | Forecast plot from `python -m forecasting.plots` |

Generate a forecast plot (run from the **project root**, not inside `forecasting/`):

```bash
cd D:\AI-Dealer-Assistant
python -m forecasting.evaluate
python -m forecasting.plots --sku BRK-1041
```

Output: `forecasting/forecast_BRK-1041.png`

Note: only SKUs in `sales_history.csv` appear in the test window. BRK-1042 is in the catalogue but not in the sales dataset — pick a SKU from `prophet_results.csv`.
