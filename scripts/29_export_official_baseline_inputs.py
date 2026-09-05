from _common import *
import argparse,json,numpy as np
from cncjepa.config import load_config
from cncjepa.pipeline import prepare
p=argparse.ArgumentParser(); p.add_argument('--config',default='configs/base.yaml'); p.add_argument('--out',default='outputs/official_baseline_export'); a=p.parse_args(); c=load_config(a.config); _,sp,_,_,_=prepare(c,training_mask=False); out=Path(a.out); out.mkdir(parents=True,exist_ok=True)
for k in ['source_train','source_val','source_test','target_all']: sp[k].to_csv(out/f'{k}.csv',index=False)
(out/'README.json').write_text(json.dumps({'purpose':'Identical audited split export for official SimMTM/other repository integrations','warning':'Style baselines in scripts 22-26 are controlled in-house implementations, not claims of exact reproduction of every original paper.'},indent=2)); print(out)
