"""Diagnostic checks for Pearson/regression assumptions by month, day type, and POC metric."""
import argparse, math
from pathlib import Path
import numpy as np
import pandas as pd

METRICS=['overall_accessibility_score','connectivity_score','road_width_score','vehicle_access_score','guest_convenience_score','operational_access_score','data_confidence_score','beta','graph_nodes','graph_links','nearest_road_width_m','coordinate_to_road_m','nearby_poi_count','nearby_poi_categories']
DAYS={'weekday':'OCCUPANCY_WEEKDAY','friday':'OCCUPANCY_FRIDAY','saturday':'OCCUPANCY_SATURDAY'}
def jb(x):
    x=np.asarray(x); n=len(x); z=(x-x.mean())/x.std(ddof=1); s=np.mean(z**3); k=np.mean(z**4); stat=n/6*(s*s+(k-3)**2/4); return stat, math.exp(-stat/2)
def fit(x,y,quadratic=False):
    X=np.column_stack([np.ones(len(x)),x]+([x*x] if quadratic else [])); b=np.linalg.lstsq(X,y,rcond=None)[0]; pred=X@b; ss=((y-y.mean())**2).sum(); r2=1-((y-pred)**2).sum()/ss; h=np.sum(X*(X@np.linalg.inv(X.T@X)),axis=1); mse=((y-pred)**2).sum()/(len(x)-X.shape[1]); cooks=((y-pred)**2/(X.shape[1]*mse))*h/(1-h)**2; return r2, pred, cooks
p=argparse.ArgumentParser(); p.add_argument('--accessibility',type=Path,required=True);p.add_argument('--occupancy',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
acc=pd.read_csv(a.accessibility);occ=pd.read_csv(a.occupancy);occ['MONTH_YEAR']=pd.to_datetime(occ.MONTH_YEAR);j=acc.merge(occ,on='PROPERTY_CODE')
for c in METRICS+list(DAYS.values()): j[c]=pd.to_numeric(j[c],errors='coerce')
rows=[]
for month,g in j.groupby(j.MONTH_YEAR.dt.strftime('%Y-%m')):
 for day,target in DAYS.items():
  for m in METRICS:
   d=g[[m,target]].dropna(); x=d[m].to_numpy(); y=d[target].to_numpy(); jr,jp=jb(x); oy,op=jb(y); lr,pred,cook=fit(x,y); qr,_,_=fit(x,y,True); resid=y-pred
   rows.append({'month':month,'occupancy_day_type':day,'poc_metric':m,'n':len(d),'metric_jb_p':round(jp,5),'occupancy_jb_p':round(op,5),'linear_r2':round(lr,4),'quadratic_r2':round(qr,4),'quadratic_r2_gain':round(qr-lr,4),'abs_residual_correlation':round(pd.Series(x).corr(pd.Series(np.abs(resid))),4),'max_cooks_distance':round(float(cook.max()),4),'influential_observations':int((cook>4/len(d)).sum())})
a.output.parent.mkdir(parents=True,exist_ok=True);pd.DataFrame(rows).to_csv(a.output,index=False);print(f'Wrote {len(rows)} diagnostics to {a.output}')
