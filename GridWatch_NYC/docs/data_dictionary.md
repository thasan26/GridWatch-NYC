# Data Dictionary

## assets.csv
- `asset_id`: synthetic unique asset identifier
- `asset_type`: Substation, Circuit Breaker House, Feeder Cable, Third Rail Segment
- `borough`: synthetic operating geography
- `install_year`: installation year
- `age_years`: age at operational as-of date
- `criticality`: 1–5 portfolio criticality indicator
- `base_condition`: initial synthetic condition score
- `required_skill`: technician skill required for maintenance

## inspections.csv
- `asset_id`
- `inspection_date`
- `condition_score`: 0–100
- `condition_band`: Good, Fair, Poor, Critical

## incidents.csv
- `incident_id`
- `asset_id`
- `incident_date`
- `severity`
- `downtime_hours`
- `incident_type`

## work_orders.csv
- `work_order_id`
- `asset_id`
- `work_type`: Preventive or Corrective
- `priority`: Medium, High, Critical
- `created_date`
- `sla_due_date`
- `completed_date`
- `status`: Completed, Open, or Future
- `estimated_hours`
- `required_skill`

## asset_month_snapshots.csv
Monthly modeling table containing only information available as of each snapshot date, plus the future 30-day target.
