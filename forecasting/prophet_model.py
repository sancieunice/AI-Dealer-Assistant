from __future__ import annotations

import pandas as pd


def prophet_forecast(train: pd.DataFrame, periods: int) -> pd.DataFrame:
    try:
        from prophet import Prophet
    except ImportError as exc:
        raise RuntimeError("Install prophet to use the Prophet forecasting model.") from exc

    model = Prophet(yearly_seasonality=True, weekly_seasonality=False, daily_seasonality=False)
    model.add_regressor("promo_flag")
    prophet_train = train.rename(columns={"date": "ds", "units_sold": "y"})
    model.fit(prophet_train[["ds", "y", "promo_flag"]])
    future = model.make_future_dataframe(periods=periods, freq="W-MON")
    future = future.merge(prophet_train[["ds", "promo_flag"]], on="ds", how="left")
    future["promo_flag"] = future["promo_flag"].fillna(0)
    forecast = model.predict(future)
    return forecast[["ds", "yhat", "yhat_lower", "yhat_upper"]]


def prophet_forecast_per_sku(train: pd.DataFrame, test: pd.DataFrame) -> pd.DataFrame:
    """Fit one Prophet model per SKU on train data and score the held-out test window."""
    try:
        from prophet import Prophet
    except ImportError:
        return pd.DataFrame()

    scored_frames: list[pd.DataFrame] = []
    for sku, sku_train in train.groupby("sku"):
        sku_test = test[test["sku"] == sku].copy()
        if sku_test.empty or len(sku_train) < 8:
            continue

        model = Prophet(yearly_seasonality=True, weekly_seasonality=False, daily_seasonality=False)
        model.add_regressor("promo_flag")
        prophet_train = sku_train.rename(columns={"date": "ds", "units_sold": "y"})
        model.fit(prophet_train[["ds", "y", "promo_flag"]])

        future = sku_test.rename(columns={"date": "ds"})[["ds", "promo_flag"]]
        forecast = model.predict(future)
        sku_test = sku_test.copy()
        sku_test["forecast"] = forecast["yhat"].values
        scored_frames.append(sku_test)

    if not scored_frames:
        return pd.DataFrame()
    return pd.concat(scored_frames, ignore_index=True)
