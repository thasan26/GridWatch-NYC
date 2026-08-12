from pathlib import Path
import numpy as np
import pandas as pd

SEED = 42
AS_OF = pd.Timestamp("2026-07-31")
RAW_END = pd.Timestamp("2026-08-31")
START = pd.Timestamp("2024-01-01")

ASSET_TYPES = ["Substation", "Circuit Breaker House", "Feeder Cable", "Third Rail Segment"]
BOROUGHS = ["Manhattan", "Brooklyn", "Queens", "Bronx"]
SKILLS = {
    "Substation": "power",
    "Circuit Breaker House": "breaker",
    "Feeder Cable": "cable",
    "Third Rail Segment": "third_rail",
}

def _rng():
    return np.random.default_rng(SEED)

def generate_assets(n_assets=1000):
    rng = _rng()
    asset_type = rng.choice(ASSET_TYPES, n_assets, p=[0.18, 0.22, 0.35, 0.25])
    age = rng.integers(1, 41, n_assets)
    criticality = np.clip(np.round(rng.normal(3.2, 1.0, n_assets)), 1, 5).astype(int)
    base_condition = np.clip(100 - age * 1.15 + rng.normal(0, 7, n_assets), 30, 100)
    borough = rng.choice(BOROUGHS, n_assets, p=[0.25, 0.30, 0.28, 0.17])
    install_year = AS_OF.year - age
    return pd.DataFrame({
        "asset_id": [f"AST-{i:05d}" for i in range(1, n_assets + 1)],
        "asset_type": asset_type,
        "borough": borough,
        "install_year": install_year,
        "age_years": age,
        "criticality": criticality,
        "base_condition": np.round(base_condition, 1),
        "required_skill": [SKILLS[x] for x in asset_type],
    })

def generate_inspections(assets):
    rng = np.random.default_rng(SEED + 1)
    rows = []
    dates = pd.date_range(START, AS_OF, freq="90D")
    degradation = dict(zip(assets.asset_id, rng.uniform(0.35, 1.45, len(assets))))
    for r in assets.itertuples(index=False):
        for i, d in enumerate(dates):
            score = np.clip(r.base_condition - degradation[r.asset_id] * i + rng.normal(0, 3.3), 18, 100)
            band = "Critical" if score < 45 else "Poor" if score < 60 else "Fair" if score < 75 else "Good"
            rows.append((r.asset_id, d.date(), round(float(score), 1), band))
    return pd.DataFrame(rows, columns=["asset_id", "inspection_date", "condition_score", "condition_band"])

def generate_incidents(assets, inspections):
    rng = np.random.default_rng(SEED + 2)
    latest = inspections.sort_values("inspection_date").groupby("asset_id").tail(1)[["asset_id", "condition_score"]]
    frame = assets.merge(latest, on="asset_id", how="left")
    span = (RAW_END - START).days
    rows = []
    incident_id = 1
    for r in frame.itertuples(index=False):
        # Persistent asset propensity creates learnable, longitudinal reliability differences.
        annual_lambda = np.clip(
            0.10
            + 0.014 * r.age_years
            + 0.19 * (r.criticality - 1)
            + 0.018 * max(0, 72 - r.condition_score),
            0.08,
            3.8,
        )
        count = rng.poisson(annual_lambda * span / 365.25)
        for _ in range(count):
            dt = START + pd.to_timedelta(int(rng.integers(0, span + 1)), unit="D")
            severity = rng.choice(["Low", "Medium", "High", "Critical"], p=[0.35, 0.35, 0.23, 0.07])
            multiplier = {"Low": 0.6, "Medium": 1.0, "High": 1.8, "Critical": 3.0}[severity]
            downtime = max(0.4, rng.gamma(2.0, 1.35) * multiplier)
            kind = rng.choice(["Electrical fault", "Overheating", "Protection trip", "Inspection finding", "Physical damage"])
            rows.append((f"INC-{incident_id:06d}", r.asset_id, dt.date(), severity, round(float(downtime), 1), kind))
            incident_id += 1
    return pd.DataFrame(rows, columns=["incident_id", "asset_id", "incident_date", "severity", "downtime_hours", "incident_type"])

def generate_work_orders(assets, inspections, incidents):
    rng = np.random.default_rng(SEED + 3)
    rows = []
    wo_id = 1

    def add_order(asset_id, skill, work_type, priority, created, hours):
        nonlocal wo_id
        created = pd.Timestamp(created)
        sla_days = {"Medium": 10, "High": 5, "Critical": 2}[priority]
        due = created + pd.Timedelta(days=sla_days)
        repair_days = max(0.5, float(rng.gamma(2.0, 1.8)))
        completed = created + pd.Timedelta(days=repair_days)

        if created > AS_OF:
            status = "Future"
            completed_out = completed.date()
        else:
            # Current backlog is concentrated in recent work, with a small realistic overdue tail.
            age_at_asof = (AS_OF - created).days
            open_prob = 0.05
            if priority == "Critical":
                open_prob += 0.12
            if age_at_asof <= 45:
                open_prob += 0.30
            if age_at_asof <= 14:
                open_prob += 0.22
            is_open = rng.random() < min(open_prob, 0.72)
            if age_at_asof > 90:
                is_open = rng.random() < 0.025
            if completed > AS_OF:
                is_open = True
            status = "Open" if is_open else "Completed"
            completed_out = None if is_open else min(completed, AS_OF).date()

        rows.append((
            f"WO-{wo_id:07d}", asset_id, work_type, priority, created.date(), due.date(),
            completed_out, status, round(float(hours), 1), skill
        ))
        wo_id += 1

    # Preventive program
    for a in assets.itertuples(index=False):
        interval_days = 180 if a.criticality >= 4 else 270 if a.criticality == 3 else 365
        offset = int(rng.integers(0, interval_days))
        for created in pd.date_range(START + pd.Timedelta(days=offset), RAW_END, freq=f"{interval_days}D"):
            hours = np.clip(rng.normal(5.0, 1.4), 1.5, 10)
            add_order(a.asset_id, a.required_skill, "Preventive", "Medium", created, hours)

    # Incident-triggered corrective work
    asset_skill = assets.set_index("asset_id")["required_skill"].to_dict()
    for inc in incidents.itertuples(index=False):
        p = {"Low": 0.35, "Medium": 0.58, "High": 0.84, "Critical": 0.97}[inc.severity]
        if rng.random() <= p:
            created = pd.Timestamp(inc.incident_date) + pd.Timedelta(days=int(rng.integers(0, 4)))
            if created > RAW_END:
                continue
            priority = "Critical" if inc.severity == "Critical" else "High" if inc.severity == "High" else "Medium"
            hours = np.clip(rng.normal(8.0 if priority == "Critical" else 6.2, 2.0), 2, 16)
            add_order(inc.asset_id, asset_skill[inc.asset_id], "Corrective", priority, created, hours)

    # Poor inspections can trigger corrective work even without a recorded incident.
    for ins in inspections.itertuples(index=False):
        if ins.condition_score >= 60:
            continue
        p = 0.18 if ins.condition_score >= 50 else 0.42
        if rng.random() <= p:
            created = pd.Timestamp(ins.inspection_date) + pd.Timedelta(days=int(rng.integers(1, 6)))
            if created > RAW_END:
                continue
            priority = "High" if ins.condition_score < 45 else "Medium"
            hours = np.clip(rng.normal(6.0, 1.8), 2, 14)
            add_order(ins.asset_id, asset_skill[ins.asset_id], "Corrective", priority, created, hours)

    df = pd.DataFrame(rows, columns=[
        "work_order_id", "asset_id", "work_type", "priority", "created_date", "sla_due_date",
        "completed_date", "status", "estimated_hours", "required_skill"
    ])

    # Keep the manager-facing backlog realistic: only a small tail of open work may be older than 90 days.
    created_ts = pd.to_datetime(df["created_date"])
    old_open_idx = df[
        (df["status"]=="Open")
        & (created_ts <= AS_OF)
        & ((AS_OF-created_ts).dt.days > 90)
    ].index.tolist()
    if len(old_open_idx) > 8:
        keep = set(sorted(old_open_idx, key=lambda i: created_ts.loc[i], reverse=True)[:8])
        for i in old_open_idx:
            if i in keep:
                continue
            created = created_ts.loc[i]
            completion = min(created + pd.Timedelta(days=12), AS_OF)
            df.loc[i,"status"] = "Completed"
            df.loc[i,"completed_date"] = completion.date()

    return df.sort_values(["created_date", "work_order_id"]).reset_index(drop=True)

def generate_technicians(n=24):
    rng = np.random.default_rng(SEED + 4)
    skills = ["power", "breaker", "cable", "third_rail"]
    rows = []
    for i in range(1, n + 1):
        primary = skills[(i - 1) % len(skills)]
        secondary = rng.choice([s for s in skills if s != primary])
        rows.append((f"TECH-{i:03d}", primary, secondary, float(rng.choice([7.5, 8.0, 10.0]))))
    return pd.DataFrame(rows, columns=["technician_id", "primary_skill", "secondary_skill", "available_hours"])

def generate_all(output_dir):
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    assets = generate_assets()
    inspections = generate_inspections(assets)
    incidents = generate_incidents(assets, inspections)
    work_orders = generate_work_orders(assets, inspections, incidents)
    technicians = generate_technicians()

    for name, df in {
        "assets": assets,
        "inspections": inspections,
        "incidents": incidents,
        "work_orders": work_orders,
        "technicians": technicians,
    }.items():
        df.to_csv(out / f"{name}.csv", index=False)

    print("Generated coherent operational data:")
    for name, df in [("assets", assets), ("inspections", inspections), ("incidents", incidents), ("work_orders", work_orders), ("technicians", technicians)]:
        print(f"  {name}: {len(df):,} rows")
    print("Operational as-of:", AS_OF.date())
    print("Backtesting raw-data horizon:", RAW_END.date())

if __name__ == "__main__":
    generate_all("data/raw")
