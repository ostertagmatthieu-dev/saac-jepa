from _common import *
import argparse, json, numpy as np
from cncjepa.config import load_config
from cncjepa.data import load_table
p=argparse.ArgumentParser(); p.add_argument('--config',default='configs/base.yaml'); p.add_argument('--out',default='outputs/audit_sessions_channels.json'); a=p.parse_args(); cfg=load_config(a.config); df=load_table(cfg['paths']['data']); s=cfg['schema']; rep={}
for m,g in df.groupby(s['machine']):
    rep[str(m)]={'rows':len(g),'sessions':int(g[s['session']].nunique()),'runs':int(g[s['run']].nunique()),'channel_nonmissing_fraction':{c:float(g[c].notna().mean()) for c in s['sensors']}}
Path(a.out).parent.mkdir(parents=True,exist_ok=True); Path(a.out).write_text(json.dumps(rep,indent=2),encoding='utf-8'); print(json.dumps(rep,indent=2))
