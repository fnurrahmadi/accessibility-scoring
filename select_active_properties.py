#!/usr/bin/env python3
"""Select a city-stratified active-occupancy property batch for POC scoring."""
import argparse
from pathlib import Path
import pandas as pd

def main():
    p=argparse.ArgumentParser(); p.add_argument('--properties',type=Path,required=True); p.add_argument('--occupancy',type=Path,required=True); p.add_argument('--exclude',type=Path,required=True); p.add_argument('--output',type=Path,required=True); p.add_argument('--size',type=int,default=107); p.add_argument('--seed',type=int,default=20260715); a=p.parse_args()
    props=pd.read_csv(a.properties); occ=pd.read_csv(a.occupancy); prior=pd.read_csv(a.exclude)
    cols=['OCCUPANCY_WEEKDAY','OCCUPANCY_FRIDAY','OCCUPANCY_SATURDAY']
    for c in cols: occ[c]=pd.to_numeric(occ[c],errors='coerce')
    active=occ.groupby('PROPERTY_CODE')[cols].max().max(axis=1).gt(0)
    eligible=props[props.PROPERTY_CODE.isin(active[active].index) & ~props.PROPERTY_CODE.isin(prior.PROPERTY_CODE)].copy()
    # Random selection preserves each city's representation in expectation while
    # avoiding over-allocating one row to every small city.
    out=eligible.sample(n=min(a.size,len(eligible)),random_state=a.seed)
    if len(out)<a.size: raise SystemExit(f'Only {len(out)} eligible properties available')
    a.output.parent.mkdir(parents=True,exist_ok=True); out.to_csv(a.output,index=False); print(f'Selected {len(out)} active properties from {len(eligible)} eligible properties')
if __name__=='__main__': main()
