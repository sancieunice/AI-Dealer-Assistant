from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
FORECASTING_DIR = Path(__file__).resolve().parent


def _resolve_path(*candidates: Path) -> Path:
    for path in candidates:
        if path.exists():
            return path
    return candidates[0]


def plot_forecast(sku: str | None = None, output_path: Path | None = None) -> Path:
    prophet_path = _resolve_path(
        FORECASTING_DIR / "prophet_results.csv",
        ROOT / "forecasting" / "prophet_results.csv",
    )
    baseline_path = _resolve_path(
        FORECASTING_DIR / "forecast_results.csv",
        ROOT / "forecasting" / "forecast_results.csv",
    )

    if not prophet_path.exists():
        raise FileNotFoundError(
            f"No prophet results at {prophet_path}. "
            "Run from the project root: python -m forecasting.evaluate"
        )

    prophet_df = pd.read_csv(prophet_path, parse_dates=["date"])
    if sku is None:
        sku = str(prophet_df["sku"].iloc[0])

    df = prophet_df[prophet_df["sku"] == sku].copy()
    if df.empty:
        available = ", ".join(sorted(prophet_df["sku"].unique())[:8])
        raise ValueError(f"SKU {sku} not in test results. Try one of: {available}")

    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(df["date"], df["units_sold"], label="Actual", marker="o", markersize=4)
    ax.plot(df["date"], df["forecast"], label="Prophet forecast", marker="o", markersize=4)

    if baseline_path.exists():
        baseline_df = pd.read_csv(baseline_path, parse_dates=["date"])
        baseline_slice = baseline_df[baseline_df["sku"] == sku]
        if not baseline_slice.empty and "baseline_forecast" in baseline_slice.columns:
            ax.plot(
                baseline_slice["date"],
                baseline_slice["baseline_forecast"],
                label="4-week MA baseline",
                linestyle="--",
                marker="x",
                markersize=4,
            )

    ax.set_title(f"Demand forecast — {sku} (test window)")
    ax.set_xlabel("Week")
    ax.set_ylabel("Units sold")
    ax.legend()
    ax.grid(True, alpha=0.3)

    output = output_path or (FORECASTING_DIR / f"forecast_{sku}.png")
    fig.tight_layout()
    fig.savefig(output, dpi=160)
    plt.close(fig)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot demand forecast for a SKU.")
    parser.add_argument(
        "--sku",
        default=None,
        help="SKU to plot (default: first SKU in prophet_results.csv)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional output PNG path",
    )
    args = parser.parse_args()
    output = plot_forecast(
        sku=args.sku,
        output_path=Path(args.output) if args.output else None,
    )
    print(f"Saved plot to {output}")


if __name__ == "__main__":
    main()
