"""
model.py
--------
Train the hybrid ARIMAX-LSTM model with proper train/test split,
baseline comparisons, and evaluation on unseen test data.
"""

import os
import logging
import warnings

import numpy as np
import pandas as pd
import joblib

from statsmodels.tsa.statespace.sarimax import SARIMAX
from sklearn.preprocessing import MinMaxScaler

import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Input, LSTM, Dense, Dropout
from tensorflow.keras.callbacks import EarlyStopping

from config import (
    MODELS_DIR, DATE_COL, PRICE_COL,
    FORECAST_HORIZON, FORECAST_DAYS, LSTM_WINDOW,
    ARIMAX_ORDER, LSTM_UNITS, LSTM_DROPOUT,
    LSTM_EPOCHS, LSTM_BATCH_SIZE, EARLY_STOP_PAT,
    TRAIN_SPLIT_RATIO, LSTM_MIN_SEQUENCES,
)
from evaluation import compute_metrics, compare_models, save_evaluation_report

logger = logging.getLogger(__name__)
warnings.filterwarnings("ignore")


# ---------------------------------------------------------------------------
# Artifact paths
# ---------------------------------------------------------------------------

def _arimax_path(crop):     return os.path.join(MODELS_DIR, f"{crop}_arimax.pkl")
def _lstm_path(crop):       return os.path.join(MODELS_DIR, f"{crop}_lstm.keras")
def _scaler_path(crop):     return os.path.join(MODELS_DIR, f"{crop}_scaler.pkl")
def _meta_path(crop):       return os.path.join(MODELS_DIR, f"{crop}_meta.pkl")

def model_exists(crop_name: str) -> bool:
    return all(os.path.exists(p) for p in [
        _arimax_path(crop_name), _lstm_path(crop_name),
        _scaler_path(crop_name), _meta_path(crop_name),
    ])


# ---------------------------------------------------------------------------
# Helper: build LSTM sequences
# ---------------------------------------------------------------------------

def _build_sequences(data: np.ndarray, window: int):
    """Build supervised-learning sequences from 1-D array."""
    X, y = [], []
    for i in range(window, len(data)):
        X.append(data[i - window : i])
        y.append(data[i])
    return np.array(X), np.array(y)


def _lstm_autoregressive_forecast(model, last_seq, steps, scaler):
    """Autoregressively forecast `steps` values from the LSTM."""
    seq = last_seq.copy()
    preds = []
    for _ in range(steps):
        p = model.predict(seq, verbose=0)[0, 0]
        preds.append(p)
        seq = np.roll(seq, -1, axis=1)
        seq[0, -1, 0] = p
    return scaler.inverse_transform(np.array(preds).reshape(-1, 1)).flatten()


# ---------------------------------------------------------------------------
# Baseline: ARIMA (no exogenous)
# ---------------------------------------------------------------------------

def _train_arima_baseline(y_train, y_test, order):
    """Fit ARIMA on train, forecast on test horizon."""
    try:
        model = SARIMAX(y_train, order=order,
                        enforce_stationarity=False, enforce_invertibility=False)
        fit = model.fit(disp=False, maxiter=200)
        forecast = np.asarray(fit.forecast(steps=len(y_test)))
        return forecast, compute_metrics(y_test, forecast)
    except Exception as e:
        logger.warning("ARIMA baseline failed: %s", e)
        return np.full(len(y_test), np.nan), {"rmse": float("nan"), "mae": float("nan"), "mape_pct": float("nan")}


# ---------------------------------------------------------------------------
# Baseline: ARIMAX (with exogenous, no LSTM)
# ---------------------------------------------------------------------------

def _train_arimax_baseline(y_train, X_train, y_test, X_test, order):
    """Fit ARIMAX on train set, forecast on test set."""
    try:
        exog_tr = X_train if not X_train.empty else None
        model = SARIMAX(y_train, exog=exog_tr, order=order,
                        enforce_stationarity=False, enforce_invertibility=False)
        fit = model.fit(disp=False, maxiter=200)
        exog_te = X_test if not X_test.empty else None
        forecast = np.asarray(fit.forecast(steps=len(y_test), exog=exog_te))
        return fit, forecast, compute_metrics(y_test, forecast)
    except Exception as e:
        logger.warning("ARIMAX baseline failed: %s", e)
        return None, np.full(len(y_test), np.nan), {"rmse": float("nan"), "mae": float("nan"), "mape_pct": float("nan")}


# ---------------------------------------------------------------------------
# Baseline: Standalone LSTM on price
# ---------------------------------------------------------------------------

def _train_standalone_lstm(y_train, y_test, window):
    """Train LSTM directly on price (no ARIMAX component)."""
    try:
        scaler = MinMaxScaler()
        scaled = scaler.fit_transform(y_train.reshape(-1, 1))
        X_seq, y_seq = _build_sequences(scaled, window)
        if len(X_seq) < LSTM_MIN_SEQUENCES:
            raise ValueError(
                f"Not enough sequences ({len(X_seq)}) for standalone LSTM "
                f"(minimum: {LSTM_MIN_SEQUENCES}). Skipping."
            )

        model = Sequential([
            Input(shape=(window, 1)),
            LSTM(LSTM_UNITS, return_sequences=True),
            Dropout(LSTM_DROPOUT),
            LSTM(LSTM_UNITS),
            Dropout(LSTM_DROPOUT),
            Dense(1),
        ])
        model.compile(optimizer="adam", loss="mse")
        model.fit(X_seq, y_seq, epochs=LSTM_EPOCHS, batch_size=LSTM_BATCH_SIZE,
                  verbose=0, callbacks=[EarlyStopping(monitor="loss", patience=EARLY_STOP_PAT, restore_best_weights=True)])

        # Forecast test set autoregressively
        last_seq = scaled[-window:].reshape(1, window, 1)
        forecast = _lstm_autoregressive_forecast(model, last_seq, len(y_test), scaler)
        return forecast, compute_metrics(y_test, forecast)
    except Exception as e:
        logger.warning("Standalone LSTM baseline failed: %s", e)
        return np.full(len(y_test), np.nan), {"rmse": float("nan"), "mae": float("nan"), "mape_pct": float("nan")}


# ---------------------------------------------------------------------------
# Main: Hybrid ARIMAX + LSTM training with full evaluation
# ---------------------------------------------------------------------------

def train_hybrid(aligned_df: pd.DataFrame, crop_name: str) -> dict:
    """
    Train the hybrid ARIMAX + LSTM model with:
    - 80/20 time-series train/test split (NO shuffling)
    - Baseline comparisons (ARIMA, ARIMAX, standalone LSTM)
    - Test-set evaluation on truly unseen data
    - 90-day forward forecast from last date
    """
    logger.info("[%s] Starting hybrid model training …", crop_name)

    # ==================================================================
    # 1. Prepare data
    # ==================================================================
    y = aligned_df[PRICE_COL].values.copy()
    dates = aligned_df[DATE_COL].values.copy()
    X = aligned_df.drop(columns=[DATE_COL, PRICE_COL], errors="ignore")
    X = X.ffill().bfill().fillna(0)

    # ==================================================================
    # 2. Time-series train/test split (strictly chronological)
    # ==================================================================
    split_idx = int(len(y) * TRAIN_SPLIT_RATIO)
    y_train, y_test = y[:split_idx], y[split_idx:]
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    dates_test = dates[split_idx:]

    logger.info("[%s] Split: %d train, %d test (unseen).", crop_name, len(y_train), len(y_test))

    # ==================================================================
    # 3. Baselines — ARIMA, ARIMAX, standalone LSTM
    # ==================================================================
    logger.info("[%s] Training baseline: ARIMA …", crop_name)
    arima_forecast, arima_metrics = _train_arima_baseline(y_train, y_test, ARIMAX_ORDER)

    logger.info("[%s] Training baseline: ARIMAX …", crop_name)
    arimax_fit, arimax_test_fc, arimax_metrics = _train_arimax_baseline(
        y_train, X_train, y_test, X_test, ARIMAX_ORDER
    )

    logger.info("[%s] Training baseline: Standalone LSTM …", crop_name)
    lstm_only_fc, lstm_only_metrics = _train_standalone_lstm(y_train, y_test, LSTM_WINDOW)

    # ==================================================================
    # 4. HYBRID: ARIMAX + LSTM(residuals) on TRAIN set
    # ==================================================================
    logger.info("[%s] Fitting ARIMAX (hybrid) on train set …", crop_name)
    exog_tr = X_train if not X_train.empty else None
    arimax_model = SARIMAX(y_train, exog=exog_tr, order=ARIMAX_ORDER,
                           enforce_stationarity=False, enforce_invertibility=False)
    arimax_hybrid_fit = arimax_model.fit(disp=False, maxiter=200)

    # Residuals on the training set
    fitted_train = arimax_hybrid_fit.fittedvalues.values
    residuals_train = y_train - fitted_train

    # Train LSTM on residuals
    res_scaler = MinMaxScaler()
    scaled_res = res_scaler.fit_transform(residuals_train.reshape(-1, 1))
    X_seq, y_seq = _build_sequences(scaled_res, LSTM_WINDOW)

    lstm_model = None
    if len(X_seq) >= LSTM_MIN_SEQUENCES:
        logger.info("[%s] Training LSTM on residuals (%d sequences) …", crop_name, len(X_seq))
        lstm_model = Sequential([
            Input(shape=(LSTM_WINDOW, 1)),
            LSTM(LSTM_UNITS, return_sequences=True),
            Dropout(LSTM_DROPOUT),
            LSTM(LSTM_UNITS),
            Dropout(LSTM_DROPOUT),
            Dense(1),
        ])
        lstm_model.compile(optimizer="adam", loss="mse")
        lstm_model.fit(
            X_seq, y_seq,
            epochs=LSTM_EPOCHS,
            batch_size=LSTM_BATCH_SIZE,
            verbose=0,
            callbacks=[EarlyStopping(monitor="loss", patience=EARLY_STOP_PAT, restore_best_weights=True)],
        )
    else:
        logger.warning(
            "[%s] Only %d residual sequences (need %d) — Hybrid falls back to pure ARIMAX, "
            "which is the better model for this dataset size.",
            crop_name, len(X_seq), LSTM_MIN_SEQUENCES,
        )

    # ==================================================================
    # 5. Evaluate HYBRID on TEST set (unseen data)
    # ==================================================================
    # ARIMAX forecast on test period
    exog_te = X_test if not X_test.empty else None
    hybrid_arimax_fc = arimax_hybrid_fit.forecast(steps=len(y_test), exog=exog_te).values

    # LSTM residual forecast on test period
    if lstm_model is not None:
        last_res_seq = scaled_res[-LSTM_WINDOW:].reshape(1, LSTM_WINDOW, 1)
        hybrid_lstm_fc = _lstm_autoregressive_forecast(lstm_model, last_res_seq, len(y_test), res_scaler)
    else:
        hybrid_lstm_fc = np.zeros(len(y_test))

    hybrid_test_fc = hybrid_arimax_fc + hybrid_lstm_fc
    hybrid_metrics = compute_metrics(y_test, hybrid_test_fc)

    logger.info("[%s] Test metrics — Hybrid: %s", crop_name, hybrid_metrics)

    # ==================================================================
    # 6. Model comparison
    # ==================================================================
    all_results = {
        "ARIMA":           arima_metrics,
        "ARIMAX":          arimax_metrics,
        "Standalone_LSTM": lstm_only_metrics,
        "Hybrid_ARIMAX_LSTM": hybrid_metrics,
    }
    comparison = compare_models(all_results)
    logger.info("[%s] Model comparison:\n%s", crop_name, comparison.to_string(index=False))

    # ==================================================================
    # 7. Re-train HYBRID on FULL dataset for production forecasting
    # ==================================================================
    logger.info("[%s] Re-training hybrid on FULL dataset for production …", crop_name)
    exog_full = X if not X.empty else None
    arimax_prod = SARIMAX(y, exog=exog_full, order=ARIMAX_ORDER,
                          enforce_stationarity=False, enforce_invertibility=False)
    arimax_prod_fit = arimax_prod.fit(disp=False, maxiter=200)

    # LSTM on full residuals
    fitted_full = arimax_prod_fit.fittedvalues.values
    residuals_full = y - fitted_full
    prod_scaler = MinMaxScaler()
    scaled_res_full = prod_scaler.fit_transform(residuals_full.reshape(-1, 1))
    X_full_seq, y_full_seq = _build_sequences(scaled_res_full, LSTM_WINDOW)

    lstm_prod = None
    if len(X_full_seq) >= LSTM_MIN_SEQUENCES:
        lstm_prod = Sequential([
            Input(shape=(LSTM_WINDOW, 1)),
            LSTM(LSTM_UNITS, return_sequences=True),
            Dropout(LSTM_DROPOUT),
            LSTM(LSTM_UNITS),
            Dropout(LSTM_DROPOUT),
            Dense(1),
        ])
        lstm_prod.compile(optimizer="adam", loss="mse")
        lstm_prod.fit(
            X_full_seq, y_full_seq,
            epochs=LSTM_EPOCHS,
            batch_size=LSTM_BATCH_SIZE,
            verbose=0,
            callbacks=[EarlyStopping(monitor="loss", patience=EARLY_STOP_PAT, restore_best_weights=True)],
        )

    # ==================================================================
    # 8. Generate 90-day forecast (weekly → interpolate to daily)
    # ==================================================================
    last_date = pd.Timestamp(dates[-1])
    last_X_row = X.iloc[-1].values

    # Future exogenous (repeat last known row)
    if not X.empty:
        future_exog = pd.DataFrame(
            np.tile(last_X_row, (FORECAST_HORIZON, 1)),
            columns=X.columns,
        )
    else:
        future_exog = None

    arimax_fc = arimax_prod_fit.forecast(steps=FORECAST_HORIZON, exog=future_exog).values

    if lstm_prod is not None:
        last_seq = scaled_res_full[-LSTM_WINDOW:].reshape(1, LSTM_WINDOW, 1)
        lstm_fc = _lstm_autoregressive_forecast(lstm_prod, last_seq, FORECAST_HORIZON, prod_scaler)
    else:
        lstm_fc = np.zeros(FORECAST_HORIZON)

    weekly_forecast = arimax_fc + lstm_fc

    # Interpolate weekly forecast to daily (90 days)
    weekly_dates = pd.date_range(start=last_date + pd.Timedelta(weeks=1),
                                  periods=FORECAST_HORIZON, freq="W")
    weekly_series = pd.Series(weekly_forecast, index=weekly_dates)
    daily_dates = pd.date_range(start=last_date + pd.Timedelta(days=1),
                                 periods=FORECAST_DAYS, freq="D")
    daily_forecast = weekly_series.reindex(weekly_series.index.union(daily_dates)).interpolate(method="time")
    daily_forecast = daily_forecast.reindex(daily_dates).ffill().bfill().values

    # ==================================================================
    # 9. Save artifacts
    # ==================================================================
    joblib.dump(arimax_prod_fit, _arimax_path(crop_name))
    joblib.dump(prod_scaler, _scaler_path(crop_name))
    joblib.dump({
        "last_date":      last_date,
        "last_X_row":     last_X_row,
        "exog_columns":   list(X.columns),
        "hybrid_metrics": hybrid_metrics,
        "all_metrics":    all_results,
        "train_size":     len(y_train),
        "test_size":      len(y_test),
        "total_size":     len(y),
    }, _meta_path(crop_name))

    if lstm_prod is not None:
        lstm_prod.save(_lstm_path(crop_name))
    else:
        # Remove any stale LSTM artifact so inference doesn't accidentally load it
        import pathlib
        stale = pathlib.Path(_lstm_path(crop_name))
        if stale.exists():
            stale.unlink()
            logger.info("[%s] Removed stale LSTM artifact (dataset too small).", crop_name)

    # Save evaluation report
    save_evaluation_report(crop_name, {
        "crop": crop_name,
        "train_size": len(y_train),
        "test_size": len(y_test),
        "model_comparison": all_results,
        "best_model": comparison.iloc[0]["model"] if not comparison.empty else "N/A",
        "test_actuals": y_test.tolist(),
        "test_predictions": {
            "ARIMA": arima_forecast.tolist(),
            "ARIMAX": arimax_test_fc.tolist(),
            "Standalone_LSTM": lstm_only_fc.tolist(),
            "Hybrid": hybrid_test_fc.tolist(),
        },
        "test_dates": [str(d) for d in dates_test],
    })

    logger.info("[%s] All artifacts saved to %s", crop_name, MODELS_DIR)

    return {
        "forecast":       daily_forecast,
        "dates":          daily_dates,
        "metrics":        hybrid_metrics,
        "all_metrics":    all_results,
        "last_date":      last_date,
        "test_actuals":   y_test,
        "test_predicted": hybrid_test_fc,
        "test_dates":     dates_test,
    }
