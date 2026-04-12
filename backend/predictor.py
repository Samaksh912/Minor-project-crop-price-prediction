from __future__ import annotations

import json
import logging
import os

os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
os.environ.setdefault(
    "MPLCONFIGDIR",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), ".mplconfig"),
)
os.makedirs(os.environ["MPLCONFIGDIR"], exist_ok=True)

import joblib
import numpy as np
import pandas as pd
from tensorflow.keras.models import load_model

from config import DATE_COL, FORECAST_HORIZON, LSTM_WINDOW, OUTPUTS_DIR, PRICE_COL
from evaluation import compare_models
from model import (
    _artifact_paths,
    _interpolate_weekly_to_daily,
    _lstm_autoregressive_forecast,
    _recursive_tabular_forecast,
    _tile_future_exog,
    model_exists,
    train_hybrid,
)
from output_generator import (
    save_forecast_csv,
    save_model_comparison_csv,
    save_predictions_csv,
)
from visualizer import (
    plot_actual_vs_predicted,
    plot_all_model_comparison,
    plot_feature_correlations,
    plot_forecast,
    plot_model_metrics_comparison,
    plot_residuals,
)


LOGGER = logging.getLogger(__name__)


def predict(crop_name: str, df: pd.DataFrame, force_retrain=False) -> dict:
    if force_retrain or not model_exists(crop_name):
        LOGGER.info("Artifacts missing or retrain requested; training fresh model for %s", crop_name)
        result = train_hybrid(df=df, crop_name=crop_name)
        _generate_outputs(crop_name, result, df)
        return result

    artifact_paths = _artifact_paths(crop_name)
    meta = joblib.load(artifact_paths["meta"])
    best_model_name = meta["best_model_name"]
    last_date = pd.Timestamp(meta["last_date"])
    first_date = pd.Timestamp(meta.get("first_date", pd.to_datetime(df[DATE_COL]).iloc[0]))
    last_actual = float(df[PRICE_COL].iloc[-1])

    try:
        if best_model_name == "ARIMA":
            arima_model = joblib.load(artifact_paths["arima"])
            weekly_forecast = np.asarray(arima_model.forecast(steps=FORECAST_HORIZON), dtype=float)

        elif best_model_name == "ARIMAX":
            arimax_model = joblib.load(artifact_paths["arimax"])
            last_x_row = pd.Series(meta["last_X_row"], index=meta["exog_columns"], dtype=float)
            future_exog = _tile_future_exog(last_x_row, FORECAST_HORIZON)
            weekly_forecast = np.asarray(
                arimax_model.forecast(steps=FORECAST_HORIZON, exog=future_exog),
                dtype=float,
            )

        elif best_model_name == "Hybrid_ARIMAX_LSTM":
            arimax_model = joblib.load(artifact_paths["arimax"])
            residual_model = load_model(artifact_paths["lstm"])
            residual_scaler = joblib.load(artifact_paths["scaler"])
            exog_columns = meta["exog_columns"]
            last_x_row = pd.Series(meta["last_X_row"], index=exog_columns, dtype=float)
            future_exog = _tile_future_exog(last_x_row, FORECAST_HORIZON)
            base_forecast = np.asarray(
                arimax_model.forecast(steps=FORECAST_HORIZON, exog=future_exog),
                dtype=float,
            )
            fitted_values = np.asarray(arimax_model.fittedvalues, dtype=float)
            residuals = df[PRICE_COL].astype(float).to_numpy() - fitted_values
            scaled_residuals = residual_scaler.transform(residuals.reshape(-1, 1)).reshape(-1)
            if len(scaled_residuals) < LSTM_WINDOW:
                raise RuntimeError("Not enough residual history to seed hybrid inference")
            residual_forecast = _lstm_autoregressive_forecast(
                model=residual_model,
                last_seq=scaled_residuals[-LSTM_WINDOW:],
                steps=FORECAST_HORIZON,
                scaler=residual_scaler,
            )
            weekly_forecast = base_forecast + residual_forecast

        elif best_model_name == "Standalone_LSTM":
            price_model = load_model(artifact_paths["lstm"])
            price_scaler = joblib.load(artifact_paths["price_scaler"])
            price_history = df[PRICE_COL].astype(float).to_numpy()
            if len(price_history) < LSTM_WINDOW:
                raise RuntimeError("Not enough price history to seed standalone LSTM inference")
            scaled_prices = price_scaler.transform(price_history.reshape(-1, 1)).reshape(-1)
            weekly_forecast = _lstm_autoregressive_forecast(
                model=price_model,
                last_seq=scaled_prices[-LSTM_WINDOW:],
                steps=FORECAST_HORIZON,
                scaler=price_scaler,
            )

        elif best_model_name == "Tabular_GBM":
            gbm_model = joblib.load(artifact_paths["gbr"])
            exog_columns = meta["exog_columns"]
            last_x_row = pd.Series(meta["last_X_row"], index=exog_columns, dtype=float)
            future_exog = _tile_future_exog(last_x_row, FORECAST_HORIZON)
            future_dates = pd.date_range(
                start=last_date + pd.Timedelta(days=7),
                periods=FORECAST_HORIZON,
                freq="7D",
            )
            weekly_forecast = _recursive_tabular_forecast(
                model=gbm_model,
                history_prices=df[PRICE_COL].astype(float).to_numpy(),
                future_dates=future_dates,
                future_exog=future_exog,
                first_date=first_date,
                feature_columns=meta["tabular_feature_columns"],
            )

        else:
            raise ValueError(f"Unsupported best_model_name: {best_model_name}")

    except Exception:
        LOGGER.exception("Inference failed for saved production model %s; retraining", best_model_name)
        result = train_hybrid(df=df, crop_name=crop_name)
        _generate_outputs(crop_name, result, df)
        return result

    daily_dates, daily_forecast = _interpolate_weekly_to_daily(
        last_date=last_date,
        last_actual=last_actual,
        weekly_forecast=weekly_forecast,
    )

    result = {
        "best_model_name": best_model_name,
        "forecast": daily_forecast,
        "dates": daily_dates,
        "weekly_forecast": weekly_forecast,
        "weekly_dates": pd.date_range(start=last_date + pd.Timedelta(days=7), periods=FORECAST_HORIZON, freq="7D"),
        "metrics": meta["metrics"],
        "all_metrics": meta["all_metrics"],
        "rolling_origin_metrics": meta.get("rolling_origin_metrics", {}),
        "last_date": last_date,
        "test_actuals": np.asarray([], dtype=float),
        "test_predicted": np.asarray([], dtype=float),
        "test_dates": pd.to_datetime([]),
        "all_test_predictions": {},
        "comparison": compare_models(meta["all_metrics"]),
    }

    evaluation_path = os.path.join(OUTPUTS_DIR, f"{crop_name}_evaluation_report.json")
    if os.path.exists(evaluation_path):
        try:
            with open(evaluation_path, "r", encoding="utf-8") as file_obj:
                report = json.load(file_obj)
            result["test_actuals"] = np.asarray(report.get("test_actuals", []), dtype=float)
            result["test_predicted"] = np.asarray(
                report.get("test_predictions", {}).get(best_model_name, []),
                dtype=float,
            )
            result["test_dates"] = pd.to_datetime(report.get("test_dates", []))
            result["all_test_predictions"] = {
                model_name: np.asarray(values, dtype=float)
                for model_name, values in report.get("test_predictions", {}).items()
            }
        except Exception:
            LOGGER.warning("Failed to read evaluation report at %s", evaluation_path, exc_info=True)

    _generate_outputs(crop_name, result, df)
    return result


def _generate_outputs(crop_name, result, df):
    try:
        comparison_df = result.get("comparison")
        if comparison_df is None or comparison_df.empty:
            comparison_df = compare_models(result.get("all_metrics", {}))

        if len(result.get("test_dates", [])) and len(result.get("test_actuals", [])):
            save_predictions_csv(
                crop_name=crop_name,
                dates=result["test_dates"],
                actual=result["test_actuals"],
                predicted=result["test_predicted"],
                all_predictions=result.get("all_test_predictions"),
            )
            plot_actual_vs_predicted(
                crop_name=crop_name,
                dates=result["test_dates"],
                actual=result["test_actuals"],
                predicted=result["test_predicted"],
            )
            plot_residuals(
                crop_name=crop_name,
                dates=result["test_dates"],
                actual=result["test_actuals"],
                predicted=result["test_predicted"],
            )
            if result.get("all_test_predictions"):
                plot_all_model_comparison(
                    crop_name=crop_name,
                    dates=result["test_dates"],
                    actual=result["test_actuals"],
                    all_predictions=result["all_test_predictions"],
                )

        save_forecast_csv(crop_name=crop_name, dates=result["dates"], forecast=result["forecast"])
        if comparison_df is not None and not comparison_df.empty:
            save_model_comparison_csv(crop_name=crop_name, comparison_df=comparison_df)
            plot_model_metrics_comparison(crop_name=crop_name, comparison_df=comparison_df)

        history_slice = df.tail(min(26, len(df)))
        plot_forecast(
            crop_name=crop_name,
            history_dates=history_slice[DATE_COL],
            history_values=history_slice[PRICE_COL],
            forecast_dates=result["dates"],
            forecast_values=result["forecast"],
        )
        plot_feature_correlations(crop_name=crop_name, df=df)
    except Exception:
        LOGGER.warning("Output generation failed for %s", crop_name, exc_info=True)

