from _common import *
import argparse
from cncjepa.config import load_config
from cncjepa.data import load_table,resample_dataframe,deterministic_group_split,save_split_manifest
p=argparse.ArgumentParser(); p.add_argument('--config',default='configs/base.yaml'); p.add_argument('--out',default='outputs/split_manifest.json'); a=p.parse_args(); cfg=load_config(a.config); df=resample_dataframe(load_table(cfg['paths']['data']),cfg); sp=deterministic_group_split(df,cfg); save_split_manifest(sp,cfg,a.out); print(a.out)
