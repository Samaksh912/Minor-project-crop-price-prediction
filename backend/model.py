from __future__ import annotations

import os

os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

import logging
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.preprocessing import MinMaxScaler
from statsmodels.tsa.statespace.sarimax import SARIMAX
from tensorflow.keras import Sequential
from tensorflow.keras.callbacks import EarlyStopping
from tensorflow.keras.layers import LSTM, Dense, Dropout, Input

from config import (
    ARIMAX_ORDER,
    DATE_COL,
    EARLY_STOP_PAT,
    FORECAST_DAYS,
    FORECAST_HORIZON,
    LSTM_BATCH_SIZE,
    LSTM_DROPOUT,
    LSTM_EPOCHS,
    LSTM_MIN_SEQUENCES,
    LSTM_UNITS,
    LSTM_WINDOW,
    MODELS_DIR,
    PRICE_COL,
    TRAIN_SPLIT_RATIO,
)
from data_loader import get_exog_cols
from evaluation import compare_models, compute_metrics, save_evaluation_report


LOGGER = logging.getLogger(__name__)
MODEL_NAMES = [
    "ARIMA",
    "ARIMAX",
    "Standalone_LSTM",
    "Hybrid_ARIMAX_LSTM",
    "Tabular_GBM",
]
TABULAR_PRICE_FEATURES = [
    "price_lag_1",
    "price_lag_4",
    "price_lag_13",
    "price_rmean_4",
    "price_rmean_8",
    "price_rmean_13",
    "price_rstd_4",
    "price_rstd_8",
    "price_rstd_13",
    "price_pct_change",
]
TABULAR_CALENDAR_FEATURES = [
    "month",
    "quarter",
    "iso_week",
    "year",
    "week_sin",
    "week_cos",
    "month_sin",
    "month_cos",
    "weeks_since_start",
]


def _build_lstm_model(window):
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

    x_seq = []
    y_seq = []
    for index in range(window, len(values)):
        x_seq.append(values[index - window : index].reshape(window, 1))
        y_seq.append(values[index])
    return np.asarray(x_seq, dtype=float), np.asarray(y_seq, dtype=float)


def _lstm_autoregressive_forecast(model, last_seq, steps, scaler):
    seq = np.asarray(last_seq, dtype=float).reshape(-1)
    if len(seq) == 0:
        return np.asarray([], dtype=float)

    preds_scaled = []
    for _ in range(steps):
        next_scaled = float(model.predict(seq.reshape(1, len(seq), 1), verbose=0)[0][0])
        preds_scaled.append(next_scaled)
        seq = np.append(seq[1:], next_scaled)

    pred_array = np.asarray(preds_scaled, dtype=float).reshape(-1, 1)
    if scaler is None:
        return pred_array.reshape(-1)
    return scaler.inverse_transform(pred_array).reshape(-1)


def model_exists(crop_name):
    meta_path = os.path.join(MODELS_DIR, f"{crop_name}_meta.pkl")
    if not os.path.exists(meta_path):
        return False

    try:
        meta = joblib.load(meta_path)
    except Exception:
        LOGGER.exception("Failed to load metadata from %s", meta_path)
        return False

    required_meta_keys = {
        "last_date",
        "last_X_row",
        "exog_columns",
        "best_model_name",
        "metrics",
        "all_metrics",
        "train_size",
        "test_size",
        "total_size",
    }
    if not required_meta_keys.issubset(meta):
        LOGGER.warning("Metadata for %s is missing required keys", crop_name)
        return False

    artifact_paths = _artifact_paths(crop_name)
    best_model_name = meta.get("best_model_name")
    required_artifacts = {
        "ARIMA": [artifact_paths["arima"], artifact_paths["meta"]],
        "ARIMAX": [artifact_paths["arimax"], artifact_paths["meta"]],
        "Hybrid_ARIMAX_LSTM": [
            artifact_paths["arimax"],
            artifact_paths["lstm"],
            artifact_paths["scaler"],
            artifact_paths["meta"],
        ],
        "Standalone_LSTM": [
            artifact_paths["lstm"],
            artifact_paths["price_scaler"],
            artifact_paths["meta"],
        ],
        "Tabular_GBM": [artifact_paths["gbr"], artifact_paths["meta"]],
    }.get(best_model_name)

    if not required_artifacts:
        LOGGER.warning("Unknown best model name in metadata: %s", best_model_name)
        return False

    exists = all(os.path.exists(path) for path in required_artifacts)
    if not exists:
        LOGGER.warning("Missing one or more required artifacts for %s", best_model_name)
    return exists


def train_hybrid(df: pd.DataFrame, crop_name: str) -> dict:
    LOGGER.info("Starting training pipeline for crop=%s", crop_name)

    y = df[PRICE_COL].astype(float).to_numpy()
    dates = pd.to_datetime(df[DATE_COL]).reset_index(drop=True)
    first_date = pd.Timestamp(dates.iloc[0])
    last_date = pd.Timestamp(dates.iloc[-1])
    exog_columns = get_exog_cols(df)
    x_exog = df[exog_columns].astype(float).copy()
    tabular_df = _build_tabular_feature_frame(df, exog_columns, first_date)
    tabular_columns = tabular_df.columns.tolist()

    split_index = int(len(df) * TRAIN_SPLIT_RATIO)
    split_index = min(max(split_index, LSTM_WINDOW + 1), len(df) - 1)
    if split_index <= 0 or split_index >= len(df):
        raise ValueError("Insufficient data after preprocessing for train/test split")

    y_train, y_test = y[:split_index], y[split_index:]
    x_train, x_test = x_exog.iloc[:split_index], x_exog.iloc[split_index:]
    tab_train = tabular_df.iloc[:split_index]
    test_dates = pd.to_datetime(dates.iloc[split_index:])

    results: dict[str, dict[str, Any]] = {}
    all_test_predictions = {
        model_name: np.full(len(y_test), np.nan, dtype=float) for model_name in MODEL_NAMES
    }

    arima_result = _train_sarimax_candidate("ARIMA", y_train, y_test)
    results["ARIMA"] = {"metrics": arima_result["metrics"]}
    all_test_predictions["ARIMA"] = arima_result["predictions"]

    arimax_result = _train_sarimax_candidate("ARIMAX", y_train, y_test, x_train, x_test)
    results["ARIMAX"] = {"metrics": arimax_result["metrics"]}
    all_test_predictions["ARIMAX"] = arimax_result["predictions"]

    standalone_result = _train_standalone_lstm_candidate(y_train, y_test)
    results["Standalone_LSTM"] = {"metrics": standalone_result["metrics"]}
    all_test_predictions["Standalone_LSTM"] = standalone_result["predictions"]

    hybrid_result = _train_hybrid_candidate(y_train, y_test, x_train, x_test)
    results["Hybrid_ARIMAX_LSTM"] = {"metrics": hybrid_result["metrics"]}
    all_test_predictions["Hybrid_ARIMAX_LSTM"] = hybrid_result["predictions"]

    tabular_result = _train_tabular_candidate(
        y_train=y_train,
        y_test=y_test,
        tab_train=tab_train,
        future_exog=x_test,
        future_dates=test_dates,
        first_date=first_date,
        feature_columns=tabular_columns,
    )
    results["Tabular_GBM"] = {"metrics": tabular_result["metrics"]}
    all_test_predictions["Tabular_GBM"] = tabular_result["predictions"]

    comparison_df = compare_models(results)
    if comparison_df.empty:
        raise RuntimeError("No valid model completed training successfully")

    rolling_origin_metrics = _run_rolling_origin_backtest(
        df=df,
        y=y,
        x_exog=x_exog,
        exog_columns=exog_columns,
        tabular_df=tabular_df,
        tabular_columns=tabular_columns,
        first_date=first_date,
    )

    deployed_model_name = None
    deployed_artifacts = None
    training_failures = {}

    for model_name in comparison_df["model_name"].tolist():
        try:
            deployed_artifacts = _retrain_full_model(
                model_name=model_name,
                crop_name=crop_name,
                y=y,
                x_exog=x_exog,
                exog_columns=exog_columns,
                tabular_df=tabular_df,
                tabular_columns=tabular_columns,
                first_date=first_date,
                last_date=last_date,
            )
            deployed_model_name = model_name
            LOGGER.info("Selected production model: %s", deployed_model_name)
            break
        except Exception as exc:
            LOGGER.exception("Full-data retraining failed for %s", model_name)
            training_failures[model_name] = str(exc)

    if deployed_model_name is None or deployed_artifacts is None:
        raise RuntimeError(f"All candidate production retrains failed: {training_failures}")

    final_metrics = results[deployed_model_name]["metrics"]
    test_predicted = all_test_predictions[deployed_model_name]

    meta = {
        "last_date": last_date.isoformat(),
        "first_date": first_date.isoformat(),
        "last_X_row": (
            None
            if deployed_model_name == "ARIMA"
            else x_exog.iloc[-1][exog_columns].astype(float).to_dict()
        ),
        "exog_columns": [] if deployed_model_name == "ARIMA" else exog_columns,
        "tabular_feature_columns": tabular_columns,
        "best_model_name": deployed_model_name,
        "metrics": final_metrics,
        "all_metrics": {name: results[name]["metrics"] for name in MODEL_NAMES},
        "rolling_origin_metrics": rolling_origin_metrics,
        "train_size": int(len(y_train)),
        "test_size": int(len(y_test)),
        "total_size": int(len(y)),
    }
    joblib.dump(meta, _artifact_paths(crop_name)["meta"])

    evaluation_payload = {
        "crop_name": crop_name,
        "best_model_name": deployed_model_name,
        "metrics": final_metrics,
        "all_metrics": meta["all_metrics"],
        "rolling_origin_metrics": rolling_origin_metrics,
        "train_size": meta["train_size"],
        "test_size": meta["test_size"],
        "total_size": meta["total_size"],
        "forecast": deployed_artifacts["forecast"].tolist(),
        "forecast_dates": [pd.Timestamp(item).strftime("%Y-%m-%d") for item in deployed_artifacts["forecast_dates"]],
        "test_predictions": {
            model_name: prediction_array.tolist()
            for model_name, prediction_array in all_test_predictions.items()
        },
        "test_actuals": y_test.tolist(),
        "test_dates": [pd.Timestamp(item).strftime("%Y-%m-%d") for item in test_dates],
    }
    evaluation_report_path = save_evaluation_report(crop_name, evaluation_payload)

    return {
        "best_model_name": deployed_model_name,
        "forecast": deployed_artifacts["daily_forecast"],
        "dates": deployed_artifacts["daily_dates"],
        "weekly_forecast": deployed_artifacts["forecast"],
        "weekly_dates": deployed_artifacts["forecast_dates"],
        "metrics": final_metrics,
        "all_metrics": meta["all_metrics"],
        "rolling_origin_metrics": rolling_origin_metrics,
        "last_date": pd.Timestamp(meta["last_date"]),
        "test_actuals": y_test,
        "test_predicted": test_predicted,
        "test_dates": test_dates,
        "all_test_predictions": all_test_predictions,
        "evaluation_report_path": evaluation_report_path,
        "comparison": comparison_df,
    }


def _train_sarimax_candidate(model_name, y_train, y_test, x_train=None, x_test=None):
    predictions = np.full(len(y_test), np.nan, dtype=float)
    metrics = {"rmse": np.nan, "mae": np.nan, "mape_pct": np.nan}

    try:
        model = _fit_sarimax(y_train, exog=x_train)
        if model_name == "ARIMAX":
            predictions = np.asarray(model.forecast(steps=len(y_test), exog=x_test), dtype=float)
        else:
            predictions = np.asarray(model.forecast(steps=len(y_test)), dtype=float)
        metrics = compute_metrics(y_test, predictions)
    except Exception:
        LOGGER.warning("%s training failed; continuing with NaN metrics", model_name, exc_info=True)

    return {"predictions": predictions, "metrics": metrics}


def _train_standalone_lstm_candidate(y_train, y_test):
    predictions = np.full(len(y_test), np.nan, dtype=float)
    metrics = {"rmse": np.nan, "mae": np.nan, "mape_pct": np.nan}

    try:
        scaler = MinMaxScaler()
        train_scaled = scaler.fit_transform(np.asarray(y_train, dtype=float).reshape(-1, 1)).reshape(-1)
        x_seq, y_seq = _build_sequences(train_scaled, LSTM_WINDOW)
        if len(x_seq) < LSTM_MIN_SEQUENCES:
            LOGGER.warning(
                "Standalone LSTM skipped because only %d sequences are available", len(x_seq)
            )
            return {"predictions": predictions, "metrics": metrics}

        model = _build_lstm_model(LSTM_WINDOW)
        model.fit(
            x_seq,
            y_seq,
            epochs=LSTM_EPOCHS,
            batch_size=LSTM_BATCH_SIZE,
            validation_split=0.1 if len(x_seq) >= 50 else 0.0,
            callbacks=[EarlyStopping(patience=EARLY_STOP_PAT, restore_best_weights=True)],
            verbose=0,
        )
        predictions = _lstm_autoregressive_forecast(
            model=model,
            last_seq=train_scaled[-LSTM_WINDOW:],
            steps=len(y_test),
            scaler=scaler,
        )
        metrics = compute_metrics(y_test, predictions)
    except Exception:
        LOGGER.warning("Standalone_LSTM training failed; continuing with NaN metrics", exc_info=True)

    return {"predictions": predictions, "metrics": metrics}


def _train_hybrid_candidate(y_train, y_test, x_train, x_test):
    predictions = np.full(len(y_test), np.nan, dtype=float)
    metrics = {"rmse": np.nan, "mae": np.nan, "mape_pct": np.nan}

    try:
        arimax_model = _fit_sarimax(y_train, exog=x_train)
        arimax_predictions = np.asarray(
            arimax_model.forecast(steps=len(y_test), exog=x_test), dtype=float
        )
        residuals = np.asarray(y_train, dtype=float) - np.asarray(arimax_model.fittedvalues, dtype=float)
        scaler = MinMaxScaler()
        residuals_scaled = scaler.fit_transform(residuals.reshape(-1, 1)).reshape(-1)
        x_seq, y_seq = _build_sequences(residuals_scaled, LSTM_WINDOW)
        if len(x_seq) < LSTM_MIN_SEQUENCES:
            LOGGER.warning("Hybrid model skipped because only %d residual sequences are available", len(x_seq))
            return {"predictions": predictions, "metrics": metrics}

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
    except Exception:
        LOGGER.warning("Hybrid_ARIMAX_LSTM training failed; continuing with NaN metrics", exc_info=True)

    return {"predictions": predictions, "metrics": metrics}


def _train_tabular_candidate(y_train, y_test, tab_train, future_exog, future_dates, first_date, feature_columns):
    predictions = np.full(len(y_test), np.nan, dtype=float)
    metrics = {"rmse": np.nan, "mae": np.nan, "mape_pct": np.nan}

    try:
        model = _fit_tabular_regressor(tab_train, y_train)
        predictions = _recursive_tabular_forecast(
            model=model,
            history_prices=y_train,
            future_dates=future_dates,
            future_exog=future_exog,
            first_date=first_date,
            feature_columns=feature_columns,
        )
        metrics = compute_metrics(y_test, predictions)
    except Exception:
        LOGGER.warning("Tabular_GBM training failed; continuing with NaN metrics", exc_info=True)

    return {"predictions": predictions, "metrics": metrics}


def _fit_sarimax(y_values, exog=None):
    model = SARIMAX(
        endog=np.asarray(y_values, dtype=float),
        exog=None if exog is None else np.asarray(exog, dtype=float),
        order=ARIMAX_ORDER,
        enforce_stationarity=False,
        enforce_invertibility=False,
    )
    return model.fit(disp=False, maxiter=200)


def _fit_tabular_regressor(feature_frame: pd.DataFrame, y_values) -> GradientBoostingRegressor:
    model = GradientBoostingRegressor(
        random_state=42,
        n_estimators=400,
        learning_rate=0.03,
        max_depth=3,
        min_samples_leaf=2,
        subsample=0.9,
        loss="squared_error",
    )
    model.fit(feature_frame, np.asarray(y_values, dtype=float))
    return model


def _build_tabular_feature_frame(df: pd.DataFrame, exog_columns: list[str], first_date: pd.Timestamp) -> pd.DataFrame:
    feature_frame = pd.DataFrame(index=df.index)
    for column in TABULAR_PRICE_FEATURES:
        if column in df.columns:
            feature_frame[column] = df[column].astype(float)
    for column in exog_columns:
        feature_frame[column] = df[column].astype(float)

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


def _tabular_feature_row(history_prices, exog_row, future_date, first_date, feature_columns):
    history_series = pd.Series(history_prices, dtype=float)
    row = {}

    row["price_lag_1"] = float(history_series.iloc[-1])
    row["price_lag_4"] = float(history_series.iloc[-4]) if len(history_series) >= 4 else float(history_series.iloc[0])
    row["price_lag_13"] = float(history_series.iloc[-13]) if len(history_series) >= 13 else float(history_series.iloc[0])
    row["price_rmean_4"] = float(history_series.tail(4).mean())
    row["price_rmean_8"] = float(history_series.tail(8).mean())
    row["price_rmean_13"] = float(history_series.tail(13).mean())
    row["price_rstd_4"] = float(history_series.tail(4).std(ddof=1)) if len(history_series) >= 4 else 0.0
    row["price_rstd_8"] = float(history_series.tail(8).std(ddof=1)) if len(history_series) >= 8 else 0.0
    row["price_rstd_13"] = float(history_series.tail(13).std(ddof=1)) if len(history_series) >= 13 else 0.0
    if len(history_series) >= 2 and history_series.iloc[-2] != 0:
        row["price_pct_change"] = float((history_series.iloc[-1] - history_series.iloc[-2]) / history_series.iloc[-2])
    else:
        row["price_pct_change"] = 0.0

    exog_values = {}
    if hasattr(exog_row, "to_dict"):
        exog_values = {key: float(value) for key, value in exog_row.to_dict().items()}
    elif isinstance(exog_row, dict):
        exog_values = {key: float(value) for key, value in exog_row.items()}

    row.update(exog_values)

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


def _recursive_tabular_forecast(model, history_prices, future_dates, future_exog, first_date, feature_columns):
    predictions = []
    history = list(np.asarray(history_prices, dtype=float).reshape(-1))
    future_dates = pd.to_datetime(future_dates)

    if hasattr(future_exog, "reset_index"):
        future_exog = future_exog.reset_index(drop=True)

    for idx, future_date in enumerate(future_dates):
        exog_row = future_exog.iloc[idx] if hasattr(future_exog, "iloc") else future_exog[idx]
        feature_row = _tabular_feature_row(
            history_prices=history,
            exog_row=exog_row,
            future_date=future_date,
            first_date=first_date,
            feature_columns=feature_columns,
        )
        next_value = float(model.predict(feature_row)[0])
        predictions.append(next_value)
        history.append(next_value)

    return np.asarray(predictions, dtype=float)


def _run_rolling_origin_backtest(df, y, x_exog, exog_columns, tabular_df, tabular_columns, first_date):
    horizon = min(FORECAST_HORIZON, 13)
    min_train_size = max(52, len(df) // 2)
    split_starts = list(range(max(min_train_size, len(df) - (3 * horizon)), len(df) - horizon + 1, horizon))

    model_actuals = {name: [] for name in MODEL_NAMES}
    model_predictions = {name: [] for name in MODEL_NAMES}

    for split_index in split_starts:
        y_train, y_test = y[:split_index], y[split_index : split_index + horizon]
        x_train = x_exog.iloc[:split_index]
        x_test = x_exog.iloc[split_index : split_index + horizon]
        tab_train = tabular_df.iloc[:split_index]
        test_dates = pd.to_datetime(df.iloc[split_index : split_index + horizon][DATE_COL])

        if len(y_test) == 0:
            continue

        arima = _train_sarimax_candidate("ARIMA", y_train, y_test)
        arimax = _train_sarimax_candidate("ARIMAX", y_train, y_test, x_train, x_test)
        hybrid = _train_hybrid_candidate(y_train, y_test, x_train, x_test)
        tabular = _train_tabular_candidate(
            y_train=y_train,
            y_test=y_test,
            tab_train=tab_train,
            future_exog=x_test,
            future_dates=test_dates,
            first_date=first_date,
            feature_columns=tabular_columns,
        )

        for name, candidate in {
            "ARIMA": arima,
            "ARIMAX": arimax,
            "Hybrid_ARIMAX_LSTM": hybrid,
            "Tabular_GBM": tabular,
        }.items():
            model_actuals[name].extend(y_test.tolist())
            model_predictions[name].extend(candidate["predictions"].tolist())

    rolling_metrics = {}
    for name in MODEL_NAMES:
        if model_actuals[name] and model_predictions[name]:
            rolling_metrics[name] = compute_metrics(model_actuals[name], model_predictions[name])
        else:
            rolling_metrics[name] = {"rmse": np.nan, "mae": np.nan, "mape_pct": np.nan}
    return rolling_metrics


def _retrain_full_model(
    model_name,
    crop_name,
    y,
    x_exog,
    exog_columns,
    tabular_df,
    tabular_columns,
    first_date,
    last_date,
):
    artifact_paths = _artifact_paths(crop_name)

    if model_name == "ARIMA":
        arima_model = _fit_sarimax(y, exog=None)
        forecast = np.asarray(arima_model.forecast(steps=FORECAST_HORIZON), dtype=float)
        joblib.dump(arima_model, artifact_paths["arima"])
        _cleanup_stale_artifacts(crop_name, {"arima", "meta"})

    elif model_name == "ARIMAX":
        arimax_model = _fit_sarimax(y, exog=x_exog[exog_columns])
        future_exog = _tile_future_exog(x_exog.iloc[-1][exog_columns], FORECAST_HORIZON)
        forecast = np.asarray(arimax_model.forecast(steps=FORECAST_HORIZON, exog=future_exog), dtype=float)
        joblib.dump(arimax_model, artifact_paths["arimax"])
        _cleanup_stale_artifacts(crop_name, {"arimax", "meta"})

    elif model_name == "Hybrid_ARIMAX_LSTM":
        arimax_model = _fit_sarimax(y, exog=x_exog[exog_columns])
        residuals = np.asarray(y, dtype=float) - np.asarray(arimax_model.fittedvalues, dtype=float)
        scaler = MinMaxScaler()
        residuals_scaled = scaler.fit_transform(residuals.reshape(-1, 1)).reshape(-1)
        x_seq, y_seq = _build_sequences(residuals_scaled, LSTM_WINDOW)
        if len(x_seq) < LSTM_MIN_SEQUENCES:
            raise RuntimeError(
                f"Hybrid full retrain requires at least {LSTM_MIN_SEQUENCES} sequences; found {len(x_seq)}"
            )
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
        future_exog = _tile_future_exog(x_exog.iloc[-1][exog_columns], FORECAST_HORIZON)
        base_forecast = np.asarray(arimax_model.forecast(steps=FORECAST_HORIZON, exog=future_exog), dtype=float)
        residual_forecast = _lstm_autoregressive_forecast(
            model=lstm_model,
            last_seq=residuals_scaled[-LSTM_WINDOW:],
            steps=FORECAST_HORIZON,
            scaler=scaler,
        )
        forecast = base_forecast + residual_forecast
        joblib.dump(arimax_model, artifact_paths["arimax"])
        lstm_model.save(artifact_paths["lstm"])
        joblib.dump(scaler, artifact_paths["scaler"])
        _cleanup_stale_artifacts(crop_name, {"arimax", "lstm", "scaler", "meta"})

    elif model_name == "Standalone_LSTM":
        scaler = MinMaxScaler()
        price_scaled = scaler.fit_transform(np.asarray(y, dtype=float).reshape(-1, 1)).reshape(-1)
        x_seq, y_seq = _build_sequences(price_scaled, LSTM_WINDOW)
        if len(x_seq) < LSTM_MIN_SEQUENCES:
            raise RuntimeError(
                f"Standalone LSTM full retrain requires at least {LSTM_MIN_SEQUENCES} sequences; found {len(x_seq)}"
            )
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
        forecast = _lstm_autoregressive_forecast(
            model=lstm_model,
            last_seq=price_scaled[-LSTM_WINDOW:],
            steps=FORECAST_HORIZON,
            scaler=scaler,
        )
        lstm_model.save(artifact_paths["lstm"])
        joblib.dump(scaler, artifact_paths["price_scaler"])
        _cleanup_stale_artifacts(crop_name, {"lstm", "price_scaler", "meta"})

    elif model_name == "Tabular_GBM":
        gbm_model = _fit_tabular_regressor(tabular_df, y)
        future_exog = _tile_future_exog(x_exog.iloc[-1][exog_columns], FORECAST_HORIZON)
        future_dates = pd.date_range(
            start=pd.Timestamp(last_date) + pd.Timedelta(days=7),
            periods=FORECAST_HORIZON,
            freq="7D",
        )
        forecast = _recursive_tabular_forecast(
            model=gbm_model,
            history_prices=y,
            future_dates=future_dates,
            future_exog=future_exog,
            first_date=first_date,
            feature_columns=tabular_columns,
        )
        joblib.dump(gbm_model, artifact_paths["gbr"])
        _cleanup_stale_artifacts(crop_name, {"gbr", "meta"})

    else:
        raise ValueError(f"Unsupported model name: {model_name}")

    forecast_dates = pd.date_range(
        start=pd.Timestamp(last_date) + pd.Timedelta(days=7),
        periods=FORECAST_HORIZON,
        freq="7D",
    )
    daily_dates, daily_forecast = _interpolate_weekly_to_daily(
        last_date=last_date,
        last_actual=float(y[-1]),
        weekly_forecast=forecast,
    )

    return {
        "forecast": forecast,
        "forecast_dates": forecast_dates,
        "daily_forecast": daily_forecast,
        "daily_dates": daily_dates,
    }


def _interpolate_weekly_to_daily(last_date, last_actual, weekly_forecast):
    future_weekly_dates = pd.date_range(
        start=pd.Timestamp(last_date) + pd.Timedelta(days=7),
        periods=len(weekly_forecast),
        freq="7D",
    )
    anchor_series = pd.Series(
        data=[float(last_actual)] + np.asarray(weekly_forecast, dtype=float).tolist(),
        index=[pd.Timestamp(last_date)] + future_weekly_dates.tolist(),
    )
    daily_dates = pd.date_range(
        start=pd.Timestamp(last_date) + pd.Timedelta(days=1),
        periods=FORECAST_DAYS,
        freq="D",
    )
    interpolated = (
        anchor_series.reindex(anchor_series.index.union(daily_dates))
        .sort_index()
        .interpolate(method="time")
        .reindex(daily_dates)
        .ffill()
        .bfill()
    )
    return daily_dates, interpolated.to_numpy(dtype=float)


def _tile_future_exog(last_x_row, steps):
    values = np.asarray(last_x_row, dtype=float).reshape(1, -1)
    tiled = np.repeat(values, repeats=steps, axis=0)
    if hasattr(last_x_row, "index"):
        return pd.DataFrame(tiled, columns=list(last_x_row.index))
    return tiled


def _artifact_paths(crop_name):
    return {
        "arima": os.path.join(MODELS_DIR, f"{crop_name}_arima.pkl"),
        "arimax": os.path.join(MODELS_DIR, f"{crop_name}_arimax.pkl"),
        "lstm": os.path.join(MODELS_DIR, f"{crop_name}_lstm.keras"),
        "scaler": os.path.join(MODELS_DIR, f"{crop_name}_scaler.pkl"),
        "price_scaler": os.path.join(MODELS_DIR, f"{crop_name}_price_scaler.pkl"),
        "gbr": os.path.join(MODELS_DIR, f"{crop_name}_gbr.pkl"),
        "meta": os.path.join(MODELS_DIR, f"{crop_name}_meta.pkl"),
    }


def _cleanup_stale_artifacts(crop_name, keep_keys):
    for key, path in _artifact_paths(crop_name).items():
        if key in keep_keys:
            continue
        if os.path.exists(path):
            os.remove(path)
            LOGGER.info("Removed stale artifact %s", path)

