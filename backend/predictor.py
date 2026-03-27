"""
predictor.py
------------
Inference wrapper: loads saved ARIMAX + LSTM artifacts and produces
a 90-day forecast. Falls back to training if no saved model is found.
Also orchestrates output generation (CSVs, plots).
"""

import os
import logging

import numpy as np
import pandas as pd
import joblib

import tensorflow as tf
from tensorflow.keras.models import load_model

from config import (
    MODELS_DIR, DATE_COL, PRICE_COL,
    FORECAST_HORIZON, FORECAST_DAYS, LSTM_WINDOW,
)
from model import (
    _arimax_path, _lstm_path, _scaler_path, _meta_path,
    model_exists, train_hybrid, _lstm_autoregressive_forecast,
)
from visualizer import (
    plot_actual_vs_predicted, plot_all_models, plot_residuals,
    plot_feature_correlations, plot_forecast, plot_model_metrics_bar,
)
from output_generator import (
    save_predictions_csv, save_forecast_csv, save_model_comparison_csv,
)

logger = logging.getLogger(__name__)


def predict(crop_name: str, aligned_df: pd.DataFrame, force_retrain: bool = False) -> dict:
    """
    Produce a 90-day price forecast for *crop_name*.
    Trains if no model exists. Generates all output files.
    """
    # ------------------------------------------------------------------
    # Train or re-train
    # ------------------------------------------------------------------
    if force_retrain or not model_exists(crop_name):
        logger.info("[%s] Training model …", crop_name)
        result = train_hybrid(aligned_df, crop_name)
        _generate_outputs(crop_name, result, aligned_df)
        return result

    # ------------------------------------------------------------------
    # Load saved artifacts for inference
    # ------------------------------------------------------------------
    logger.info("[%s] Loading saved model …", crop_name)
    arimax_fit = joblib.load(_arimax_path(crop_name))
    scaler     = joblib.load(_scaler_path(crop_name))
    meta       = joblib.load(_meta_path(crop_name))

    last_date    = meta["last_date"]
    last_X_row   = meta["last_X_row"]
    exog_columns = meta["exog_columns"]
    metrics      = meta.get("hybrid_metrics", meta.get("metrics", {}))
    all_metrics  = meta.get("all_metrics", {})

    # ARIMAX forecast
    if exog_columns:
        future_exog = pd.DataFrame(
            np.tile(last_X_row, (FORECAST_HORIZON, 1)),
            columns=exog_columns,
        )
    else:
        future_exog = None

    arimax_fc = arimax_fit.forecast(steps=FORECAST_HORIZON, exog=future_exog).values

    # LSTM residual forecast
    lstm_path = _lstm_path(crop_name)
    if os.path.exists(lstm_path):
        lstm_model = load_model(lstm_path)
        y_series = aligned_df[PRICE_COL].values
        fitted   = arimax_fit.fittedvalues.values
        n = min(len(y_series), len(fitted))
        residuals = y_series[-n:] - fitted[-n:]
        scaled_res = scaler.transform(residuals.reshape(-1, 1))
        last_seq = scaled_res[-LSTM_WINDOW:].reshape(1, LSTM_WINDOW, 1)
        lstm_fc = _lstm_autoregressive_forecast(lstm_model, last_seq, FORECAST_HORIZON, scaler)
    else:
        lstm_fc = np.zeros(FORECAST_HORIZON)

    weekly_forecast = arimax_fc + lstm_fc

    # Interpolate to daily
    weekly_dates = pd.date_range(start=last_date + pd.Timedelta(weeks=1),
                                  periods=FORECAST_HORIZON, freq="W")
    weekly_series = pd.Series(weekly_forecast, index=weekly_dates)
    daily_dates = pd.date_range(start=last_date + pd.Timedelta(days=1),
                                 periods=FORECAST_DAYS, freq="D")
    daily_forecast = weekly_series.reindex(weekly_series.index.union(daily_dates)).interpolate(method="time")
    daily_forecast = daily_forecast.reindex(daily_dates).ffill().bfill().values

    return {
        "forecast":    daily_forecast,
        "dates":       daily_dates,
        "metrics":     metrics,
        "all_metrics": all_metrics,
        "last_date":   last_date,
    }


def _generate_outputs(crop_name: str, result: dict, aligned_df: pd.DataFrame):
    """Generate all CSV and plot outputs after training."""
    try:
        # Test-set outputs
        if "test_actuals" in result and "test_predicted" in result:
            test_act = result["test_actuals"]
            test_pred = result["test_predicted"]
            test_dates = result.get("test_dates", range(len(test_act)))

            save_predictions_csv(crop_name, test_act, test_pred, test_dates)
            plot_actual_vs_predicted(crop_name, test_act, test_pred, test_dates)
            plot_residuals(crop_name, test_act, test_pred, test_dates)

        # Forecast outputs
        save_forecast_csv(crop_name, result["forecast"], result["dates"])
        plot_forecast(crop_name, result["forecast"], result["dates"])

        # Feature correlations
        plot_feature_correlations(crop_name, aligned_df)

        # Model comparison
        if "all_metrics" in result:
            save_model_comparison_csv(crop_name, result["all_metrics"])
            plot_model_metrics_bar(crop_name, result["all_metrics"])

            # All-models test prediction plot
            if "test_actuals" in result:
                from evaluation import save_evaluation_report
                import json
                eval_path = os.path.join("outputs", "metrics", f"{crop_name}_evaluation.json")
                if os.path.exists(eval_path):
                    with open(eval_path) as f:
                        eval_data = json.load(f)
                    test_preds = eval_data.get("test_predictions", {})
                    if test_preds:
                        pred_arrays = {}
                        for k, v in test_preds.items():
                            arr = np.array(v)
                            if len(arr) == len(result["test_actuals"]):
                                pred_arrays[k] = arr
                        if pred_arrays:
                            plot_all_models(crop_name, result["test_actuals"],
                                          pred_arrays, result["test_dates"])

    except Exception as e:
        logger.warning("[%s] Output generation error (non-fatal): %s", crop_name, e)
