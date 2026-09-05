from _common import *
import argparse, json
from cncjepa.config import load_config
from cncjepa.data import load_table, validate_schema
p=argparse.ArgumentParser(); p.add_argument('--config',default='configs/base.yaml'); a=p.parse_args(); cfg=load_config(a.config); df=load_table(cfg['paths']['data']); print(json.dumps(validate_schema(df,cfg),indent=2))
