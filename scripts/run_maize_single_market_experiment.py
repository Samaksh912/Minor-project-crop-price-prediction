from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).resolve().parents[1] / "backend" / ".mplconfig"))
os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "-1")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from run_maize_v3_split_experiments import (
    POLICY_COLS,
    _prepare_weekly_dataset,
    _run_holdout_experiment,
    _run_rolling_backtest,
    _serialize_for_json,
)


REPO_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_DIR / "backend"
DATA_DIR = BACKEND_DIR / "data"
OUTPUTS_DIR = BACKEND_DIR / "outputs"

MARKET_PANEL_PATH = DATA_DIR / "coimbatore_maize_market_panel_v3.csv"
DISTRICT_MODEL_V3_PATH = DATA_DIR / "coimbatore_maize_model_daily_v3.csv"
DISTRICT_SUMMARY_PATH = OUTPUTS_DIR / "maize_v3_split_experiment_summary.json"

SINGLE_MARKET_DATA_PATH = DATA_DIR / "udumalpet_maize_model_daily_v1.csv"
SINGLE_MARKET_VALIDATION_PATH = DATA_DIR / "udumalpet_maize_model_daily_v1_validation.json"
SUMMARY_JSON_PATH = OUTPUTS_DIR / "maize_single_market_experiment_summary.json"
SUMMARY_MD_PATH = OUTPUTS_DIR / "maize_single_market_experiment_summary.md"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _select_best_market(panel_df: pd.DataFrame) -> tuple[str, pd.DataFrame]:
    ranking = (
        panel_df.groupby("market_name")
        .agg(
            rows=("date", "size"),
            unique_days=("date", "nunique"),
            start=("date", "min"),
            end=("date", "max"),
            modal_missing=("modal_price", lambda s: int(s.isna().sum())),
            varieties=("variety", "nunique"),
        )
        .assign(span_days=lambda x: (x["end"] - x["start"]).dt.days)
        .sort_values(
            ["unique_days", "span_days", "rows", "modal_missing"],
            ascending=[False, False, False, True],
        )
    )
    selected_market = ranking.index[0]
    return selected_market, ranking.reset_index()


def _mode_or_nan(series: pd.Series):
    clean = series.dropna().astype(str)
    if clean.empty:
        return np.nan
    return clean.mode().iloc[0]


def _build_single_market_dataset(panel_df: pd.DataFrame, market_name: str) -> pd.DataFrame:
    market_df = panel_df.loc[panel_df["market_name"] == market_name].copy()
    market_df = market_df.sort_values(["date", "variety"]).reset_index(drop=True)

    grouped = (
        market_df.groupby("date")
        .agg(
            modal_price=("modal_price", "mean"),
            min_price=("min_price", "mean"),
            max_price=("max_price", "mean"),
            markets_reporting=("market_name", "nunique"),
            varieties_reporting=("variety", "nunique"),
            rows_reporting=("modal_price", "size"),
            tavg=("tavg", "mean"),
            tmin=("tmin", "mean"),
            tmax=("tmax", "mean"),
            prcp=("prcp", "mean"),
            wdir=("wdir", "mean"),
            wspd=("wspd", "mean"),
            pres=("pres", "mean"),
            msp_applicable=("msp_applicable", "mean"),
            msp_value_per_quintal=("msp_value_per_quintal", "mean"),
            govt_procurement_active=("govt_procurement_active", "mean"),
            pmfby_insurance_active=("pmfby_insurance_active", "mean"),
            state_scheme_active=("state_scheme_active", "mean"),
            harvest_season_active=("harvest_season_active", "mean"),
            price_impact_direction=("price_impact_direction", _mode_or_nan),
        )
        .reset_index()
    )
    grouped["market_name"] = market_name
    return grouped[
        [
            "date",
            "market_name",
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
    ]


def _build_validation_summary(
    single_market_df: pd.DataFrame,
    market_panel_df: pd.DataFrame,
    district_df: pd.DataFrame,
    market_name: str,
    ranking_df: pd.DataFrame,
) -> dict:
    missingness = {
        column: int(single_market_df[column].isna().sum())
        for column in single_market_df.columns
        if column not in {"date", "market_name"}
    }
    market_raw = market_panel_df.loc[market_panel_df["market_name"] == market_name].copy()

    validation = {
        "selected_market": market_name,
        "selection_reason": (
            "Selected as the strongest maize market by unique trading-day coverage, then span length, "
            "then total rows, using the existing v3 market panel."
        ),
        "market_ranking_top10": ranking_df.head(10).to_dict(orient="records"),
        "single_market_dataset": {
            "path": str(SINGLE_MARKET_DATA_PATH),
            "date_start": pd.Timestamp(single_market_df["date"].min()).strftime("%Y-%m-%d"),
            "date_end": pd.Timestamp(single_market_df["date"].max()).strftime("%Y-%m-%d"),
            "rows": int(len(single_market_df)),
            "unique_weeks": int(pd.to_datetime(single_market_df["date"]).dt.to_period("W").nunique()),
            "missingness": missingness,
            "variety_coverage": {
                "total_unique_varieties": int(market_raw["variety"].nunique()),
                "varieties": sorted(market_raw["variety"].dropna().astype(str).unique().tolist()),
                "median_varieties_per_day": float(market_raw.groupby("date")["variety"].nunique().median()),
            },
        },
        "district_average_v3": {
            "path": str(DISTRICT_MODEL_V3_PATH),
            "date_start": pd.Timestamp(district_df["date"].min()).strftime("%Y-%m-%d"),
            "date_end": pd.Timestamp(district_df["date"].max()).strftime("%Y-%m-%d"),
            "rows": int(len(district_df)),
            "unique_weeks": int(pd.to_datetime(district_df["date"]).dt.to_period("W").nunique()),
        },
        "comparison_against_district_average_v3": {
            "row_delta": int(len(single_market_df) - len(district_df)),
            "unique_week_delta": int(
                pd.to_datetime(single_market_df["date"]).dt.to_period("W").nunique()
                - pd.to_datetime(district_df["date"]).dt.to_period("W").nunique()
            ),
            "policy_complete_in_single_market": bool(
                single_market_df[POLICY_COLS + ["price_impact_direction"]].notna().all(axis=1).all()
            ),
            "single_market_has_cleaner_target_series_hypothesis": True,
        },
    }
    return validation


def _plot_single_market_model_comparison(summary: dict):
    exp_a = summary["single_market_experiment_a"]
    exp_b = summary["single_market_experiment_b"]

    holdout_a = pd.read_csv(exp_a["comparison_path"])
    holdout_b = pd.read_csv(exp_b["comparison_path"])

    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))
    for ax, frame, title in [
        (axes[0], holdout_a, "Single-Market Full-History (No Policy)"),
        (axes[1], holdout_b, "Single-Market Policy-Aware Subset"),
    ]:
        ax.bar(frame["model_name"], frame["rmse"], color=["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"])
        ax.set_title(title, fontsize=13, weight="bold")
        ax.set_ylabel("Holdout RMSE")
        ax.tick_params(axis="x", rotation=20)
        ax.grid(axis="y", alpha=0.25)
        for idx, value in enumerate(frame["rmse"]):
            ax.text(idx, value + 2, f"{value:.1f}", ha="center", va="bottom", fontsize=9)

    fig.suptitle("Single-Market Maize Model Comparison", fontsize=16, weight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(OUTPUTS_DIR / "maize_single_market_model_comparison.png", dpi=220)
    plt.close(fig)


def _plot_best_single_market_forecast(summary: dict):
    best_regime_key = summary["recommendation"]["single_market_demo_regime"]
    payload = summary[best_regime_key]
    pred_df = pd.read_csv(payload["predictions_path"], parse_dates=["date"])
    pred_col = f"pred_{payload['winner']}"

    fig, ax = plt.subplots(figsize=(12.5, 5.5))
    ax.plot(pred_df["date"], pred_df["actual"], label="Actual", color="#111111", linewidth=2.5)
    ax.plot(pred_df["date"], pred_df[pred_col], label=payload["winner"], color="#2ca02c", linewidth=2.1)
    ax.set_title(
        f"Best Single-Market Holdout Forecast: {summary['selected_market']}",
        fontsize=15,
        weight="bold",
    )
    ax.set_xlabel("Date")
    ax.set_ylabel("Modal price")
    ax.grid(alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUTPUTS_DIR / "maize_single_market_best_forecast_plot.png", dpi=220)
    plt.close(fig)


def _plot_district_vs_single_market(summary: dict, district_summary: dict):
    district_demo = district_summary[district_summary["recommendation"]["product_demo"]]
    single_demo = summary[summary["recommendation"]["single_market_demo_regime"]]

    labels = ["District-average", f"Single-market\n({summary['selected_market']})"]
    best_holdout = [district_demo["winner_metrics"]["rmse"], single_demo["winner_metrics"]["rmse"]]
    best_rolling = [
        district_demo["rolling"]["winner_metrics"]["rmse"],
        single_demo["rolling"]["winner_metrics"]["rmse"],
    ]
    naive = [
        district_demo["naive_last_value_baseline"]["rmse"],
        single_demo["naive_last_value_baseline"]["rmse"],
    ]

    x = np.arange(2)
    width = 0.24
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.bar(x - width, best_holdout, width, label="Best holdout RMSE", color="#2ca02c")
    ax.bar(x, best_rolling, width, label="Best rolling RMSE", color="#1f77b4")
    ax.bar(x + width, naive, width, label="Naive RMSE", color="#7f7f7f")

    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("RMSE")
    ax.set_title("District-Average vs Single-Market Demo Candidate", fontsize=15, weight="bold")
    ax.grid(axis="y", alpha=0.25)
    ax.legend()
    for xpos, values in [(x - width, best_holdout), (x, best_rolling), (x + width, naive)]:
        for xp, value in zip(xpos, values):
            ax.text(xp, value + 2, f"{value:.1f}", ha="center", va="bottom", fontsize=10)

    fig.tight_layout()
    fig.savefig(OUTPUTS_DIR / "maize_district_vs_single_market_comparison.png", dpi=220)
    plt.close(fig)


def _write_markdown_summary(summary: dict):
    md = f"""# Single-Market Maize Experiment Summary

## Market selection

- Selected market: `{summary['selected_market']}`
- Reason: it has the strongest usable maize coverage in the existing market panel.

## Dataset quality

- Single-market daily rows: {summary['single_market_dataset']['rows']}
- Weekly coverage after preprocessing:
  - Full-history regime: {summary['single_market_experiment_a']['rows']}
  - Policy-aware regime: {summary['single_market_experiment_b']['rows']}
- Variety coverage: {summary['single_market_dataset']['variety_coverage']['total_unique_varieties']} varieties

## Experiment results

- Full-history no-policy winner: `{summary['single_market_experiment_a']['winner']}` with holdout RMSE {summary['single_market_experiment_a']['winner_metrics']['rmse']:.2f}
- Policy-aware subset winner: `{summary['single_market_experiment_b']['winner']}` with holdout RMSE {summary['single_market_experiment_b']['winner_metrics']['rmse']:.2f}
- Demo candidate: `{summary['recommendation']['single_market_demo_regime']}`

## Direct comparison to district-average

- District demo baseline RMSE: {summary['district_average_reference']['demo_holdout_rmse']:.2f}
- Single-market demo RMSE: {summary['comparison_against_district_average']['single_market_demo_holdout_rmse']:.2f}
- Improvement vs district on holdout: {summary['comparison_against_district_average']['holdout_rmse_improvement_vs_district_demo']:.2f}
- Single-market rolling winner RMSE: {summary['comparison_against_district_average']['single_market_demo_rolling_rmse']:.2f}
- District demo rolling winner RMSE: {summary['comparison_against_district_average']['district_demo_rolling_rmse']:.2f}

## Recommendation

- Demo baseline: {summary['recommendation']['demo_baseline_choice']}
- Research baseline: {summary['recommendation']['research_baseline_choice']}
- Rationale: {summary['recommendation']['rationale']}
"""
    SUMMARY_MD_PATH.write_text(md, encoding="utf-8")


def main():
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    panel_df = pd.read_csv(MARKET_PANEL_PATH, parse_dates=["date"])
    district_df = pd.read_csv(DISTRICT_MODEL_V3_PATH, parse_dates=["date"])
    district_summary = _load_json(DISTRICT_SUMMARY_PATH)

    selected_market, ranking_df = _select_best_market(panel_df)
    single_market_df = _build_single_market_dataset(panel_df, selected_market)
    single_market_df.to_csv(SINGLE_MARKET_DATA_PATH, index=False)

    validation = _build_validation_summary(
        single_market_df=single_market_df,
        market_panel_df=panel_df,
        district_df=district_df,
        market_name=selected_market,
        ranking_df=ranking_df,
    )
    SINGLE_MARKET_VALIDATION_PATH.write_text(
        json.dumps(validation, indent=2, default=_serialize_for_json),
        encoding="utf-8",
    )

    policy_mask = single_market_df[POLICY_COLS + ["price_impact_direction"]].notna().all(axis=1)
    exp_a_df = _prepare_weekly_dataset(single_market_df.copy(), include_policy=False)
    exp_b_df = _prepare_weekly_dataset(single_market_df.loc[policy_mask].copy(), include_policy=True)

    exp_a = _run_holdout_experiment("single_market_experiment_a", exp_a_df, include_policy=False)
    exp_a["rolling"] = _run_rolling_backtest(
        "single_market_experiment_a",
        exp_a_df,
        include_policy=False,
    )

    exp_b = _run_holdout_experiment("single_market_experiment_b", exp_b_df, include_policy=True)
    exp_b["rolling"] = _run_rolling_backtest(
        "single_market_experiment_b",
        exp_b_df,
        include_policy=True,
    )

    single_market_demo_regime = (
        "single_market_experiment_b"
        if exp_b["winner_metrics"]["rmse"] <= exp_a["winner_metrics"]["rmse"]
        else "single_market_experiment_a"
    )
    single_market_research_regime = (
        "single_market_experiment_a"
        if exp_a["rolling"]["winner_metrics"]["rmse"] <= exp_b["rolling"]["winner_metrics"]["rmse"]
        else "single_market_experiment_b"
    )

    district_demo = district_summary[district_summary["recommendation"]["product_demo"]]
    district_research = district_summary[district_summary["recommendation"]["research_paper"]]
    single_demo = exp_b if single_market_demo_regime == "single_market_experiment_b" else exp_a
    single_research = exp_a if single_market_research_regime == "single_market_experiment_a" else exp_b

    summary = {
        "selected_market": selected_market,
        "single_market_dataset": validation["single_market_dataset"],
        "single_market_experiment_a": exp_a,
        "single_market_experiment_b": exp_b,
        "district_average_reference": {
            "summary_path": str(DISTRICT_SUMMARY_PATH),
            "demo_regime": district_summary["recommendation"]["product_demo"],
            "research_regime": district_summary["recommendation"]["research_paper"],
            "demo_holdout_rmse": district_demo["winner_metrics"]["rmse"],
            "demo_rolling_rmse": district_demo["rolling"]["winner_metrics"]["rmse"],
            "research_holdout_rmse": district_research["winner_metrics"]["rmse"],
            "research_rolling_rmse": district_research["rolling"]["winner_metrics"]["rmse"],
        },
        "comparison_against_district_average": {
            "single_market_demo_regime": single_market_demo_regime,
            "single_market_demo_holdout_rmse": single_demo["winner_metrics"]["rmse"],
            "single_market_demo_rolling_rmse": single_demo["rolling"]["winner_metrics"]["rmse"],
            "district_demo_holdout_rmse": district_demo["winner_metrics"]["rmse"],
            "district_demo_rolling_rmse": district_demo["rolling"]["winner_metrics"]["rmse"],
            "holdout_rmse_improvement_vs_district_demo": float(
                district_demo["winner_metrics"]["rmse"] - single_demo["winner_metrics"]["rmse"]
            ),
            "rolling_rmse_improvement_vs_district_demo": float(
                district_demo["rolling"]["winner_metrics"]["rmse"]
                - single_demo["rolling"]["winner_metrics"]["rmse"]
            ),
            "single_market_reduced_optimizer_issues": bool(
                not any(
                    "non-convergence" in " ".join(candidate.get("notes", []))
                    for candidate in [
                        exp_a["holdout_results"]["ARIMAX"],
                        exp_a["holdout_results"]["Hybrid_ARIMAX_LSTM"],
                        exp_b["holdout_results"]["ARIMAX"],
                        exp_b["holdout_results"]["Hybrid_ARIMAX_LSTM"],
                    ]
                )
            ),
        },
        "recommendation": {
            "single_market_demo_regime": single_market_demo_regime,
            "single_market_research_regime": single_market_research_regime,
            "demo_baseline_choice": (
                "switch to single-market maize"
                if single_demo["winner_metrics"]["rmse"] < district_demo["winner_metrics"]["rmse"]
                else "stay with district-average maize"
            ),
            "research_baseline_choice": (
                "switch to single-market maize"
                if single_research["rolling"]["winner_metrics"]["rmse"]
                < district_research["rolling"]["winner_metrics"]["rmse"]
                else "stay with district-average maize"
            ),
            "rationale": (
                "A single-market setup is preferred only if it improves recent holdout RMSE materially and "
                "does not regress rolling stability. Otherwise the district-average regime remains the safer baseline."
            ),
        },
    }

    SUMMARY_JSON_PATH.write_text(
        json.dumps(summary, indent=2, default=_serialize_for_json),
        encoding="utf-8",
    )
    _write_markdown_summary(summary)
    _plot_single_market_model_comparison(summary)
    _plot_best_single_market_forecast(summary)
    _plot_district_vs_single_market(summary, district_summary)

    print(SUMMARY_JSON_PATH)


if __name__ == "__main__":
    main()
