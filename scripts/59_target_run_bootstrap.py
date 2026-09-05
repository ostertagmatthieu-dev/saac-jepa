"""Run-level uncertainty for the small n=6 DS03 target set.
Consumes per-run metrics produced by script 32 or 56 and reports bootstrap CIs.
"""
from _common import *
import argparse, numpy as np, pandas as pd, json
p=argparse.ArgumentParser(); p.add_argument('--csv',required=True); p.add_argument('--metric',default='rmse_z'); p.add_argument('--out',default='outputs/target_run_bootstrap.json'); p.add_argument('--samples',type=int,default=20000); p.add_argument('--seed',type=int,default=20260820); a=p.parse_args()
df=pd.read_csv(a.csv)
if a.metric not in df.columns: raise KeyError(f'{a.metric} not in {list(df.columns)}')
# Aggregate channels/horizons within each run first. Runs, not windows, are the independent units.
run_col='run' if 'run' in df.columns else 'run_id'
r=df.groupby(run_col,dropna=False)[a.metric].mean().dropna().to_numpy(float)
if len(r)<2: raise RuntimeError('Need at least 2 independent target runs')
rng=np.random.default_rng(a.seed); means=np.empty(a.samples)
for i in range(a.samples): means[i]=rng.choice(r,size=len(r),replace=True).mean()
res={'n_independent_runs':int(len(r)),'mean':float(r.mean()),'median':float(np.median(r)),'std':float(r.std(ddof=1)),'bootstrap_95_ci':[float(np.quantile(means,.025)),float(np.quantile(means,.975))]}
Path(a.out).parent.mkdir(parents=True,exist_ok=True); Path(a.out).write_text(json.dumps(res,indent=2)); print(json.dumps(res,indent=2))
