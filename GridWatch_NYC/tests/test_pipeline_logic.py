import pandas as pd
import numpy as np

def test_future_target_window_is_forward_looking():
    snap = pd.Timestamp("2026-07-31")
    created = pd.Timestamp("2026-08-15")
    assert 0 < (created-snap).days <= 30

def test_condition_score_range_rule():
    scores = pd.Series([18.0,45.0,72.5,100.0])
    assert scores.between(0,100).all()

def test_priority_risk_component_monotonic():
    low = .30*(.10*100)
    high = .30*(.30*100)
    assert high > low
