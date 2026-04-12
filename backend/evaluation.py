    comparison_df = pd.DataFrame(rows).sort_values(
        by=["rmse", "mae", "mape_pct"],
        ascending=[True, True, True],
        return pd.DataFrame(columns=["model_name", "rmse", "mae", "mape_pct"])
from __future__ import annotations

import json
import logging
import os

import numpy as np
import pandas as pd

from config import OUTPUTS_DIR


LOGGER = logging.getLogger(__name__)


def compute_metrics(actual, predicted) -> dict:
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
    spike_metrics = _compute_spike_metrics(actual_valid, predicted_valid)
    return {
        "rmse": rmse,
        "mae": mae,
        "mape_pct": mape_pct,
        "spike_rmse": spike_metrics["spike_rmse"],
        "spike_recall": spike_metrics["spike_recall"],
        "spike_precision": spike_metrics["spike_precision"],
    }
    else:
        mape_pct = np.nan

    return {"rmse": rmse, "mae": mae, "mape_pct": mape_pct}


def compare_models(results: dict) -> pd.DataFrame:
    rows = []
    for model_name, payload in results.items():
        metrics = payload.get("metrics", payload) if isinstance(payload, dict) else {}
        rmse = metrics.get("rmse", np.nan)
        mae = metrics.get("mae", np.nan)
        mape_pct = metrics.get("mape_pct", np.nan)
        if not np.isfinite(rmse):
            continue
        rows.append(
            {
                "spike_rmse": float(metrics.get("spike_rmse", np.nan)),
                "spike_recall": float(metrics.get("spike_recall", np.nan)),
                "spike_precision": float(metrics.get("spike_precision", np.nan)),
                "model_name": model_name,
                "rmse": float(rmse),
                "mae": float(mae) if np.isfinite(mae) else np.nan,
                "mape_pct": float(mape_pct) if np.isfinite(mape_pct) else np.nan,
        return pd.DataFrame(
            columns=[
                "model_name",
                "rmse",
                "mae",
                "mape_pct",
                "spike_rmse",
                "spike_recall",
                "spike_precision",
                "composite_score",
            ]
        )
        )
    comparison_df = pd.DataFrame(rows)
    comparison_df["_rmse_rank"] = comparison_df["rmse"].rank(method="min", ascending=True)
    comparison_df["_spike_rmse_rank"] = comparison_df["spike_rmse"].fillna(comparison_df["rmse"]).rank(
        method="min",
        ascending=True,
    )
    comparison_df["_spike_recall_rank"] = comparison_df["spike_recall"].fillna(0.0).rank(
        method="min",
        ascending=False,
    )
    comparison_df["composite_score"] = (
        0.55 * comparison_df["_rmse_rank"]
        + 0.30 * comparison_df["_spike_rmse_rank"]
        + 0.15 * comparison_df["_spike_recall_rank"]
    )
    comparison_df = comparison_df.sort_values(
        by=["composite_score", "rmse", "mae", "mape_pct"],
        ascending=[True, True, True, True],

    comparison_df = pd.DataFrame(rows).sort_values(
    comparison_df = comparison_df.drop(columns=["_rmse_rank", "_spike_rmse_rank", "_spike_recall_rank"])
        by=["rmse", "mae", "mape_pct"],
        ascending=[True, True, True],
        na_position="last",
    )
def _compute_spike_metrics(actual_valid: np.ndarray, predicted_valid: np.ndarray) -> dict:
    if len(actual_valid) < 3:
        return {"spike_rmse": np.nan, "spike_recall": np.nan, "spike_precision": np.nan}

    actual_returns = pd.Series(actual_valid).pct_change().replace([np.inf, -np.inf], np.nan).fillna(0.0).to_numpy()
    pred_returns = pd.Series(predicted_valid).pct_change().replace([np.inf, -np.inf], np.nan).fillna(0.0).to_numpy()
    threshold = float(np.nanpercentile(np.abs(actual_returns), 80))
    threshold = max(threshold, 0.05)

    actual_spikes = np.abs(actual_returns) >= threshold
    pred_spikes = np.abs(pred_returns) >= threshold

    if np.any(actual_spikes):
        spike_errors = actual_valid[actual_spikes] - predicted_valid[actual_spikes]
        spike_rmse = float(np.sqrt(np.mean(np.square(spike_errors))))
        true_positive = float(np.sum(actual_spikes & pred_spikes))
        spike_recall = true_positive / float(np.sum(actual_spikes))
    else:
        spike_rmse = np.nan
        spike_recall = np.nan

    if np.any(pred_spikes):
        true_positive = float(np.sum(actual_spikes & pred_spikes))
        spike_precision = true_positive / float(np.sum(pred_spikes))
    else:
        spike_precision = np.nan

    return {
        "spike_rmse": spike_rmse,
        "spike_recall": spike_recall,
        "spike_precision": spike_precision,
    }


    comparison_df = comparison_df.reset_index(drop=True)
    return comparison_df
def save_evaluation_report(crop_name, data: dict) -> str:
    report_path = os.path.join(OUTPUTS_DIR, f"{crop_name}_evaluation_report.json")
    serializable = json.loads(json.dumps(data, default=_json_default))
    with open(report_path, "w", encoding="utf-8") as file_obj:
        json.dump(serializable, file_obj, indent=2)
    LOGGER.info("Saved evaluation report to %s", report_path)
    return report_path


def _json_default(value):
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if np.isnan(value) else float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value

