from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_DIR = Path(__file__).resolve().parents[1]

os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "-1")
os.environ.setdefault("MPLCONFIGDIR", str(REPO_DIR / "backend" / ".mplconfig"))

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from statsmodels.tsa.statespace.sarimax import SARIMAX
from tensorflow.keras import Sequential
from tensorflow.keras.callbacks import EarlyStopping
from tensorflow.keras.layers import LSTM, Dense, Dropout, Input
from sklearn.preprocessing import MinMaxScaler

BACKEND_DIR = REPO_DIR / "backend"
DATA_PATH = BACKEND_DIR / "data" / "coimbatore_maize_model_daily_v3.csv"
OUTPUTS_DIR = BACKEND_DIR / "outputs"

DATE_COL = "date"
PRICE_COL = "modal_price"
WEATHER_COLS = ["tavg", "tmin", "tmax", "prcp", "wdir", "wspd", "pres"]
POLICY_COLS = [
    "msp_applicable",
    "msp_value_per_quintal",
    "govt_procurement_active",
    "pmfby_insurance_active",
    "state_scheme_active",
    "harvest_season_active",
]
IQR_MULTIPLIER = 1.5
LAG_PERIODS = [1, 4, 13]
ROLL_WINDOWS = [4, 8, 13]
TRAIN_SPLIT_RATIO = 0.80
FORECAST_HORIZON = 13
ARIMAX_ORDER = (2, 1, 2)
LSTM_WINDOW = 4
LSTM_UNITS = 64
LSTM_DROPOUT = 0.2
LSTM_EPOCHS = 150
LSTM_BATCH_SIZE = 16
EARLY_STOP_PAT = 15
LSTM_MIN_SEQUENCES = 40
ROLLING_WINDOWS = 3
MODEL_NAMES = ["ARIMA", "ARIMAX", "Tabular", "Hybrid_ARIMAX_LSTM"]
DIRECTION_ORDER = ["price_floor", "neutral", "upward", "downward"]
SUMMARY_JSON_PATH = OUTPUTS_DIR / "maize_v3_split_experiment_summary.json"
SUMMARY_MD_PATH = OUTPUTS_DIR / "maize_v3_split_experiment_summary.md"


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
LOGGER = logging.getLogger("maize_v3_split_experiment")

OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)


try:
    from xgboost import XGBRegressor

    TABULAR_MODEL_LABEL = "XGBoostRegressor"
    TABULAR_MODEL_REASON = "Preferred choice available in the environment."

    def build_tabular_model():
        return XGBRegressor(
            n_estimators=400,
            learning_rate=0.03,
            max_depth=4,
            min_child_weight=2,
            subsample=0.9,
            colsample_bytree=0.9,
            objective="reg:squarederror",
            random_state=42,
        )

except Exception:
    TABULAR_MODEL_LABEL = "GradientBoostingRegressor"
    TABULAR_MODEL_REASON = (
        "XGBoost is not available in the current environment, so the experiment uses "
        "the sklearn fallback without changing the backend dependency stack."
    )

    def build_tabular_model():
        return GradientBoostingRegressor(
            random_state=42,
            n_estimators=400,
            learning_rate=0.03,
            max_depth=3,
            min_samples_leaf=2,
            subsample=0.9,
            loss="squared_error",
        )


@dataclass
class CandidateResult:
    name: str
    predictions: np.ndarray
    metrics: dict[str, float]
    notes: list[str]


def compute_metrics(actual, predicted) -> dict[str, float]:
    actual_arr = np.asarray(actual, dtype=float)
    predicted_arr = np.asarray(predicted, dtype=float)
    valid_mask = np.isfinite(actual_arr) & np.isfinite(predicted_arr)
    if not np.any(valid_mask):
        return {"rmse": np.nan, "mae": np.nan, "mape_pct": np.nan}

    actual_valid = actual_arr[valid_mask]
    predicted_valid = predicted_arr[valid_mask]
    errors = actual_valid - predicted_valid
    rmse = float(np.sqrt(np.mean(np.square(errors))))
    mae = float(np.mean(np.abs(errors)))

    non_zero_mask = actual_valid != 0
    if np.any(non_zero_mask):
        mape_pct = float(
            np.mean(
                np.abs(
                    (actual_valid[non_zero_mask] - predicted_valid[non_zero_mask])
                    / actual_valid[non_zero_mask]
                )
            )
            * 100.0
        )
    else:
        mape_pct = np.nan

    return {"rmse": rmse, "mae": mae, "mape_pct": mape_pct}


def _load_v3_daily() -> pd.DataFrame:
    df = pd.read_csv(DATA_PATH, parse_dates=[DATE_COL]).sort_values(DATE_COL).reset_index(drop=True)
    return df.dropna(subset=[PRICE_COL]).copy()


def _remove_price_outliers(df: pd.DataFrame) -> pd.DataFrame:
    q1 = df[PRICE_COL].quantile(0.25)
    q3 = df[PRICE_COL].quantile(0.75)
    iqr = q3 - q1
    lower = q1 - (IQR_MULTIPLIER * iqr)
    upper = q3 + (IQR_MULTIPLIER * iqr)
    return df[df[PRICE_COL].between(lower, upper)].copy()


def _prepare_weekly_dataset(daily_df: pd.DataFrame, include_policy: bool) -> pd.DataFrame:
    df = _remove_price_outliers(daily_df.copy())

    if include_policy:
        direction_series = (
            df["price_impact_direction"]
            .fillna("neutral")
            .astype(str)
            .str.strip()
            .str.lower()
        )
        direction_series = direction_series.where(direction_series.isin(DIRECTION_ORDER), "neutral")
        direction_series = pd.Categorical(direction_series, categories=DIRECTION_ORDER, ordered=True)
        direction_dummies = pd.get_dummies(direction_series, prefix="dir", drop_first=True, dtype=float)
        df = pd.concat(
            [df.drop(columns=["price_impact_direction"], errors="ignore"), direction_dummies],
            axis=1,
        )
    else:
        df = df.drop(columns=["price_impact_direction"], errors="ignore")

    weekly_df = df.set_index(DATE_COL).resample("W").mean(numeric_only=True)
    weekly_df[PRICE_COL] = weekly_df[PRICE_COL].ffill().bfill()

    present_weather_cols = [col for col in WEATHER_COLS if col in weekly_df.columns]
    weekly_df[present_weather_cols] = weekly_df[present_weather_cols].ffill().bfill()
    for col in present_weather_cols:
        weekly_df[col] = weekly_df[col].fillna(weekly_df[col].mean())

    if include_policy:
        policy_like_cols = [col for col in POLICY_COLS if col in weekly_df.columns]
        direction_cols = [col for col in weekly_df.columns if col.startswith("dir_")]
        fill_cols = policy_like_cols + direction_cols
        if fill_cols:
            weekly_df[fill_cols] = weekly_df[fill_cols].ffill().bfill()

    rolling_tavg = weekly_df["tavg"].rolling(window=4, min_periods=1).mean()
    rolling_prcp = weekly_df["prcp"].rolling(window=4, min_periods=1).mean()
    weekly_df["temp_anomaly"] = weekly_df["tavg"] - rolling_tavg
    weekly_df["rain_anomaly"] = weekly_df["prcp"] - rolling_prcp

    for lag in LAG_PERIODS:
        weekly_df[f"price_lag_{lag}"] = weekly_df[PRICE_COL].shift(lag)
    for window in ROLL_WINDOWS:
        weekly_df[f"price_rmean_{window}"] = weekly_df[PRICE_COL].rolling(window=window, min_periods=window).mean()
        weekly_df[f"price_rstd_{window}"] = weekly_df[PRICE_COL].rolling(window=window, min_periods=window).std()
    weekly_df["price_pct_change"] = weekly_df[PRICE_COL].pct_change()

    weekly_df = weekly_df.iloc[13:].copy()
    numeric_cols = weekly_df.select_dtypes(include=[np.number]).columns.tolist()
    fill_zero_cols = [col for col in numeric_cols if col != PRICE_COL]
    weekly_df[fill_zero_cols] = weekly_df[fill_zero_cols].fillna(0.0)

    return weekly_df.reset_index()


def _get_exog_columns(df: pd.DataFrame, include_policy: bool) -> list[str]:
    exog_cols = WEATHER_COLS + ["temp_anomaly", "rain_anomaly"]
    if include_policy:
        exog_cols.extend([col for col in POLICY_COLS if col in df.columns])
        exog_cols.extend(sorted(col for col in df.columns if col.startswith("dir_")))
    return [col for col in exog_cols if col in df.columns]


def _build_tabular_frame(df: pd.DataFrame, feature_exog_cols: list[str], first_date: pd.Timestamp) -> pd.DataFrame:
    feature_frame = pd.DataFrame(index=df.index)
    for col in [f"price_lag_{lag}" for lag in LAG_PERIODS]:
        feature_frame[col] = df[col].astype(float)
    for window in ROLL_WINDOWS:
        feature_frame[f"price_rmean_{window}"] = df[f"price_rmean_{window}"].astype(float)
        feature_frame[f"price_rstd_{window}"] = df[f"price_rstd_{window}"].astype(float)
    feature_frame["price_pct_change"] = df["price_pct_change"].astype(float)

    for col in feature_exog_cols:
        feature_frame[col] = df[col].astype(float)

    dates = pd.to_datetime(df[DATE_COL])
    iso_week = dates.dt.isocalendar().week.astype(int).astype(float)
    month = dates.dt.month.astype(float)
    feature_frame["month"] = month
    feature_frame["quarter"] = dates.dt.quarter.astype(float)
    feature_frame["iso_week"] = iso_week
    feature_frame["year"] = dates.dt.year.astype(float)
    feature_frame["week_sin"] = np.sin(2.0 * np.pi * iso_week / 52.0)
    feature_frame["week_cos"] = np.cos(2.0 * np.pi * iso_week / 52.0)
    feature_frame["month_sin"] = np.sin(2.0 * np.pi * month / 12.0)
    feature_frame["month_cos"] = np.cos(2.0 * np.pi * month / 12.0)
    feature_frame["weeks_since_start"] = ((dates - first_date).dt.days / 7.0).astype(float)

    return feature_frame.fillna(0.0)


def _fit_sarimax(y_values, exog=None):
    model = SARIMAX(
        endog=np.asarray(y_values, dtype=float),
        exog=None if exog is None else np.asarray(exog, dtype=float),
        order=ARIMAX_ORDER,
        enforce_stationarity=False,
        enforce_invertibility=False,
    )
    fitted = model.fit(disp=False, maxiter=200)
    converged = bool(getattr(fitted, "mle_retvals", {}).get("converged", True))
    return fitted, converged


def _build_lstm_model(window: int):
    model = Sequential(
        [
            Input(shape=(window, 1)),
            LSTM(LSTM_UNITS),
            Dropout(LSTM_DROPOUT),
            Dense(1),
        ]
    )
    model.compile(optimizer="adam", loss="mse")
    return model


def _build_sequences(data, window):
    values = np.asarray(data, dtype=float).reshape(-1)
    if len(values) <= window:
        return np.empty((0, window, 1)), np.empty((0,))
    x_seq, y_seq = [], []
    for idx in range(window, len(values)):
        x_seq.append(values[idx - window : idx].reshape(window, 1))
        y_seq.append(values[idx])
    return np.asarray(x_seq, dtype=float), np.asarray(y_seq, dtype=float)


def _lstm_autoregressive_forecast(model, last_seq, steps, scaler):
    seq = np.asarray(last_seq, dtype=float).reshape(-1)
    preds_scaled = []
    for _ in range(steps):
        next_scaled = float(model.predict(seq.reshape(1, len(seq), 1), verbose=0)[0][0])
        preds_scaled.append(next_scaled)
        seq = np.append(seq[1:], next_scaled)
    pred_array = np.asarray(preds_scaled, dtype=float).reshape(-1, 1)
    return scaler.inverse_transform(pred_array).reshape(-1)


def _recursive_tabular_forecast(model, history_prices, future_dates, future_exog, first_date, feature_columns):
    history = list(np.asarray(history_prices, dtype=float).reshape(-1))
    predictions = []
    for idx, future_date in enumerate(pd.to_datetime(future_dates)):
        exog_row = future_exog.iloc[idx]
        row = _tabular_feature_row(history, exog_row, future_date, first_date, feature_columns)
        next_value = float(model.predict(row)[0])
        predictions.append(next_value)
        history.append(next_value)
    return np.asarray(predictions, dtype=float)


def _tabular_feature_row(history_prices, exog_row, future_date, first_date, feature_columns):
    history = pd.Series(history_prices, dtype=float)
    row = {
        "price_lag_1": float(history.iloc[-1]),
        "price_lag_4": float(history.iloc[-4]) if len(history) >= 4 else float(history.iloc[0]),
        "price_lag_13": float(history.iloc[-13]) if len(history) >= 13 else float(history.iloc[0]),
        "price_rmean_4": float(history.tail(4).mean()),
        "price_rmean_8": float(history.tail(8).mean()),
        "price_rmean_13": float(history.tail(13).mean()),
        "price_rstd_4": float(history.tail(4).std(ddof=1)) if len(history) >= 4 else 0.0,
        "price_rstd_8": float(history.tail(8).std(ddof=1)) if len(history) >= 8 else 0.0,
        "price_rstd_13": float(history.tail(13).std(ddof=1)) if len(history) >= 13 else 0.0,
        "price_pct_change": (
            float((history.iloc[-1] - history.iloc[-2]) / history.iloc[-2])
            if len(history) >= 2 and history.iloc[-2] != 0
            else 0.0
        ),
    }
    row.update({key: float(value) for key, value in exog_row.to_dict().items()})

    future_date = pd.Timestamp(future_date)
    iso_week = float(future_date.isocalendar().week)
    month = float(future_date.month)
    row["month"] = month
    row["quarter"] = float(future_date.quarter)
    row["iso_week"] = iso_week
    row["year"] = float(future_date.year)
    row["week_sin"] = float(np.sin(2.0 * np.pi * iso_week / 52.0))
    row["week_cos"] = float(np.cos(2.0 * np.pi * iso_week / 52.0))
    row["month_sin"] = float(np.sin(2.0 * np.pi * month / 12.0))
    row["month_cos"] = float(np.cos(2.0 * np.pi * month / 12.0))
    row["weeks_since_start"] = float((future_date - pd.Timestamp(first_date)).days / 7.0)

    for column in feature_columns:
        row.setdefault(column, 0.0)
        if row[column] is None or (isinstance(row[column], float) and np.isnan(row[column])):
            row[column] = 0.0
    return pd.DataFrame([{column: row[column] for column in feature_columns}])


def _train_arima(y_train, y_test) -> CandidateResult:
    notes = []
    predictions = np.full(len(y_test), np.nan)
    try:
        model, converged = _fit_sarimax(y_train)
        if not converged:
            notes.append("SARIMAX optimizer reported non-convergence on holdout fit.")
        predictions = np.asarray(model.forecast(steps=len(y_test)), dtype=float)
        metrics = compute_metrics(y_test, predictions)
    except Exception as exc:
        notes.append(f"Training failed: {exc}")
        metrics = {"rmse": np.nan, "mae": np.nan, "mape_pct": np.nan}
    return CandidateResult("ARIMA", predictions, metrics, notes)


def _train_arimax(y_train, y_test, x_train, x_test) -> CandidateResult:
    notes = []
    predictions = np.full(len(y_test), np.nan)
    try:
        model, converged = _fit_sarimax(y_train, exog=x_train)
        if not converged:
            notes.append("SARIMAX optimizer reported non-convergence on holdout fit.")
        predictions = np.asarray(model.forecast(steps=len(y_test), exog=x_test), dtype=float)
        metrics = compute_metrics(y_test, predictions)
    except Exception as exc:
        notes.append(f"Training failed: {exc}")
        metrics = {"rmse": np.nan, "mae": np.nan, "mape_pct": np.nan}
    return CandidateResult("ARIMAX", predictions, metrics, notes)


def _train_tabular(y_train, y_test, tab_train, x_test, test_dates, first_date, feature_columns) -> CandidateResult:
    notes = [f"Tabular model: {TABULAR_MODEL_LABEL}"]
    predictions = np.full(len(y_test), np.nan)
    try:
        model = build_tabular_model()
        model.fit(tab_train, np.asarray(y_train, dtype=float))
        predictions = _recursive_tabular_forecast(
            model=model,
            history_prices=y_train,
            future_dates=test_dates,
            future_exog=x_test.reset_index(drop=True),
            first_date=first_date,
            feature_columns=feature_columns,
        )
        metrics = compute_metrics(y_test, predictions)
    except Exception as exc:
        notes.append(f"Training failed: {exc}")
        metrics = {"rmse": np.nan, "mae": np.nan, "mape_pct": np.nan}
    return CandidateResult("Tabular", predictions, metrics, notes)


def _train_hybrid(y_train, y_test, x_train, x_test) -> CandidateResult:
    notes = []
    predictions = np.full(len(y_test), np.nan)
    try:
        arimax_model, converged = _fit_sarimax(y_train, exog=x_train)
        if not converged:
            notes.append("ARIMAX base optimizer reported non-convergence on holdout fit.")
        arimax_predictions = np.asarray(arimax_model.forecast(steps=len(y_test), exog=x_test), dtype=float)
        residuals = np.asarray(y_train, dtype=float) - np.asarray(arimax_model.fittedvalues, dtype=float)
        scaler = MinMaxScaler()
        residuals_scaled = scaler.fit_transform(residuals.reshape(-1, 1)).reshape(-1)
        x_seq, y_seq = _build_sequences(residuals_scaled, LSTM_WINDOW)
        if len(x_seq) < LSTM_MIN_SEQUENCES:
            notes.append(f"Skipped because only {len(x_seq)} residual sequences are available.")
            metrics = {"rmse": np.nan, "mae": np.nan, "mape_pct": np.nan}
            return CandidateResult("Hybrid_ARIMAX_LSTM", predictions, metrics, notes)

        lstm_model = _build_lstm_model(LSTM_WINDOW)
        lstm_model.fit(
            x_seq,
            y_seq,
            epochs=LSTM_EPOCHS,
            batch_size=LSTM_BATCH_SIZE,
            validation_split=0.1 if len(x_seq) >= 50 else 0.0,
            callbacks=[EarlyStopping(patience=EARLY_STOP_PAT, restore_best_weights=True)],
            verbose=0,
        )
        residual_predictions = _lstm_autoregressive_forecast(
            model=lstm_model,
            last_seq=residuals_scaled[-LSTM_WINDOW:],
            steps=len(y_test),
            scaler=scaler,
        )
        predictions = arimax_predictions + residual_predictions
        metrics = compute_metrics(y_test, predictions)
    except Exception as exc:
        notes.append(f"Training failed: {exc}")
        metrics = {"rmse": np.nan, "mae": np.nan, "mape_pct": np.nan}
    return CandidateResult("Hybrid_ARIMAX_LSTM", predictions, metrics, notes)


def _run_holdout_experiment(name: str, weekly_df: pd.DataFrame, include_policy: bool) -> dict[str, Any]:
    y = weekly_df[PRICE_COL].astype(float).to_numpy()
    dates = pd.to_datetime(weekly_df[DATE_COL])
    first_date = pd.Timestamp(dates.iloc[0])
    exog_columns = _get_exog_columns(weekly_df, include_policy)
    x_exog = weekly_df[exog_columns].astype(float).copy()
    tabular_df = _build_tabular_frame(weekly_df, exog_columns, first_date)

    split_index = int(len(weekly_df) * TRAIN_SPLIT_RATIO)
    split_index = min(max(split_index, LSTM_WINDOW + 1), len(weekly_df) - 1)
    y_train, y_test = y[:split_index], y[split_index:]
    x_train, x_test = x_exog.iloc[:split_index], x_exog.iloc[split_index:]
    tab_train = tabular_df.iloc[:split_index]
    test_dates = dates.iloc[split_index:]

    candidates = [
        _train_arima(y_train, y_test),
        _train_arimax(y_train, y_test, x_train, x_test),
        _train_tabular(
            y_train=y_train,
            y_test=y_test,
            tab_train=tab_train,
            x_test=x_test,
            test_dates=test_dates,
            first_date=first_date,
            feature_columns=tabular_df.columns.tolist(),
        ),
        _train_hybrid(y_train, y_test, x_train, x_test),
    ]

    comparison_df = pd.DataFrame(
        [
            {
                "model_name": candidate.name,
                "rmse": candidate.metrics["rmse"],
                "mae": candidate.metrics["mae"],
                "mape_pct": candidate.metrics["mape_pct"],
                "notes": " | ".join(candidate.notes),
            }
            for candidate in candidates
            if np.isfinite(candidate.metrics["rmse"])
        ]
    ).sort_values(["rmse", "mae", "mape_pct"], ascending=[True, True, True], na_position="last")

    comparison_path = OUTPUTS_DIR / f"maize_v3_{name.lower()}_holdout_model_comparison.csv"
    comparison_df.to_csv(comparison_path, index=False)

    predictions_df = pd.DataFrame(
        {
            "date": test_dates.dt.strftime("%Y-%m-%d"),
            "actual": y_test,
        }
    )
    for candidate in candidates:
        predictions_df[f"pred_{candidate.name}"] = candidate.predictions
    predictions_path = OUTPUTS_DIR / f"maize_v3_{name.lower()}_holdout_predictions.csv"
    predictions_df.to_csv(predictions_path, index=False)

    naive_predictions = np.full(len(y_test), y_train[-1], dtype=float)
    naive_metrics = compute_metrics(y_test, naive_predictions)

    return {
        "name": name,
        "rows": int(len(weekly_df)),
        "date_start": dates.min().strftime("%Y-%m-%d"),
        "date_end": dates.max().strftime("%Y-%m-%d"),
        "train_size": int(len(y_train)),
        "test_size": int(len(y_test)),
        "exog_columns": exog_columns,
        "comparison_path": str(comparison_path),
        "predictions_path": str(predictions_path),
        "holdout_results": {
            candidate.name: {
                "metrics": candidate.metrics,
                "notes": candidate.notes,
            }
            for candidate in candidates
        },
        "naive_last_value_baseline": naive_metrics,
        "winner": comparison_df.iloc[0]["model_name"] if not comparison_df.empty else None,
        "winner_metrics": (
            comparison_df.iloc[0][["rmse", "mae", "mape_pct"]].to_dict()
            if not comparison_df.empty
            else {"rmse": np.nan, "mae": np.nan, "mape_pct": np.nan}
        ),
    }


def _run_rolling_backtest(name: str, weekly_df: pd.DataFrame, include_policy: bool) -> dict[str, Any]:
    y = weekly_df[PRICE_COL].astype(float).to_numpy()
    dates = pd.to_datetime(weekly_df[DATE_COL])
    first_date = pd.Timestamp(dates.iloc[0])
    exog_columns = _get_exog_columns(weekly_df, include_policy)
    x_exog = weekly_df[exog_columns].astype(float).copy()
    tabular_df = _build_tabular_frame(weekly_df, exog_columns, first_date)

    min_train_size = max(52, len(weekly_df) // 2)
    split_starts = list(
        range(max(min_train_size, len(weekly_df) - (ROLLING_WINDOWS * FORECAST_HORIZON)),
              len(weekly_df) - FORECAST_HORIZON + 1,
              FORECAST_HORIZON)
    )

    aggregated_actuals = {model_name: [] for model_name in MODEL_NAMES}
    aggregated_predictions = {model_name: [] for model_name in MODEL_NAMES}
    notes = {model_name: [] for model_name in MODEL_NAMES}

    for split_index in split_starts:
        y_train = y[:split_index]
        y_test = y[split_index : split_index + FORECAST_HORIZON]
        x_train = x_exog.iloc[:split_index]
        x_test = x_exog.iloc[split_index : split_index + FORECAST_HORIZON]
        tab_train = tabular_df.iloc[:split_index]
        test_dates = dates.iloc[split_index : split_index + FORECAST_HORIZON]

        candidates = [
            _train_arima(y_train, y_test),
            _train_arimax(y_train, y_test, x_train, x_test),
            _train_tabular(
                y_train=y_train,
                y_test=y_test,
                tab_train=tab_train,
                x_test=x_test,
                test_dates=test_dates,
                first_date=first_date,
                feature_columns=tabular_df.columns.tolist(),
            ),
            _train_hybrid(y_train, y_test, x_train, x_test),
        ]

        for candidate in candidates:
            aggregated_actuals[candidate.name].extend(y_test.tolist())
            aggregated_predictions[candidate.name].extend(candidate.predictions.tolist())
            notes[candidate.name].extend(candidate.notes)

    rows = []
    metrics_by_model = {}
    for model_name in MODEL_NAMES:
        metrics = compute_metrics(aggregated_actuals[model_name], aggregated_predictions[model_name])
        metrics_by_model[model_name] = {"metrics": metrics, "notes": sorted(set(notes[model_name]))}
        if np.isfinite(metrics["rmse"]):
            rows.append(
                {
                    "model_name": model_name,
                    "rmse": metrics["rmse"],
                    "mae": metrics["mae"],
                    "mape_pct": metrics["mape_pct"],
                    "notes": " | ".join(sorted(set(notes[model_name]))),
                }
            )

    comparison_df = pd.DataFrame(rows).sort_values(
        ["rmse", "mae", "mape_pct"],
        ascending=[True, True, True],
        na_position="last",
    )
    comparison_path = OUTPUTS_DIR / f"maize_v3_{name.lower()}_rolling_model_comparison.csv"
    comparison_df.to_csv(comparison_path, index=False)

    return {
        "splits_evaluated": len(split_starts),
        "comparison_path": str(comparison_path),
        "results": metrics_by_model,
        "winner": comparison_df.iloc[0]["model_name"] if not comparison_df.empty else None,
        "winner_metrics": (
            comparison_df.iloc[0][["rmse", "mae", "mape_pct"]].to_dict()
            if not comparison_df.empty
            else {"rmse": np.nan, "mae": np.nan, "mape_pct": np.nan}
        ),
    }


def _build_experiment_datasets() -> tuple[pd.DataFrame, pd.DataFrame]:
    daily_df = _load_v3_daily()

    exp_a_daily = daily_df.copy()

    valid_policy_mask = daily_df[POLICY_COLS + ["price_impact_direction"]].notna().all(axis=1)
    exp_b_daily = daily_df.loc[valid_policy_mask].copy()

    return (
        _prepare_weekly_dataset(exp_a_daily, include_policy=False),
        _prepare_weekly_dataset(exp_b_daily, include_policy=True),
    )


def _serialize_for_json(obj):
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return None if np.isnan(obj) else float(obj)
    if isinstance(obj, (pd.Timestamp,)):
        return obj.isoformat()
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj


def _write_markdown_summary(summary: dict[str, Any]):
    exp_a = summary["experiment_a"]
    exp_b = summary["experiment_b"]
    md = f"""# Maize V3 Split Experiment

Tabular model used: `{summary['tabular_model']}`

Reason: {summary['tabular_model_reason']}

## Experiment A — Full-history, no-policy

- Weekly rows: {exp_a['rows']}
- Date range: {exp_a['date_start']} to {exp_a['date_end']}
- Holdout winner: {exp_a['winner']} with RMSE {exp_a['winner_metrics']['rmse']:.3f}
- Rolling winner: {exp_a['rolling']['winner']} with RMSE {exp_a['rolling']['winner_metrics']['rmse']:.3f}
- Naive last-value RMSE: {exp_a['naive_last_value_baseline']['rmse']:.3f}

## Experiment B — Policy-aware subset

- Weekly rows: {exp_b['rows']}
- Date range: {exp_b['date_start']} to {exp_b['date_end']}
- Holdout winner: {exp_b['winner']} with RMSE {exp_b['winner_metrics']['rmse']:.3f}
- Rolling winner: {exp_b['rolling']['winner']} with RMSE {exp_b['rolling']['winner_metrics']['rmse']:.3f}
- Naive last-value RMSE: {exp_b['naive_last_value_baseline']['rmse']:.3f}

## Recommendation

- Better regime for product/demo: {summary['recommendation']['product_demo']}
- Better regime for research paper: {summary['recommendation']['research_paper']}
- Evidence summary: {summary['recommendation']['evidence']}
"""
    SUMMARY_MD_PATH.write_text(md, encoding="utf-8")


def main():
    LOGGER.info("Running maize V3 split experiments from %s", DATA_PATH)
    exp_a_df, exp_b_df = _build_experiment_datasets()

    exp_a = _run_holdout_experiment("experiment_a", exp_a_df, include_policy=False)
    exp_a["rolling"] = _run_rolling_backtest("experiment_a", exp_a_df, include_policy=False)

    exp_b = _run_holdout_experiment("experiment_b", exp_b_df, include_policy=True)
    exp_b["rolling"] = _run_rolling_backtest("experiment_b", exp_b_df, include_policy=True)

    better_holdout = "experiment_a" if exp_a["winner_metrics"]["rmse"] < exp_b["winner_metrics"]["rmse"] else "experiment_b"
    better_rolling = (
        "experiment_a"
        if exp_a["rolling"]["winner_metrics"]["rmse"] < exp_b["rolling"]["winner_metrics"]["rmse"]
        else "experiment_b"
    )

    holdout_gap = abs(exp_a["winner_metrics"]["rmse"] - exp_b["winner_metrics"]["rmse"])
    rolling_gap = abs(
        exp_a["rolling"]["winner_metrics"]["rmse"] - exp_b["rolling"]["winner_metrics"]["rmse"]
    )

    if better_holdout == better_rolling:
        product_demo = better_holdout
    elif holdout_gap >= max(10.0, rolling_gap * 2.0):
        product_demo = better_holdout
    else:
        product_demo = better_rolling

    recommendation = {
        "better_holdout_regime": better_holdout,
        "better_rolling_regime": better_rolling,
        "product_demo": product_demo,
        "research_paper": (
            "experiment_a"
            if exp_a["rows"] > exp_b["rows"]
            and exp_a["rolling"]["winner_metrics"]["rmse"]
            <= (exp_b["rolling"]["winner_metrics"]["rmse"] * 1.03)
            else better_holdout
        ),
        "evidence": (
            "Experiment A measures whether longer history plus weather-only exogenous structure is enough. "
            "Experiment B measures whether policy/MSP features justify discarding the older pre-policy years. "
            "The recommendation prefers recent holdout performance for the product/demo when that gap is materially "
            "larger, but still values longer-history rolling stability for the research direction."
        ),
    }

    summary = {
        "dataset": str(DATA_PATH),
        "tabular_model": TABULAR_MODEL_LABEL,
        "tabular_model_reason": TABULAR_MODEL_REASON,
        "experiment_a": exp_a,
        "experiment_b": exp_b,
        "recommendation": recommendation,
    }
    SUMMARY_JSON_PATH.write_text(
        json.dumps(summary, indent=2, default=_serialize_for_json),
        encoding="utf-8",
    )
    _write_markdown_summary(summary)

    LOGGER.info("Saved summary to %s", SUMMARY_JSON_PATH)
    LOGGER.info("Saved markdown summary to %s", SUMMARY_MD_PATH)


if __name__ == "__main__":
    main()
