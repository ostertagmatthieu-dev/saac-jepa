"""Reviewer experiment: retrain/evaluate at several sampling rates while preserving physical time spans.
This is stronger than only counting rows after resampling.
"""
from _common import *
import argparse, copy, json
import pandas as pd
from cncjepa.config import load_config, save_config
from cncjepa.data import load_table, resample_dataframe
from cncjepa.pipeline import prepare, loaders_from_ds
from cncjepa.factory import build_jepa
from cncjepa.trainers import train_jepa, evaluate_jepa
from cncjepa.checkpoint import load_jepa_checkpoint
from cncjepa.utils import device_from_arg

p=argparse.ArgumentParser()
p.add_argument('--config',default='configs/base.yaml')
p.add_argument('--device',default='auto')
p.add_argument('--out',default='outputs/sampling_rate_sensitivity')
p.add_argument('--rates',default='0.5,1,2,5')
p.add_argument('--epochs',type=int,default=None)
a=p.parse_args(); base=load_config(a.config); out=Path(a.out); out.mkdir(parents=True,exist_ok=True)
raw=load_table(base['paths']['data']); rates=[float(x) for x in a.rates.split(',')]
base_hz=float(base['protocol']['eval_hz']); base_ctx=int(base['protocol']['context_len']); base_h=list(map(int,base['protocol']['horizons']))
rows=[]
for hz in rates:
    c=copy.deepcopy(base); c['protocol']['eval_hz']=hz
    scale=hz/base_hz
    c['protocol']['context_len']=max(2,int(round(base_ctx*scale)))
    c['protocol']['horizons']=sorted(set(max(1,int(round(h*scale))) for h in base_h))
    rdir=out/f'{hz:g}Hz'; rdir.mkdir(parents=True,exist_ok=True)
    # Save a rate-specific CSV so prepare() uses exactly the audited resampling.
    rr=resample_dataframe(raw,c,hz)
    csv=rdir/'resampled.csv'; rr.to_csv(csv,index=False); c['paths']['data']=str(csv)
    save_config(c,rdir/'config.yaml')
    _,_,ds,_,_=prepare(c,training_mask=True); ld=loaders_from_ds(ds,c)
    model=build_jepa(c,True); dev=device_from_arg(a.device)
    train_jepa(model,ld['source_train'],ld['source_val'],c,dev,rdir,max_epochs=a.epochs)
    model,_=load_jepa_checkpoint(rdir/'best.pt',c,dev)
    src,_=evaluate_jepa(model,ld['source_test'],dev); tgt,_=evaluate_jepa(model,ld['target_all'],dev)
    rows.append({'hz':hz,'context_steps':c['protocol']['context_len'],'horizon_steps':c['protocol']['horizons'],'source_rmse_z':src['rmse'],'target_rmse_z':tgt['rmse']})
pd.DataFrame(rows).to_csv(out/'sampling_rate_results.csv',index=False)
print(json.dumps(rows,indent=2))
