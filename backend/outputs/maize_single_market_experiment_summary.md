# Single-Market Maize Experiment Summary

## Market selection

- Selected market: `Udumalpet`
- Reason: it has the strongest usable maize coverage in the existing market panel.

## Dataset quality

- Single-market daily rows: 862
- Weekly coverage after preprocessing:
  - Full-history regime: 291
  - Policy-aware regime: 127
- Variety coverage: 2 varieties

## Experiment results

- Full-history no-policy winner: `ARIMA` with holdout RMSE 697.15
- Policy-aware subset winner: `ARIMAX` with holdout RMSE 264.51
- Demo candidate: `single_market_experiment_b`

## Direct comparison to district-average

- District demo baseline RMSE: 113.42
- Single-market demo RMSE: 264.51
- Improvement vs district on holdout: -151.09
- Single-market rolling winner RMSE: 389.75
- District demo rolling winner RMSE: 143.32

## Recommendation

- Demo baseline: stay with district-average maize
- Research baseline: stay with district-average maize
- Rationale: A single-market setup is preferred only if it improves recent holdout RMSE materially and does not regress rolling stability. Otherwise the district-average regime remains the safer baseline.
