# Maize V3 Split Experiment

Tabular model used: `GradientBoostingRegressor`

Reason: XGBoost is not available in the current environment, so the experiment uses the sklearn fallback without changing the backend dependency stack.

## Experiment A — Full-history, no-policy

- Weekly rows: 292
- Date range: 2020-04-05 to 2025-11-02
- Holdout winner: Hybrid_ARIMAX_LSTM with RMSE 218.526
- Rolling winner: ARIMA with RMSE 141.804
- Naive last-value RMSE: 237.737

## Experiment B — Policy-aware subset

- Weekly rows: 127
- Date range: 2023-06-04 to 2025-11-02
- Holdout winner: ARIMA with RMSE 113.419
- Rolling winner: ARIMA with RMSE 143.323
- Naive last-value RMSE: 113.090

## Recommendation

- Better regime for product/demo: experiment_b
- Better regime for research paper: experiment_a
- Evidence summary: Experiment A measures whether longer history plus weather-only exogenous structure is enough. Experiment B measures whether policy/MSP features justify discarding the older pre-policy years. The recommendation prefers recent holdout performance for the product/demo when that gap is materially larger, but still values longer-history rolling stability for the research direction.
