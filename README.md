# GridWatch NYC

### Reliability Engineering, Predictive Maintenance & Decision Analytics Platform

**Python · SQL · Machine Learning · Optimization · Streamlit · Power BI · Excel**

GridWatch NYC is an end-to-end analytics portfolio project that transforms synthetic urban rail power-infrastructure data into **risk intelligence, maintenance priorities, workforce optimization, scenario planning, and management-ready decision support**.

> **Portfolio disclaimer:** All operational data in this project is synthetic. No confidential, proprietary, or internal MTA data is used. This project is not affiliated with or endorsed by the MTA or New York City Transit.

---

## Executive Command Center

The Command Center brings asset risk, maintenance backlog, predictive signals, and recommended actions into a single operational view.

![GridWatch NYC Command Center](screenshots/command-center.png)

### Executive KPIs

| Metric | Current View |
|---|---:|
| Assets monitored | 1,000 |
| Critical-risk assets | 5 |
| Model-flagged assets | 286 |
| Open work orders | 195 |
| Overdue work orders | 145 |
| Operational snapshot | 2026-07-31 |

The goal is to move beyond static reporting and answer a more useful management question: **what requires attention next, and why?**

---

## Business Problem

Infrastructure maintenance teams must balance asset condition, incident history, overdue work, limited technician capacity, and competing operational priorities. GridWatch NYC demonstrates an analytical workflow for turning those signals into a structured decision process.

**Decision flow:**

`Operational Data → Quality Controls → Feature Engineering → Predictive Risk → Prioritization → Optimization → Scenario Testing → Management Decision Support`

---

## Asset Intelligence

The Asset Intelligence view provides asset-level drill-down analysis using the same operational history that feeds the predictive model.

![Asset Intelligence](screenshots/asset-intelligence.png)

It combines **30-day modeled risk, condition score, incident history, criticality, inspections, and work-order history** to provide an interpretable operational profile and recommended action.

### Condition Trend Analysis

![Inspection History](screenshots/inspection-history.png)

Historical inspection scores help identify deterioration patterns and provide context for model-generated risk signals.

---

## Maintenance Optimizer

Predictive analytics becomes more valuable when it can support resource-allocation decisions. The Maintenance Optimizer evaluates technician skills, labor capacity, work-order priority, SLA deadlines, job duration, and modeled asset risk.

![Maintenance Optimizer](screenshots/maintenance-optimizer.png)

### Optimization Snapshot

| Metric | Result |
|---|---:|
| Priority points scheduled | 1,678 |
| Unresolved weighted priority | 1,140 |
| Jobs assigned | 40 |
| Improvement vs. rule-based baseline | **20.3%** |
| Solver status | **Optimal** |

### Technician Utilization

![Technician Utilization](screenshots/technician-utilization.png)

This layer connects predictive insights to an operational question: **given limited labor capacity, which work should be scheduled first?**

---

## Scenario Planning

Scenario Planning compares alternative maintenance strategies under the same resource constraints.

![Scenario Planning](screenshots/scenario-planning.png)

The platform compares **risk-first**, **SLA/backlog-first**, and **optimized** allocation strategies. In the displayed synthetic scenario, the optimized plan schedules 40 jobs, reaches 97.0% labor utilization, and achieves a 59.4% weighted-risk reduction.

### Capacity Stress Test

![Capacity Stress Test](screenshots/capacity-stress-test.png)

Capacity stress testing measures how residual weighted risk changes as maintenance capacity increases or decreases, helping identify where additional resources produce the strongest modeled benefit.

---

## Predictive Modeling & Validation

GridWatch NYC includes a chronological machine-learning validation workflow for predicting future corrective-maintenance events.

![Model Validation](screenshots/model-validation.png)

### Selected Model — Histogram Gradient Boosting

| Holdout Metric | Result |
|---|---:|
| PR-AUC | **0.178** |
| ROC-AUC | **0.711** |
| Precision | **14.4%** |
| Recall | **59.1%** |
| Brier score | **0.064** |
| Operating threshold | **7.2%** |

Validation includes **chronological holdout testing, precision-recall analysis, probability calibration, confusion-matrix evaluation, feature-importance analysis, and threshold selection**.

The model is designed for **prioritization and decision support**, not autonomous maintenance decisions.

---

## Data Quality & Controls

Analytics outputs are only useful when the underlying data is trustworthy. GridWatch NYC includes automated controls for identifiers, referential integrity, valid ranges, dates, nulls, targets, technician capacity, and backlog realism.

![Data Quality and Controls](screenshots/data-quality.png)

**15 / 15 automated validation checks pass** in the current project snapshot.

---

## Data Lineage, Freshness & Governance

The project separates raw synthetic operational history from leakage-controlled modeling snapshots and manager-facing current-state views.

![Data Governance](screenshots/data-governance.png)

The workflow explicitly accounts for **temporal leakage, backtesting horizons, snapshot freshness, holdout evaluation, and production-governance limitations**.

---

## Analytics Architecture

```text
Synthetic Asset Registry
        │
        ├── Inspection History
        ├── Incident History
        └── Maintenance Work Orders
                    │
                    ▼
          Data Quality Controls
                    │
                    ▼
        Monthly Asset Snapshots
                    │
                    ▼
           Feature Engineering
                    │
                    ▼
      30-Day Maintenance-Risk Model
                    │
          ┌─────────┴─────────┐
          ▼                   ▼
 Risk Prioritization   Model Validation
          │
          ▼
 Maintenance Optimization
          │
          ▼
   Scenario / Capacity Testing
          │
          ▼
 Management Decision Support
```

---

## Technology Stack

| Area | Technologies |
|---|---|
| Data analysis | Python, Pandas, NumPy |
| Querying / data work | SQL |
| Machine learning | scikit-learn |
| Visualization | Plotly, Matplotlib |
| Interactive application | Streamlit |
| Business intelligence | Power BI |
| Operational reporting | Excel |
| Version control | Git, GitHub |

---

## What This Project Demonstrates

### Data Analytics
- KPI design and operational reporting
- Asset-condition and incident analysis
- Maintenance backlog and SLA analysis
- Trend analysis and decision-oriented visualization

### Machine Learning
- Feature engineering
- Predictive maintenance classification
- Chronological train/validation/holdout design
- Precision-recall and ROC evaluation
- Probability calibration
- Threshold selection and model interpretation

### Optimization & Operations Analytics
- Resource-constrained maintenance scheduling
- Technician skill/capacity allocation
- Priority-based optimization
- Strategy comparison
- Capacity stress testing

### Data Quality & Governance
- Referential-integrity controls
- Range and null validation
- Leakage-aware analytical snapshots
- Backtesting controls
- Data lineage and freshness checks

### Business Intelligence
- Executive KPI design
- Interactive decision dashboards
- Risk prioritization
- Management-facing recommendations
- Translating technical outputs into operational actions

---

## Business Value

GridWatch NYC demonstrates the progression from traditional descriptive reporting to decision analytics:

**What happened?** → operational KPIs and historical analysis  
**What is likely to happen?** → predictive maintenance risk  
**What deserves attention?** → risk-based prioritization  
**What should we do with limited resources?** → maintenance optimization  
**What happens if capacity changes?** → scenario and stress testing

The result is a portfolio case study that connects **data analysis, machine learning, optimization, visualization, and business decision support** in one coherent workflow.

---

## Disclaimer

GridWatch NYC is an independent educational and professional portfolio project. **All data is synthetic.** It is not affiliated with, endorsed by, or developed for the Metropolitan Transportation Authority (MTA) or New York City Transit, and it contains no confidential or internal agency information.
