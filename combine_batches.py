import argparse
from pathlib import Path
import pandas as pd

p=argparse.ArgumentParser(); p.add_argument('--first',type=Path,required=True); p.add_argument('--second',type=Path,required=True); p.add_argument('--output',type=Path,required=True); a=p.parse_args()
first=pd.read_csv(a.first); second=pd.read_csv(a.second)
combined=pd.concat([first.assign(batch='initial_100'),second.assign(batch='additional_107')],ignore_index=True)
dupes=combined[combined.PROPERTY_CODE.duplicated(keep=False)]
if not dupes.empty: raise SystemExit('Duplicate PROPERTY_CODE values found: '+', '.join(sorted(dupes.PROPERTY_CODE.unique())))
a.output.parent.mkdir(parents=True,exist_ok=True); combined.to_csv(a.output,index=False)
print(f'Wrote {len(combined)} rows with {combined.PROPERTY_CODE.nunique()} unique properties')
