# BestCropPrice — Production-Grade Forecasting System

A robust, modular **Flask REST API** that uses a hybrid **ARIMAX + LSTM** model to predict crop modal prices for the next **90 days**. It includes advanced feature engineering, automatic column mapping, outlier removal, robust handling of missing policy/weather data, and full evaluation on unseen test data.

---

## Architecture & Modules

```
backend/
├── api.py               # Flask server (Endpoints: predict, train, train-all, evaluate)
├── config.py            # Model parameters, column mappings, outputs configuration
├── data_loader.py       # Data cleaning, alignment, and Feature Engineering
├── evaluation.py        # Metrics computation (RMSE, MAE, MAPE) and model comparison
├── model.py             # Time-series Split, ARIMAX + LSTM training, Baselines
├── output_generator.py  # Generates CSV outputs for predictions and metrics
├── predictor.py         # Inference wrapper orchestrating ML + Output generation
├── train_all.py         # Convenience script to train all crops sequentially
├── visualizer.py        # Matplotlib visualization generation
├── requirements.txt     # Python dependencies
├── data/
│   ├── formatted_weather.csv               ← Required
│   ├── apple.csv, banana-green.csv, etc.   ← Crop datasets
│   └── coimbatore_crop_policy_2023_2026.csv ← Policy dataset (MSP, etc.)
├── models/              ← Saved model artifacts (ARIMAX weights, LSTM keras, scalers)
└── outputs/             ← Auto-generated system outputs
    ├── metrics/         # model_comparison JSON reports
    ├── plots/           # Actual vs Predicted, Residuals, Correlations, Forecasts
    └── *.csv            # 90-day forecasts and test set predictions
```

---

## Setup & Running

```powershell
cd C:\bestcropprice\backend

# Install dependencies
pip install -r requirements.txt

# Initial Training (Train all crops and generate all output plots/CSVs)
python train_all.py

# Start the API Server
python api.py
```

Server runs on `http://localhost:5000`.

---

## API Endpoints

### `GET /api/health`
Status check.

### `GET /api/crops`
List all crops found in the data directory.

### `POST /api/predict`
Get a 90-day price forecast and summary statistics for charts.
**Request:** `{ "crop": "apple", "force_retrain": false }`
**Response:** JSON with 90-day daily interpolated forecast, stats, and evaluation metrics. Includes baseline comparisons.

### `GET /api/evaluate/<crop>`
Get the detailed Train/Test evaluation report including ARIMA, ARIMAX, LSTM-only, and Hybrid metrics.

### `POST /api/train` and `POST /api/train-all`
Force a retrain of one or all models, overwriting the saved artifacts and outputs.

---

## Data Pipeline Details

### Preprocessing & Alignment
- **Column Remapping**: Automatically maps CSV `t` and `p_modal` columns to standard names (`date`, `price`).
- **Outlier Removal**: Uses IQR bounds (1.5x) to remove extreme price spikes/drops.
- **Weekly Resampling**: Averages daily data to weekly frequency to reduce noise and stabilize the LSTM.
- **Graceful Degradation**: 
  - If policy data does not match the crop name, or MSP values are missing/zero, policy features are automatically skipped.
  - If weather data does not overlap the crop dates, the system aligns as best as possible.

### Feature Engineering
The pipeline automatically generates the following features:
1. **Lags**: 1-week, 2-week, 4-week historical prices.
2. **Rolling Statistics**: 4-week, 8-week, 13-week rolling means and standard deviations.
3. **Weather Anomalies**: Deviation of temperature and rainfall from their recent 4-week rolling average.
4. **Policy Indicators**: Price minus MSP, Price / MSP, and a binary indicator if the price is below MSP.

### Model Evaluation
- **Chronological Split**: 80% Train, 20% Test (strictly unseen chronological data, no shuffling).
- **Baselines**: ARIMA (no exog), ARIMAX (with exog/features), Standalone LSTM.
- **Hybrid**: ARIMAX to catch linear/seasonal trends + LSTM on the residuals to capture non-linear patterns.
- After evaluating on the 20% test set, the system automatically **re-trains on the 100% full dataset** to provide the 90-day forward forecast.
- **Limitations**: Crops with very small datasets (e.g. Apple only starting from July 2024) will naturally exhibit high test-set error margins due to lack of historical seasonality.
