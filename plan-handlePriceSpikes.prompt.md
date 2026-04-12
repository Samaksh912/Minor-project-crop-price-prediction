# Plan: Comprehensive Spike Detection & Handling Strategy
**TL;DR:** Implement a multi-tier spike detection system that classifies spikes by type (market, policy, weather, seasonal, anomalous), passes spike metadata through the model pipeline, adjusts model confidence based on spike context, and provides actionable spike risk scoring in forecasts.
## Spike Types
- **Market-driven**: Abrupt ≥15% weekly jump with sustained persistence (2+ weeks)
- **Policy-driven**: Aligns with policy change dates
- **Weather-driven**: Correlates with temp/rainfall anomalies >2σ
- **Seasonal**: Recurring harvest/off-season patterns
- **Anomalous**: Single-day outliers with no structural cause
## Implementation Steps
### Phase 1: Create spike_classifier.py
- Classify spike types using domain-specific rules
- Output spike classification DataFrame with confidence scores
### Phase 2: Enhance data_loader.py
- Integrate spike classifier after initial spike flag detection
- Add spike-type columns and metadata to DataFrame
- Ensure no data leakage
### Phase 3: Add config parameters
- SPIKE_HANDLING_MODE: 'exclude', 'downweight', 'separate', 'robust'
- Per-type exclusion thresholds and confidence penalties
### Phase 4: Modify model training (model.py)
- Apply spike handling per strategy
- Track spike-specific metrics (spike_mape_pct, normal_mape_pct)
### Phase 5: Enhance predictor inference (predictor.py)
- Return spike types, drivers, and confidence adjustments
- Update API response format
## Testing Strategy
- Unit tests for spike detection per type
- Integration tests for data leakage avoidance
- Model tests comparing spike vs. normal period RMSE
- Synthetic spike injection tests
- Backtest spike type detection on hold-out set (target: 75% recall, 60% precision)
## Expected Outcomes
- 70%+ precision/recall per spike type
- Improved forecast stability with confidence penalties
- Actionable driver attribution in API responses
- Better model selection with separate spike/normal metrics
