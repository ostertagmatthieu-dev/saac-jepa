"""Reviewer support experiment: repeated/grouped source-session CV.
It cannot replace missing extra machines, but quantifies variance across the 30 DS01 sessions.
"""
from _common import *
import argparse, copy, json, numpy as np, pandas as pd
from sklearn.model_selection import GroupKFold
from cncjepa.config import load_config, save_config
from cncjepa.data import load_table

p=argparse.ArgumentParser(); p.add_argument('--config',default='configs/base.yaml'); p.add_argument('--out',default='outputs/source_group_cv'); p.add_argument('--folds',type=int,default=5); a=p.parse_args()
cfg=load_config(a.config); df=load_table(cfg['paths']['data']); s=cfg['schema']; src=df[df[s['machine']].astype(str)==str(s['source_machine'])].copy(); group_col=s['session']; groups=src[group_col].astype(str).to_numpy(); idx=np.arange(len(src)); out=Path(a.out); out.mkdir(parents=True,exist_ok=True)
gkf=GroupKFold(n_splits=min(a.folds,len(np.unique(groups))))
rows=[]
for fold,(tr,va) in enumerate(gkf.split(idx,groups=groups)):
    train_sessions=sorted(src.iloc[tr][group_col].astype(str).unique().tolist()); val_sessions=sorted(src.iloc[va][group_col].astype(str).unique().tolist())
    rows.append({'fold':fold,'n_train_rows':len(tr),'n_val_rows':len(va),'n_train_sessions':len(train_sessions),'n_val_sessions':len(val_sessions),'train_sessions':train_sessions,'val_sessions':val_sessions})
(out/'source_group_cv_manifest.json').write_text(json.dumps(rows,indent=2))
print(json.dumps([ {k:v for k,v in r.items() if not k.endswith('sessions')} for r in rows],indent=2))
