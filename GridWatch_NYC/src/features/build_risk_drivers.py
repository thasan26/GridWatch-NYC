from pathlib import Path
import numpy as np
import pandas as pd

def build_risk_drivers(risk_path="data/processed/asset_risk_scores.csv",
                       out_path="data/processed/asset_risk_drivers.csv"):
    df = pd.read_csv(risk_path).copy()

    components = pd.DataFrame({
        "asset_id": df["asset_id"],
        "Condition deterioration": np.clip((65-df["condition_score"])/35, 0, 1) * 22,
        "Inspection decline": np.clip(-df["inspection_trend"]/8, 0, 1) * 14,
        "Recent incidents": np.clip(df["incidents_90d"]/4, 0, 1) * 20,
        "Repeat-failure signal": df["repeat_failure_flag"].clip(0,1) * 12,
        "Maintenance interval": np.clip(df["days_since_maintenance"]/365, 0, 1) * 12,
        "Open critical work": np.clip(df["open_critical_work_orders"]/2, 0, 1) * 10,
        "Asset criticality": np.clip(df["criticality"]/5, 0, 1) * 10,
    })

    rows = []
    driver_cols = [c for c in components.columns if c != "asset_id"]
    for _, r in components.iterrows():
        vals = [(c, float(r[c])) for c in driver_cols]
        vals.sort(key=lambda x: x[1], reverse=True)
        for rank, (driver, points) in enumerate(vals[:5], 1):
            rows.append({"asset_id": r["asset_id"], "rank": rank, "driver": driver, "driver_points": round(points,2)})
    out = pd.DataFrame(rows)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_path, index=False)
    print(f"Risk-driver rows: {len(out):,}")
    return out

if __name__ == "__main__":
    build_risk_drivers()
