    if crop != CROP_NAME:
        return _error_response("Unsupported crop", 400, {"allowed": [CROP_NAME]})
        df = load_data()
    crop = payload.get("crop", CROP_NAME)
    if crop != CROP_NAME:
        return _error_response("Unsupported crop", 400, {"allowed": [CROP_NAME]})
        df = load_data()
    crop = payload.get("crop", CROP_NAME)
    if crop != CROP_NAME:
        return _error_response("Unsupported crop", 400, {"allowed": [CROP_NAME]})
    return jsonify({"status": "ok", "crops": [CROP_NAME]})
from __future__ import annotations

import json
import logging
from config import CROP_NAME, OUTPUTS_DIR, SUPPORTED_CROPS, normalize_crop_name

os.environ.setdefault(
    "MPLCONFIGDIR",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), ".mplconfig"),
)
os.makedirs(os.environ["MPLCONFIGDIR"], exist_ok=True)

import joblib
from flask import Flask, jsonify, request

from config import CROP_NAME, OUTPUTS_DIR
from data_loader import load_data
from model import model_exists
from predictor import predict


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
LOGGER = logging.getLogger(__name__)

app = Flask(__name__)


def _error_response(message, status_code=400, details=None):
    payload = {"status": "error", "message": message}
    if details is not None:
        payload["details"] = details
    return jsonify(payload), status_code


@app.get("/api/health")
def health():
    return jsonify(
    return jsonify({"status": "ok", "crops": SUPPORTED_CROPS})
            "status": "ok",
            "service": "BestCropPrice",
            "crop": CROP_NAME,
            "model_ready": model_exists(CROP_NAME),
        }
    crop = normalize_crop_name(payload.get("crop", CROP_NAME))
    if crop not in SUPPORTED_CROPS:
        return _error_response("Unsupported crop", 400, {"allowed": SUPPORTED_CROPS})
@app.get("/api/crops")
def crops():
        df = load_data(crop)


@app.post("/api/predict")
def predict_endpoint():
    payload = request.get_json(silent=True) or {}
    crop = payload.get("crop", CROP_NAME)
    if crop != CROP_NAME:
        return _error_response("Unsupported crop", 400, {"allowed": [CROP_NAME]})

    try:
        df = load_data()
        result = predict(crop_name=crop, df=df, force_retrain=bool(payload.get("force_retrain", False)))
    except Exception as exc:
            "spike_flags": [int(item) for item in result.get("spike_flags", [])],
            "spike_scores": [float(item) for item in result.get("spike_scores", [])],
            "spike_rule": result.get("spike_rule", {}),
        LOGGER.exception("Prediction failed")
        return _error_response("Prediction failed", 500, {"error": str(exc)})

    return jsonify(
        {
            "status": "ok",
            "crop": crop,
    crop = normalize_crop_name(payload.get("crop", CROP_NAME))
    if crop not in SUPPORTED_CROPS:
        return _error_response("Unsupported crop", 400, {"allowed": SUPPORTED_CROPS})
            "forecast": [float(item) for item in result["forecast"]],
        }
        df = load_data(crop)


@app.post("/api/train")
def train_endpoint():
    payload = request.get_json(silent=True) or {}
    crop = payload.get("crop", CROP_NAME)
    if crop != CROP_NAME:
        return _error_response("Unsupported crop", 400, {"allowed": [CROP_NAME]})

    try:
        df = load_data()
        result = predict(crop_name=crop, df=df, force_retrain=True)
    except Exception as exc:
        LOGGER.exception("Training failed")
        return _error_response("Training failed", 500, {"error": str(exc)})

    return jsonify(
        {
    crop = normalize_crop_name(crop)
    if crop not in SUPPORTED_CROPS:
        return _error_response("Unsupported crop", 400, {"allowed": SUPPORTED_CROPS})
            "best_model_name": result["best_model_name"],
            "metrics": result["metrics"],
            "all_metrics": result["all_metrics"],
        }
    )


@app.get("/api/evaluate/<crop>")
def evaluate_endpoint(crop):
    if crop != CROP_NAME:
        return _error_response("Unsupported crop", 400, {"allowed": [CROP_NAME]})

    report_path = os.path.join(OUTPUTS_DIR, f"{crop}_evaluation_report.json")
    if not os.path.exists(report_path):
        return _error_response("Evaluation report not found", 404)

    try:
        with open(report_path, "r", encoding="utf-8") as file_obj:
            report = json.load(file_obj)
    except Exception as exc:
        LOGGER.exception("Failed to read evaluation report")
        return _error_response("Failed to load evaluation report", 500, {"error": str(exc)})

    trimmed = {
        key: value
        for key, value in report.items()
        if key not in {"test_predictions", "test_actuals", "test_dates", "forecast", "forecast_dates"}
    }
    return jsonify({"status": "ok", "crop": crop, "evaluation": trimmed})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
