"""Pretrain the action-conditioned JEPA from random initialisation (pure SSL).

P3-FIX protocol:
  * best.pt is selected on a TRUE held-out SSL objective (val_ssl = latent_weight*latent
    prediction loss + vicreg_weight*vicreg on source_val), never on training loss.
  * `jepa.physical_weight` is overridden to 0.0 here (and again inside train_jepa when
    pretrain_only=True) so no gradient reaches the physical mu/logvar head during pure SSL.
    Use script 11 to train that head.
  * Schema consistency runs in ssl_mode: it constrains LATENT predictions under a dropped
    sensor view, not the untrained physical head.
  * Validation masks are deterministic (per-index seeded); all RNGs are seeded from cfg.seed.
  * Optional scheduled EMA via cfg.jepa.ema_schedule={start,end,kind}; otherwise fixed cfg.jepa.ema.

Outputs: <out>/{best.pt,last.pt,history.csv,latent_health.csv,config.yaml}
"""
from _common import *
import argparse, copy
from cncjepa.config import load_config,save_config
from cncjepa.pipeline import prepare,loaders_from_ds
from cncjepa.factory import build_jepa
from cncjepa.trainers import train_jepa
from cncjepa.utils import set_seed,device_from_arg

p=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
p.add_argument('--config',default='configs/base.yaml')
p.add_argument('--out',default='outputs/jepa_pretrain')
p.add_argument('--device',default='auto')
p.add_argument('--epochs',type=int)
p.add_argument('--seed',type=int,default=None,help='override cfg.seed (python/numpy/torch/cuda/DataLoader workers)')
p.add_argument('--val-mask',action='store_true',help='apply the deterministic per-index mask to source_val too (masked-SSL validation protocol)')
p.add_argument('--ema-schedule',default=None,metavar='START,END',help='scheduled EMA, e.g. 0.99,0.9999 (default: fixed cfg.jepa.ema)')
a=p.parse_args()

cfg=copy.deepcopy(load_config(a.config))
if a.seed is not None: cfg['seed']=int(a.seed)
cfg['jepa']['physical_weight']=0.0   # pure SSL: physical head is not trained here
if a.ema_schedule:
    s,e=[float(v) for v in a.ema_schedule.split(',')]; cfg['jepa']['ema_schedule']={'start':s,'end':e,'kind':'linear'}
set_seed(cfg['seed'])
_,_,ds,_,_=prepare(cfg,training_mask=True,val_mask=a.val_mask)
ld=loaders_from_ds(ds,cfg)
m=build_jepa(cfg,True)
save_config(cfg,Path(a.out)/'config.yaml')
train_jepa(m,ld['source_train'],ld['source_val'],cfg,device_from_arg(a.device),a.out,pretrain_only=True,max_epochs=a.epochs)
print(Path(a.out)/'best.pt')
