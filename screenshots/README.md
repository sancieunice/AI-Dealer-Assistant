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

Generate a forecast plot:

```bash
python -m forecasting.evaluate
python -c "from forecasting.plots import plot_forecast; plot_forecast(sku='BRK-1042')"
```
