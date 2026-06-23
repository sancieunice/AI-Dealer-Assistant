from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def plot_forecast(results_path: str = "forecasting/forecast_results.csv", sku: str | None = None) -> Path:
    df = pd.read_csv(results_path, parse_dates=["date"])
    if sku:
        df = df[df["sku"] == sku]
    elif not df.empty:
        sku = str(df.iloc[0]["sku"])
        df = df[df["sku"] == sku]

    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(df["date"], df["units_sold"], label="Actual")
    ax.plot(df["date"], df["forecast"], label="Forecast")
    ax.set_title(f"Demand forecast - {sku}")
    ax.set_xlabel("Week")
    ax.set_ylabel("Units")
    ax.legend()
    output = Path("forecasting") / f"forecast_{sku}.png"
    fig.tight_layout()
    fig.savefig(output, dpi=160)
    plt.close(fig)
    return output
