"""
evaluation.py
-------------
Metrics computation and model comparison utilities.
"""

import json
import os
import logging

import numpy as np
import pandas as pd

from config import METRICS_DIR

logger = logging.getLogger(__name__)


def compute_metrics(actual: np.ndarray, predicted: np.ndarray) -> dict:
    """Compute RMSE, MAE, and MAPE between actual and predicted arrays."""
    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)

    # Remove any NaN pairs
    mask = ~(np.isnan(actual) | np.isnan(predicted))
    actual = actual[mask]
    predicted = predicted[mask]

    if len(actual) == 0:
        return {"rmse": float("nan"), "mae": float("nan"), "mape_pct": float("nan")}

    errors = actual - predicted
    mae = float(np.mean(np.abs(errors)))
    rmse = float(np.sqrt(np.mean(errors ** 2)))

    # MAPE: avoid division by zero
    nonzero = actual != 0
    if nonzero.sum() > 0:
        mape = float(np.mean(np.abs(errors[nonzero] / actual[nonzero])) * 100)
    else:
        mape = float("nan")

    return {
        "rmse":     round(rmse, 2),
        "mae":      round(mae, 2),
        "mape_pct": round(mape, 2),
    }


def compare_models(results: dict) -> pd.DataFrame:
    """
    Create a comparison DataFrame from a dict of {model_name: metrics_dict}.

    Example input:
        {"ARIMA": {"rmse":10, "mae":8, "mape_pct":5}, "Hybrid": {...}}
    """
    rows = []
    for model_name, metrics in results.items():
        rows.append({"model": model_name, **metrics})
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("rmse").reset_index(drop=True)
    return df


def save_evaluation_report(crop_name: str, results: dict) -> str:
    """Save model comparison metrics to a JSON file. Returns path."""
    out_path = os.path.join(METRICS_DIR, f"{crop_name}_evaluation.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    logger.info("Evaluation report saved → %s", out_path)
    return out_path
