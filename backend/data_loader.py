"""
data_loader.py
--------------
Loads, cleans, and feature-engineers crop price + weather + policy data
into a weekly-frequency DataFrame ready for modelling.
"""

import os
import logging
from typing import Optional

import numpy as np
import pandas as pd

from config import (
    DATA_DIR, WEATHER_FILE, POLICY_FILE,
    # Crop columns
    CROP_DATE_COL, CROP_PRICE_COL, DATE_COL, PRICE_COL,
    # Weather columns
    WEATHER_DATE_COL, WEATHER_COLS,
    # Policy columns
    POLICY_DATE_COL, POLICY_CROP_COL,
    POLICY_NUMERIC_COLS, POLICY_BINARY_COLS,
    CROP_NAME_MAP,
    # Feature engineering
    WEEKLY_LAG_PERIODS, WEEKLY_ROLL_WINDOWS,
    # Quality thresholds
    NAN_DROP_THRESHOLD, IQR_MULTIPLIER,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Individual loaders
# ============================================================================

def load_crop(name: str, path: Optional[str] = None) -> pd.DataFrame:
    """Load a single crop CSV, remap columns, clean basics."""
    path = path or os.path.join(DATA_DIR, f"{name}.csv")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Crop CSV not found: {path}")

    df = pd.read_csv(path)

    # Remap columns to standard names
    if CROP_DATE_COL in df.columns:
        df = df.rename(columns={CROP_DATE_COL: DATE_COL})
    if CROP_PRICE_COL in df.columns:
        df = df.rename(columns={CROP_PRICE_COL: PRICE_COL})

    # Also handle legacy column names from README
    if "Price Date" in df.columns and DATE_COL not in df.columns:
        df = df.rename(columns={"Price Date": DATE_COL})
    if "Modal Price (Rs./Quintal)" in df.columns and PRICE_COL not in df.columns:
        df = df.rename(columns={"Modal Price (Rs./Quintal)": PRICE_COL})

    if DATE_COL not in df.columns:
        raise ValueError(f"No date column found in {path}. Expected '{CROP_DATE_COL}' or 'Price Date'.")
    if PRICE_COL not in df.columns:
        raise ValueError(f"No price column found in {path}. Expected '{CROP_PRICE_COL}' or 'Modal Price (Rs./Quintal)'.")

    df[DATE_COL] = pd.to_datetime(df[DATE_COL], dayfirst=True, errors="coerce")
    df = df.dropna(subset=[DATE_COL, PRICE_COL])
    df[PRICE_COL] = pd.to_numeric(df[PRICE_COL], errors="coerce")
    df = df.dropna(subset=[PRICE_COL])

    # Keep only date + price (aggregate duplicates later)
    df = df[[DATE_COL, PRICE_COL]].copy()
    df = df.sort_values(DATE_COL).reset_index(drop=True)
    return df


def load_weather(path: Optional[str] = None) -> pd.DataFrame:
    """Load and parse the weather CSV."""
    path = path or os.path.join(DATA_DIR, WEATHER_FILE)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Weather file not found: {path}")

    df = pd.read_csv(path)

    # Standardise date column
    if WEATHER_DATE_COL in df.columns:
        df = df.rename(columns={WEATHER_DATE_COL: DATE_COL})
    elif DATE_COL not in df.columns:
        raise ValueError(f"No date column in weather file. Expected '{WEATHER_DATE_COL}'.")

    df[DATE_COL] = pd.to_datetime(df[DATE_COL], dayfirst=True, errors="coerce")
    df = df.dropna(subset=[DATE_COL]).sort_values(DATE_COL).reset_index(drop=True)

    keep = [DATE_COL] + [c for c in WEATHER_COLS if c in df.columns]
    df = df[keep].copy()

    # Convert weather cols to numeric
    for c in keep[1:]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    return df


def load_policy(crop_name: str, path: Optional[str] = None) -> Optional[pd.DataFrame]:
    """
    Load policy data for a specific crop.
    Returns None if file missing, crop not found, or MSP values are zero/missing.
    """
    path = path or os.path.join(DATA_DIR, POLICY_FILE)
    if not os.path.exists(path):
        logger.info("Policy file not found — skipping policy variables.")
        return None

    try:
        df = pd.read_csv(path)
    except Exception as e:
        logger.warning("Failed to read policy file: %s", e)
        return None

    # Check required columns exist
    if POLICY_CROP_COL not in df.columns or POLICY_DATE_COL not in df.columns:
        logger.warning("Policy file missing required columns (crop/date) — skipping.")
        return None

    # Map crop filename to policy crop name
    policy_crop = CROP_NAME_MAP.get(crop_name)
    if policy_crop is None:
        logger.info("No policy mapping for crop '%s' — skipping policy.", crop_name)
        return None

    # Filter to this crop only
    mask = df[POLICY_CROP_COL].str.strip().str.lower() == policy_crop.lower()
    crop_policy = df[mask].copy()

    if crop_policy.empty:
        logger.info("No policy rows found for crop '%s' — skipping.", policy_crop)
        return None

    # Standardise date
    crop_policy = crop_policy.rename(columns={POLICY_DATE_COL: DATE_COL})
    crop_policy[DATE_COL] = pd.to_datetime(crop_policy[DATE_COL], errors="coerce")
    crop_policy = crop_policy.dropna(subset=[DATE_COL])

    # Collect usable policy columns
    use_cols = [DATE_COL]

    # Numeric cols — only keep if present and has valid non-zero data
    for c in POLICY_NUMERIC_COLS:
        if c in crop_policy.columns:
            crop_policy[c] = pd.to_numeric(crop_policy[c], errors="coerce")
            non_zero = crop_policy[c].dropna()
            non_zero = non_zero[non_zero != 0]
            if len(non_zero) >= 3:
                use_cols.append(c)
            else:
                logger.info("Policy col '%s' has <3 non-zero values for %s — dropping.", c, policy_crop)

    # Binary cols
    for c in POLICY_BINARY_COLS:
        if c in crop_policy.columns:
            crop_policy[c] = pd.to_numeric(crop_policy[c], errors="coerce").fillna(0).astype(int)
            if crop_policy[c].nunique() > 1 or crop_policy[c].sum() > 0:
                use_cols.append(c)

    if len(use_cols) <= 1:
        logger.info("No usable policy columns for '%s' — skipping.", policy_crop)
        return None

    result = crop_policy[use_cols].sort_values(DATE_COL).reset_index(drop=True)
    logger.info("Loaded %d policy rows with cols %s for '%s'.", len(result), use_cols[1:], policy_crop)
    return result


def list_crops() -> list:
    """Return names of all crop CSVs present in DATA_DIR."""
    exclude = {WEATHER_FILE, POLICY_FILE}
    crops = []
    for f in sorted(os.listdir(DATA_DIR)):
        if f.endswith(".csv") and f not in exclude:
            crops.append(f.replace(".csv", ""))
    return crops


# ============================================================================
# Preprocessing
# ============================================================================

def remove_outliers(df: pd.DataFrame) -> pd.DataFrame:
    """Remove price outliers using IQR method."""
    q1 = df[PRICE_COL].quantile(0.25)
    q3 = df[PRICE_COL].quantile(0.75)
    iqr = q3 - q1
    lower = q1 - IQR_MULTIPLIER * iqr
    upper = q3 + IQR_MULTIPLIER * iqr
    n_before = len(df)
    df = df[(df[PRICE_COL] >= lower) & (df[PRICE_COL] <= upper)].copy()
    n_removed = n_before - len(df)
    if n_removed > 0:
        logger.info("Removed %d outlier rows (IQR bounds: %.1f–%.1f).", n_removed, lower, upper)
    return df


def resample_weekly(df: pd.DataFrame) -> pd.DataFrame:
    """Resample daily data to weekly frequency using mean."""
    df = df.set_index(DATE_COL)
    weekly = df.resample("W").mean().dropna(subset=[PRICE_COL])
    weekly = weekly.reset_index()
    logger.info("Resampled to weekly: %d rows.", len(weekly))
    return weekly


# ============================================================================
# Alignment (merge crop + weather + policy)
# ============================================================================

def align_all(
    crop_df: pd.DataFrame,
    weather_df: pd.DataFrame,
    policy_df: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """
    Merge crop, weather, policy into one aligned DataFrame.
    1. Aggregate duplicate crop dates (mean)
    2. Backward-merge weather
    3. Backward-merge policy (if available)
    4. Drop high-NaN exogenous columns
    5. Forward/backward fill remaining NaNs
    """
    # Restrict to overlapping date range with weather
    w_start, w_end = weather_df[DATE_COL].min(), weather_df[DATE_COL].max()
    crop = crop_df[
        (crop_df[DATE_COL] >= w_start) & (crop_df[DATE_COL] <= w_end)
    ].copy()

    if crop.empty:
        logger.warning("No crop data overlaps with weather range %s–%s.", w_start, w_end)
        # Use all crop data if no overlap
        crop = crop_df.copy()

    # Aggregate duplicate dates
    crop = crop.groupby(DATE_COL, as_index=False)[PRICE_COL].mean()
    crop = crop.sort_values(DATE_COL).reset_index(drop=True)

    # Backward merge weather
    merged = pd.merge_asof(
        crop,
        weather_df.sort_values(DATE_COL),
        on=DATE_COL,
        direction="backward",
    )

    # Backward merge policy (optional)
    if policy_df is not None and not policy_df.empty:
        merged = pd.merge_asof(
            merged,
            policy_df.sort_values(DATE_COL),
            on=DATE_COL,
            direction="backward",
        )

    # Drop rows without price
    merged = merged.dropna(subset=[PRICE_COL])

    # Drop exog columns with too many NaNs
    exog_cols = [c for c in merged.columns if c not in (DATE_COL, PRICE_COL)]
    if exog_cols:
        nan_ratio = merged[exog_cols].isna().mean()
        drop_cols = nan_ratio[nan_ratio > NAN_DROP_THRESHOLD].index.tolist()
        if drop_cols:
            logger.info("Dropping high-NaN columns: %s", drop_cols)
            merged = merged.drop(columns=drop_cols)

    # Fill remaining NaNs
    exog_cols = [c for c in merged.columns if c not in (DATE_COL, PRICE_COL)]
    if exog_cols:
        merged[exog_cols] = merged[exog_cols].ffill().bfill().fillna(0)

    return merged.reset_index(drop=True)


# ============================================================================
# Feature engineering
# ============================================================================

def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add engineered features to the weekly DataFrame.
      - Lag features (1, 4, 13 weeks ≈ 1 week, 1 month, 3 months)
      - Rolling statistics (4, 8, 13 week windows)
      - Weather anomalies (temp and rain deviation from rolling mean)
      - Policy features (price−MSP, price/MSP, below_MSP binary)
    """
    df = df.copy()

    # --- Lag features ---
    for lag in WEEKLY_LAG_PERIODS:
        df[f"price_lag_{lag}"] = df[PRICE_COL].shift(lag)

    # --- Rolling statistics ---
    for w in WEEKLY_ROLL_WINDOWS:
        df[f"price_rmean_{w}"] = df[PRICE_COL].rolling(window=w, min_periods=1).mean()
        df[f"price_rstd_{w}"]  = df[PRICE_COL].rolling(window=w, min_periods=1).std()

    # --- Price momentum (week-over-week change) ---
    df["price_pct_change"] = df[PRICE_COL].pct_change()

    # --- Weather anomalies ---
    if "tavg" in df.columns:
        tavg_rm = df["tavg"].rolling(window=4, min_periods=1).mean()
        df["temp_anomaly"] = df["tavg"] - tavg_rm
    if "prcp" in df.columns:
        prcp_rm = df["prcp"].rolling(window=4, min_periods=1).mean()
        df["rain_anomaly"] = df["prcp"] - prcp_rm

    # --- Policy features ---
    if "msp_value_per_quintal" in df.columns:
        msp = df["msp_value_per_quintal"]
        valid_msp = msp.notna() & (msp > 0)
        if valid_msp.sum() >= 3:
            df["price_minus_msp"] = np.where(valid_msp, df[PRICE_COL] - msp, 0)
            df["price_over_msp"]  = np.where(valid_msp, df[PRICE_COL] / msp, 1)
            df["below_msp"]       = np.where(valid_msp & (df[PRICE_COL] < msp), 1, 0)
        else:
            # MSP data is not usable — drop it
            logger.info("MSP values mostly zero/missing — dropping policy price features.")
            df = df.drop(columns=["msp_value_per_quintal"], errors="ignore")

    # --- Drop rows with NaN from lag/rolling (head of series) ---
    max_lag = max(WEEKLY_LAG_PERIODS)
    df = df.iloc[max_lag:].reset_index(drop=True)

    # Final fillna for any remaining
    num_cols = df.select_dtypes(include=[np.number]).columns
    df[num_cols] = df[num_cols].fillna(0)

    return df


# ============================================================================
# Convenience: full pipeline
# ============================================================================

def load_and_align(crop_name: str) -> pd.DataFrame:
    """
    Full pipeline: load crop, weather, policy → clean → align → resample weekly
    → engineer features → return DataFrame ready for modelling.
    """
    logger.info("Loading data for '%s' …", crop_name)

    crop_df    = load_crop(crop_name)
    weather_df = load_weather()
    policy_df  = load_policy(crop_name)  # None if unavailable

    logger.info("Crop rows: %d, Weather rows: %d, Policy: %s",
                len(crop_df), len(weather_df),
                f"{len(policy_df)} rows" if policy_df is not None else "skipped")

    # Remove outliers from crop prices
    crop_df = remove_outliers(crop_df)

    # Align all datasets (daily)
    daily_df = align_all(crop_df, weather_df, policy_df)
    logger.info("Aligned daily rows: %d", len(daily_df))

    # Resample to weekly frequency
    weekly_df = resample_weekly(daily_df)

    # Engineer features
    featured_df = engineer_features(weekly_df)
    logger.info("Final featured dataset: %d rows, %d columns.", len(featured_df), len(featured_df.columns))

    if featured_df.empty:
        raise ValueError(
            f"Featured dataset for '{crop_name}' is empty after preprocessing. "
            "Check data coverage and date ranges."
        )

    return featured_df
