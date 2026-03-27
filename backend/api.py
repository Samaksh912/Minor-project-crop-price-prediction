"""
api.py
------
Flask REST API for the BestCropPrice hybrid ARIMAX-LSTM prediction backend.

Endpoints
---------
GET  /api/health          → health check
GET  /api/crops           → list available crops
POST /api/predict         → 90-day price forecast
POST /api/train           → force-retrain a specific crop model
POST /api/train-all       → train models for all crops
GET  /api/evaluate/<crop> → model comparison metrics

Run with:
    python api.py
"""

import logging
import traceback
from datetime import datetime, timezone

import numpy as np
from flask import Flask, jsonify, request

from config import FORECAST_DAYS
from data_loader import list_crops, load_and_align
from predictor import predict

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_predictions(forecast: np.ndarray, dates) -> list:
    return [
        {"date": d.strftime("%Y-%m-%d"), "predicted_modal_price": round(float(v), 2)}
        for d, v in zip(dates, forecast)
    ]


def _build_summary(forecast: np.ndarray) -> dict:
    n = len(forecast)
    m1 = forecast[:30]
    m2 = forecast[30:60] if n >= 60 else forecast[30:]
    m3 = forecast[60:90] if n >= 90 else forecast[60:] if n > 60 else np.array([])

    return {
        "min_price":   round(float(forecast.min()), 2),
        "max_price":   round(float(forecast.max()), 2),
        "avg_price":   round(float(forecast.mean()), 2),
        "month_1_avg": round(float(m1.mean()), 2) if len(m1) else None,
        "month_2_avg": round(float(m2.mean()), 2) if len(m2) else None,
        "month_3_avg": round(float(m3.mean()), 2) if len(m3) else None,
    }


def _error(message: str, code: int = 400):
    return jsonify({"error": message}), code


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()})


@app.get("/api/crops")
def crops():
    available = list_crops()
    return jsonify({"crops": available, "count": len(available)})


@app.post("/api/predict")
def api_predict():
    """
    Request body (JSON): { "crop": "apple" }
    Optional:            { "crop": "apple", "force_retrain": true }
    """
    body = request.get_json(silent=True) or {}
    crop_name     = body.get("crop", "").strip().lower()
    force_retrain = bool(body.get("force_retrain", False))

    if not crop_name:
        return _error("'crop' field is required.")

    available = list_crops()
    if crop_name not in available:
        return _error(f"Crop '{crop_name}' not found. Available crops: {available}")

    try:
        aligned   = load_and_align(crop_name)
        result    = predict(crop_name, aligned, force_retrain=force_retrain)
        forecast  = result["forecast"]
        dates     = result["dates"]
        metrics   = result["metrics"]
        last_date = result["last_date"]
    except FileNotFoundError as exc:
        return _error(str(exc), 404)
    except ValueError as exc:
        return _error(str(exc), 422)
    except Exception:
        logger.error("Unexpected error:\n%s", traceback.format_exc())
        return _error("Internal server error — check server logs.", 500)

    response = {
        "crop":                  crop_name,
        "unit":                  "Rs./Quintal",
        "forecast_horizon_days": FORECAST_DAYS,
        "generated_at":          datetime.now(timezone.utc).isoformat(),
        "last_observed_date":    last_date.strftime("%Y-%m-%d"),
        "model_metrics":         metrics,
        "predictions":           _build_predictions(forecast, dates),
        "summary":               _build_summary(forecast),
    }

    # Include baseline comparison if available
    all_metrics = result.get("all_metrics")
    if all_metrics:
        response["model_comparison"] = all_metrics

    return jsonify(response)


@app.post("/api/train")
def api_train():
    """Force-retrain the model for a given crop."""
    body      = request.get_json(silent=True) or {}
    crop_name = body.get("crop", "").strip().lower()

    if not crop_name:
        return _error("'crop' field is required.")

    available = list_crops()
    if crop_name not in available:
        return _error(f"Crop '{crop_name}' not found. Available: {available}")

    try:
        aligned = load_and_align(crop_name)
        result  = predict(crop_name, aligned, force_retrain=True)
    except FileNotFoundError as exc:
        return _error(str(exc), 404)
    except Exception:
        logger.error("Training error:\n%s", traceback.format_exc())
        return _error("Training failed — check server logs.", 500)

    return jsonify({
        "status":             "trained",
        "crop":               crop_name,
        "metrics":            result["metrics"],
        "model_comparison":   result.get("all_metrics", {}),
        "last_observed_date": result["last_date"].strftime("%Y-%m-%d"),
    })


@app.post("/api/train-all")
def api_train_all():
    """Train models for all available crops."""
    available = list_crops()
    results = {}
    errors = {}

    for crop_name in available:
        try:
            aligned = load_and_align(crop_name)
            result = predict(crop_name, aligned, force_retrain=True)
            results[crop_name] = {
                "status":  "trained",
                "metrics": result["metrics"],
                "model_comparison": result.get("all_metrics", {}),
            }
        except Exception as e:
            logger.error("[%s] Training failed: %s", crop_name, e)
            errors[crop_name] = str(e)

    return jsonify({
        "trained": results,
        "errors":  errors,
        "total":   len(available),
        "success": len(results),
        "failed":  len(errors),
    })


@app.get("/api/evaluate/<crop_name>")
def api_evaluate(crop_name: str):
    """Return model comparison metrics for a crop."""
    import json
    from config import METRICS_DIR
    import os

    eval_path = os.path.join(METRICS_DIR, f"{crop_name}_evaluation.json")
    if not os.path.exists(eval_path):
        return _error(f"No evaluation data for '{crop_name}'. Train the model first.", 404)

    with open(eval_path) as f:
        data = json.load(f)

    # Remove large arrays for API response
    data.pop("test_actuals", None)
    data.pop("test_predictions", None)
    data.pop("test_dates", None)

    return jsonify(data)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logger.info("Starting BestCropPrice Prediction API …")
    logger.info("Available crops: %s", list_crops())
    app.run(host="0.0.0.0", port=5000, debug=False)
