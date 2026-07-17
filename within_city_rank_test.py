"""Within-city rank associations with permutation testing for POC metrics."""
import argparse
from pathlib import Path
import numpy as np
import pandas as pd

METRICS=['overall_accessibility_score','connectivity_score','road_width_score','vehicle_access_score','guest_convenience_score','operational_access_score','data_confidence_score','beta','graph_nodes','graph_links','nearest_road_width_m','coordinate_to_road_m','nearby_poi_count','nearby_poi_categories']
DAYS={'weekday':'OCCUPANCY_WEEKDAY','friday':'OCCUPANCY_FRIDAY','saturday':'OCCUPANCY_SATURDAY'}
p=argparse.ArgumentParser();p.add_argument('--accessibility',type=Path,required=True);p.add_argument('--occupancy',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--permutations',type=int,default=999);a=p.parse_args()
acc=pd.read_csv(a.accessibility);occ=pd.read_csv(a.occupancy);occ['MONTH_YEAR']=pd.to_datetime(occ.MONTH_YEAR);j=acc.merge(occ,on='PROPERTY_CODE')
for c in METRICS+list(DAYS.values()):j[c]=pd.to_numeric(j[c],errors='coerce')
rng=np.random.default_rng(20260715); rows=[]
for month,g in j.groupby(j.MONTH_YEAR.dt.strftime('%Y-%m')):
 for day,target in DAYS.items():
  for metric in METRICS:
   d=g[['CITY',metric,target]].dropna(); d=d[d.groupby('CITY').CITY.transform('size')>=3].copy().reset_index(drop=True)
   d['xrank']=d.groupby('CITY')[metric].rank(method='average',pct=True);d['yrank']=d.groupby('CITY')[target].rank(method='average',pct=True)
   obs=d.xrank.corr(d.yrank); city_indices=[v.index.to_numpy() for _,v in d.groupby('CITY')]; y=d.yrank.to_numpy();x=d.xrank.to_numpy(); null=[]
   for _ in range(a.permutations):
    yp=y.copy()
    for idx in city_indices: yp[idx] = rng.permutation(yp[idx])
    null.append(np.corrcoef(x,yp)[0,1])
   null=np.array(null);pvalue=(1+(np.abs(null)>=abs(obs)).sum())/(a.permutations+1)
   rows.append({'month':month,'occupancy_day_type':day,'poc_metric':metric,'properties_in_cities_with_3_plus':len(d),'cities_included':d.CITY.nunique(),'within_city_rank_correlation':round(obs,4),'permutation_p_value':round(pvalue,4)})
a.output.parent.mkdir(parents=True,exist_ok=True);pd.DataFrame(rows).to_csv(a.output,index=False);print(f'Wrote {len(rows)} tests to {a.output}')
