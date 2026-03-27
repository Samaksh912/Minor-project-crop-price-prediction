"""
output_generator.py
-------------------
Generate output CSV files: prediction CSVs (actual vs predicted)
and 90-day forecast CSVs.
"""

import os
import logging

import numpy as np
import pandas as pd

from config import OUTPUTS_DIR

logger = logging.getLogger(__name__)


def save_predictions_csv(crop_name: str, actual: np.ndarray,
                          predicted: np.ndarray, dates) -> str:
    """Save actual vs predicted values (test set) to CSV."""
    df = pd.DataFrame({
        "date":      dates,
        "actual":    np.round(actual, 2),
        "predicted": np.round(predicted, 2),
        "error":     np.round(actual - predicted, 2),
        "abs_error": np.round(np.abs(actual - predicted), 2),
        "pct_error": np.round(
            np.abs((actual - predicted) / np.where(actual != 0, actual, 1)) * 100, 2
        ),
    })
    path = os.path.join(OUTPUTS_DIR, f"{crop_name}_test_predictions.csv")
    df.to_csv(path, index=False)
    logger.info("Test predictions CSV → %s", path)
    return path


def save_forecast_csv(crop_name: str, forecast: np.ndarray, dates) -> str:
    """Save 90-day forecast to CSV."""
    df = pd.DataFrame({
        "date":                 dates,
        "predicted_modal_price": np.round(forecast, 2),
    })
    path = os.path.join(OUTPUTS_DIR, f"{crop_name}_90day_forecast.csv")
    df.to_csv(path, index=False)
    logger.info("Forecast CSV → %s", path)
    return path


def save_model_comparison_csv(crop_name: str, all_metrics: dict) -> str:
    """Save model comparison metrics to CSV."""
    rows = []
    for model_name, metrics in all_metrics.items():
        rows.append({"model": model_name, **metrics})
    df = pd.DataFrame(rows).sort_values("rmse")
    path = os.path.join(OUTPUTS_DIR, f"{crop_name}_model_comparison.csv")
    df.to_csv(path, index=False)
    logger.info("Model comparison CSV → %s", path)
    return path
