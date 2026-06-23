from __future__ import annotations

from pathlib import Path

import pandas as pd

from assistant.entities import data_path
from forecasting.baseline import moving_average_forecast
from forecasting.prophet_model import prophet_forecast_per_sku


def chronological_split(df: pd.DataFrame, test_weeks: int = 4) -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = sorted(df["date"].unique())
    cutoff = dates[-test_weeks]
    train = df[df["date"] < cutoff].copy()
    test = df[df["date"] >= cutoff].copy()
    return train, test


def mae(actual: pd.Series, predicted: pd.Series) -> float:
    return float((actual - predicted).abs().mean())


def mape(actual: pd.Series, predicted: pd.Series) -> float:
    mask = actual != 0
    if not mask.any():
        return 0.0
    return float((actual[mask] - predicted[mask]).abs().div(actual[mask]).mean() * 100)


def evaluate_model(scored: pd.DataFrame) -> dict[str, float]:
    return {
        "mae": mae(scored["units_sold"], scored["forecast"]),
        "mape": mape(scored["units_sold"], scored["forecast"]),
    }


def main() -> None:
    df = pd.read_csv(data_path("sales_history.csv"), parse_dates=["date"])
    train, test = chronological_split(df)
    timeline = pd.concat([train, test], ignore_index=True)

    baseline_scored = moving_average_forecast(timeline)
    baseline_scored = baseline_scored.merge(test[["date", "sku"]], on=["date", "sku"], how="inner")
    baseline_metrics = evaluate_model(baseline_scored)

    prophet_scored = prophet_forecast_per_sku(train, test)
    prophet_metrics = evaluate_model(prophet_scored) if not prophet_scored.empty else None

    output = Path("forecasting/forecast_results.csv")
    baseline_scored.rename(columns={"forecast": "baseline_forecast"}).to_csv(output, index=False)

    prophet_path = Path("forecasting/prophet_results.csv")
    if prophet_scored is not None and not prophet_scored.empty:
        prophet_scored.to_csv(prophet_path, index=False)

    print("Validation scheme: chronological holdout of the latest 4 weeks")
    print(f"Train rows: {len(train)} | Test rows: {len(test)}")
    print(f"Baseline 4-week MA MAE: {baseline_metrics['mae']:.3f}")
    print(f"Baseline 4-week MA MAPE: {baseline_metrics['mape']:.2f}%")
    if prophet_metrics:
        print(f"Prophet per-SKU MAE: {prophet_metrics['mae']:.3f}")
        print(f"Prophet per-SKU MAPE: {prophet_metrics['mape']:.2f}%")
        winner = "Prophet" if prophet_metrics["mae"] < baseline_metrics["mae"] else "Baseline"
        print(f"Winner on MAE: {winner}")
    else:
        print("Prophet model skipped or unavailable.")

    _write_results_markdown(train, test, baseline_metrics, prophet_metrics)
    print(f"Wrote {output}")


def _write_results_markdown(
    train: pd.DataFrame,
    test: pd.DataFrame,
    baseline_metrics: dict[str, float],
    prophet_metrics: dict[str, float] | None,
) -> None:
    lines = [
        "# Forecasting Results",
        "",
        "## Validation",
        "",
        "- Train window: all weekly sales before the final 4 weeks.",
        "- Test window: the most recent 4 weeks per SKU.",
        "- Leakage prevention: the baseline uses `shift(1)` before rolling averages; Prophet is fit only on the train window.",
        "",
        "## Metrics",
        "",
        f"- Baseline (4-week moving average) MAE: **{baseline_metrics['mae']:.3f}**",
        f"- Baseline MAPE: **{baseline_metrics['mape']:.2f}%**",
    ]
    if prophet_metrics:
        lines.extend(
            [
                f"- Prophet per-SKU MAE: **{prophet_metrics['mae']:.3f}**",
                f"- Prophet MAPE: **{prophet_metrics['mape']:.2f}%**",
                "",
                "## Model choice",
                "",
            ]
        )
        if prophet_metrics["mae"] < baseline_metrics["mae"]:
            lines.append(
                "Prophet beats the moving-average baseline on MAE while using the promo flag as a regressor. "
                "The added complexity is justified for promo-sensitive SKUs."
            )
        else:
            lines.append(
                "The simple 4-week moving average remains competitive or better on MAE. "
                "For this catalogue size and horizon, the baseline is the safer production default."
            )
    lines.extend(
        [
            "",
            "## How to rerun",
            "",
            "```bash",
            "python -m forecasting.evaluate",
            "```",
        ]
    )
    Path("forecasting/results.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
