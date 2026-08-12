from pathlib import Path
import pandas as pd
import pytest

@pytest.mark.skipif(not Path("data/raw/assets.csv").exists(), reason="Pipeline data not generated")
def test_referential_integrity():
    assets=pd.read_csv("data/raw/assets.csv")
    incidents=pd.read_csv("data/raw/incidents.csv")
    work_orders=pd.read_csv("data/raw/work_orders.csv")
    ids=set(assets.asset_id)
    assert set(incidents.asset_id).issubset(ids)
    assert set(work_orders.asset_id).issubset(ids)

@pytest.mark.skipif(not Path("data/processed/asset_month_snapshots.csv").exists(), reason="Pipeline data not generated")
def test_snapshot_target_binary():
    df=pd.read_csv("data/processed/asset_month_snapshots.csv")
    assert set(df.target_corrective_30d.unique()).issubset({0,1})
    assert df.isna().sum().sum()==0
