-- GridWatch NYC advanced analytical queries

-- 1. Latest inspection + 90-day incident burden + current open-work exposure.
WITH latest_inspection AS (
    SELECT asset_id, inspection_date, condition_score,
           ROW_NUMBER() OVER (PARTITION BY asset_id ORDER BY inspection_date DESC) AS rn
    FROM fact_inspection
),
recent_incidents AS (
    SELECT asset_id,
           COUNT(*) AS incidents_90d,
           SUM(downtime_hours) AS downtime_90d,
           SUM(CASE WHEN severity IN ('High','Critical') THEN 1 ELSE 0 END) AS severe_incidents_90d
    FROM fact_incident
    WHERE incident_date >= DATE '2026-05-02'
      AND incident_date <= DATE '2026-07-31'
    GROUP BY asset_id
),
open_work AS (
    SELECT asset_id,
           COUNT(*) AS open_work_orders,
           SUM(CASE WHEN priority='Critical' THEN 1 ELSE 0 END) AS open_critical_work,
           SUM(CASE WHEN sla_due_date < DATE '2026-07-31' THEN 1 ELSE 0 END) AS overdue_work
    FROM fact_work_order
    WHERE created_date <= DATE '2026-07-31'
      AND (completed_date IS NULL OR completed_date > DATE '2026-07-31')
    GROUP BY asset_id
)
SELECT
    a.asset_id,
    a.asset_type,
    a.borough,
    a.criticality,
    li.condition_score,
    COALESCE(r.incidents_90d,0) AS incidents_90d,
    COALESCE(r.downtime_90d,0) AS downtime_90d,
    COALESCE(r.severe_incidents_90d,0) AS severe_incidents_90d,
    COALESCE(w.open_work_orders,0) AS open_work_orders,
    COALESCE(w.open_critical_work,0) AS open_critical_work,
    COALESCE(w.overdue_work,0) AS overdue_work
FROM dim_asset a
LEFT JOIN latest_inspection li ON a.asset_id=li.asset_id AND li.rn=1
LEFT JOIN recent_incidents r ON a.asset_id=r.asset_id
LEFT JOIN open_work w ON a.asset_id=w.asset_id;

-- 2. SLA aging profile with percentile context.
WITH open_jobs AS (
    SELECT
        work_order_id,
        asset_id,
        priority,
        created_date,
        sla_due_date,
        DATE '2026-07-31' - sla_due_date AS days_past_sla,
        estimated_hours
    FROM fact_work_order
    WHERE created_date <= DATE '2026-07-31'
      AND (completed_date IS NULL OR completed_date > DATE '2026-07-31')
)
SELECT
    *,
    PERCENT_RANK() OVER (ORDER BY days_past_sla) AS backlog_age_percentile,
    SUM(estimated_hours) OVER (PARTITION BY priority) AS labor_hours_by_priority
FROM open_jobs
ORDER BY days_past_sla DESC;

-- 3. Repeat-failure ranking using rolling incident history.
WITH asset_incidents AS (
    SELECT
        asset_id,
        incident_date,
        downtime_hours,
        COUNT(*) OVER (
            PARTITION BY asset_id
            ORDER BY incident_date
            RANGE BETWEEN INTERVAL '90 days' PRECEDING AND CURRENT ROW
        ) AS rolling_90d_incidents,
        SUM(downtime_hours) OVER (
            PARTITION BY asset_id
            ORDER BY incident_date
            RANGE BETWEEN INTERVAL '90 days' PRECEDING AND CURRENT ROW
        ) AS rolling_90d_downtime
    FROM fact_incident
),
latest AS (
    SELECT *,
           ROW_NUMBER() OVER (PARTITION BY asset_id ORDER BY incident_date DESC) AS rn
    FROM asset_incidents
)
SELECT
    a.asset_id,
    a.asset_type,
    a.criticality,
    l.rolling_90d_incidents,
    l.rolling_90d_downtime,
    DENSE_RANK() OVER (
        ORDER BY l.rolling_90d_incidents DESC, l.rolling_90d_downtime DESC
    ) AS repeat_failure_rank
FROM latest l
JOIN dim_asset a ON a.asset_id=l.asset_id
WHERE l.rn=1
ORDER BY repeat_failure_rank;

-- 4. Monthly corrective-work trend with a 3-month moving average.
WITH monthly AS (
    SELECT
        DATE_TRUNC('month', created_date) AS month,
        COUNT(*) FILTER (WHERE work_type='Corrective') AS corrective_work_orders,
        SUM(estimated_hours) FILTER (WHERE work_type='Corrective') AS corrective_hours
    FROM fact_work_order
    GROUP BY 1
)
SELECT
    month,
    corrective_work_orders,
    corrective_hours,
    AVG(corrective_work_orders) OVER (
        ORDER BY month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
    ) AS corrective_wo_3mo_avg
FROM monthly
ORDER BY month;
