import os


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
MODELS_DIR = os.path.join(BASE_DIR, "models")
OUTPUTS_DIR = os.path.join(BASE_DIR, "outputs")
PLOTS_DIR = os.path.join(BASE_DIR, "plots")

for _path in (DATA_DIR, MODELS_DIR, OUTPUTS_DIR, PLOTS_DIR):
    os.makedirs(_path, exist_ok=True)

CROP_NAME = "maize"
DAILY_FILE = "coimbatore_maize_model_daily_v3.csv"
DATE_COL = "date"
PRICE_COL = "modal_price"
EXOG_WEATHER_COLS = ["tavg", "tmin", "tmax", "prcp", "wdir", "wspd", "pres"]
EXOG_POLICY_COLS = [
    "msp_applicable",
    "msp_value_per_quintal",
    "govt_procurement_active",
    "pmfby_insurance_active",
    "state_scheme_active",
    "harvest_season_active",
]
WEEKLY_LAG_PERIODS = [1, 4, 13]
WEEKLY_ROLL_WINDOWS = [4, 8, 13]
TRAIN_SPLIT_RATIO = 0.80
FORECAST_HORIZON = 13
FORECAST_DAYS = 90
LSTM_WINDOW = 4
ARIMAX_ORDER = (2, 1, 2)
LSTM_UNITS = 64
LSTM_DROPOUT = 0.2
LSTM_EPOCHS = 150
LSTM_BATCH_SIZE = 16
EARLY_STOP_PAT = 15
LSTM_MIN_SEQUENCES = 40
IQR_MULTIPLIER = 1.5

