"""Run-level paired statistical tests on DS03 (exact sign-flip, Wilcoxon, bootstrap CI). Runs are the independent units: 7 on the real target machine."""
from _common import *
import argparse,json,pandas as pd,numpy as np
from cncjepa.metrics import paired_stats
p=argparse.ArgumentParser(); p.add_argument('--jepa',default='outputs/per_channel_run.csv'); p.add_argument('--baseline'); p.add_argument('--out',default='outputs/paired_stats_run_level.json'); a=p.parse_args(); j=pd.read_csv(a.jepa); jrun=j.groupby('run').rmse_z.mean();
if a.baseline:
 b=pd.read_csv(a.baseline).groupby('run').rmse_z.mean(); common=jrun.index.intersection(b.index); rep=paired_stats(jrun.loc[common].values,b.loc[common].values); rep['n_runs']=len(common)
else: rep={'n_runs':int(jrun.size),'note':'Pass --baseline per_channel_run.csv from a competing model to obtain paired exact sign-flip, Wilcoxon and bootstrap CI.','jepa_run_rmse':jrun.to_dict()}
Path(a.out).parent.mkdir(parents=True,exist_ok=True); Path(a.out).write_text(json.dumps(rep,indent=2)); print(json.dumps(rep,indent=2))
