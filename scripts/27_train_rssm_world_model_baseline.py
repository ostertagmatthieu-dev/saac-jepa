from _common import *
import argparse
from cncjepa.config import load_config
from cncjepa.pipeline import prepare,loaders_from_ds
from cncjepa.factory import build_forecaster
from cncjepa.trainers import train_forecaster
from cncjepa.utils import device_from_arg
p=argparse.ArgumentParser(); p.add_argument('--config',default='configs/base.yaml'); p.add_argument('--out',default='outputs/rssm'); p.add_argument('--device',default='auto'); a=p.parse_args(); c=load_config(a.config); _,_,ds,_,_=prepare(c,training_mask=False); ld=loaders_from_ds(ds,c); print(train_forecaster(build_forecaster('rssm',c),ld['source_train'],ld['source_val'],c,device_from_arg(a.device),a.out))
