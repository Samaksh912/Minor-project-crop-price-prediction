from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

REPO_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_DIR / "backend"
PRESENTATION_DIR = BACKEND_DIR / "presentation_outputs"

os.environ.setdefault("MPLCONFIGDIR", str(BACKEND_DIR / ".mplconfig"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


DATA_DIR = BACKEND_DIR / "data"
OUTPUTS_DIR = BACKEND_DIR / "outputs"

V1_DATASET = DATA_DIR / "coimbatore_maize_model_daily.csv"
V2_DATASET = DATA_DIR / "coimbatore_maize_model_daily_v2.csv"
V3_DATASET = DATA_DIR / "coimbatore_maize_model_daily_v3.csv"
V2_VALIDATION = DATA_DIR / "coimbatore_maize_model_daily_v2_validation.json"
V3_VALIDATION = DATA_DIR / "coimbatore_maize_model_daily_v3_validation.json"
EXPERIMENT_SUMMARY = OUTPUTS_DIR / "maize_v3_split_experiment_summary.json"
EXP_A_HOLDOUT = OUTPUTS_DIR / "maize_v3_experiment_a_holdout_model_comparison.csv"
EXP_A_ROLLING = OUTPUTS_DIR / "maize_v3_experiment_a_rolling_model_comparison.csv"
EXP_B_HOLDOUT = OUTPUTS_DIR / "maize_v3_experiment_b_holdout_model_comparison.csv"
EXP_B_ROLLING = OUTPUTS_DIR / "maize_v3_experiment_b_rolling_model_comparison.csv"
EXP_A_PRED = OUTPUTS_DIR / "maize_v3_experiment_a_holdout_predictions.csv"
EXP_B_PRED = OUTPUTS_DIR / "maize_v3_experiment_b_holdout_predictions.csv"

SUMMARY_TABLE = PRESENTATION_DIR / "summary_table.csv"
SUMMARY_MD = PRESENTATION_DIR / "RESULTS_SUMMARY.md"

MODEL_COLORS = {
    "ARIMA": "#1f77b4",
    "ARIMAX": "#ff7f0e",
    "Hybrid_ARIMAX_LSTM": "#2ca02c",
    "Tabular": "#d62728",
    "Naive": "#7f7f7f",
}
DATASET_COLORS = {
    "v1": "#4c78a8",
    "v2": "#72b7b2",
    "v3": "#f58518",
}
EXPERIMENT_COLORS = {
    "experiment_a": "#2ca02c",
    "experiment_b": "#9467bd",
}


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _prepare_dataset_summary() -> pd.DataFrame:
    v2_validation = _load_json(V2_VALIDATION)
    v3_validation = _load_json(V3_VALIDATION)

    raw_frames = {
        "v1": pd.read_csv(V1_DATASET, parse_dates=["date"]),
        "v2": pd.read_csv(V2_DATASET, parse_dates=["date"]),
        "v3": pd.read_csv(V3_DATASET, parse_dates=["date"]),
    }
    validation_payload = {
        "v1": v3_validation["v1"],
        "v2": v2_validation["model_v2"],
        "v3": v3_validation["v3"],
    }

    rows = []
    key_missing_cols = [
        "modal_price",
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

    for version, frame in raw_frames.items():
        payload = validation_payload[version]
        frame = frame.sort_values("date").reset_index(drop=True)
        date_start = pd.Timestamp(frame["date"].min())
        date_end = pd.Timestamp(frame["date"].max())
        missingness = payload["missingness"]
        rows.append(
            {
                "dataset_version": version,
                "rows": int(len(frame)),
                "unique_weeks": int(frame["date"].dt.to_period("W").nunique()),
                "date_start": date_start,
                "date_end": date_end,
                "date_span_days": int((date_end - date_start).days),
                "key_missing_total": int(sum(int(missingness.get(col, 0)) for col in key_missing_cols)),
                "weather_missing_total": int(
                    sum(int(missingness.get(col, 0)) for col in ["tavg", "tmin", "tmax", "prcp", "wdir", "wspd", "pres"])
                ),
                "policy_missing_total": int(
                    sum(
                        int(missingness.get(col, 0))
                        for col in [
                            "msp_applicable",
                            "msp_value_per_quintal",
                            "govt_procurement_active",
                            "pmfby_insurance_active",
                            "state_scheme_active",
                            "harvest_season_active",
                            "price_impact_direction",
                        ]
                    )
                ),
            }
        )

    return pd.DataFrame(rows)


def _add_bar_labels(ax, values, fmt="{:.0f}", offset=0.01):
    max_value = max(values) if len(values) else 0
    for idx, value in enumerate(values):
        ax.text(
            value + max(max_value * offset, 0.5),
            idx,
            fmt.format(value),
            va="center",
            fontsize=10,
        )


def generate_dataset_evolution_comparison(dataset_df: pd.DataFrame):
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    versions = dataset_df["dataset_version"].tolist()
    colors = [DATASET_COLORS[item] for item in versions]

    for ax, column, title, xfmt in [
        (axes[0, 0], "rows", "Total Daily Rows", "{:.0f}"),
        (axes[0, 1], "unique_weeks", "Unique Weekly Coverage", "{:.0f}"),
        (axes[1, 0], "date_span_days", "Date Span (Days)", "{:.0f}"),
        (axes[1, 1], "key_missing_total", "Total Key-Column Missing Values", "{:.0f}"),
    ]:
        values = dataset_df[column].tolist()
        ax.barh(versions, values, color=colors)
        ax.set_title(title, fontsize=13, weight="bold")
        ax.grid(axis="x", alpha=0.25)
        _add_bar_labels(ax, values, fmt=xfmt)

    axes[1, 1].barh(
        versions,
        dataset_df["weather_missing_total"],
        color="#4c78a8",
        alpha=0.8,
        label="Weather missing",
    )
    axes[1, 1].barh(
        versions,
        dataset_df["policy_missing_total"],
        left=dataset_df["weather_missing_total"],
        color="#e45756",
        alpha=0.8,
        label="Policy/MSP missing",
    )
    axes[1, 1].legend(loc="lower right")

    for idx, row in dataset_df.iterrows():
        axes[0, 0].text(
            row["rows"] * 0.02,
            idx - 0.32,
            f"{row['date_start'].date()} to {row['date_end'].date()}",
            fontsize=9,
            color="#333333",
        )

    fig.suptitle("Coimbatore Maize Dataset Evolution: V1 to V3", fontsize=16, weight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(PRESENTATION_DIR / "dataset_evolution_comparison.png", dpi=220)
    plt.close(fig)


def generate_experiment_regime_comparison(summary: dict):
    regimes = ["experiment_a", "experiment_b"]
    labels = ["A: Full-history\nNo-policy", "B: Policy-aware\nSubset"]
    best_holdout = [summary[regime]["winner_metrics"]["rmse"] for regime in regimes]
    best_rolling = [summary[regime]["rolling"]["winner_metrics"]["rmse"] for regime in regimes]
    naive = [summary[regime]["naive_last_value_baseline"]["rmse"] for regime in regimes]

    x = np.arange(len(regimes))
    width = 0.24

    fig, ax = plt.subplots(figsize=(11, 6))
    ax.bar(x - width, best_holdout, width, label="Best holdout RMSE", color="#2ca02c")
    ax.bar(x, best_rolling, width, label="Best rolling RMSE", color="#1f77b4")
    ax.bar(x + width, naive, width, label="Naive RMSE", color="#7f7f7f")

    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("RMSE")
    ax.set_title("Experiment Regime Comparison", fontsize=15, weight="bold")
    ax.grid(axis="y", alpha=0.25)
    ax.legend()

    for xpos, values in [(x - width, best_holdout), (x, best_rolling), (x + width, naive)]:
        for xp, val in zip(xpos, values):
            ax.text(xp, val + 2, f"{val:.1f}", ha="center", va="bottom", fontsize=10)

    fig.tight_layout()
    fig.savefig(PRESENTATION_DIR / "experiment_regime_comparison.png", dpi=220)
    plt.close(fig)


def _plot_model_comparison(holdout_path: Path, rolling_path: Path, output_name: str, title: str):
    holdout_df = pd.read_csv(holdout_path)
    rolling_df = pd.read_csv(rolling_path)

    holdout_df["regime"] = "Holdout"
    rolling_df["regime"] = "Rolling"
    combined = pd.concat([holdout_df, rolling_df], ignore_index=True)

    fig, axes = plt.subplots(1, 3, figsize=(16, 5.5))
    metrics = [("rmse", "RMSE"), ("mae", "MAE"), ("mape_pct", "MAPE (%)")]

    for ax, (metric, label) in zip(axes, metrics):
        pivot = combined.pivot(index="model_name", columns="regime", values=metric).reindex(
            ["ARIMA", "ARIMAX", "Hybrid_ARIMAX_LSTM", "Tabular"]
        )
        x = np.arange(len(pivot.index))
        width = 0.35
        ax.bar(
            x - width / 2,
            pivot["Holdout"],
            width,
            label="Holdout",
            color="#4c78a8",
        )
        ax.bar(
            x + width / 2,
            pivot["Rolling"],
            width,
            label="Rolling",
            color="#f58518",
        )
        ax.set_xticks(x)
        ax.set_xticklabels(pivot.index, rotation=20)
        ax.set_title(label, fontsize=12, weight="bold")
        ax.grid(axis="y", alpha=0.25)
        if metric == "rmse":
            ax.legend()

    fig.suptitle(title, fontsize=16, weight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(PRESENTATION_DIR / output_name, dpi=220)
    plt.close(fig)


def _plot_best_forecast(pred_path: Path, best_model: str, output_name: str, title: str):
    df = pd.read_csv(pred_path, parse_dates=["date"])
    pred_col = f"pred_{best_model}"
    if pred_col not in df.columns:
        pred_candidates = [col for col in df.columns if col.startswith("pred_")]
        pred_col = pred_candidates[0]

    fig, ax = plt.subplots(figsize=(12.5, 5.5))
    ax.plot(df["date"], df["actual"], label="Actual", color="#111111", linewidth=2.5)
    ax.plot(df["date"], df[pred_col], label=best_model, color=MODEL_COLORS.get(best_model, "#2ca02c"), linewidth=2.2)
    ax.set_title(title, fontsize=15, weight="bold")
    ax.set_xlabel("Date")
    ax.set_ylabel("Modal price")
    ax.grid(alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(PRESENTATION_DIR / output_name, dpi=220)
    plt.close(fig)


def build_summary_table(dataset_df: pd.DataFrame, summary: dict) -> pd.DataFrame:
    rows = []
    for _, row in dataset_df.iterrows():
        rows.append(
            {
                "section": "dataset",
                "name": row["dataset_version"],
                "date_start": row["date_start"].strftime("%Y-%m-%d"),
                "date_end": row["date_end"].strftime("%Y-%m-%d"),
                "rows": int(row["rows"]),
                "unique_weeks": int(row["unique_weeks"]),
                "winner": None,
                "holdout_rmse": None,
                "rolling_rmse": None,
                "naive_rmse": None,
                "mae": None,
                "mape_pct": None,
                "notes": f"Key missing total={int(row['key_missing_total'])}",
            }
        )

    for regime in ["experiment_a", "experiment_b"]:
        payload = summary[regime]
        rows.append(
            {
                "section": "experiment",
                "name": regime,
                "date_start": payload["date_start"],
                "date_end": payload["date_end"],
                "rows": int(payload["rows"]),
                "unique_weeks": None,
                "winner": payload["winner"],
                "holdout_rmse": payload["winner_metrics"]["rmse"],
                "rolling_rmse": payload["rolling"]["winner_metrics"]["rmse"],
                "naive_rmse": payload["naive_last_value_baseline"]["rmse"],
                "mae": payload["winner_metrics"]["mae"],
                "mape_pct": payload["winner_metrics"]["mape_pct"],
                "notes": f"Rolling winner={payload['rolling']['winner']}",
            }
        )

    table = pd.DataFrame(rows)
    table.to_csv(SUMMARY_TABLE, index=False)
    return table


def build_results_summary_md(dataset_df: pd.DataFrame, summary: dict):
    v1 = dataset_df.loc[dataset_df["dataset_version"] == "v1"].iloc[0]
    v2 = dataset_df.loc[dataset_df["dataset_version"] == "v2"].iloc[0]
    v3 = dataset_df.loc[dataset_df["dataset_version"] == "v3"].iloc[0]
    exp_a = summary["experiment_a"]
    exp_b = summary["experiment_b"]
    recommendation = summary["recommendation"]

    md = f"""# Maize Forecasting Results Summary

## Dataset evolution

- V1 covered {v1['date_start'].date()} to {v1['date_end'].date()} with {int(v1['rows'])} daily rows and {int(v1['unique_weeks'])} unique weeks, but weather coverage still had gaps.
- V2 extended the weather-aligned modeling horizon to {v2['date_end'].date()} and reached {int(v2['rows'])} daily rows with zero key weather/policy missingness.
- V3 expanded the real maize history back to {v3['date_start'].date()} and reached {int(v3['rows'])} daily rows and {int(v3['unique_weeks'])} unique weeks, but pre-2023 policy fields remain missing.

## Experiment comparison

- Experiment A, full-history without policy features: best holdout model was `{exp_a['winner']}` with RMSE {exp_a['winner_metrics']['rmse']:.2f}; best rolling model was `{exp_a['rolling']['winner']}` with RMSE {exp_a['rolling']['winner_metrics']['rmse']:.2f}.
- Experiment B, policy-aware subset: best holdout model was `{exp_b['winner']}` with RMSE {exp_b['winner_metrics']['rmse']:.2f}; best rolling model was `{exp_b['rolling']['winner']}` with RMSE {exp_b['rolling']['winner_metrics']['rmse']:.2f}.
- For the demo decision, the current evidence favors `{recommendation['product_demo']}` because its recent holdout performance is materially stronger.
- For the research framing, the current evidence favors `{recommendation['research_paper']}` because it preserves the longer historical regime while staying competitive in rolling evaluation.

## Current strength

- The current result is directionally useful but not strong enough to present as a solved forecasting problem.
- The policy-aware subset currently gives the best recent holdout accuracy, but it is still essentially tied with the naive baseline.
- SARIMAX-family models also continue to show convergence warnings, so stability is still a concern.

## Recommended next step

- Use this pack for a credible progress review, not a claims-heavy final result.
- Next modeling work should focus on beating the naive baseline consistently before any stronger product or paper claim is made.
"""
    SUMMARY_MD.write_text(md, encoding="utf-8")


def main():
    PRESENTATION_DIR.mkdir(parents=True, exist_ok=True)

    dataset_df = _prepare_dataset_summary()
    summary = _load_json(EXPERIMENT_SUMMARY)

    generate_dataset_evolution_comparison(dataset_df)
    generate_experiment_regime_comparison(summary)
    _plot_model_comparison(
        EXP_A_HOLDOUT,
        EXP_A_ROLLING,
        "experiment_a_model_comparison.png",
        "Experiment A Model Comparison",
    )
    _plot_model_comparison(
        EXP_B_HOLDOUT,
        EXP_B_ROLLING,
        "experiment_b_model_comparison.png",
        "Experiment B Model Comparison",
    )
    _plot_best_forecast(
        EXP_A_PRED,
        summary["experiment_a"]["winner"],
        "experiment_a_best_forecast_plot.png",
        "Experiment A Best Holdout Forecast",
    )
    _plot_best_forecast(
        EXP_B_PRED,
        summary["experiment_b"]["winner"],
        "experiment_b_best_forecast_plot.png",
        "Experiment B Best Holdout Forecast",
    )
    build_summary_table(dataset_df, summary)
    build_results_summary_md(dataset_df, summary)

    print(PRESENTATION_DIR)


if __name__ == "__main__":
    main()
