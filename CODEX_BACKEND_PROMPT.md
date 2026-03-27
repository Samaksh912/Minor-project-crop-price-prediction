# BestCropPrice Backend: Final Approved Codex Prompt

This file captures the final validated prompt for Codex after architectural review and corrections.

Key validated constraints:
- No price leakage into ARIMAX
- Best model by test RMSE must drive production
- `meta.pkl` is the inference source of truth
- All 4 winning-model inference paths must work
- Artifact naming must be explicit by model type
- Sparse trading-date gaps must be preserved through weekly resampling

---

## Final Prompt for Codex

Build the complete Python backend for `BestCropPrice` — a maize price forecasting system for Coimbatore, Tamil Nadu. This is a research backend trained on Kaggle and served via a Flask REST API.

Use the existing project structure and keep the implementation production-style, modular, and fully runnable.

## DATASET

Two CSV files already exist in `backend/data/`:

1. `coimbatore_maize_model_daily.csv`
- Primary modeling dataset
- Columns:
  `date, modal_price, min_price, max_price, markets_reporting, varieties_reporting, rows_reporting, tavg, tmin, tmax, prcp, wdir, wspd, pres, msp_applicable, msp_value_per_quintal, govt_procurement_active, pmfby_insurance_active, state_scheme_active, harvest_season_active, price_impact_direction`

2. `coimbatore_maize_market_panel.csv`
- Supplementary market-level dataset
- Not used for direct modeling in this backend

The data is already merged. No alignment with external files is needed.

## HIGH-LEVEL RULES

1. No price leakage into ARIMAX.
Only truly external features may be passed to `exog=` in SARIMAX.
Allowed ARIMAX exog:
- weather columns
- policy columns
- weather-only derived anomalies
- optionally encoded policy-direction metadata

Forbidden in ARIMAX exog:
- `price_lag_*`
- `price_rmean_*`
- `price_rstd_*`
- `price_pct_change`
- `price_minus_msp`
- `price_over_msp`
- `below_msp`
- any other feature derived from `modal_price`

2. Best model wins production.
After test-set comparison, select the model with lowest RMSE and retrain that exact model on full data for production artifacts and 90-day forecasting.

3. Single crop only.
`CROP_NAME = "maize"`.

4. Use SARIMAX, not ARIMA class.
Always use `SARIMAX(..., enforce_stationarity=False, enforce_invertibility=False)` and `fit(disp=False, maxiter=200)`.

5. Kaggle output.
`train_kaggle.py` must zip `models/` and `outputs/` into one downloadable archive at the end.

6. Use Python logging throughout.

7. Suppress TensorFlow noise with:
- `os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")`
- `os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")`

## FILES TO CREATE

Create exactly these files inside `backend/`:

### `config.py`

Constants only.
Include:
- path constants and `os.makedirs`
- `CROP_NAME = "maize"`
- `DAILY_FILE = "coimbatore_maize_model_daily.csv"`
- `DATE_COL = "date"`
- `PRICE_COL = "modal_price"`
- `EXOG_WEATHER_COLS = ["tavg", "tmin", "tmax", "prcp", "wdir", "wspd", "pres"]`
- `EXOG_POLICY_COLS = ["msp_applicable", "msp_value_per_quintal", "govt_procurement_active", "pmfby_insurance_active", "state_scheme_active", "harvest_season_active"]`
- `WEEKLY_LAG_PERIODS = [1, 4, 13]`
- `WEEKLY_ROLL_WINDOWS = [4, 8, 13]`
- `TRAIN_SPLIT_RATIO = 0.80`
- `FORECAST_HORIZON = 13`
- `FORECAST_DAYS = 90`
- `LSTM_WINDOW = 4`
- `ARIMAX_ORDER = (2, 1, 2)`
- `LSTM_UNITS = 64`
- `LSTM_DROPOUT = 0.2`
- `LSTM_EPOCHS = 150`
- `LSTM_BATCH_SIZE = 16`
- `EARLY_STOP_PAT = 15`
- `LSTM_MIN_SEQUENCES = 40`
- `IQR_MULTIPLIER = 1.5`

### `data_loader.py`

Expose:
- `load_data() -> pd.DataFrame`
- `get_exog_cols(df) -> list[str]`

Processing steps:
1. Read `DAILY_FILE`, parse `date`, sort ascending.
2. Drop rows with missing `modal_price`.
3. Remove modal-price outliers using IQR.
4. Encode `price_impact_direction` safely:
 - lowercase the `price_impact_direction` column values before calling `pd.get_dummies()` so all resulting `dir_*` columns are lowercase (`dir_price_floor`, `dir_neutral`, `dir_upward`, `dir_downward`)
 - before one-hot encoding, map any unknown or unmapped `price_impact_direction` value to `"neutral"`
 - set an explicit ordered categorical before one-hot encoding, for example `["price_floor", "neutral", "upward", "downward"]`, so the dropped reference category is deterministic across runs
 - use `drop_first=True` in `pd.get_dummies()` so one direction category is dropped as the reference class and the ARIMAX exog matrix does not have perfect multicollinearity
 - one-hot encode into columns such as
  `dir_neutral`, `dir_upward`, `dir_downward` with one dropped reference category (for example `dir_price_floor`)
 - after one-hot encoding, drop the original `price_impact_direction` string column before weekly resampling
5. Set date index and resample weekly with `mean` for numeric columns.
6. Do not call `dropna()` after weekly resampling. The dataset contains sparse trading dates, and weekly gaps must be preserved and filled using `ffill()` / `bfill()` to maintain time-series continuity.
7. After weekly resampling, forward-fill then backward-fill `PRICE_COL` to preserve target continuity across gap weeks. `PRICE_COL` must never be filled with 0.
8. Forward-fill then backward-fill weather and policy columns, then fill remaining numeric NaNs in those columns with column means.
9. Engineer safe exogenous features:
- `temp_anomaly = tavg - rolling_mean_4(tavg)`
- `rain_anomaly = prcp - rolling_mean_4(prcp)`
10. Engineer price-derived features for non-ARIMAX use only:
- `price_lag_1`, `price_lag_4`, `price_lag_13`
- `price_rmean_4`, `price_rmean_8`, `price_rmean_13`
- `price_rstd_4`, `price_rstd_8`, `price_rstd_13`
- `price_pct_change`
11. Drop first 13 rows after lag engineering.
12. Fill remaining numeric NaNs with 0, but never overwrite `PRICE_COL` during this step.
13. Return final weekly DataFrame.

`get_exog_cols(df)` must return only:
- weather columns
- policy columns
- one-hot policy-direction columns
- `temp_anomaly`
- `rain_anomaly`

`get_exog_cols(df)` must explicitly exclude:
- `markets_reporting`
- `varieties_reporting`
- `rows_reporting`
- `min_price`
- `max_price`
- all `price_*` engineered features

Weekly mean of one-hot encoded direction columns is intentional. It represents the proportion of observed trading days in that week belonging to each direction class, and this is consistent with future exog tiling.

### `evaluation.py`

Implement:
- `compute_metrics(actual, predicted) -> dict`
- `compare_models(results: dict) -> pd.DataFrame`
- `save_evaluation_report(crop_name, data: dict) -> str`

Metrics:
- `rmse`
- `mae`
- `mape_pct`

Handle NaNs safely and ignore invalid models in ranking.

### `model.py`

Main function:
- `train_hybrid(df: pd.DataFrame, crop_name: str) -> dict`

Required helpers:
- `_build_lstm_model(window)`
- `_build_sequences(data, window)`
- `_lstm_autoregressive_forecast(model, last_seq, steps, scaler)`
- `model_exists(crop_name)`

Training flow:
1. Prepare:
- `y = df[PRICE_COL].values`
- `dates = df[DATE_COL].values`
- `X_exog = df[get_exog_cols(df)]`

2. Chronological 80/20 split.

3. Train baselines:
- ARIMA using SARIMAX without exog
- ARIMAX using only `X_exog`
- Standalone LSTM on price only

Wrap every baseline SARIMAX fit in `try/except`. On failure, log a warning and return NaN metrics for that model instead of aborting training.

4. Train hybrid:
- ARIMAX on `y_train, X_exog_train`
- residuals on train
- LSTM on residuals if enough sequences
- hybrid test forecast = ARIMAX forecast + residual forecast

5. Compare models by RMSE.

6. Select best model.

7. Retrain best model on full data:
- ARIMA full
- ARIMAX full with only `X_exog`
- Hybrid full
- Standalone LSTM full

If full-data retraining of the winning model fails, log the failure and fall back to the next-best valid model by RMSE until one retrains successfully.

8. Produce 13-week forecast.
- For ARIMAX-based models, future exog = tiled last exog row
- Interpolate weekly forecast to 90 daily outputs

9. Save artifacts based on `best_model_name`:
- `"ARIMA"`: `{crop}_arima.pkl` + `{crop}_meta.pkl`
- `"ARIMAX"`: `{crop}_arimax.pkl` + `{crop}_meta.pkl`
- `"Hybrid_ARIMAX_LSTM"`: `{crop}_arimax.pkl` + `{crop}_lstm.keras` + `{crop}_scaler.pkl` + `{crop}_meta.pkl`
- `"Standalone_LSTM"`: `{crop}_lstm.keras` + `{crop}_price_scaler.pkl` + `{crop}_meta.pkl`

Remove stale artifacts from previous runs that no longer apply.

`meta.pkl` must include:
- `last_date`
- `last_X_row`
- `exog_columns`
- `best_model_name`
- `metrics`
- `all_metrics`
- `train_size`
- `test_size`
- `total_size`

For `ARIMA`:
- `last_X_row = None`
- `exog_columns = []`

Inference must not attempt to construct `future_exog` when `best_model_name == "ARIMA"`.

`model_exists(crop_name)` should validate `meta.pkl` and then confirm model-specific artifacts required by `best_model_name`.

Return:
- `forecast`
- `dates`
- `metrics`
- `all_metrics`
- `last_date`
- `test_actuals`
- `test_predicted`
- `test_dates`
- `all_test_predictions`

`test_predicted` must be the test-set forecast of `best_model_name`, not always the Hybrid forecast.
`all_test_predictions` must be a dict mapping each model name to its full test-set forecast array:
- `"ARIMA": np.ndarray`
- `"ARIMAX": np.ndarray`
- `"Standalone_LSTM": np.ndarray`
- `"Hybrid_ARIMAX_LSTM": np.ndarray`

If a model failed or was skipped, its value must be `np.full(len(y_test), np.nan)`.

The evaluation report dict passed to `save_evaluation_report()` must include:
- `"test_predictions"`: dict of `{model_name: forecast_array.tolist()}` for all 4 models
- `"test_actuals"`: `y_test.tolist()`
- `"test_dates"`: list of date strings

These are required for `_generate_outputs()` to produce the all-model comparison plot.

### `predictor.py`

Implement:
- `predict(crop_name: str, df: pd.DataFrame, force_retrain=False) -> dict`
- `_generate_outputs(crop_name, result, df)`

Behavior:
- retrain if forced or missing valid artifacts
- otherwise use `meta.pkl` to determine winning production model and load correct artifacts
- output generation should be non-fatal

Inference must branch on `meta["best_model_name"]` and load only the relevant artifacts. All 4 model types must have working inference paths:
- ARIMA: `forecast(steps=FORECAST_HORIZON)` with no exog
- ARIMAX: `forecast(steps=FORECAST_HORIZON, exog=future_exog)`
- Hybrid: ARIMAX forecast plus LSTM residual autoregressive forecast
- Standalone LSTM: reconstruct `last_seq` from the tail of `df[PRICE_COL]`, scale it, forecast autoregressively, then inverse transform

For `Standalone_LSTM` inference, load `{crop}_price_scaler.pkl` (the scaler fitted on price). Do not use `{crop}_scaler.pkl`, which is reserved for Hybrid residual scaling.

For `Hybrid` inference: load the ARIMAX model, compute its `fittedvalues` against `df[PRICE_COL]` to get current residuals, scale them with `{crop}_scaler.pkl`, then use the last `LSTM_WINDOW` scaled residuals as the LSTM seed sequence for autoregressive forecasting.

`meta.pkl` is the source of truth for selecting the inference path.

### `output_generator.py`

Implement:
- `save_predictions_csv`
- `save_forecast_csv`
- `save_model_comparison_csv`

### `visualizer.py`

Implement plots saved into `PLOTS_DIR`:
- actual vs predicted
- residuals
- forecast
- feature correlations
- model metrics comparison
- all-model comparison

### `train_all.py`

Load data and train maize with `force_retrain=True`.

### `train_kaggle.py`

Same as `train_all.py`, then create ZIP archive of `models/` and `outputs/`.

ZIP path must be:
- `os.path.join(BASE_DIR, "bestcropprice_outputs.zip")`

Print the absolute ZIP path after creation.

### `api.py`

Flask API on port 5000.

Endpoints:
- `GET /api/health`
- `GET /api/crops`
- `POST /api/predict`
- `POST /api/train`
- `GET /api/evaluate/<crop>`

Rules:
- only valid crop is `maize`
- return structured JSON errors
- evaluation endpoint should omit large arrays from response for brevity

### `requirements.txt`

Include:
- `flask>=3.0`
- `pandas>=2.0`
- `numpy>=1.26`
- `statsmodels>=0.14`
- `tensorflow>=2.16`
- `scikit-learn>=1.4`
- `joblib>=1.3`
- `matplotlib>=3.8`

## FINAL NON-NEGOTIABLE CONSTRAINTS

1. Never pass price-derived features into ARIMAX.
2. Never use `price_minus_msp`, `price_over_msp`, or `below_msp` as exogenous predictors.
3. Best test RMSE model must drive production retraining.
4. `LSTM_MIN_SEQUENCES = 40`.
5. Kaggle ZIP output is required.
6. `meta.pkl` is the inference source of truth.
7. All 4 model-specific inference paths must work.
8. Artifact naming must follow the explicit model-specific rules above.
9. Use clean logging and working code only.
