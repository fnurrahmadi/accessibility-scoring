"""Dependency-free shallow random-tree ensemble with grouped CV and permutation importance."""
import argparse
from pathlib import Path
import numpy as np
import pandas as pd

POC=['overall_accessibility_score','connectivity_score','road_width_score','vehicle_access_score','guest_convenience_score','operational_access_score','data_confidence_score','beta','graph_nodes','graph_links','nearest_road_width_m','coordinate_to_road_m','nearby_poi_count','nearby_poi_categories']
DAYS=['OCCUPANCY_WEEKDAY','OCCUPANCY_FRIDAY','OCCUPANCY_SATURDAY']
class Tree:
 def __init__(s,depth=4,minleaf=12,rng=None):s.depth=depth;s.minleaf=minleaf;s.rng=rng
 def fit(s,X,y,d=0):
  node={'v':float(y.mean())}
  if d==s.depth or len(y)<2*s.minleaf:return node
  best=None; features=s.rng.choice(X.shape[1],max(1,int(np.sqrt(X.shape[1]))),replace=False)
  for f in features:
   vals=np.unique(X[:,f]); cuts=vals[1:-1: max(1,len(vals)//12)]
   for c in cuts:
    l=X[:,f]<=c
    if l.sum()<s.minleaf or (~l).sum()<s.minleaf:continue
    loss=l.sum()*np.var(y[l])+(~l).sum()*np.var(y[~l])
    if best is None or loss<best[0]:best=(loss,f,c,l)
  if best is None:return node
  _,f,c,l=best;node.update(f=f,c=c,l=s.fit(X[l],y[l],d+1),r=s.fit(X[~l],y[~l],d+1));return node
 def predict(s,node,X):
  if 'f' not in node:return np.full(len(X),node['v'])
  m=X[:,node['f']]<=node['c'];out=np.empty(len(X));out[m]=s.predict(node['l'],X[m]);out[~m]=s.predict(node['r'],X[~m]);return out
def forest_fit(X,y,seed,trees=60):
 rng=np.random.default_rng(seed);model=[]
 for _ in range(trees):
  ix=rng.integers(0,len(y),len(y));t=Tree(rng=rng);model.append(t.fit(X[ix],y[ix]))
 return model
def predict(model,X):return np.mean([Tree().predict(t,X) for t in model],axis=0)
p=argparse.ArgumentParser();p.add_argument('--accessibility',type=Path,required=True);p.add_argument('--occupancy',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args();rng=np.random.default_rng(20260715)
acc=pd.read_csv(a.accessibility);occ=pd.read_csv(a.occupancy);occ['MONTH_YEAR']=pd.to_datetime(occ.MONTH_YEAR)
long=occ.melt(id_vars=['PROPERTY_CODE','MONTH_YEAR'],value_vars=DAYS,var_name='day_type',value_name='occupancy');long['occupancy']=pd.to_numeric(long.occupancy,errors='coerce');d=acc.merge(long,on='PROPERTY_CODE').dropna(subset=['occupancy']).copy()
for c in POC:d[c]=pd.to_numeric(d[c],errors='coerce').fillna(pd.to_numeric(d[c],errors='coerce').median())
Xbase=pd.get_dummies(d[POC+['CITY','MONTH_YEAR','day_type']],columns=['CITY','MONTH_YEAR','day_type'],dtype=float);names=list(Xbase.columns);X=Xbase.to_numpy(float);y=d.occupancy.to_numpy(float);groups=d.PROPERTY_CODE.to_numpy();fold=np.array([hash(x)%5 for x in groups])
pred=np.zeros(len(y));models=[];imports=np.zeros((5,len(POC)))
for k in range(5):
 tr=fold!=k;te=~tr;m=forest_fit(X[tr],y[tr],k);base=np.mean((y[te]-predict(m,X[te]))**2);pred[te]=predict(m,X[te]);models.append(m)
 for j,name in enumerate(POC):
  col=names.index(name);z=X[te].copy();z[:,col]=rng.permutation(z[:,col]);imports[k,j]=np.mean((y[te]-predict(m,z))**2)-base
r2=1-np.sum((y-pred)**2)/np.sum((y-y.mean())**2);a.output_dir.mkdir(parents=True,exist_ok=True)
pd.DataFrame([{'property_month_day_rows':len(d),'unique_properties':d.PROPERTY_CODE.nunique(),'grouped_cv_r2':round(float(r2),4),'grouped_cv_rmse':round(float(np.sqrt(np.mean((y-pred)**2))),4)}]).to_csv(a.output_dir/'tree_model_summary.csv',index=False)
imp=pd.DataFrame({'poc_metric':POC,'mean_permutation_mse_increase':imports.mean(0),'positive_fold_count':(imports>0).sum(0)}).sort_values('mean_permutation_mse_increase',ascending=False);imp.to_csv(a.output_dir/'tree_permutation_importance.csv',index=False)
print(f'Grouped CV R2={r2:.4f}; wrote results to {a.output_dir}')
