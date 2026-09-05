from _common import *
import argparse, copy
from cncjepa.config import load_config, save_config
from cncjepa.pipeline import prepare, loaders_from_ds
from cncjepa.factory import build_jepa
from cncjepa.trainers import train_jepa
from cncjepa.utils import device_from_arg

p=argparse.ArgumentParser()
p.add_argument('--config',default='configs/base.yaml')
p.add_argument('--device',default='auto')
p.add_argument('--out',default='outputs/abl_layernorm')
a=p.parse_args(); base=load_config(a.config)

# Primary reviewer ablation: JEPA latent vectors with vs without LayerNorm before latent/VICReg losses.
# We keep the Transformer architecture fixed so the ablation isolates the anti-collapse design choice.
for name, latent_ln in [('latent_ln_on', True), ('latent_ln_off', False)]:
    c=copy.deepcopy(base)
    c['jepa']['latent_layernorm']=latent_ln
    _,_,ds,_,_=prepare(c,training_mask=True)
    ld=loaders_from_ds(ds,c)
    out=Path(a.out)/name
    save_config(c,out/'config.yaml')
    train_jepa(build_jepa(c,True),ld['source_train'],ld['source_val'],c,device_from_arg(a.device),out)

# Secondary architectural norm-location ablation, kept separate from the primary JEPA loss ablation.
for mode in ['pre','post']:
    c=copy.deepcopy(base)
    c['model']['layernorm']=mode
    c['jepa']['latent_layernorm']=True
    _,_,ds,_,_=prepare(c,training_mask=True)
    ld=loaders_from_ds(ds,c)
    out=Path(a.out)/f'encoder_{mode}'
    save_config(c,out/'config.yaml')
    train_jepa(build_jepa(c,True),ld['source_train'],ld['source_val'],c,device_from_arg(a.device),out)
