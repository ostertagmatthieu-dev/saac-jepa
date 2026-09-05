"""Train SAAC-JEPA: flexible sensor tokenizer + schema consistency.

P3-FIX: schema consistency acts on LATENT dynamics, not on the physical head. This script
runs in pure-SSL mode (pretrain_only=True) so best.pt is selected on the held-out SSL
objective and the physical head stays untrained; fine-tune with script 11 --head fresh.
Use --supervised to instead co-train the physical head (schema consistency then reverts to
the mu-space form, which is only meaningful once the head is being trained).

Outputs: <out>/{best.pt,last.pt,history.csv,latent_health.csv,config.yaml}
"""
from _common import *
import argparse,copy
from cncjepa.config import load_config,save_config
from cncjepa.pipeline import prepare,loaders_from_ds
from cncjepa.factory import build_jepa
from cncjepa.trainers import train_jepa
from cncjepa.utils import device_from_arg,set_seed

p=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
p.add_argument('--config',default='configs/base.yaml')
p.add_argument('--out',default='outputs/saac_jepa')
p.add_argument('--device',default='auto')
p.add_argument('--epochs',type=int)
p.add_argument('--seed',type=int,default=None)
p.add_argument('--supervised',action='store_true',help='co-train the physical head (disables pure-SSL selection)')
p.add_argument('--val-mask',action='store_true',help='deterministic per-index masks on source_val too')
a=p.parse_args()

cfg=copy.deepcopy(load_config(a.config))
if a.seed is not None: cfg['seed']=int(a.seed)
cfg['jepa']['schema_consistency_weight']=max(.1,float(cfg['jepa'].get('schema_consistency_weight',0)))
if not a.supervised: cfg['jepa']['physical_weight']=0.0
set_seed(cfg['seed'])
_,_,ds,_,_=prepare(cfg,training_mask=True,val_mask=a.val_mask); ld=loaders_from_ds(ds,cfg)
m=build_jepa(cfg,True)
save_config(cfg,Path(a.out)/'config.yaml')
train_jepa(m,ld['source_train'],ld['source_val'],cfg,device_from_arg(a.device),a.out,pretrain_only=(not a.supervised),max_epochs=a.epochs)
print(Path(a.out)/'best.pt')
