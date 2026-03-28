# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**BestCropPrice** — a crop modal price forecasting system for 6 crops (apple, banana-green, beans, beetroot, maize, mango) in Coimbatore district, Tamil Nadu. Predicts 90-day daily prices using a hybrid ARIMAX + LSTM model exposed via a Flask REST API.

Model training is intended to run on **Kaggle** and produce a **ZIP archive** of all outputs (models, CSVs, plots) at the end.

---

## Commands

All commands run from `backend/`:

```bash
# Install dependencies
pip install -r requirements.txt

# Train all crops (generates models + outputs)
python train_all.py

# Start Flask API server (port 5000)
python api.py

# Train a specific crop via API
curl -X POST http://localhost:5000/api/predict -H "Content-Type: application/json" -d '{"crop": "apple"}'

# Get evaluation metrics
curl http://localhost:5000/api/evaluate/apple
```

---

## Architecture & Data Flow

```
data/ (CSV files)
    ├── {crop}.csv          → load_crop()
    ├── formatted_weather.csv → load_weather()
    └── coimbatore_crop_policy_2023_2026.csv → load_policy()
            ↓
    data_loader.load_and_align()
        • remove_outliers() — IQR 1.5×
        • align_all() — merge_asof backward on date
        • resample_weekly() — mean aggregation
        • engineer_features() — lags, rolling stats, weather anomaly, policy
            ↓
    model.train_hybrid()
        • 80/20 chronological split (no shuffle)
        • Baselines: ARIMA, ARIMAX, standalone LSTM
        • Hybrid: ARIMAX on y_train → residuals → LSTM on residuals
        • Evaluate on held-out test set
        • Re-train on 100% data for production forecast
        • 90-day weekly forecast → interpolate to daily
            ↓
    predictor.predict()   ← orchestrates training + output generation
            ↓
    outputs/ (CSVs, plots, metric JSONs)
    models/ (ARIMAX .pkl, LSTM .keras, scaler .pkl, meta .pkl)
```

**Column name mapping** (raw CSV → internal):
- Crop: `t` → `date`, `p_modal` → `price`
- Weather date: `Price Date` → `date`
- Policy crop lookup via `CROP_NAME_MAP` in `config.py`

**Per-crop artifacts saved** (`models/{crop}_*.pkl / .keras`):
- `_arimax.pkl` — fitted ARIMAX model (joblib)
- `_lstm.keras` — LSTM residual model (only if ≥50 sequences available)
- `_scaler.pkl` — MinMaxScaler for residuals
- `_meta.pkl` — last_date, last_X_row, exog_columns, metrics

---

## Known Bugs (to be fixed)

These bugs were identified by analysis and must be addressed:

### 1. Data Leakage in Exogenous Variables (Critical)
`engineer_features()` computes lag features (`price_lag_1`, `price_lag_4`, etc.) across the **entire dataset** before the train/test split. When `X_test` (which contains lags computed from actual test prices) is passed to ARIMAX's `forecast()`, the model receives future price information. This causes maize to show RMSE=0.0 — a perfect score that is impossible without leakage. Fix: exclude price-derived lag/rolling features from `X_test` during evaluation, or only pass truly exogenous features (weather, policy) to ARIMAX.

### 2. Best Model Not Used in Production (Critical)
After `compare_models()`, the system always saves/uses the Hybrid (which falls back to pure ARIMAX for small datasets), even when ARIMA clearly outperforms it (e.g., apple ARIMA MAPE=10% vs ARIMAX MAPE=76%). The comparison is printed to logs but the result is never used to select the production model. Fix: after comparison, select the best model by RMSE and use it for the production forecast and saved artifacts.

### 3. Insufficient Data for Most Crops
After the full pipeline, most crops produce only 20–25 usable weekly rows because crop price data only spans ~5 months (mid-2025 onward) while weather data starts from 2020. 20 rows → 16 training samples with 23–30 exogenous features = extreme ARIMAX overfitting. The LSTM minimum of 50 sequences is never reached for these crops. Root cause: needs crop price CSVs from 2020–2025 to fully align with weather data.

---

## Configuration (`config.py`)

Key parameters to know when modifying model behavior:

| Parameter | Value | Meaning |
|---|---|---|
| `LSTM_MIN_SEQUENCES` | 50 | Below this, LSTM is skipped; Hybrid = pure ARIMAX |
| `LSTM_WINDOW` | 4 | Weeks of lookback for LSTM |
| `ARIMAX_ORDER` | (2,1,2) | SARIMAX p,d,q order |
| `TRAIN_SPLIT_RATIO` | 0.80 | 80% train, 20% test |
| `FORECAST_HORIZON` | 13 | Weeks ahead for forecast |
| `FORECAST_DAYS` | 90 | Daily interpolation output |
| `IQR_MULTIPLIER` | 1.5 | Outlier removal aggressiveness |

---

## Kaggle Training Requirements

When adapting `train_all.py` for Kaggle:
- All outputs go to `outputs/` and `models/` directories
- At the end of training, ZIP all artifacts: `outputs/`, `models/`, and the metric JSONs
- The ZIP should be created as the final step so it can be downloaded from Kaggle as a dataset output
- Kaggle has TensorFlow available; no special flags needed beyond `TF_ENABLE_ONEDNN_OPTS=0` to suppress oneDNN warnings

---

## API Endpoints Summary

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/health` | Health check |
| GET | `/api/crops` | List available crops |
| POST | `/api/predict` | 90-day forecast (`{"crop": "apple"}`) |
| POST | `/api/train` | Force retrain one crop |
| POST | `/api/train-all` | Retrain all crops |
| GET | `/api/evaluate/<crop>` | Model comparison metrics JSON |
