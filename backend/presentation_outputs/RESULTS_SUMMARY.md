# Maize Forecasting Results Summary

## Dataset evolution

- V1 covered 2023-03-15 to 2024-12-31 with 416 daily rows and 85 unique weeks, but weather coverage still had gaps.
- V2 extended the weather-aligned modeling horizon to 2025-10-30 and reached 701 daily rows with zero key weather/policy missingness.
- V3 expanded the real maize history back to 2020-01-02 and reached 1190 daily rows and 273 unique weeks, but pre-2023 policy fields remain missing.

## Experiment comparison

- Experiment A, full-history without policy features: best holdout model was `Hybrid_ARIMAX_LSTM` with RMSE 218.53; best rolling model was `ARIMA` with RMSE 141.80.
- Experiment B, policy-aware subset: best holdout model was `ARIMA` with RMSE 113.42; best rolling model was `ARIMA` with RMSE 143.32.
- For the demo decision, the current evidence favors `experiment_b` because its recent holdout performance is materially stronger.
- For the research framing, the current evidence favors `experiment_a` because it preserves the longer historical regime while staying competitive in rolling evaluation.

## Current strength

- The current result is directionally useful but not strong enough to present as a solved forecasting problem.
- The policy-aware subset currently gives the best recent holdout accuracy, but it is still essentially tied with the naive baseline.
- SARIMAX-family models also continue to show convergence warnings, so stability is still a concern.

## Recommended next step

- Use this pack for a credible progress review, not a claims-heavy final result.
- Next modeling work should focus on beating the naive baseline consistently before any stronger product or paper claim is made.
