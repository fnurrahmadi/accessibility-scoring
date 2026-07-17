"""Five-band occupancy comparisons using permutation Kruskal–Wallis tests."""
import argparse
from pathlib import Path
import numpy as np
import pandas as pd

METRICS=['overall_accessibility_score','connectivity_score','road_width_score','vehicle_access_score','guest_convenience_score','operational_access_score','data_confidence_score','beta','graph_nodes','graph_links','nearest_road_width_m','coordinate_to_road_m','nearby_poi_count','nearby_poi_categories']
DAYS={'weekday':'OCCUPANCY_WEEKDAY','friday':'OCCUPANCY_FRIDAY','saturday':'OCCUPANCY_SATURDAY'}
def band(x):
    return np.minimum(((pd.Series(x).rank(method='first').to_numpy()-1)*5/len(x)).astype(int),4)
def h_stat(y,g):
    ranks=pd.Series(y).rank(method='average').to_numpy(); n=len(y); total=0
    for i in range(5):
        r=ranks[g==i]; total+=(r.sum()**2)/len(r)
    h=12*total/(n*(n+1))-3*(n+1)
    _,counts=np.unique(y,return_counts=True); correction=1-(np.sum(counts**3-counts)/(n**3-n)); return h/correction if correction else 0
p=argparse.ArgumentParser();p.add_argument('--accessibility',type=Path,required=True);p.add_argument('--occupancy',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--permutations',type=int,default=999);a=p.parse_args()
acc=pd.read_csv(a.accessibility);occ=pd.read_csv(a.occupancy);occ['MONTH_YEAR']=pd.to_datetime(occ.MONTH_YEAR);j=acc.merge(occ,on='PROPERTY_CODE')
for c in METRICS+list(DAYS.values()): j[c]=pd.to_numeric(j[c],errors='coerce')
rng=np.random.default_rng(20260715); rows=[]
for month,g in j.groupby(j.MONTH_YEAR.dt.strftime('%Y-%m')):
 for day,target in DAYS.items():
  for metric in METRICS:
   d=g[[metric,target]].dropna(); x=d[metric].to_numpy(); y=d[target].to_numpy(); b=band(x); observed=h_stat(y,b); null=np.array([h_stat(rng.permutation(y),b) for _ in range(a.permutations)]); row={'month':month,'occupancy_day_type':day,'poc_metric':metric,'property_count':len(d),'kruskal_wallis_h':round(observed,4),'permutation_p_value':round((1+(null>=observed).sum())/(a.permutations+1),4)}
   for i in range(5):
    values=y[b==i]; row[f'band_{i+1}_median_occupancy']=round(float(np.median(values)),4);row[f'band_{i+1}_mean_occupancy']=round(float(values.mean()),4)
   rows.append(row)
a.output.parent.mkdir(parents=True,exist_ok=True);pd.DataFrame(rows).to_csv(a.output,index=False);print(f'Wrote {len(rows)} tests to {a.output}')
