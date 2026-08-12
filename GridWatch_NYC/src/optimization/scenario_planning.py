from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import Bounds, LinearConstraint, milp

from src.optimization.compare_schedules import build_jobs


@dataclass(frozen=True)
class ScenarioConfig:
    capacity_pct: int = 100
    max_jobs: int = 70
    risk_weight: float = 0.45
    sla_weight: float = 0.25
    criticality_weight: float = 0.20
    condition_weight: float = 0.10


def _prepare_jobs(max_jobs: int = 70) -> pd.DataFrame:
    jobs = build_jobs().copy()
    jobs = jobs.sort_values("priority_score", ascending=False).head(max_jobs).reset_index(drop=True)
    jobs["risk_points"] = jobs["predicted_30d_risk"].clip(0, 1) * 100
    jobs["criticality_points"] = jobs["criticality"].clip(1, 5) / 5 * 100
    jobs["condition_points"] = (100 - jobs["condition_score"]).clip(0, 100)
    jobs["sla_points"] = np.select(
        [jobs["days_to_sla"] <= 0, jobs["days_to_sla"] <= 2, jobs["days_to_sla"] <= 5],
        [100, 90, 70],
        default=35,
    )
    return jobs


def _scaled_techs(capacity_pct: int) -> pd.DataFrame:
    techs = pd.read_csv("data/raw/technicians.csv").copy()
    techs["available_hours"] = techs["available_hours"] * capacity_pct / 100.0
    return techs


def _objective(jobs: pd.DataFrame, cfg: ScenarioConfig) -> pd.Series:
    weights = np.array([cfg.risk_weight, cfg.sla_weight, cfg.criticality_weight, cfg.condition_weight], dtype=float)
    if weights.sum() <= 0:
        weights = np.array([1.0, 0.0, 0.0, 0.0])
    weights = weights / weights.sum()
    return (
        weights[0] * jobs["risk_points"]
        + weights[1] * jobs["sla_points"]
        + weights[2] * jobs["criticality_points"]
        + weights[3] * jobs["condition_points"]
    )


def _greedy_assign(jobs: pd.DataFrame, techs: pd.DataFrame, order_cols, ascending) -> pd.DataFrame:
    remaining = techs.set_index("technician_id")["available_hours"].to_dict()
    rows = []
    ordered = jobs.sort_values(order_cols, ascending=ascending)
    for _, job in ordered.iterrows():
        eligible = techs[
            ((techs["primary_skill"] == job["required_skill"]) | (techs["secondary_skill"] == job["required_skill"]))
            & (techs["technician_id"].map(remaining) >= float(job["estimated_hours"]))
        ]
        if eligible.empty:
            continue
        tid = max(eligible["technician_id"], key=lambda x: remaining[x])
        remaining[tid] -= float(job["estimated_hours"])
        rows.append(_assignment_row(tid, job))
    return pd.DataFrame(rows)


def _assignment_row(tid, job):
    return {
        "technician_id": tid,
        "work_order_id": job["work_order_id"],
        "asset_id": job["asset_id"],
        "required_skill": job["required_skill"],
        "estimated_hours": float(job["estimated_hours"]),
        "priority_score": float(job["priority_score"]),
        "scenario_score": float(job.get("scenario_score", job["priority_score"])),
        "predicted_30d_risk": float(job["predicted_30d_risk"]),
        "criticality": int(job["criticality"]),
        "days_to_sla": int(job["days_to_sla"]),
    }


def _optimized_assign(jobs: pd.DataFrame, techs: pd.DataFrame) -> tuple[pd.DataFrame, bool]:
    eligible = [
        (j, t)
        for j, job in jobs.iterrows()
        for t, tech in techs.iterrows()
        if job["required_skill"] in {tech["primary_skill"], tech["secondary_skill"]}
    ]
    if not eligible:
        return pd.DataFrame(), False
    n = len(eligible)
    c = np.array([-jobs.loc[j, "scenario_score"] for j, _ in eligible], dtype=float)
    rows, lb, ub = [], [], []
    for j in jobs.index:
        r = np.zeros(n)
        for k, (jj, _) in enumerate(eligible):
            if jj == j:
                r[k] = 1
        rows.append(r); lb.append(-np.inf); ub.append(1)
    for t, tech in techs.iterrows():
        r = np.zeros(n)
        for k, (j, tt) in enumerate(eligible):
            if tt == t:
                r[k] = float(jobs.loc[j, "estimated_hours"])
        rows.append(r); lb.append(-np.inf); ub.append(float(tech["available_hours"]))
    result = milp(
        c=c,
        integrality=np.ones(n),
        bounds=Bounds(np.zeros(n), np.ones(n)),
        constraints=LinearConstraint(np.vstack(rows), np.array(lb), np.array(ub)),
        options={"time_limit": 12, "mip_rel_gap": 0.02},
    )
    out = []
    if result.x is not None:
        for k, value in enumerate(result.x):
            if value > 0.5:
                j, t = eligible[k]
                out.append(_assignment_row(techs.loc[t, "technician_id"], jobs.loc[j]))
    return pd.DataFrame(out), bool(result.success)


def summarize(assignments: pd.DataFrame, jobs: pd.DataFrame, techs: pd.DataFrame) -> dict:
    assigned = set(assignments["work_order_id"]) if len(assignments) else set()
    unresolved = jobs[~jobs["work_order_id"].isin(assigned)]
    total_risk = float(jobs["scenario_score"].sum())
    residual = float(unresolved["scenario_score"].sum())
    metrics_path = Path("reports/model_metrics_v3.json")
    high_cut = 0.25
    if metrics_path.exists():
        with metrics_path.open("r", encoding="utf-8") as f:
            high_cut = float(json.load(f).get("selected_threshold", high_cut))
    return {
        "jobs_assigned": int(len(assignments)),
        "labor_hours": float(assignments["estimated_hours"].sum()) if len(assignments) else 0.0,
        "available_hours": float(techs["available_hours"].sum()),
        "utilization_pct": (float(assignments["estimated_hours"].sum()) / max(float(techs["available_hours"].sum()), 1.0) * 100) if len(assignments) else 0.0,
        "high_risk_addressed": int((assignments["predicted_30d_risk"] >= high_cut).sum()) if len(assignments) else 0,
        "critical_assets_addressed": int((assignments["criticality"] >= 4).sum()) if len(assignments) else 0,
        "overdue_addressed": int((assignments["days_to_sla"] < 0).sum()) if len(assignments) else 0,
        "weighted_risk_before": total_risk,
        "weighted_risk_after": residual,
        "risk_reduction_pct": (total_risk - residual) / max(total_risk, 1.0) * 100,
        "backlog_remaining": int(len(unresolved)),
    }


def run_scenario(cfg: ScenarioConfig) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    jobs = _prepare_jobs(cfg.max_jobs)
    techs = _scaled_techs(cfg.capacity_pct)
    jobs["scenario_score"] = _objective(jobs, cfg)

    risk_first = _greedy_assign(jobs, techs, ["predicted_30d_risk", "days_to_sla"], [False, True])
    backlog_first = _greedy_assign(jobs, techs, ["days_to_sla", "priority_score"], [True, False])
    optimized, solver_success = _optimized_assign(jobs, techs)

    frames = {"Risk-first": risk_first, "SLA/backlog-first": backlog_first, "Optimized": optimized}
    summaries = []
    for name, frame in frames.items():
        s = summarize(frame, jobs, techs)
        s["strategy"] = name
        summaries.append(s)
    summary_df = pd.DataFrame(summaries)
    meta = {"solver_success": solver_success, "jobs_considered": len(jobs), "capacity_pct": cfg.capacity_pct}
    return summary_df, optimized, meta


def capacity_stress_test(cfg: ScenarioConfig, levels=(50, 60, 70, 80, 90, 100, 110, 120)) -> pd.DataFrame:
    rows = []
    for level in levels:
        level_cfg = ScenarioConfig(
            capacity_pct=level,
            max_jobs=cfg.max_jobs,
            risk_weight=cfg.risk_weight,
            sla_weight=cfg.sla_weight,
            criticality_weight=cfg.criticality_weight,
            condition_weight=cfg.condition_weight,
        )
        summary, _, meta = run_scenario(level_cfg)
        opt = summary[summary["strategy"] == "Optimized"].iloc[0].to_dict()
        opt["capacity_pct"] = level
        opt["solver_success"] = meta["solver_success"]
        rows.append(opt)
    return pd.DataFrame(rows)
