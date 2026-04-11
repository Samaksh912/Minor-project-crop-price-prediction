from __future__ import annotations

import json
import time
import traceback
from pathlib import Path
import sys

import pandas as pd

# Ensure backend modules are importable when script runs from scripts/.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from predictor import predict


CASES = [
    ("maize", "coimbatore_maize_model_daily.csv"),
    ("bananagreen", "bananagreen_model_daily.csv"),
    ("beans", "beans_model_daily.csv"),
    ("mango", "mango_model_daily.csv"),
    ("apple", "apple_model_daily.csv"),
    ("beetroot", "beetroot_model_daily.csv"),
    ("lemon", "lemon_model_daily.csv"),
    ("ladies_finger", "ladies_finger_model_daily.csv"),
]

REQUIRED_COLS = [
    "date",
    "modal_price",
    "min_price",
    "max_price",
    "markets_reporting",
    "varieties_reporting",
    "rows_reporting",
    "tavg",
    "tmin",
    "tmax",
    "prcp",
    "wdir",
    "wspd",
    "pres",
    "msp_applicable",
    "msp_value_per_quintal",
    "govt_procurement_active",
    "pmfby_insurance_active",
    "state_scheme_active",
    "harvest_season_active",
    "price_impact_direction",
]


def main() -> None:
    base = Path("data")
    outputs = Path("outputs")
    outputs.mkdir(exist_ok=True)

    report: dict = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "cases": [],
    }

    for crop, file_name in CASES:
        case = {"crop": crop, "file": file_name}
        path = base / file_name
        print("=" * 88)
        print("CHECK", crop, "::", file_name)

        if not path.exists():
            case["status"] = "file_missing"
            report["cases"].append(case)
            print("  file missing")
            continue

        try:
            df = pd.read_csv(path, parse_dates=["date"])
            case["rows"] = int(len(df))
            case["columns"] = int(len(df.columns))
            case["missing_required_cols"] = [c for c in REQUIRED_COLS if c not in df.columns]
            case["msp_nulls"] = int(df["msp_value_per_quintal"].isna().sum())
            case["date_min"] = str(df["date"].min().date())
            case["date_max"] = str(df["date"].max().date())
            case["date_unique"] = int(df["date"].nunique())
            case["date_duplicates"] = int(df["date"].duplicated().sum())

            minv = pd.to_numeric(df["min_price"], errors="coerce")
            maxv = pd.to_numeric(df["max_price"], errors="coerce")
            modv = pd.to_numeric(df["modal_price"], errors="coerce")
            case["modal_outside_range"] = int(((modv < minv) | (modv > maxv)).sum())

            started = time.time()
            result = predict(crop_name=crop, df=df, force_retrain=False)
            case["elapsed_sec"] = round(time.time() - started, 2)
            case["status"] = "ok"
            case["best_model_name"] = result.get("best_model_name")
            case["forecast_len"] = int(len(result.get("forecast", [])))
            case["metrics"] = result.get("metrics", {})
            print("  ok", case["best_model_name"], "forecast_len", case["forecast_len"])

        except Exception as exc:  # pragma: no cover - smoke script
            case["status"] = "failed"
            case["error_type"] = type(exc).__name__
            case["error"] = str(exc)
            case["traceback"] = traceback.format_exc()
            print("  failed", type(exc).__name__, str(exc))

        report["cases"].append(case)

    total = len(report["cases"])
    ok = sum(1 for item in report["cases"] if item.get("status") == "ok")
    failed_or_missing = sum(
        1 for item in report["cases"] if item.get("status") in ("failed", "file_missing")
    )
    report["summary"] = {
        "total": total,
        "ok": ok,
        "failed_or_missing": failed_or_missing,
    }

    report_path = outputs / "all_crops_dry_run_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("Report written:", report_path)


if __name__ == "__main__":
    main()
