from __future__ import annotations

import json
import time
from pathlib import Path
import sys

import pandas as pd

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


def _read_eval(outputs_dir: Path, crop: str) -> dict:
    path = outputs_dir / f"{crop}_evaluation_report.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _metrics(payload: dict) -> dict:
    return (payload or {}).get("metrics", {}) if isinstance(payload, dict) else {}


def _best_model(payload: dict) -> str | None:
    return (payload or {}).get("best_model_name") if isinstance(payload, dict) else None


def _delta(before: dict, after: dict, key: str):
    b = before.get(key)
    a = after.get(key)
    if b is None or a is None:
        return None
    try:
        return float(a) - float(b)
    except Exception:
        return None


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    data_dir = root / "data"
    outputs_dir = root / "outputs"
    outputs_dir.mkdir(exist_ok=True)

    report: dict = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "steps": {},
        "cases": [],
    }

    # Step 1: baseline snapshot.
    baseline = {crop: _read_eval(outputs_dir, crop) for crop, _ in CASES}

    # Step 2: fill msp nulls in all model_daily files.
    msp_fix = []
    for _, file_name in CASES:
        path = data_dir / file_name
        if not path.exists():
            msp_fix.append({"file": file_name, "status": "missing"})
            continue
        df = pd.read_csv(path)
        if "msp_value_per_quintal" not in df.columns:
            msp_fix.append({"file": file_name, "status": "column_missing"})
            continue
        before = int(df["msp_value_per_quintal"].isna().sum())
        df["msp_value_per_quintal"] = pd.to_numeric(
            df["msp_value_per_quintal"], errors="coerce"
        ).fillna(0.0)
        after = int(df["msp_value_per_quintal"].isna().sum())
        df.to_csv(path, index=False)
        msp_fix.append({"file": file_name, "nulls_before": before, "nulls_after": after})
    report["steps"]["msp_fill"] = msp_fix

    # Step 3-4: force retrain each crop.
    for crop, file_name in CASES:
        case = {"crop": crop, "file": file_name}
        path = data_dir / file_name
        if not path.exists():
            case["status"] = "file_missing"
            report["cases"].append(case)
            continue

        try:
            df = pd.read_csv(path, parse_dates=["date"])
            started = time.time()
            result = predict(crop_name=crop, df=df, force_retrain=True)
            elapsed = round(time.time() - started, 2)

            after_eval = _read_eval(outputs_dir, crop)
            before_eval = baseline.get(crop, {})
            before_m = _metrics(before_eval)
            after_m = _metrics(after_eval)

            case.update(
                {
                    "status": "ok",
                    "elapsed_sec": elapsed,
                    "best_model_before": _best_model(before_eval),
                    "best_model_after": result.get("best_model_name"),
                    "metrics_before": before_m,
                    "metrics_after": after_m,
                    "rmse_delta": _delta(before_m, after_m, "rmse"),
                    "mae_delta": _delta(before_m, after_m, "mae"),
                    "mape_delta": _delta(before_m, after_m, "mape_pct"),
                    "hybrid_diagnostics": after_eval.get("hybrid_diagnostics", {}),
                }
            )
        except Exception as exc:
            case.update({"status": "failed", "error": str(exc), "error_type": type(exc).__name__})

        report["cases"].append(case)

    ok = sum(1 for c in report["cases"] if c.get("status") == "ok")
    failed = sum(1 for c in report["cases"] if c.get("status") != "ok")
    report["summary"] = {"total": len(report["cases"]), "ok": ok, "failed": failed}

    out_json = outputs_dir / "all_crops_retrain_report.json"
    out_md = outputs_dir / "all_crops_retrain_report.md"
    out_json.write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = [
        "# All Crops Retrain Report",
        "",
        f"Generated: {report['generated_at']}",
        "",
        f"- Total: {report['summary']['total']}",
        f"- OK: {report['summary']['ok']}",
        f"- Failed: {report['summary']['failed']}",
        "",
        "| Crop | Status | Best Before | Best After | RMSE delta | MAPE delta |",
        "|---|---|---|---|---:|---:|",
    ]
    for c in report["cases"]:
        lines.append(
            "| {crop} | {status} | {bb} | {ba} | {rd} | {md} |".format(
                crop=c.get("crop"),
                status=c.get("status"),
                bb=c.get("best_model_before", "-"),
                ba=c.get("best_model_after", "-"),
                rd="-" if c.get("rmse_delta") is None else round(c["rmse_delta"], 4),
                md="-" if c.get("mape_delta") is None else round(c["mape_delta"], 4),
            )
        )
    out_md.write_text("\n".join(lines), encoding="utf-8")

    print("Report written:", out_json)
    print("Report written:", out_md)


if __name__ == "__main__":
    main()

