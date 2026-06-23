from __future__ import annotations

import pandas as pd


def moving_average_forecast(df: pd.DataFrame, window: int = 4) -> pd.DataFrame:
    frames = []
    for sku, group in df.sort_values("date").groupby("sku"):
        group = group.copy()
        group["forecast"] = group["units_sold"].shift(1).rolling(window=window, min_periods=1).mean()
        group["forecast"] = group["forecast"].fillna(group["units_sold"].expanding().mean())
        frames.append(group)
    return pd.concat(frames, ignore_index=True)
