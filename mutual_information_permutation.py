"""Quantile-binned mutual information with permutation tests for POC metrics."""
import argparse
from pathlib import Path
import numpy as np
import pandas as pd

METRICS = ['overall_accessibility_score','connectivity_score','road_width_score','vehicle_access_score','guest_convenience_score','operational_access_score','data_confidence_score','beta','graph_nodes','graph_links','nearest_road_width_m','coordinate_to_road_m','nearby_poi_count','nearby_poi_categories']
DAYS = {'weekday':'OCCUPANCY_WEEKDAY','friday':'OCCUPANCY_FRIDAY','saturday':'OCCUPANCY_SATURDAY'}

def bins(x, count=5):
    ranks = pd.Series(x).rank(method='average').to_numpy()
    return np.minimum(((ranks - 1) * count / len(x)).astype(int), count - 1)

def mi(x, y, count=5):
    table = np.zeros((count, count))
    np.add.at(table, (x, y), 1)
    p = table / table.sum()
    expected = p.sum(1, keepdims=True) @ p.sum(0, keepdims=True)
    mask = p > 0
    return float((p[mask] * np.log(p[mask] / expected[mask])).sum())

p = argparse.ArgumentParser()
p.add_argument('--accessibility', type=Path, required=True)
p.add_argument('--occupancy', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
p.add_argument('--permutations', type=int, default=999)
a = p.parse_args()
acc = pd.read_csv(a.accessibility)
occ = pd.read_csv(a.occupancy)
occ['MONTH_YEAR'] = pd.to_datetime(occ.MONTH_YEAR)
j = acc.merge(occ, on='PROPERTY_CODE')
for c in METRICS + list(DAYS.values()):
    j[c] = pd.to_numeric(j[c], errors='coerce')
rng = np.random.default_rng(20260715)
rows = []
for month, g in j.groupby(j.MONTH_YEAR.dt.strftime('%Y-%m')):
    for day, target in DAYS.items():
        for metric in METRICS:
            d = g[[metric, target]].dropna()
            x, y = bins(d[metric]), bins(d[target])
            observed = mi(x, y)
            null = np.array([mi(x, rng.permutation(y)) for _ in range(a.permutations)])
            pvalue = (1 + (null >= observed).sum()) / (a.permutations + 1)
            rows.append({'month':month,'occupancy_day_type':day,'poc_metric':metric,'property_count':len(d),'mutual_information_nats':round(observed,4),'permutation_p_value':round(pvalue,4),'null_mean_mi':round(float(null.mean()),4)})
a.output.parent.mkdir(parents=True, exist_ok=True)
pd.DataFrame(rows).to_csv(a.output, index=False)
print(f'Wrote {len(rows)} tests to {a.output}')
