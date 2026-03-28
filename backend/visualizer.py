from __future__ import annotations

import logging
import os

os.environ.setdefault(
    "MPLCONFIGDIR",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), ".mplconfig"),
)
os.makedirs(os.environ["MPLCONFIGDIR"], exist_ok=True)

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from config import PLOTS_DIR, PRICE_COL


LOGGER = logging.getLogger(__name__)


def plot_actual_vs_predicted(crop_name, dates, actual, predicted):
    path = os.path.join(PLOTS_DIR, f"{crop_name}_actual_vs_predicted.png")
    plt.figure(figsize=(12, 5))
    plt.plot(pd.to_datetime(dates), actual, label="Actual", linewidth=2)
    plt.plot(pd.to_datetime(dates), predicted, label="Predicted", linewidth=2)
    plt.title(f"{crop_name.title()} actual vs predicted")
    plt.xlabel("Date")
    plt.ylabel("Price")
    plt.legend()
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()
    LOGGER.info("Saved plot %s", path)
    return path


def plot_residuals(crop_name, dates, actual, predicted):
    path = os.path.join(PLOTS_DIR, f"{crop_name}_residuals.png")
    residuals = np.asarray(actual, dtype=float) - np.asarray(predicted, dtype=float)
    plt.figure(figsize=(12, 5))
    plt.plot(pd.to_datetime(dates), residuals, color="tab:red", linewidth=1.5)
    plt.axhline(0, color="black", linestyle="--", linewidth=1)
    plt.title(f"{crop_name.title()} residuals")
    plt.xlabel("Date")
    plt.ylabel("Actual - Predicted")
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()
    LOGGER.info("Saved plot %s", path)
    return path


def plot_forecast(crop_name, history_dates, history_values, forecast_dates, forecast_values):
    path = os.path.join(PLOTS_DIR, f"{crop_name}_forecast.png")
    plt.figure(figsize=(12, 5))
    plt.plot(pd.to_datetime(history_dates), history_values, label="Historical", linewidth=2)
    plt.plot(pd.to_datetime(forecast_dates), forecast_values, label="Forecast", linewidth=2)
    plt.title(f"{crop_name.title()} forecast")
    plt.xlabel("Date")
    plt.ylabel("Price")
    plt.legend()
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()
    LOGGER.info("Saved plot %s", path)
    return path


def plot_feature_correlations(crop_name, df):
    path = os.path.join(PLOTS_DIR, f"{crop_name}_feature_correlations.png")
    corr = df.select_dtypes(include=[np.number]).corr()
    plt.figure(figsize=(12, 10))
    plt.imshow(corr, cmap="coolwarm", aspect="auto", vmin=-1, vmax=1)
    plt.colorbar(label="Correlation")
    ticks = np.arange(len(corr.columns))
    plt.xticks(ticks, corr.columns, rotation=90)
    plt.yticks(ticks, corr.columns)
    plt.title(f"{crop_name.title()} feature correlations")
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()
    LOGGER.info("Saved plot %s", path)
    return path


def plot_model_metrics_comparison(crop_name, comparison_df):
    path = os.path.join(PLOTS_DIR, f"{crop_name}_model_metrics_comparison.png")
    plt.figure(figsize=(10, 5))
    plt.bar(comparison_df["model_name"], comparison_df["rmse"], color="tab:blue")
    plt.title(f"{crop_name.title()} model RMSE comparison")
    plt.xlabel("Model")
    plt.ylabel("RMSE")
    plt.xticks(rotation=20)
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()
    LOGGER.info("Saved plot %s", path)
    return path


def plot_all_model_comparison(crop_name, dates, actual, all_predictions):
    path = os.path.join(PLOTS_DIR, f"{crop_name}_all_model_comparison.png")
    plt.figure(figsize=(12, 6))
    plt.plot(pd.to_datetime(dates), actual, label="Actual", linewidth=2.5, color="black")
    for model_name, values in all_predictions.items():
        values_array = np.asarray(values, dtype=float)
        if not np.isfinite(values_array).any():
            continue
        plt.plot(pd.to_datetime(dates), values_array, label=model_name, linewidth=1.75)
    plt.title(f"{crop_name.title()} all-model comparison")
    plt.xlabel("Date")
    plt.ylabel("Price")
    plt.legend()
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()
    LOGGER.info("Saved plot %s", path)
    return path
