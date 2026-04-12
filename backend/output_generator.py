from __future__ import annotations

import logging
import os

import numpy as np
import pandas as pd

from config import OUTPUTS_DIR


LOGGER = logging.getLogger(__name__)


def save_predictions_csv(crop_name, dates, actual, predicted, all_predictions=None):
    output_path = os.path.join(OUTPUTS_DIR, f"{crop_name}_test_predictions.csv")
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(dates),
            "actual": np.asarray(actual, dtype=float),
            "predicted": np.asarray(predicted, dtype=float),
        }
    )
    if all_predictions:
        for model_name, values in all_predictions.items():
            frame[f"pred_{model_name}"] = np.asarray(values, dtype=float)
    frame.to_csv(output_path, index=False)
    LOGGER.info("Saved test predictions to %s", output_path)
    return output_path


def save_forecast_csv(crop_name, dates, forecast, spike_flags=None, spike_scores=None):
    output_path = os.path.join(OUTPUTS_DIR, f"{crop_name}_forecast.csv")
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(dates),
            "forecast": np.asarray(forecast, dtype=float),
        }
    )
    if spike_flags is not None:
        frame["spike_flag"] = np.asarray(spike_flags, dtype=int)
    if spike_scores is not None:
        frame["spike_score"] = np.asarray(spike_scores, dtype=float)
    frame.to_csv(output_path, index=False)
    LOGGER.info("Saved forecast to %s", output_path)
    return output_path


def save_model_comparison_csv(crop_name, comparison_df):
    output_path = os.path.join(OUTPUTS_DIR, f"{crop_name}_model_comparison.csv")
    comparison_df.to_csv(output_path, index=False)
    LOGGER.info("Saved model comparison to %s", output_path)
    return output_path

