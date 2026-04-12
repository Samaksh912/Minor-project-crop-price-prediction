# All Crops Dry Run Report

Generated: 2026-04-11

## Scope
- Validated newly added daily files:
  - `apple_model_daily.csv`
  - `beetroot_model_daily.csv`
  - `lemon_model_daily.csv`
  - `ladies_finger_model_daily.csv`
- Executed dry-run inference/training fallback for all available crops:
  - `maize`, `bananagreen`, `beans`, `mango`, `apple`, `beetroot`, `lemon`, `ladies_finger`

## Data Checks (newly added daily files)
- All four files have expected schema (21 columns) and required fields present.
- Date columns parse correctly and files load without schema errors.
- `msp_value_per_quintal` is fully null in all 4 files:
  - `apple_model_daily.csv`: 475 nulls
  - `beetroot_model_daily.csv`: 572 nulls
  - `lemon_model_daily.csv`: 838 nulls
  - `ladies_finger_model_daily.csv`: 838 nulls

## Dry Run Results
| Crop | Source File | Status | Best Model | Forecast Length | RMSE | MAPE % |
|---|---|---|---|---:|---:|---:|
| maize | `coimbatore_maize_model_daily.csv` | OK | ARIMA | 90 | 124.85 | 3.34 |
| bananagreen | `bananagreen_model_daily.csv` | OK | Tabular_GBM | 90 | 411.41 | 9.66 |
| beans | `beans_model_daily.csv` | OK | Hybrid_ARIMAX_LSTM | 90 | 2838.68 | 26.70 |
| mango | `mango_model_daily.csv` | OK | Hybrid_ARIMAX_LSTM | 90 | 2219.46 | 10.81 |
| apple | `apple_model_daily.csv` | OK | Tabular_GBM | 90 | 2563.28 | 8.75 |
| beetroot | `beetroot_model_daily.csv` | OK | Tabular_GBM | 90 | 1052.97 | 15.22 |
| lemon | `lemon_model_daily.csv` | OK | Tabular_GBM | 90 | 1960.58 | 18.52 |
| ladies_finger | `ladies_finger_model_daily.csv` | OK | ARIMA | 90 | 906.78 | 22.69 |

## Important Observations
- Backend dry run completed successfully for all 8 crops.
- ARIMAX/Hybrid branches emit `exog contains inf or nans` warnings for crops with null `msp_value_per_quintal`.
- Pipeline still succeeds because model comparison selects a valid fallback model (often `Tabular_GBM`/`ARIMA`).

## Readiness Verdict
- You can proceed with backend development now (all crops run end-to-end and produce 90-day forecasts).
- Recommended cleanup before finalizing model quality comparisons: fill `msp_value_per_quintal` nulls with `0.0` in the 4 newly added `*_model_daily.csv` files.

