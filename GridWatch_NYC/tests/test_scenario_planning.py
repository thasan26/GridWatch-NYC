import pandas as pd
from src.optimization.scenario_planning import ScenarioConfig, _objective


def test_objective_increases_with_risk():
    jobs = pd.DataFrame({
        "risk_points": [20, 80], "sla_points": [50, 50],
        "criticality_points": [60, 60], "condition_points": [40, 40]
    })
    scores = _objective(jobs, ScenarioConfig())
    assert scores.iloc[1] > scores.iloc[0]


def test_objective_weights_are_normalized():
    jobs = pd.DataFrame({
        "risk_points": [100], "sla_points": [0],
        "criticality_points": [0], "condition_points": [0]
    })
    a = _objective(jobs, ScenarioConfig(risk_weight=45, sla_weight=25, criticality_weight=20, condition_weight=10)).iloc[0]
    b = _objective(jobs, ScenarioConfig(risk_weight=.45, sla_weight=.25, criticality_weight=.20, condition_weight=.10)).iloc[0]
    assert abs(a - b) < 1e-9
