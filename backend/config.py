"""
config.py
---------
Central configuration for the BestCropPrice hybrid ARIMAX-LSTM backend.
"""

import os

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
DATA_DIR    = os.path.join(BASE_DIR, "data")
MODELS_DIR  = os.path.join(BASE_DIR, "models")
OUTPUTS_DIR = os.path.join(BASE_DIR, "outputs")
PLOTS_DIR   = os.path.join(OUTPUTS_DIR, "plots")
METRICS_DIR = os.path.join(OUTPUTS_DIR, "metrics")

for _d in (DATA_DIR, MODELS_DIR, OUTPUTS_DIR, PLOTS_DIR, METRICS_DIR):
    os.makedirs(_d, exist_ok=True)

# ---------------------------------------------------------------------------
# Data filenames
# ---------------------------------------------------------------------------
WEATHER_FILE = "formatted_weather.csv"
POLICY_FILE  = "coimbatore_crop_policy_2023_2026.csv"

# ---------------------------------------------------------------------------
# Column mappings — Crop CSVs
# ---------------------------------------------------------------------------
CROP_DATE_COL  = "t"           # raw date column in crop CSVs
CROP_PRICE_COL = "p_modal"     # raw modal-price column in crop CSVs

# Internal (standardised) column names used after loading
DATE_COL  = "date"
PRICE_COL = "price"

# ---------------------------------------------------------------------------
# Column mappings — Weather CSV
# ---------------------------------------------------------------------------
WEATHER_DATE_COL = "Price Date"
WEATHER_COLS = ["tavg", "tmin", "tmax", "prcp", "wdir", "wspd", "pres"]

# ---------------------------------------------------------------------------
# Column mappings — Policy CSV
# ---------------------------------------------------------------------------
POLICY_DATE_COL = "date"
POLICY_CROP_COL = "crop"
POLICY_NUMERIC_COLS = [
    "msp_value_per_quintal",
]
POLICY_BINARY_COLS = [
    "msp_applicable",
    "govt_procurement_active",
    "pmfby_insurance_active",
    "state_scheme_active",
    "harvest_season_active",
    "export_promotion_active",
]

# Map crop CSV filename stems to the crop name used in the policy file
CROP_NAME_MAP = {
    "apple":        "Apple",
    "banana-green": "Banana-Green",
    "beans":        "Beans",
    "beetroot":     "Beetroot",
    "maize":        "Maize",
    "mango":        "Mango",
}

# ---------------------------------------------------------------------------
# Feature engineering parameters
# ---------------------------------------------------------------------------
LAG_PERIODS     = [1, 7, 30]           # in original daily units (mapped to weekly later)
ROLLING_WINDOWS = [7, 14, 30]          # same
WEEKLY_LAG_PERIODS  = [1, 2, 4]        # ~1 week, ~2 weeks, ~1 month
WEEKLY_ROLL_WINDOWS = [4, 8, 13]       # ~1 month, ~2 months, ~3 months

# ---------------------------------------------------------------------------
# Train / test split
# ---------------------------------------------------------------------------
TRAIN_SPLIT_RATIO = 0.80

# ---------------------------------------------------------------------------
# Model hyper-parameters
# ---------------------------------------------------------------------------
FORECAST_HORIZON = 13       # weeks (~90 days / 7 ≈ 13 weeks)
FORECAST_DAYS    = 90       # for API output (daily interpolation)
LSTM_WINDOW      = 4        # lookback window (weeks) for LSTM residual model
ARIMAX_ORDER     = (2, 1, 2)
LSTM_UNITS       = 64
LSTM_DROPOUT     = 0.2
LSTM_EPOCHS      = 150
LSTM_BATCH_SIZE  = 16
EARLY_STOP_PAT   = 15
# Minimum number of training sequences required before activating the LSTM
# residual model. Below this threshold, Hybrid falls back to pure ARIMAX.
# Rule of thumb: need enough data to learn nonlinear patterns, not just noise.
LSTM_MIN_SEQUENCES = 50

# ---------------------------------------------------------------------------
# Data-quality thresholds
# ---------------------------------------------------------------------------
NAN_DROP_THRESHOLD = 0.90
IQR_MULTIPLIER     = 1.5   # for outlier removal
