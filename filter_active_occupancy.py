import argparse
from pathlib import Path
import pandas as pd

p=argparse.ArgumentParser(); p.add_argument('--accessibility',type=Path,required=True); p.add_argument('--occupancy',type=Path,required=True); p.add_argument('--output',type=Path,required=True); a=p.parse_args()
access=pd.read_csv(a.accessibility); occ=pd.read_csv(a.occupancy)
columns=['OCCUPANCY_WEEKDAY','OCCUPANCY_FRIDAY','OCCUPANCY_SATURDAY']
for column in columns: occ[column]=pd.to_numeric(occ[column],errors='coerce')
active=occ.groupby('PROPERTY_CODE')[columns].max().max(axis=1).gt(0)
filtered=access[access.PROPERTY_CODE.isin(active[active].index)].copy()
a.output.parent.mkdir(parents=True,exist_ok=True); filtered.to_csv(a.output,index=False)
print(f'Retained {len(filtered)} of {len(access)} properties; excluded {len(access)-len(filtered)} always-null-or-zero properties')
