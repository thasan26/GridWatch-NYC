from pathlib import Path
import numpy as np
import pandas as pd

START = pd.Timestamp("2024-01-31")
END = pd.Timestamp("2026-07-31")
HORIZON_DAYS = 30

def _counts(frame, date_col, start, end):
    if frame.empty:
        return pd.Series(dtype=int)
    x = frame[(frame[date_col] > start) & (frame[date_col] <= end)]
    return x.groupby("asset_id").size()

def build_longitudinal_features(raw_dir="data/raw", out_path="data/processed/asset_month_snapshots.csv"):
    raw = Path(raw_dir)
    assets = pd.read_csv(raw/"assets.csv")
    inspections = pd.read_csv(raw/"inspections.csv", parse_dates=["inspection_date"])
    incidents = pd.read_csv(raw/"incidents.csv", parse_dates=["incident_date"])
    wo = pd.read_csv(raw/"work_orders.csv", parse_dates=["created_date", "sla_due_date", "completed_date"])

    months = pd.date_range(START, END, freq="ME")
    rows = []

    for snap in months:
        frame = assets[["asset_id","asset_type","borough","required_skill","install_year","criticality","base_condition"]].copy()
        frame["snapshot_date"] = snap
        frame["age_years"] = np.maximum(0, snap.year - frame["install_year"]).astype(float)

        # Latest condition and last-four inspection trend, as known at the snapshot.
        hist_i = inspections[inspections["inspection_date"] <= snap].sort_values(["asset_id","inspection_date"])
        latest_i = hist_i.groupby("asset_id").tail(1).set_index("asset_id")["condition_score"]
        frame["condition_score"] = frame["asset_id"].map(latest_i).fillna(frame["base_condition"])

        trends = {}
        for aid, g in hist_i.groupby("asset_id"):
            tail = g.tail(4)
            trends[aid] = float(np.polyfit(np.arange(len(tail)), tail["condition_score"], 1)[0]) if len(tail) >= 2 else 0.0
        frame["inspection_trend"] = frame["asset_id"].map(trends).fillna(0.0)

        # Incident history windows.
        frame["incidents_30d"] = frame["asset_id"].map(_counts(incidents, "incident_date", snap-pd.Timedelta(days=30), snap)).fillna(0).astype(int)
        frame["incidents_90d"] = frame["asset_id"].map(_counts(incidents, "incident_date", snap-pd.Timedelta(days=90), snap)).fillna(0).astype(int)
        frame["incidents_365d"] = frame["asset_id"].map(_counts(incidents, "incident_date", snap-pd.Timedelta(days=365), snap)).fillna(0).astype(int)
        inc90 = incidents[(incidents["incident_date"] > snap-pd.Timedelta(days=90)) & (incidents["incident_date"] <= snap)]
        frame["downtime_90d"] = frame["asset_id"].map(inc90.groupby("asset_id")["downtime_hours"].sum()).fillna(0.0)

        # Work-order state at snapshot (not today's status field).
        known = wo[wo["created_date"] <= snap].copy()
        open_mask = known["completed_date"].isna() | (known["completed_date"] > snap)
        open_hist = known[open_mask]
        frame["open_work_orders"] = frame["asset_id"].map(open_hist.groupby("asset_id").size()).fillna(0).astype(int)
        frame["open_critical_work_orders"] = frame["asset_id"].map(
            open_hist[open_hist["priority"]=="Critical"].groupby("asset_id").size()
        ).fillna(0).astype(int)
        frame["overdue_work_orders"] = frame["asset_id"].map(
            open_hist[open_hist["sla_due_date"] < snap].groupby("asset_id").size()
        ).fillna(0).astype(int)

        completed = known[known["completed_date"].notna() & (known["completed_date"] <= snap)]
        last_maint = completed.groupby("asset_id")["completed_date"].max()
        last_date = frame["asset_id"].map(last_maint)
        frame["days_since_maintenance"] = (snap - pd.to_datetime(last_date)).dt.days.fillna(999).clip(0,999).astype(int)
        frame["repeat_failure_flag"] = (frame["incidents_90d"] >= 2).astype(int)

        # Strict future target. Raw data extends one month past END for this backtesting label.
        future_end = snap + pd.Timedelta(days=HORIZON_DAYS)
        future = wo[
            (wo["work_type"]=="Corrective")
            & (wo["created_date"] > snap)
            & (wo["created_date"] <= future_end)
        ]
        target = future.groupby("asset_id").size().gt(0).astype(int)
        frame["target_corrective_30d"] = frame["asset_id"].map(target).fillna(0).astype(int)

        rows.append(frame[[
            "snapshot_date","asset_id","asset_type","borough","required_skill","age_years","criticality",
            "condition_score","inspection_trend","incidents_30d","incidents_90d","incidents_365d","downtime_90d",
            "open_work_orders","open_critical_work_orders","overdue_work_orders","days_since_maintenance",
            "repeat_failure_flag","target_corrective_30d"
        ]])

    df = pd.concat(rows, ignore_index=True)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    print(f"Longitudinal snapshots: {len(df):,}")
    print(f"Positive events: {int(df.target_corrective_30d.sum()):,}")
    print(f"Event prevalence: {df.target_corrective_30d.mean():.2%}")
    print("Date range:", df.snapshot_date.min(), "to", df.snapshot_date.max())
    return df

if __name__ == "__main__":
    build_longitudinal_features()
