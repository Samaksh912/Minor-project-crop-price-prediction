from __future__ import annotations

import logging
import os

import numpy as np
import pandas as pd

from config import (
    DAILY_FILE,
    DATA_DIR,
    DATE_COL,
    EXOG_POLICY_COLS,
    EXOG_WEATHER_COLS,
    IQR_MULTIPLIER,
    PRICE_COL,
    WEEKLY_LAG_PERIODS,
    WEEKLY_ROLL_WINDOWS,
)


LOGGER = logging.getLogger(__name__)
_DIRECTION_ORDER = ["price_floor", "neutral", "upward", "downward"]
_EXPLICIT_EXCLUSIONS = {
    "markets_reporting",
    "varieties_reporting",
    "rows_reporting",
    "min_price",
    "max_price",
}


def load_data() -> pd.DataFrame:
    data_path = os.path.join(DATA_DIR, DAILY_FILE)
    LOGGER.info("Loading modeling dataset from %s", data_path)

    df = pd.read_csv(data_path, parse_dates=[DATE_COL])
    df = df.sort_values(DATE_COL).reset_index(drop=True)
    df = df.dropna(subset=[PRICE_COL]).copy()

    q1 = df[PRICE_COL].quantile(0.25)
    q3 = df[PRICE_COL].quantile(0.75)
    iqr = q3 - q1
    lower = q1 - (IQR_MULTIPLIER * iqr)
    upper = q3 + (IQR_MULTIPLIER * iqr)
    df = df[df[PRICE_COL].between(lower, upper)].copy()

    direction_series = (
        df.get("price_impact_direction", pd.Series(index=df.index, dtype="object"))
        .fillna("neutral")
        .astype(str)
        .str.strip()
        .str.lower()
    )
    direction_series = direction_series.where(
        direction_series.isin(_DIRECTION_ORDER), "neutral"
    )
    direction_series = pd.Categorical(
        direction_series,
        categories=_DIRECTION_ORDER,
        ordered=True,
    )
    direction_dummies = pd.get_dummies(
        direction_series,
        prefix="dir",
        drop_first=True,
        dtype=float,
    )
    df = pd.concat(
        [df.drop(columns=["price_impact_direction"], errors="ignore"), direction_dummies],
        axis=1,
    )

    df = df.set_index(DATE_COL)
    weekly_df = df.resample("W").mean(numeric_only=True)

    weekly_df[PRICE_COL] = weekly_df[PRICE_COL].ffill().bfill()

    weather_fill_cols = [col for col in EXOG_WEATHER_COLS if col in weekly_df.columns]
    policy_fill_cols = [
        col
        for col in (EXOG_POLICY_COLS + [col for col in weekly_df.columns if col.startswith("dir_")])
        if col in weekly_df.columns
    ]

    if weather_fill_cols:
        weekly_df[weather_fill_cols] = weekly_df[weather_fill_cols].ffill().bfill()
        for col in weather_fill_cols:
            weekly_df[col] = weekly_df[col].fillna(weekly_df[col].mean())

    if policy_fill_cols:
        # Do not backfill policy into dates that predate the first real policy row.
        weekly_df[policy_fill_cols] = weekly_df[policy_fill_cols].ffill()

    rolling_tavg = weekly_df["tavg"].rolling(window=4, min_periods=1).mean()
    rolling_prcp = weekly_df["prcp"].rolling(window=4, min_periods=1).mean()
    weekly_df["temp_anomaly"] = weekly_df["tavg"] - rolling_tavg
    weekly_df["rain_anomaly"] = weekly_df["prcp"] - rolling_prcp

    for lag in WEEKLY_LAG_PERIODS:
        weekly_df[f"price_lag_{lag}"] = weekly_df[PRICE_COL].shift(lag)
    for window in WEEKLY_ROLL_WINDOWS:
        weekly_df[f"price_rmean_{window}"] = (
            weekly_df[PRICE_COL].rolling(window=window, min_periods=window).mean()
        )
        weekly_df[f"price_rstd_{window}"] = (
            weekly_df[PRICE_COL].rolling(window=window, min_periods=window).std()
        )
    weekly_df["price_pct_change"] = weekly_df[PRICE_COL].pct_change()

    weekly_df = weekly_df.iloc[13:].copy()

    numeric_cols = weekly_df.select_dtypes(include=[np.number]).columns.tolist()
    fill_zero_cols = [col for col in numeric_cols if col != PRICE_COL]
    if fill_zero_cols:
        weekly_df[fill_zero_cols] = weekly_df[fill_zero_cols].fillna(0)

    weekly_df = weekly_df.reset_index()
    LOGGER.info("Prepared weekly dataset with %d rows and %d columns", *weekly_df.shape)
    return weekly_df


def get_exog_cols(df: pd.DataFrame) -> list[str]:
    allowed = []
    direction_cols = sorted(
        col
        for col in df.columns
        if col.startswith("dir_") and col != "price_impact_direction"
    )
    candidates = (
        EXOG_WEATHER_COLS
        + EXOG_POLICY_COLS
        + direction_cols
        + ["temp_anomaly", "rain_anomaly"]
    )
    for col in candidates:
        if col not in df.columns:
            continue
        if col in _EXPLICIT_EXCLUSIONS:
            continue
        if col.startswith("price_"):
            continue
        allowed.append(col)
    return allowed
