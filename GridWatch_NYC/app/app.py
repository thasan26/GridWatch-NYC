import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from src.optimization.scenario_planning import ScenarioConfig, run_scenario, capacity_stress_test

st.set_page_config(
    page_title="GridWatch NYC",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

DATA = Path("data")
REPORTS = Path("reports")
AS_OF = pd.Timestamp("2026-07-31")

@st.cache_data
def load_data():
    risk = pd.read_csv(DATA/"processed"/"asset_risk_scores.csv", parse_dates=["snapshot_date"])
    drivers_path = DATA/"processed"/"asset_risk_drivers.csv"
    drivers = pd.read_csv(drivers_path) if drivers_path.exists() else pd.DataFrame()
    schedule = pd.read_csv(DATA/"processed"/"optimized_schedule.csv", parse_dates=["sla_due_date"])
    work_orders = pd.read_csv(DATA/"raw"/"work_orders.csv", parse_dates=["created_date","sla_due_date","completed_date"])
    inspections = pd.read_csv(DATA/"raw"/"inspections.csv", parse_dates=["inspection_date"])
    incidents = pd.read_csv(DATA/"raw"/"incidents.csv", parse_dates=["incident_date"])
    technicians = pd.read_csv(DATA/"raw"/"technicians.csv")

    with open(REPORTS/"model_metrics_v3.json","r",encoding="utf-8") as f:
        metrics = json.load(f)

    comparison = {}
    if (REPORTS/"schedule_comparison.json").exists():
        with open(REPORTS/"schedule_comparison.json","r",encoding="utf-8") as f:
            comparison = json.load(f)

    quality = {}
    if (REPORTS/"data_quality_report.json").exists():
        with open(REPORTS/"data_quality_report.json","r",encoding="utf-8") as f:
            quality = json.load(f)

    return risk,drivers,schedule,work_orders,inspections,incidents,technicians,metrics,comparison,quality

risk,drivers,schedule,work_orders,inspections,incidents,technicians,metrics,comparison,quality = load_data()
OPERATING_THRESHOLD = float(metrics["selected_threshold"])
CRITICAL_CUT = max(OPERATING_THRESHOLD * 1.8, 0.20)

# Current operational view only; August raw rows exist solely to label July backtesting outcomes.
work_orders_current = work_orders[work_orders["created_date"] <= AS_OF].copy()
inspections_current = inspections[inspections["inspection_date"] <= AS_OF].copy()
incidents_current = incidents[incidents["incident_date"] <= AS_OF].copy()
open_wo = work_orders_current[work_orders_current["status"]=="Open"].copy()
open_wo["days_to_sla"] = (open_wo["sla_due_date"]-AS_OF).dt.days
overdue_wo = open_wo[open_wo["days_to_sla"]<0].copy()

def risk_band(p):
    if p >= CRITICAL_CUT:
        return "Critical"
    if p >= OPERATING_THRESHOLD:
        return "High"
    if p >= OPERATING_THRESHOLD * 0.60:
        return "Watch"
    return "Normal"

def action_for(row):
    signals=[]
    if row["condition_score"] < 45: signals.append("poor condition")
    if row["inspection_trend"] < -1: signals.append("declining inspections")
    if row["incidents_90d"] >= 2: signals.append("repeat recent incidents")
    if row["open_critical_work_orders"] > 0: signals.append("open critical work")
    if row["days_since_maintenance"] > 180: signals.append("long maintenance interval")
    if row["predicted_30d_risk"] >= CRITICAL_CUT:
        action="Immediate engineering review"
    elif row["predicted_30d_risk"] >= OPERATING_THRESHOLD:
        action="Prioritize maintenance review"
    elif row["predicted_30d_risk"] >= OPERATING_THRESHOLD*0.60:
        action="Monitor and inspect"
    else:
        action="Routine monitoring"
    return action, ", ".join(signals[:3]) if signals else "modeled reliability profile"

@st.cache_data(show_spinner=False)
def cached_scenario(capacity_pct,max_jobs,risk_w,sla_w,crit_w,cond_w):
    cfg=ScenarioConfig(
        capacity_pct=capacity_pct,max_jobs=max_jobs,
        risk_weight=risk_w,sla_weight=sla_w,
        criticality_weight=crit_w,condition_weight=cond_w,
    )
    return run_scenario(cfg)

@st.cache_data(show_spinner=False)
def cached_stress(max_jobs,risk_w,sla_w,crit_w,cond_w):
    cfg=ScenarioConfig(
        capacity_pct=100,max_jobs=max_jobs,
        risk_weight=risk_w,sla_weight=sla_w,
        criticality_weight=crit_w,condition_weight=cond_w,
    )
    return capacity_stress_test(cfg)

st.sidebar.title("GridWatch NYC")
st.sidebar.caption("Reliability Engineering & Maintenance Decision Platform")
st.sidebar.info(
    "Advanced portfolio case study using synthetic operational data. "
    "No confidential or internal MTA data is used."
)
page = st.sidebar.radio(
    "Navigate",
    [
        "Command Center",
        "Asset Intelligence",
        "Maintenance Optimizer",
        "Scenario Planning",
        "Model Validation",
        "Data Quality",
    ],
)
st.sidebar.caption(f"Operational as-of: {AS_OF.date()}")

# ------------------------------------------------------------------
# COMMAND CENTER
# ------------------------------------------------------------------
if page=="Command Center":
    st.title("GridWatch NYC")
    st.subheader("Traction Power Reliability Command Center")
    st.caption("Predict → prioritize → optimize → measure operational trade-offs.")

    critical_assets=int((risk["predicted_30d_risk"]>=CRITICAL_CUT).sum())
    flagged_assets=int((risk["predicted_30d_risk"]>=OPERATING_THRESHOLD).sum())

    c1,c2,c3,c4,c5=st.columns(5)
    c1.metric("Assets monitored",f"{len(risk):,}")
    c2.metric("Critical-risk assets",f"{critical_assets:,}")
    c3.metric("Model-flagged assets",f"{flagged_assets:,}")
    c4.metric("Open work orders",f"{len(open_wo):,}")
    c5.metric("Overdue work orders",f"{len(overdue_wo):,}")

    st.caption(
        f"Operating threshold: {OPERATING_THRESHOLD:.1%}. "
        "Risk bands are portfolio decision bands, not official MTA classifications."
    )

    st.markdown("### Executive action brief")
    top_asset=risk.sort_values("predicted_30d_risk",ascending=False).iloc[0]
    top_action,top_reason=action_for(top_asset)
    improvement=float(comparison.get("improvement",{}).get("unresolved_risk_reduction_pct",0))

    a,b,c=st.columns(3)
    with a:
        st.info(
            f"**Highest modeled-risk asset: {top_asset['asset_id']}**\n\n"
            f"{top_asset['predicted_30d_risk']:.1%} 30-day modeled risk • "
            f"Condition {top_asset['condition_score']:.0f}/100.\n\n"
            f"**Action:** {top_action}."
        )
    with b:
        if len(overdue_wo):
            oldest=overdue_wo.sort_values("days_to_sla").iloc[0]
            st.warning(
                f"**SLA exposure: {len(overdue_wo)} overdue work orders**\n\n"
                f"Oldest current item: {oldest['work_order_id']} "
                f"({abs(int(oldest['days_to_sla']))} days past SLA).\n\n"
                "Review backlog concentration before allocating discretionary capacity."
            )
        else:
            st.success("**SLA exposure:** No current overdue work orders in the synthetic scenario.")
    with c:
        st.success(
            f"**Optimization impact**\n\n"
            f"Current optimized plan reduces unresolved weighted priority by "
            f"**{improvement:.1f}%** versus the rule-based baseline in this synthetic scenario.\n\n"
            "Use Scenario Planning to test staffing and decision-weight changes."
        )

    st.markdown("### Today's decision queue")
    queue=risk.copy()
    queue["Risk Level"]=queue["predicted_30d_risk"].apply(risk_band)
    queue["Recommended Action"]=queue.apply(lambda r:action_for(r)[0],axis=1)
    q=queue.sort_values(
        ["predicted_30d_risk","open_critical_work_orders","condition_score"],
        ascending=[False,False,True]
    ).head(12)[[
        "asset_id","asset_type","borough","predicted_30d_risk","condition_score",
        "incidents_90d","open_critical_work_orders","Risk Level","Recommended Action"
    ]].copy()
    q["predicted_30d_risk"]=q["predicted_30d_risk"].map(lambda x:f"{x:.1%}")
    q["condition_score"]=q["condition_score"].map(lambda x:f"{x:.0f}/100")
    q.columns=["Asset","Type","Borough","30-Day Risk","Condition","90-Day Incidents","Open Critical WOs","Risk Level","Recommended Action"]
    st.dataframe(q,hide_index=True,use_container_width=True,height=430)

    left,right=st.columns(2)
    with left:
        st.markdown("### Risk concentration by asset type")
        type_view=risk.groupby("asset_type",as_index=False).agg(
            avg_risk=("predicted_30d_risk","mean"),
            flagged=("risk_flag","sum"),
            assets=("asset_id","count"),
        )
        type_view["avg_risk_pct"]=type_view["avg_risk"]*100
        fig=px.bar(type_view,x="asset_type",y="avg_risk_pct",hover_data=["flagged","assets"],
                   labels={"asset_type":"Asset Type","avg_risk_pct":"Average Modeled Risk (%)"})
        st.plotly_chart(fig,use_container_width=True)
    with right:
        st.markdown("### Open-work backlog by priority")
        if len(open_wo):
            backlog=open_wo.groupby("priority",as_index=False).size().rename(columns={"size":"open_jobs"})
            fig=px.bar(backlog,x="priority",y="open_jobs",labels={"priority":"Priority","open_jobs":"Open Work Orders"})
            st.plotly_chart(fig,use_container_width=True)
        else:
            st.info("No open backlog in the current scenario.")

# ------------------------------------------------------------------
# ASSET INTELLIGENCE
# ------------------------------------------------------------------
elif page=="Asset Intelligence":
    st.title("Asset Intelligence")
    st.caption("Explain a risk signal using the same operational history that feeds the predictive model.")

    asset=st.selectbox(
        "Select asset",
        risk.sort_values("predicted_30d_risk",ascending=False)["asset_id"].tolist()
    )
    row=risk[risk["asset_id"]==asset].iloc[0]
    band=risk_band(row["predicted_30d_risk"])
    action,reason=action_for(row)

    c1,c2,c3,c4,c5=st.columns(5)
    c1.metric("30-day modeled risk",f"{row['predicted_30d_risk']:.1%}")
    c2.metric("Decision band",band)
    c3.metric("Condition",f"{row['condition_score']:.0f}/100")
    c4.metric("90-day incidents",f"{int(row['incidents_90d'])}")
    c5.metric("Criticality",f"{int(row['criticality'])}/5")

    st.info(f"**Recommended action: {action}.** Primary operational signal: {reason}.")

    if len(drivers):
        d=drivers[drivers["asset_id"]==asset].sort_values("rank").head(5)
        if len(d):
            st.markdown("### Operational risk contributors")
            st.caption(
                "Transparent decision-support factors derived from asset condition and maintenance history. "
                "These are not SHAP values and do not claim causal attribution."
            )
            fig=px.bar(
                d.sort_values("driver_points"),
                x="driver_points",y="driver",orientation="h",
                labels={"driver_points":"Decision-support points","driver":"Driver"}
            )
            st.plotly_chart(fig,use_container_width=True)

    left,right=st.columns(2)
    with left:
        st.markdown("### Asset profile")
        profile=pd.DataFrame({
            "Field":["Asset Type","Borough","Age","Required Skill","Days Since Maintenance","Open Work Orders","Open Critical Work"],
            "Value":[row["asset_type"],row["borough"],f"{row['age_years']:.0f} years",row["required_skill"],
                     f"{int(row['days_since_maintenance'])} days",int(row["open_work_orders"]),int(row["open_critical_work_orders"])]
        })
        st.dataframe(profile,hide_index=True,use_container_width=True)
    with right:
        st.markdown("### Reliability signals")
        signals=pd.DataFrame({
            "Signal":["Inspection Trend","30-Day Incidents","90-Day Incidents","365-Day Incidents","90-Day Downtime","Repeat Failure","Overdue WOs at Snapshot"],
            "Value":[f"{row['inspection_trend']:.2f}",int(row["incidents_30d"]),int(row["incidents_90d"]),
                     int(row["incidents_365d"]),f"{row['downtime_90d']:.1f} h",
                     "Yes" if bool(row["repeat_failure_flag"]) else "No",int(row["overdue_work_orders"])]
        })
        st.dataframe(signals,hide_index=True,use_container_width=True)

    st.markdown("### Inspection history")
    ai=inspections_current[inspections_current["asset_id"]==asset].sort_values("inspection_date")
    if len(ai):
        fig=px.line(ai,x="inspection_date",y="condition_score",markers=True,
                    labels={"inspection_date":"Inspection Date","condition_score":"Condition Score"})
        st.plotly_chart(fig,use_container_width=True)

    l,r=st.columns(2)
    with l:
        st.markdown("### Recent incidents")
        ii=incidents_current[incidents_current["asset_id"]==asset].sort_values("incident_date",ascending=False).head(10)
        if len(ii):
            st.dataframe(ii[["incident_date","severity","incident_type","downtime_hours"]].rename(columns={
                "incident_date":"Date","severity":"Severity","incident_type":"Type","downtime_hours":"Downtime Hours"
            }),hide_index=True,use_container_width=True)
        else:
            st.info("No incidents recorded for this asset.")
    with r:
        st.markdown("### Work-order history")
        ww=work_orders_current[work_orders_current["asset_id"]==asset].sort_values("created_date",ascending=False).head(10)
        if len(ww):
            st.dataframe(ww[["work_order_id","work_type","priority","created_date","sla_due_date","status"]].rename(columns={
                "work_order_id":"Work Order","work_type":"Type","priority":"Priority",
                "created_date":"Created","sla_due_date":"SLA Due","status":"Status"
            }),hide_index=True,use_container_width=True)
        else:
            st.info("No work orders recorded for this asset.")

# ------------------------------------------------------------------
# MAINTENANCE OPTIMIZER
# ------------------------------------------------------------------
elif page=="Maintenance Optimizer":
    st.title("Maintenance Optimizer")
    st.caption("Resource-constrained technician assignment compared with a transparent rule-based baseline.")

    if comparison:
        base=comparison["baseline"]; opt=comparison["optimized"]
        a,b,c,d=st.columns(4)
        a.metric("Priority points scheduled",f"{opt['priority_points']:.0f}",delta=f"{opt['priority_points']-base['priority_points']:+.0f}")
        b.metric("Unresolved weighted priority",f"{opt['unresolved_risk']:.0f}",
                 delta=f"{opt['unresolved_risk']-base['unresolved_risk']:+.0f}",delta_color="inverse")
        c.metric("Jobs assigned",f"{opt['jobs_assigned']}",delta=f"{opt['jobs_assigned']-base['jobs_assigned']:+d}")
        d.metric("Solver status","Optimal" if comparison.get("solver_success") else "Review")
        st.caption(
            f"Optimization reduced unresolved weighted priority by "
            f"{comparison['improvement']['unresolved_risk_reduction_pct']:.1f}% "
            "relative to a priority/SLA heuristic under the same labor-hour constraints."
        )

    st.markdown("### Optimized technician assignments")
    if len(schedule):
        view=schedule.copy()
        view["predicted_30d_risk"]=view["predicted_30d_risk"].map(lambda x:f"{x:.1%}")
        view["estimated_hours"]=view["estimated_hours"].map(lambda x:f"{x:.1f}")
        view["priority_score"]=view["priority_score"].map(lambda x:f"{x:.1f}")
        view=view[["technician_id","work_order_id","asset_id","required_skill","estimated_hours","priority_score","predicted_30d_risk","sla_due_date"]]
        view.columns=["Technician","Work Order","Asset","Skill","Hours","Priority Score","30-Day Risk","SLA Due"]
        st.dataframe(view,hide_index=True,use_container_width=True,height=520)

        workload=schedule.groupby("technician_id",as_index=False)["estimated_hours"].sum().merge(
            technicians[["technician_id","available_hours"]],on="technician_id",how="left"
        )
        workload["utilization_pct"]=workload["estimated_hours"]/workload["available_hours"]*100
        st.markdown("### Technician utilization")
        fig=px.bar(workload.sort_values("utilization_pct",ascending=False),x="technician_id",y="utilization_pct",
                   hover_data=["estimated_hours","available_hours"],
                   labels={"technician_id":"Technician","utilization_pct":"Scheduled Utilization (%)"})
        st.plotly_chart(fig,use_container_width=True)

# ------------------------------------------------------------------
# SCENARIO PLANNING
# ------------------------------------------------------------------
elif page=="Scenario Planning":
    st.title("Scenario & Resource Planning Lab")
    st.caption("Test how staffing capacity and management priorities change residual operational risk.")

    with st.form("scenario_form"):
        c1,c2=st.columns(2)
        with c1:
            capacity_pct=st.slider("Maintenance capacity",50,120,100,10)
            max_jobs=st.slider("Work orders considered",30,100,70,10)
        with c2:
            risk_w=st.slider("Modeled risk weight",0,100,45,5)
            sla_w=st.slider("SLA/backlog urgency weight",0,100,25,5)
            crit_w=st.slider("Asset criticality weight",0,100,20,5)
            cond_w=st.slider("Condition deterioration weight",0,100,10,5)
        submitted=st.form_submit_button("Run scenario")

    scenario,scenario_schedule,meta=cached_scenario(capacity_pct,max_jobs,risk_w,sla_w,crit_w,cond_w)
    opt=scenario[scenario["strategy"]=="Optimized"].iloc[0]

    st.markdown("### Optimized scenario outcome")
    a,b,c,d,e=st.columns(5)
    a.metric("Jobs scheduled",f"{int(opt['jobs_assigned'])}")
    b.metric("Labor utilization",f"{opt['utilization_pct']:.1f}%")
    c.metric("Weighted-risk reduction",f"{opt['risk_reduction_pct']:.1f}%")
    d.metric("Overdue jobs addressed",f"{int(opt['overdue_addressed'])}")
    e.metric("Backlog remaining",f"{int(opt['backlog_remaining'])}")
    st.caption("Weighted risk is a scenario decision score, not an official MTA risk metric.")

    st.markdown("### Strategy comparison")
    view=scenario[["strategy","jobs_assigned","labor_hours","utilization_pct","high_risk_addressed",
                   "overdue_addressed","weighted_risk_after","risk_reduction_pct","backlog_remaining"]].copy()
    view.columns=["Strategy","Jobs","Labor Hours","Utilization %","Flagged Jobs Addressed","Overdue Addressed",
                  "Residual Weighted Risk","Risk Reduction %","Backlog Remaining"]
    st.dataframe(view.round(1),hide_index=True,use_container_width=True)

    alternatives=scenario[scenario["strategy"]!="Optimized"].sort_values("weighted_risk_after")
    if len(alternatives):
        best_alt=alternatives.iloc[0]
        delta=(best_alt["weighted_risk_after"]-opt["weighted_risk_after"])/max(best_alt["weighted_risk_after"],1)*100
        if meta["solver_success"]:
            st.success(f"Optimizer leaves {delta:.1f}% less weighted residual risk than the strongest heuristic alternative under these settings.")
        else:
            st.warning("A feasible plan was produced, but optimality was not certified within the configured solve limit.")

    st.markdown("### Capacity stress test")
    stress=cached_stress(max_jobs,risk_w,sla_w,crit_w,cond_w).sort_values("capacity_pct")
    fig=px.line(stress,x="capacity_pct",y="weighted_risk_after",markers=True,
                hover_data=["jobs_assigned","labor_hours","risk_reduction_pct","backlog_remaining"],
                labels={"capacity_pct":"Maintenance Capacity (% of baseline)","weighted_risk_after":"Residual Weighted Risk"})
    st.plotly_chart(fig,use_container_width=True)

    stress["marginal_reduction"]=stress["weighted_risk_after"].shift(1)-stress["weighted_risk_after"]
    valid=stress.dropna(subset=["marginal_reduction"])
    if len(valid):
        peak=valid.loc[valid["marginal_reduction"].idxmax()]
        st.info(
            f"Largest modeled step-down in residual risk occurs around **{int(peak['capacity_pct'])}%** "
            "of baseline capacity for this scenario. The curve shows where extra capacity begins to produce smaller incremental gains."
        )

# ------------------------------------------------------------------
# MODEL VALIDATION
# ------------------------------------------------------------------
elif page=="Model Validation":
    st.title("Model Validation")
    st.caption("Chronological holdout testing, probability calibration, threshold selection, and rare-event evaluation.")

    split=metrics["split"]; tr=metrics["train"]; va=metrics["validation"]; te=metrics["test"]; sel=metrics["selected_test"]

    c1,c2,c3,c4=st.columns(4)
    c1.metric("Training observations",f"{tr['rows']:,}")
    c2.metric("Validation observations",f"{va['rows']:,}")
    c3.metric("Holdout observations",f"{te['rows']:,}")
    c4.metric("Holdout events",f"{te['positives']:,}")
    st.caption(
        f"Train through {split['train_end']} • validate through {split['validation_end']} • "
        f"untouched holdout begins {split['test_start']}."
    )

    st.markdown(f"### Selected model — {metrics['selected_model'].replace('_',' ').title()}")
    a,b,c,d,e=st.columns(5)
    a.metric("PR-AUC",f"{sel['pr_auc']:.3f}")
    b.metric("ROC-AUC",f"{sel['roc_auc']:.3f}")
    c.metric("Precision",f"{sel['precision']:.1%}")
    d.metric("Recall",f"{sel['recall']:.1%}")
    e.metric("Brier score",f"{sel['brier']:.3f}")
    st.info(
        f"Operating threshold = {metrics['selected_threshold']:.1%}. "
        "It was chosen on validation data with recall emphasized, then frozen before final holdout evaluation."
    )

    rows=[]
    for label,key in [("Logistic Regression","logistic_regression"),("HistGradientBoosting","hist_gradient_boosting")]:
        m=metrics[key]["test"]
        rows.append({"Model":label,"PR-AUC":m["pr_auc"],"ROC-AUC":m["roc_auc"],"Precision":m["precision"],
                     "Recall":m["recall"],"F1":m["f1"],"Brier":m["brier"]})
    st.markdown("### Model comparison")
    st.dataframe(pd.DataFrame(rows).round(3),hide_index=True,use_container_width=True)

    l,r=st.columns(2)
    with l:
        st.markdown("### Precision–recall trade-off")
        pr_path=REPORTS/"precision_recall_curve.csv"
        if pr_path.exists():
            pr=pd.read_csv(pr_path)
            fig=px.line(pr,x="recall",y="precision",labels={"recall":"Recall","precision":"Precision"})
            st.plotly_chart(fig,use_container_width=True)
    with r:
        st.markdown("### Probability calibration")
        cal_path=REPORTS/"calibration_curve.csv"
        if cal_path.exists():
            cal=pd.read_csv(cal_path)
            fig=px.line(cal,x="mean_predicted_probability",y="observed_event_rate",markers=True,
                        labels={"mean_predicted_probability":"Mean Predicted Probability","observed_event_rate":"Observed Event Rate"})
            st.plotly_chart(fig,use_container_width=True)

    l,r=st.columns(2)
    with l:
        st.markdown("### Confusion matrix")
        cm=pd.DataFrame(sel["confusion_matrix"],index=["Actual No Event","Actual Event"],columns=["Predicted No Event","Predicted Event"])
        st.dataframe(cm,use_container_width=True)
    with r:
        imp_path=REPORTS/"feature_importance.csv"
        st.markdown("### Global predictive signals")
        if imp_path.exists():
            imp=pd.read_csv(imp_path).head(12)
            if len(imp):
                fig=px.bar(imp.sort_values("importance"),x="importance",y="feature",orientation="h",
                           labels={"importance":"Importance","feature":"Feature"})
                st.plotly_chart(fig,use_container_width=True)

    baseline=metrics["baseline_test"]["pr_auc"]
    lift=sel["pr_auc"]/baseline if baseline else 0
    st.markdown("### Business interpretation")
    st.write(
        f"The selected model achieves **{lift:.1f}× PR-AUC lift over the prevalence baseline** on the later holdout period. "
        f"At the frozen operating threshold it identifies **{sel['recall']:.1%}** of simulated future corrective-maintenance events "
        f"with **{sel['precision']:.1%}** precision. The model is intended for **prioritization**, not autonomous maintenance decisions."
    )
    st.warning(
        "All asset and maintenance records are synthetic. These metrics demonstrate the modeling and validation workflow; "
        "they do not establish real-world MTA predictive accuracy."
    )

# ------------------------------------------------------------------
# DATA QUALITY
# ------------------------------------------------------------------
elif page=="Data Quality":
    st.title("Data Quality & Controls")
    st.caption("Production-minded validation, lineage, and limitations.")

    if not quality:
        st.warning("Run `python run_pipeline_final.py` to generate the data-quality report.")
    else:
        a,b,c,d=st.columns(4)
        a.metric("Quality status",quality["overall_status"])
        b.metric("Checks passed",f"{quality['checks_passed']}/{quality['checks_total']}")
        c.metric("Asset-month snapshots",f"{quality['records']['asset_month_snapshots']:,}")
        d.metric("Current open work",f"{quality['records']['current_open_work_orders']:,}")

        st.markdown("### Automated validation checks")
        checks=pd.DataFrame(quality["checks"])
        checks["Status"]=checks["passed"].map({True:"PASS",False:"REVIEW"})
        checks=checks[["Status","check","value","expectation"]]
        checks.columns=["Status","Check","Observed","Expectation"]
        st.dataframe(checks,hide_index=True,use_container_width=True,height=500)

        st.markdown("### Data lineage")
        st.code(
"""Synthetic asset registry / inspections / incidents / work orders
                         ↓
             leakage-controlled monthly snapshots
                         ↓
           calibrated 30-day maintenance-risk model
                         ↓
          transparent prioritization + optimization
                         ↓
      Command Center / Scenario Planning / Validation""",
            language="text"
        )

        st.markdown("### Freshness and backtesting control")
        f=quality["freshness"]
        fres=pd.DataFrame({
            "Dataset":["Inspection history","Incident raw horizon","Work-order raw horizon","Model snapshot"],
            "Latest date":[f["latest_inspection"],f["latest_incident_raw_horizon"],f["latest_work_order_raw_horizon"],f["latest_model_snapshot"]]
        })
        st.dataframe(fres,hide_index=True,use_container_width=True)
        st.info(
            "The raw synthetic dataset intentionally extends through August 2026 so July 31 snapshots can receive a future 30-day label during backtesting. "
            "The manager-facing operational views are strictly filtered to July 31, preventing future rows from appearing in current-state decisions."
        )

        st.markdown("### Governance limitations")
        st.write(
            "A production implementation would require real asset taxonomy, domain-engineer review, approved risk thresholds, "
            "access controls, audit logging, model monitoring, change management, and safety validation before any maintenance decision could rely on the system."
        )
