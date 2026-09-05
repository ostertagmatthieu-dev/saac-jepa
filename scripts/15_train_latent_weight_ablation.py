from _common import *
import argparse,copy
from cncjepa.config import load_config,save_config
from cncjepa.pipeline import prepare,loaders_from_ds
from cncjepa.factory import build_jepa
from cncjepa.trainers import train_jepa
from cncjepa.utils import device_from_arg
p=argparse.ArgumentParser(); p.add_argument('--config',default='configs/base.yaml'); p.add_argument('--device',default='auto'); p.add_argument('--out',default='outputs/abl_latent_weight'); a=p.parse_args(); base=load_config(a.config)
for w in [0.0,0.25,0.5,1.0,2.0,4.0]:
 c=copy.deepcopy(base); c['jepa']['latent_weight']=w; _,_,ds,_,_=prepare(c,training_mask=True); ld=loaders_from_ds(ds,c); out=Path(a.out)/f'w_{w}'; save_config(c,out/'config.yaml'); train_jepa(build_jepa(c,True),ld['source_train'],ld['source_val'],c,device_from_arg(a.device),out)
