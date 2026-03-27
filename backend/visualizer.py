"""
visualizer.py
-------------
Generate matplotlib plots for model evaluation and analysis.
All plots are saved to backend/outputs/plots/.
"""

import os
import logging

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from config import PLOTS_DIR, PRICE_COL, DATE_COL

logger = logging.getLogger(__name__)

# Style
plt.style.use("seaborn-v0_8-whitegrid")
COLORS = {
    "actual":  "#2196F3",
    "hybrid":  "#FF5722",
    "arima":   "#9C27B0",
    "arimax":  "#4CAF50",
    "lstm":    "#FF9800",
}


def plot_actual_vs_predicted(crop_name: str, actual: np.ndarray,
                              predicted: np.ndarray, dates, model_name: str = "Hybrid") -> str:
    """Plot actual vs predicted prices. Returns saved path."""
    fig, ax = plt.subplots(figsize=(14, 6))
    ax.plot(dates, actual, label="Actual", color=COLORS["actual"], linewidth=2)
    ax.plot(dates, predicted, label=f"Predicted ({model_name})",
            color=COLORS["hybrid"], linewidth=2, linestyle="--")
    ax.set_title(f"{crop_name.title()} — Actual vs Predicted (Test Set)", fontsize=14, fontweight="bold")
    ax.set_xlabel("Date")
    ax.set_ylabel("Price (Rs./Quintal)")
    ax.legend(fontsize=11)
    ax.tick_params(axis="x", rotation=30)
    fig.tight_layout()
    path = os.path.join(PLOTS_DIR, f"{crop_name}_actual_vs_predicted.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Plot saved → %s", path)
    return path


def plot_all_models(crop_name: str, actual: np.ndarray, predictions: dict, dates) -> str:
    """Plot actual vs all model predictions on the test set."""
    fig, ax = plt.subplots(figsize=(14, 6))
    ax.plot(dates, actual, label="Actual", color=COLORS["actual"], linewidth=2.5)

    style_map = {
        "ARIMA": ("arima", "--"),
        "ARIMAX": ("arimax", "-."),
        "Standalone_LSTM": ("lstm", ":"),
        "Hybrid": ("hybrid", "-"),
    }
    for model_name, pred in predictions.items():
        color_key, ls = style_map.get(model_name, ("hybrid", "-"))
        ax.plot(dates, pred, label=model_name, color=COLORS.get(color_key, "#333"),
                linewidth=1.8, linestyle=ls, alpha=0.85)

    ax.set_title(f"{crop_name.title()} — Model Comparison (Test Set)", fontsize=14, fontweight="bold")
    ax.set_xlabel("Date")
    ax.set_ylabel("Price (Rs./Quintal)")
    ax.legend(fontsize=10)
    ax.tick_params(axis="x", rotation=30)
    fig.tight_layout()
    path = os.path.join(PLOTS_DIR, f"{crop_name}_model_comparison.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Plot saved → %s", path)
    return path


def plot_residuals(crop_name: str, actual: np.ndarray, predicted: np.ndarray, dates) -> str:
    """Plot residuals (actual − predicted)."""
    residuals = actual - predicted
    fig, axes = plt.subplots(2, 1, figsize=(14, 8), gridspec_kw={"height_ratios": [2, 1]})

    # Residual line
    axes[0].plot(dates, residuals, color="#E91E63", linewidth=1.5, alpha=0.8)
    axes[0].axhline(y=0, color="gray", linestyle="--", linewidth=1)
    axes[0].fill_between(dates, residuals, alpha=0.15, color="#E91E63")
    axes[0].set_title(f"{crop_name.title()} — Residuals (Actual − Predicted)", fontsize=14, fontweight="bold")
    axes[0].set_ylabel("Residual")

    # Residual histogram
    axes[1].hist(residuals, bins=25, color="#E91E63", alpha=0.7, edgecolor="white")
    axes[1].set_xlabel("Residual Value")
    axes[1].set_ylabel("Frequency")
    axes[1].set_title("Residual Distribution", fontsize=12)

    fig.tight_layout()
    path = os.path.join(PLOTS_DIR, f"{crop_name}_residuals.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Plot saved → %s", path)
    return path


def plot_feature_correlations(crop_name: str, df: pd.DataFrame) -> str:
    """Plot correlation heatmap of features vs price."""
    num_df = df.select_dtypes(include=[np.number])
    if num_df.shape[1] < 2:
        logger.warning("Not enough numeric columns for correlation plot.")
        return ""

    # Limit to top 15 correlated features for readability
    if PRICE_COL in num_df.columns:
        corrs = num_df.corr()[PRICE_COL].drop(PRICE_COL, errors="ignore").abs().sort_values(ascending=False)
        top_features = corrs.head(15).index.tolist()
        plot_cols = [PRICE_COL] + top_features
        num_df = num_df[plot_cols]

    corr = num_df.corr()
    fig, ax = plt.subplots(figsize=(12, 10))
    im = ax.imshow(corr.values, aspect="auto", cmap="RdYlBu_r", vmin=-1, vmax=1)
    ax.set_xticks(range(len(corr.columns)))
    ax.set_yticks(range(len(corr.columns)))
    ax.set_xticklabels(corr.columns, rotation=45, ha="right", fontsize=8)
    ax.set_yticklabels(corr.columns, fontsize=8)
    fig.colorbar(im, ax=ax, shrink=0.8)
    ax.set_title(f"{crop_name.title()} — Feature Correlations", fontsize=14, fontweight="bold")
    fig.tight_layout()
    path = os.path.join(PLOTS_DIR, f"{crop_name}_correlations.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Plot saved → %s", path)
    return path


def plot_forecast(crop_name: str, forecast: np.ndarray, dates) -> str:
    """Plot the 90-day forward forecast."""
    fig, ax = plt.subplots(figsize=(14, 6))
    ax.plot(dates, forecast, color=COLORS["hybrid"], linewidth=2, marker="o", markersize=2)
    ax.fill_between(dates, forecast * 0.95, forecast * 1.05, alpha=0.15, color=COLORS["hybrid"])
    ax.set_title(f"{crop_name.title()} — 90-Day Price Forecast", fontsize=14, fontweight="bold")
    ax.set_xlabel("Date")
    ax.set_ylabel("Predicted Price (Rs./Quintal)")
    ax.tick_params(axis="x", rotation=30)
    fig.tight_layout()
    path = os.path.join(PLOTS_DIR, f"{crop_name}_forecast.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Plot saved → %s", path)
    return path


def plot_model_metrics_bar(crop_name: str, all_metrics: dict) -> str:
    """Bar chart comparing RMSE, MAE, MAPE across models."""
    models = list(all_metrics.keys())
    rmse_vals = [all_metrics[m].get("rmse", 0) for m in models]
    mae_vals  = [all_metrics[m].get("mae", 0) for m in models]
    mape_vals = [all_metrics[m].get("mape_pct", 0) for m in models]

    x = np.arange(len(models))
    width = 0.25

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.bar(x - width, rmse_vals, width, label="RMSE", color="#2196F3", alpha=0.85)
    ax.bar(x, mae_vals, width, label="MAE", color="#4CAF50", alpha=0.85)
    ax.bar(x + width, mape_vals, width, label="MAPE (%)", color="#FF9800", alpha=0.85)
    ax.set_xticks(x)
    ax.set_xticklabels(models, fontsize=10)
    ax.set_title(f"{crop_name.title()} — Model Metrics Comparison", fontsize=14, fontweight="bold")
    ax.legend()

    # Add value labels
    for bars in ax.containers:
        ax.bar_label(bars, fmt="%.1f", fontsize=8, padding=2)

    fig.tight_layout()
    path = os.path.join(PLOTS_DIR, f"{crop_name}_metrics_comparison.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Plot saved → %s", path)
    return path
