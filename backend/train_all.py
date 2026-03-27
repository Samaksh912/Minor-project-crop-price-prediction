"""
train_all.py
------------
Convenience script to train models for all available crops and generate outputs.
"""

import logging
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


def train_all_crops():
    """Train models for all crops and generate outputs."""
    from data_loader import list_crops, load_and_align
    from predictor import predict

    crops = list_crops()
    logger.info("Found %d crops: %s", len(crops), crops)

    results = {}
    errors  = {}

    for crop_name in crops:
        logger.info("=" * 60)
        logger.info("Training: %s", crop_name)
        logger.info("=" * 60)
        t0 = time.time()
        try:
            aligned = load_and_align(crop_name)
            result = predict(crop_name, aligned, force_retrain=True)
            elapsed = time.time() - t0
            results[crop_name] = {
                "metrics":          result["metrics"],
                "model_comparison": result.get("all_metrics", {}),
                "time_seconds":     round(elapsed, 1),
            }
            logger.info("[%s] Done in %.1fs — metrics: %s", crop_name, elapsed, result["metrics"])
        except Exception as e:
            elapsed = time.time() - t0
            logger.error("[%s] FAILED after %.1fs: %s", crop_name, elapsed, e)
            errors[crop_name] = str(e)

    # Print summary
    logger.info("=" * 60)
    logger.info("TRAINING COMPLETE")
    logger.info("Successful: %d / %d", len(results), len(crops))
    if errors:
        logger.error("Failed: %s", list(errors.keys()))

    for crop, data in results.items():
        logger.info("  %s: MAPE=%.1f%% RMSE=%.1f MAE=%.1f (%.1fs)",
                     crop,
                     data["metrics"].get("mape_pct", -1),
                     data["metrics"].get("rmse", -1),
                     data["metrics"].get("mae", -1),
                     data["time_seconds"])
        if data.get("model_comparison"):
            for model, m in data["model_comparison"].items():
                logger.info("    %-20s MAPE=%.1f%% RMSE=%.1f",
                             model, m.get("mape_pct", -1), m.get("rmse", -1))

    return results, errors


if __name__ == "__main__":
    results, errors = train_all_crops()
    sys.exit(1 if errors else 0)
