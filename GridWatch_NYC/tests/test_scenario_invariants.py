from pathlib import Path
import pytest

@pytest.mark.skipif(not Path("data/processed/asset_risk_scores.csv").exists(), reason="Pipeline data not generated")
def test_scenario_residual_risk_not_negative():
    from src.optimization.scenario_planning import ScenarioConfig, run_scenario
    summary, _, _ = run_scenario(ScenarioConfig(capacity_pct=100,max_jobs=40))
    assert (summary.weighted_risk_after >= 0).all()
    assert (summary.risk_reduction_pct >= 0).all()
    assert (summary.risk_reduction_pct <= 100).all()
