from pathlib import Path
import json
import numpy as np
import pandas as pd
from scipy.optimize import milp, LinearConstraint, Bounds
AS_OF=pd.Timestamp('2026-07-31')


def build_jobs():
    wo=pd.read_csv('data/raw/work_orders.csv',parse_dates=['created_date','sla_due_date','completed_date'])
    risk=pd.read_csv('data/processed/asset_risk_scores.csv')
    open_wo=wo[wo.status=='Open'].copy()
    cols=['asset_id','predicted_30d_risk','condition_score','inspection_trend','incidents_90d','repeat_failure_flag','open_critical_work_orders','overdue_work_orders','criticality']
    open_wo=open_wo.merge(risk[cols],on='asset_id',how='left')
    open_wo['days_to_sla']=(open_wo.sla_due_date-AS_OF).dt.days
    sla=np.where(open_wo.days_to_sla<=0,100,np.where(open_wo.days_to_sla<=2,90,np.where(open_wo.days_to_sla<=5,70,35)))
    cond=np.clip(100-open_wo.condition_score,0,100); trend=np.clip(-open_wo.inspection_trend*15,0,100)
    open_wo['priority_score']=(.30*(open_wo.predicted_30d_risk*100)+.18*(open_wo.criticality/5*100)+.14*cond+.08*trend+.10*np.clip(open_wo.incidents_90d*25,0,100)+.08*(open_wo.repeat_failure_flag*100)+.12*sla).clip(0,100)
    return open_wo.sort_values('priority_score',ascending=False).head(70).reset_index(drop=True)


def baseline(jobs,techs):
    remain=techs.set_index('technician_id').available_hours.to_dict(); out=[]
    rank={'Critical':3,'High':2,'Medium':1}
    b=jobs.assign(p=jobs.priority.map(rank).fillna(0)).sort_values(['p','sla_due_date','priority_score'],ascending=[False,True,False])
    for _,j in b.iterrows():
        el=techs[((techs.primary_skill==j.required_skill)|(techs.secondary_skill==j.required_skill)) & (techs.technician_id.map(remain)>=j.estimated_hours)]
        if len(el):
            tid=max(el.technician_id,key=lambda x:remain[x]); remain[tid]-=j.estimated_hours; out.append((tid,j))
    return out


def optimize(jobs,techs):
    elig=[(j,t) for j,row in jobs.iterrows() for t,tr in techs.iterrows() if row.required_skill in {tr.primary_skill,tr.secondary_skill}]
    n=len(elig); c=np.array([-jobs.loc[j,'priority_score'] for j,t in elig]); rows=[]; lb=[]; ub=[]
    for j in jobs.index:
        r=np.zeros(n); [r.__setitem__(k,1) for k,(jj,t) in enumerate(elig) if jj==j]; rows.append(r); lb.append(-np.inf); ub.append(1)
    for t,tr in techs.iterrows():
        r=np.zeros(n); [r.__setitem__(k,jobs.loc[j,'estimated_hours']) for k,(j,tt) in enumerate(elig) if tt==t]; rows.append(r); lb.append(-np.inf); ub.append(float(tr.available_hours))
    res=milp(c=c,integrality=np.ones(n),bounds=Bounds(np.zeros(n),np.ones(n)),constraints=LinearConstraint(np.vstack(rows),np.array(lb),np.array(ub)),options={'time_limit':20,'mip_rel_gap':0.02})
    out=[]
    if res.x is not None:
        for k,v in enumerate(res.x):
            if v>.5:
                j,t=elig[k]; out.append((techs.loc[t,'technician_id'],jobs.loc[j]))
    return out,res


def frame(assignments):
    return pd.DataFrame([{'technician_id':tid,'work_order_id':j.work_order_id,'asset_id':j.asset_id,'required_skill':j.required_skill,'estimated_hours':float(j.estimated_hours),'priority_score':float(j.priority_score),'predicted_30d_risk':float(j.predicted_30d_risk),'sla_due_date':j.sla_due_date,'priority':j.priority,'days_to_sla':int(j.days_to_sla)} for tid,j in assignments])

def summary(df,jobs):
    assigned=set(df.work_order_id) if len(df) else set(); unresolved=jobs[~jobs.work_order_id.isin(assigned)]
    return {'jobs_assigned':int(len(df)),'labor_hours':float(df.estimated_hours.sum()) if len(df) else 0,'priority_points':float(df.priority_score.sum()) if len(df) else 0,'critical_jobs':int((df.priority=='Critical').sum()) if len(df) else 0,'overdue_jobs':int((df.days_to_sla<0).sum()) if len(df) else 0,'unresolved_risk':float(unresolved.priority_score.sum())}

def run():
    jobs=build_jobs(); techs=pd.read_csv('data/raw/technicians.csv')
    bdf=frame(baseline(jobs,techs)); od,res=optimize(jobs,techs); odf=frame(od)
    bs,os=summary(bdf,jobs),summary(odf,jobs)
    comp={'baseline':bs,'optimized':os,'solver_success':bool(res.success),'solver_status':str(res.message),'improvement':{'priority_points_pct':(os['priority_points']-bs['priority_points'])/max(bs['priority_points'],1)*100,'unresolved_risk_reduction_pct':(bs['unresolved_risk']-os['unresolved_risk'])/max(bs['unresolved_risk'],1)*100}}
    odf.to_csv('data/processed/optimized_schedule.csv',index=False); bdf.to_csv('data/processed/baseline_schedule.csv',index=False)
    with open('reports/schedule_comparison.json','w') as f: json.dump(comp,f,indent=2,default=str)
    print(json.dumps(comp,indent=2)); return comp
if __name__=='__main__': run()
