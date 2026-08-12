# Methodology

## Target
For an asset at month-end, predict whether a **corrective work order will be created within the next 30 days**.

## Leakage control
Features are calculated using only records dated on or before the snapshot. Future corrective work is used only to create the target.

## Validation design
Chronological periods are used rather than a random split:
- training through 2025-12-31
- validation through 2026-04-30
- later holdout beginning 2026-05-01

The validation period is used for calibration and threshold selection. The later holdout is not used for those choices.

## Candidate models
- Logistic Regression
- Histogram Gradient Boosting

The selected model is chosen by validation-period PR-AUC.

## Calibration
Raw model scores are passed through Platt-style logistic calibration fitted on the validation period.

## Threshold
The operating threshold is selected on validation data with recall emphasized. This is a portfolio decision threshold, not an engineering safety limit.

## Optimization
A mixed-integer optimization problem maximizes weighted scheduled priority subject to technician-skill compatibility and labor-hour capacity.

## Scenario analysis
The decision objective can rebalance modeled risk, SLA urgency, asset criticality, and condition deterioration. Capacity is stress-tested from 50% to 120% of the baseline labor pool.
