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
        )
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
                "model_name": model_name,
                "rmse": float(rmse),
                "mae": float(mae) if np.isfinite(mae) else np.nan,
                "mape_pct": float(mape_pct) if np.isfinite(mape_pct) else np.nan,
            }
        )

    if not rows:
        return pd.DataFrame(columns=["model_name", "rmse", "mae", "mape_pct"])

    comparison_df = pd.DataFrame(rows).sort_values(
        by=["rmse", "mae", "mape_pct"],
        ascending=[True, True, True],
        na_position="last",
    )
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

