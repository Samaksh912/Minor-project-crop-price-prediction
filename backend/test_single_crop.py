"""Quick single-crop test to verify the updated pipeline."""
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

from data_loader import load_data
from predictor import predict

df = load_data(crop_name="maize")
print(f"Loaded {len(df)} rows")

result = predict(crop_name="maize", df=df, force_retrain=True)
print(f"\nBest model: {result['best_model_name']}")
print(f"Deployed metrics: {result['metrics']}")
print("\nAll model metrics:")
for name, m in result["all_metrics"].items():
    rmse = m.get("rmse", float("nan"))
    mae = m.get("mae", float("nan"))
    mape = m.get("mape_pct", float("nan"))
    print(f"  {name}: RMSE={rmse:.1f}, MAE={mae:.1f}, MAPE={mape:.1f}%")

if "rolling_origin_metrics" in result and result["rolling_origin_metrics"]:
    print("\nRolling origin metrics:")
    for name, m in result["rolling_origin_metrics"].items():
        rmse = m.get("rmse", float("nan"))
        print(f"  {name}: RMSE={rmse:.1f}")

print("\nDone!")
