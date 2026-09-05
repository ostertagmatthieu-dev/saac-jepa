from _common import *
import argparse,json,numpy as np
from cncjepa.config import load_config
from cncjepa.data import load_table,resample_dataframe,deterministic_group_split
p=argparse.ArgumentParser(); p.add_argument('--config',default='configs/base.yaml'); a=p.parse_args(); c=load_config(a.config); s=c['schema']; sp=deterministic_group_split(resample_dataframe(load_table(c['paths']['data']),c),c); tr=sp['source_train']; tgt=sp['target_all']; rep={'source_train_mean':tr[s['sensors']].mean().round(4).to_dict(),'target_mean_diagnostic_only':tgt[s['sensors']].mean().round(4).to_dict(),'warning':'target statistics must not enter source-trained normalizer except in explicitly labeled target-support/oracle sensitivity conditions'}; print(json.dumps(rep,indent=2))
