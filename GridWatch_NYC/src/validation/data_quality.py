from pathlib import Path
import json
import pandas as pd

AS_OF = pd.Timestamp("2026-07-31")

def run_quality_checks(raw_dir="data/raw", snapshot_path="data/processed/asset_month_snapshots.csv"):
    raw = Path(raw_dir)
    assets = pd.read_csv(raw/"assets.csv")
    inspections = pd.read_csv(raw/"inspections.csv", parse_dates=["inspection_date"])
    incidents = pd.read_csv(raw/"incidents.csv", parse_dates=["incident_date"])
    wo = pd.read_csv(raw/"work_orders.csv", parse_dates=["created_date","sla_due_date","completed_date"])
    tech = pd.read_csv(raw/"technicians.csv")
    snaps = pd.read_csv(snapshot_path, parse_dates=["snapshot_date"])

    asset_ids = set(assets["asset_id"])
    checks = []

    def add(name, passed, value, expectation):
        checks.append({"check":name, "passed":bool(passed), "value":value, "expectation":expectation})

    add("Unique asset IDs", assets["asset_id"].is_unique, int(assets["asset_id"].nunique()), "All asset IDs unique")
    add("Unique incident IDs", incidents["incident_id"].is_unique, int(incidents["incident_id"].nunique()), "All incident IDs unique")
    add("Unique work-order IDs", wo["work_order_id"].is_unique, int(wo["work_order_id"].nunique()), "All work-order IDs unique")
    add("Inspection referential integrity", set(inspections["asset_id"]).issubset(asset_ids), int((~inspections["asset_id"].isin(asset_ids)).sum()), "0 orphan rows")
    add("Incident referential integrity", set(incidents["asset_id"]).issubset(asset_ids), int((~incidents["asset_id"].isin(asset_ids)).sum()), "0 orphan rows")
    add("Work-order referential integrity", set(wo["asset_id"]).issubset(asset_ids), int((~wo["asset_id"].isin(asset_ids)).sum()), "0 orphan rows")
    add("Condition-score range", inspections["condition_score"].between(0,100).all(), f"{inspections['condition_score'].min():.1f}–{inspections['condition_score'].max():.1f}", "0–100")
    add("Criticality range", assets["criticality"].between(1,5).all(), f"{assets['criticality'].min()}–{assets['criticality'].max()}", "1–5")
    add("Positive job durations", (wo["estimated_hours"]>0).all(), float(wo["estimated_hours"].min()), "> 0")
    add("SLA dates valid", (wo["sla_due_date"]>=wo["created_date"]).all(), int((wo["sla_due_date"]<wo["created_date"]).sum()), "0 invalid")
    valid_completed = wo["completed_date"].isna() | (wo["completed_date"]>=wo["created_date"])
    add("Completion dates valid", valid_completed.all(), int((~valid_completed).sum()), "0 invalid")
    add("Snapshot null control", snaps.isna().sum().sum()==0, int(snaps.isna().sum().sum()), "0 null feature values")
    add("Snapshot target binary", set(snaps["target_corrective_30d"].unique()).issubset({0,1}), sorted(snaps["target_corrective_30d"].unique().tolist()), "Only 0/1")
    add("Technician capacity positive", (tech["available_hours"]>0).all(), float(tech["available_hours"].min()), "> 0")

    current = wo[(wo["created_date"]<=AS_OF) & ((wo["completed_date"].isna()) | (wo["completed_date"]>AS_OF))]
    overdue = current[current["sla_due_date"]<AS_OF]
    old_open = current[(AS_OF-current["created_date"]).dt.days>90]
    add("Aged-backlog realism", len(old_open) <= max(5, int(len(current)*0.12)), int(len(old_open)), "≤12% or ≤5 open jobs older than 90 days")

    report = {
        "overall_status": "PASS" if all(x["passed"] for x in checks) else "REVIEW",
        "checks_passed": int(sum(x["passed"] for x in checks)),
        "checks_total": int(len(checks)),
        "as_of": str(AS_OF.date()),
        "records": {
            "assets": int(len(assets)),
            "inspections": int(len(inspections)),
            "incidents": int(len(incidents)),
            "work_orders": int(len(wo)),
            "technicians": int(len(tech)),
            "asset_month_snapshots": int(len(snaps)),
            "current_open_work_orders": int(len(current)),
            "current_overdue_work_orders": int(len(overdue)),
        },
        "freshness": {
            "latest_inspection": str(inspections["inspection_date"].max().date()),
            "latest_incident_raw_horizon": str(incidents["incident_date"].max().date()),
            "latest_work_order_raw_horizon": str(wo["created_date"].max().date()),
            "latest_model_snapshot": str(snaps["snapshot_date"].max().date()),
        },
        "checks": checks,
    }
    Path("reports").mkdir(exist_ok=True)
    with open("reports/data_quality_report.json","w",encoding="utf-8") as f:
        json.dump(report,f,indent=2)
    print(f"Data quality: {report['overall_status']} ({report['checks_passed']}/{report['checks_total']} checks)")
    return report

if __name__ == "__main__":
    run_quality_checks()
