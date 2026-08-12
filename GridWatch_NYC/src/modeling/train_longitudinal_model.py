from pathlib import Path
import json, joblib
import numpy as np
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import (
    roc_auc_score, average_precision_score, precision_score, recall_score,
    f1_score, brier_score_loss, confusion_matrix, precision_recall_curve
)
from sklearn.inspection import permutation_importance
from sklearn.calibration import calibration_curve

NUM = [
    "age_years","criticality","condition_score","inspection_trend",
    "incidents_30d","incidents_90d","incidents_365d","downtime_90d",
    "open_work_orders","open_critical_work_orders","overdue_work_orders",
    "days_since_maintenance","repeat_failure_flag"
]
CAT = ["asset_type","borough"]
TRAIN_END = pd.Timestamp("2025-12-31")
VAL_END = pd.Timestamp("2026-04-30")

def evaluate(y, p, threshold):
    pred = (p >= threshold).astype(int)
    return {
        "roc_auc": float(roc_auc_score(y,p)) if len(np.unique(y)) > 1 else None,
        "pr_auc": float(average_precision_score(y,p)),
        "precision": float(precision_score(y,pred,zero_division=0)),
        "recall": float(recall_score(y,pred,zero_division=0)),
        "f1": float(f1_score(y,pred,zero_division=0)),
        "brier": float(brier_score_loss(y,p)),
        "threshold": float(threshold),
        "positives": int(y.sum()),
        "rows": int(len(y)),
        "confusion_matrix": confusion_matrix(y,pred).tolist(),
    }

def choose_threshold(y, p):
    precision, recall, thresholds = precision_recall_curve(y,p)
    candidates = []
    for i,t in enumerate(thresholds):
        if recall[i] >= 0.55:
            candidates.append((precision[i], recall[i], float(t)))
    if candidates:
        return max(candidates, key=lambda x:(x[0],x[1]))[2]
    # fallback: maximize F2
    best=(0,0.5)
    for i,t in enumerate(thresholds):
        pr,rc=precision[i],recall[i]
        f2=(5*pr*rc)/(4*pr+rc) if (4*pr+rc) else 0
        if f2>best[0]: best=(f2,float(t))
    return best[1]

def _save_curves(y, p, prefix="reports"):
    precision, recall, thresholds = precision_recall_curve(y,p)
    pr = pd.DataFrame({
        "precision": precision[:-1],
        "recall": recall[:-1],
        "threshold": thresholds
    })
    pr.to_csv(Path(prefix)/"precision_recall_curve.csv",index=False)

    frac_pos, mean_pred = calibration_curve(y,p,n_bins=10,strategy="quantile")
    pd.DataFrame({
        "mean_predicted_probability":mean_pred,
        "observed_event_rate":frac_pos
    }).to_csv(Path(prefix)/"calibration_curve.csv",index=False)

def train(path="data/processed/asset_month_snapshots.csv"):
    df = pd.read_csv(path, parse_dates=["snapshot_date"])
    tr = df[df["snapshot_date"] <= TRAIN_END].copy()
    va = df[(df["snapshot_date"] > TRAIN_END) & (df["snapshot_date"] <= VAL_END)].copy()
    te = df[df["snapshot_date"] > VAL_END].copy()

    Xtr,ytr = tr[NUM+CAT], tr["target_corrective_30d"].astype(int)
    Xv,yv = va[NUM+CAT], va["target_corrective_30d"].astype(int)
    Xt,yt = te[NUM+CAT], te["target_corrective_30d"].astype(int)

    pre = ColumnTransformer([
        ("num",Pipeline([("impute",SimpleImputer(strategy="median")),("scale",StandardScaler())]),NUM),
        ("cat",Pipeline([("impute",SimpleImputer(strategy="most_frequent")),("onehot",OneHotEncoder(handle_unknown="ignore",sparse_output=False))]),CAT)
    ], sparse_threshold=0)

    # Interpretable benchmark
    logit = Pipeline([
        ("pre",pre),
        ("model",LogisticRegression(max_iter=1600,class_weight="balanced",C=0.7))
    ])
    logit.fit(Xtr,ytr)
    pv_l_raw = logit.predict_proba(Xv)[:,1]
    pt_l_raw = logit.predict_proba(Xt)[:,1]
    cal_l = LogisticRegression(C=1.0,max_iter=600).fit(pv_l_raw.reshape(-1,1),yv)
    pv_l = cal_l.predict_proba(pv_l_raw.reshape(-1,1))[:,1]
    pt_l = cal_l.predict_proba(pt_l_raw.reshape(-1,1))[:,1]
    th_l = choose_threshold(yv.to_numpy(),pv_l)

    # Nonlinear challenger
    pre_g = pre.fit(Xtr)
    Xtrg,Xvg,Xtg = pre_g.transform(Xtr),pre_g.transform(Xv),pre_g.transform(Xt)
    gb = HistGradientBoostingClassifier(
        learning_rate=0.055,max_iter=160,max_leaf_nodes=15,
        l2_regularization=1.5,min_samples_leaf=35,random_state=42
    )
    gb.fit(Xtrg,ytr)
    pv_g_raw = gb.predict_proba(Xvg)[:,1]
    pt_g_raw = gb.predict_proba(Xtg)[:,1]
    cal_g = LogisticRegression(C=1.0,max_iter=600).fit(pv_g_raw.reshape(-1,1),yv)
    pv_g = cal_g.predict_proba(pv_g_raw.reshape(-1,1))[:,1]
    pt_g = cal_g.predict_proba(pt_g_raw.reshape(-1,1))[:,1]
    th_g = choose_threshold(yv.to_numpy(),pv_g)

    val_l,test_l = evaluate(yv.to_numpy(),pv_l,th_l), evaluate(yt.to_numpy(),pt_l,th_l)
    val_g,test_g = evaluate(yv.to_numpy(),pv_g,th_g), evaluate(yt.to_numpy(),pt_g,th_g)

    prevalence = float(ytr.mean())
    base = np.full(len(yt),prevalence)
    base_test = evaluate(yt.to_numpy(),base,0.5)

    latest = df.sort_values("snapshot_date").groupby("asset_id").tail(1).copy()
    feature_importance = pd.DataFrame()

    if val_g["pr_auc"] >= val_l["pr_auc"]:
        selected = "hist_gradient_boosting"
        threshold = th_g
        selected_test = test_g
        raw = gb.predict_proba(pre_g.transform(latest[NUM+CAT]))[:,1]
        latest["predicted_30d_risk"] = cal_g.predict_proba(raw.reshape(-1,1))[:,1]
        bundle = {"preprocessor":pre_g,"model":gb,"calibrator":cal_g,"threshold":threshold,"model_type":selected}
        try:
            r = permutation_importance(gb,Xtg,yt,n_repeats=4,random_state=42,scoring="average_precision")
            feature_importance = pd.DataFrame({
                "feature":pre_g.get_feature_names_out(),
                "importance":r.importances_mean
            }).sort_values("importance",ascending=False).head(25)
        except Exception:
            pass
        selected_probs = pt_g
    else:
        selected = "logistic_regression"
        threshold = th_l
        selected_test = test_l
        raw = logit.predict_proba(latest[NUM+CAT])[:,1]
        latest["predicted_30d_risk"] = cal_l.predict_proba(raw.reshape(-1,1))[:,1]
        bundle = {"pipeline":logit,"calibrator":cal_l,"threshold":threshold,"model_type":selected}
        names = logit.named_steps["pre"].get_feature_names_out()
        coef = logit.named_steps["model"].coef_[0]
        feature_importance = pd.DataFrame({
            "feature":names,
            "importance":np.abs(coef),
            "direction":np.where(coef>=0,"increases modeled risk","decreases modeled risk")
        }).sort_values("importance",ascending=False).head(25)
        selected_probs = pt_l

    latest["risk_flag"] = (latest["predicted_30d_risk"] >= threshold).astype(int)
    Path("data/processed").mkdir(parents=True,exist_ok=True)
    Path("reports").mkdir(exist_ok=True)
    Path("models").mkdir(exist_ok=True)

    latest.to_csv("data/processed/asset_risk_scores.csv",index=False)
    feature_importance.to_csv("reports/feature_importance.csv",index=False)
    joblib.dump(bundle,"models/risk_model.joblib")
    _save_curves(yt.to_numpy(),selected_probs)

    results = {
        "split":{
            "train_end":str(TRAIN_END.date()),
            "validation_end":str(VAL_END.date()),
            "test_start":str((VAL_END+pd.Timedelta(days=1)).date()),
            "method":"chronological holdout"
        },
        "train":{"rows":int(len(tr)),"positives":int(ytr.sum()),"prevalence":float(ytr.mean())},
        "validation":{"rows":int(len(va)),"positives":int(yv.sum()),"prevalence":float(yv.mean())},
        "test":{"rows":int(len(te)),"positives":int(yt.sum()),"prevalence":float(yt.mean())},
        "baseline_test":base_test,
        "logistic_regression":{"validation":val_l,"test":test_l},
        "hist_gradient_boosting":{"validation":val_g,"test":test_g},
        "selected_model":selected,
        "selected_threshold":float(threshold),
        "selected_test":selected_test,
        "calibration_method":"logistic/Platt calibration on validation period",
        "target_definition":"corrective work order created within the next 30 days",
    }

    with open("reports/model_metrics_v3.json","w",encoding="utf-8") as f:
        json.dump(results,f,indent=2)

    print(json.dumps(results,indent=2))
    print("Selected:",selected)
    print("Current calibrated risk range:",float(latest.predicted_30d_risk.min()),"to",float(latest.predicted_30d_risk.max()))
    return results

if __name__=="__main__":
    train()
