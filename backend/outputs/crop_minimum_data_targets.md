# Crop Minimum Data Targets (3-Month Forecasting)

Assumptions: weekly modeling, lag burn-in=13, train/test=80/20, horizon=13 weeks, LSTM window=4, LSTM min sequences=40.

- Minimum usable weekly rows required: **66**
- Robust target usable weekly rows: **113** (train/exog >= 5 with ~18 exogenous features)

| Crop | Weekly total | Weekly observed | Usable after lag13 | Train/Test | LSTM seq | Gap to min | Gap to robust | Verdict |
|---|---:|---:|---:|---|---:|---:|---:|---|
| apple | 249 | 96 | 236 | 188/48 | 184 | 0 | 0 | READY |
| banana-green | 46 | 30 | 33 | 26/7 | 22 | 33 | 80 | NOT_READY |
| beans | 46 | 30 | 33 | 26/7 | 22 | 33 | 80 | NOT_READY |
| beetroot | 251 | 108 | 238 | 190/48 | 186 | 0 | 0 | READY |
| maize | 138 | 128 | 125 | 100/25 | 96 | 0 | 0 | READY |
| mango | 46 | 27 | 33 | 26/7 | 22 | 33 | 80 | NOT_READY |

Interpretation: `READY` means it clears minimum data quantity; it does not guarantee strong accuracy. Sparse observed-week coverage can still hurt generalization.