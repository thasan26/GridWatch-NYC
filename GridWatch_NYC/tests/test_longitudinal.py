import pandas as pd

def test_target_window_is_future_only():
    snap=pd.Timestamp('2026-01-31'); event=pd.Timestamp('2026-02-15')
    assert 0 < (event-snap).days <= 30

def test_feature_event_must_precede_snapshot():
    snap=pd.Timestamp('2026-01-31'); incident=pd.Timestamp('2026-01-15')
    assert incident <= snap
