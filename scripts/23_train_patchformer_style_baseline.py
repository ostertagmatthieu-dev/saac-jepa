from _common import *
from _ssl_common import run_ssl
import argparse
from cncjepa.config import load_config
p=argparse.ArgumentParser(); p.add_argument('--config',default='configs/base.yaml'); p.add_argument('--out',default='outputs/ssl_patchformer_style'); p.add_argument('--device',default='auto'); a=p.parse_args(); print(run_ssl(load_config(a.config),'patchformer_style',a.out,a.device))
