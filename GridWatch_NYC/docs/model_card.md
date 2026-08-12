# Model Card — 30-Day Corrective-Maintenance Risk

## Intended use
Prioritize synthetic assets for analyst review in a portfolio demonstration.

## Not intended for
- autonomous maintenance decisions
- safety-critical dispatch
- real MTA asset prediction
- replacement of engineering judgment

## Target
Corrective work order created within 30 days after a monthly asset snapshot.

## Inputs
Asset age, criticality, condition, inspection trend, recent incident counts, downtime, open/critical/overdue work, maintenance interval, repeat-failure flag, asset type, and borough.

## Evaluation
Performance is reported on a chronological holdout using PR-AUC, ROC-AUC, precision, recall, F1, Brier score, and a confusion matrix.

## Calibration and thresholding
Calibration and threshold selection occur before final holdout evaluation.

## Known limitations
The data-generating process is synthetic. Predictive performance therefore demonstrates methodology rather than real-world generalization.

## Governance required for production
Real deployment would require domain validation, documented model ownership, access controls, bias/error review, data lineage, monitoring, retraining policy, audit logging, and approval from safety/engineering stakeholders.
