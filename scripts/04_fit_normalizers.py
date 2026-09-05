from _common import *
import argparse, json
from cncjepa.config import load_config
from cncjepa.data import load_table,resample_dataframe,deterministic_group_split
from cncjepa.normalization import Normalizer
p=argparse.ArgumentParser(); p.add_argument('--config',default='configs/base.yaml'); p.add_argument('--out',default='outputs/normalizers.json'); a=p.parse_args(); cfg=load_config(a.config); s=cfg['schema']; sp=deterministic_group_split(resample_dataframe(load_table(cfg['paths']['data']),cfg),cfg); tr=sp['source_train']; sn=Normalizer('zscore').fit(tr[s['sensors']]); an=Normalizer('zscore').fit(tr[s['actions']]); Path(a.out).parent.mkdir(parents=True,exist_ok=True); Path(a.out).write_text(json.dumps({'sensor':sn.state_dict(),'action':an.state_dict()},indent=2)); print(a.out)
