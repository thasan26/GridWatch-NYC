-- SQL-side data quality checks

SELECT 'orphan_incidents' AS check_name, COUNT(*) AS failures
FROM fact_incident i
LEFT JOIN dim_asset a ON a.asset_id=i.asset_id
WHERE a.asset_id IS NULL

UNION ALL

SELECT 'orphan_work_orders', COUNT(*)
FROM fact_work_order w
LEFT JOIN dim_asset a ON a.asset_id=w.asset_id
WHERE a.asset_id IS NULL

UNION ALL

SELECT 'invalid_condition_scores', COUNT(*)
FROM fact_inspection
WHERE condition_score NOT BETWEEN 0 AND 100

UNION ALL

SELECT 'invalid_completion_dates', COUNT(*)
FROM fact_work_order
WHERE completed_date IS NOT NULL AND completed_date < created_date;
