"""Train all crops and print a summary comparison table."""
import logging
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

from config import SUPPORTED_CROPS
from data_loader import load_data
from predictor import predict

results_summary = []

for crop_name in SUPPORTED_CROPS:
    print(f"\n{'='*60}")
    print(f"Training: {crop_name}")
    print(f"{'='*60}")
    start = time.time()
    try:
        df = load_data(crop_name=crop_name)
        result = predict(crop_name=crop_name, df=df, force_retrain=True)
        elapsed = time.time() - start
        results_summary.append({
            "crop": crop_name,
            "best": result["best_model_name"],
            "metrics": result["metrics"],
            "all_metrics": result["all_metrics"],
            "elapsed": elapsed,
        })
        print(f"  Best: {result['best_model_name']}")
        print(f"  RMSE: {result['metrics']['rmse']:.1f}")
        print(f"  MAPE: {result['metrics']['mape_pct']:.1f}%")
        print(f"  Time: {elapsed:.0f}s")
    except Exception as e:
        elapsed = time.time() - start
        print(f"  FAILED: {e}")
        results_summary.append({"crop": crop_name, "best": "FAILED", "elapsed": elapsed})

print(f"\n\n{'='*80}")
print("FINAL COMPARISON TABLE")
print(f"{'='*80}")
print(f"{'Crop':<16} {'Best Model':<22} {'RMSE':>10} {'MAE':>10} {'MAPE%':>8} {'Time':>6}")
print("-" * 80)
for r in results_summary:
    if r["best"] == "FAILED":
        print(f"{r['crop']:<16} {'FAILED':<22}")
        continue
    m = r["metrics"]
    print(f"{r['crop']:<16} {r['best']:<22} {m['rmse']:>10.1f} {m['mae']:>10.1f} {m['mape_pct']:>7.1f}% {r['elapsed']:>5.0f}s")

print(f"\n\nDETAILED PER-MODEL MAPE COMPARISON")
print(f"{'='*80}")
model_names = ["ARIMA", "ARIMAX", "Standalone_LSTM", "Hybrid_ARIMAX_LSTM", "Tabular_GBM"]
header = f"{'Crop':<16}" + "".join(f"{n:>16}" for n in model_names)
print(header)
print("-" * 96)
for r in results_summary:
    if r["best"] == "FAILED":
        continue
    row = f"{r['crop']:<16}"
    for mn in model_names:
        mape = r["all_metrics"].get(mn, {}).get("mape_pct", float("nan"))
        marker = " *" if mn == r["best"] else "  "
        row += f"{mape:>13.1f}%{marker}"
    print(row)
print("\n* = selected production model")
