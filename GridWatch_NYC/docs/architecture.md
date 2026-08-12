# Architecture

GridWatch separates data generation, longitudinal feature engineering, predictive modeling, optimization, scenario analysis, and presentation.

## Analytical flow

```text
Raw operational records
        ↓
Data-quality checks
        ↓
Asset-month snapshots
        ↓
Temporal train / validation / holdout split
        ↓
Model comparison + calibration
        ↓
Frozen operating threshold
        ↓
Current asset-risk scores
        ↓
Priority engine
        ↓
Technician-capacity optimization
        ↓
Scenario stress testing
        ↓
Manager-facing Streamlit application
```

The August 2026 raw horizon exists only to provide future labels for the July 31, 2026 backtesting snapshot. Manager-facing pages filter current-state data to July 31.
