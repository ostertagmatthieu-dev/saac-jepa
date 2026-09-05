from _common import *
import argparse, json
from cncjepa.config import load_config
from cncjepa.data import load_table,resample_dataframe
p=argparse.ArgumentParser(); p.add_argument('--config',default='configs/base.yaml'); p.add_argument('--rates',default='0.5,1,2,5'); p.add_argument('--out',default='outputs/resample_sensitivity.json'); a=p.parse_args(); cfg=load_config(a.config); df=load_table(cfg['paths']['data']); rep={}
for hz in map(float,a.rates.split(',')): rep[str(hz)]={'rows':len(resample_dataframe(df,cfg,hz))}
Path(a.out).parent.mkdir(parents=True,exist_ok=True); Path(a.out).write_text(json.dumps(rep,indent=2)); print(rep)
