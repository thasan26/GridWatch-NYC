import pandas as pd
import numpy as np

def priority_score(risk, criticality, condition, trend, incidents, repeat, sla):
    cond_risk=np.clip(100-condition,0,100)
    trend_risk=np.clip(-trend*15,0,100)
    return (
        0.28*(risk*100)
        +0.18*(criticality/5*100)
        +0.14*cond_risk
        +0.10*trend_risk
        +0.10*np.clip(incidents*25,0,100)
        +0.08*(repeat*100)
        +0.12*sla
    )

def test_higher_risk_increases_priority():
    low=priority_score(.20,3,70,0,0,0,35)
    high=priority_score(.80,3,70,0,0,0,35)
    assert high > low

def test_critical_repeat_failure_is_high_priority():
    score=priority_score(.85,5,40,-2,4,1,100)
    assert score > 80
