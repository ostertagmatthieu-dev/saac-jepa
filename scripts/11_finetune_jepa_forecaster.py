"""Fine-tune the pretrained JEPA for physical probabilistic forecasting.

P3-FIX protocol:
  * The checkpoint is loaded through the AUDITED loader: missing/unexpected keys and a
    weights_changed proof are printed and written to <out>/load_audit.json.
  * --head fresh (DEFAULT, primary result): only the SSL body (context/target encoders +
    predictor) is loaded; the physical mu/logvar head and action-recovery head are
    reinitialised. A head that was never trained (or trained on a different objective)
    is not a valid warm start and confounds the pretraining comparison.
  * --head loaded: full checkpoint including the head -- kept only as a contamination control.
  * --head none: no pretraining at all (scratch control, arm A of the A/B/C gate).
  * best.pt is selected on held-out physical val RMSE; history.csv logs RMSE/MAE/NLL separately.
"""
from _common import *
import argparse,copy,json,torch
from cncjepa.config import load_config,save_config
from cncjepa.pipeline import prepare,loaders_from_ds
from cncjepa.factory import build_jepa
from cncjepa.checkpoint import load_jepa_checkpoint,load_jepa_body_fresh_head
from cncjepa.trainers import train_jepa
from cncjepa.utils import device_from_arg,set_seed

p=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
p.add_argument('--config',default='configs/base.yaml')
p.add_argument('--pretrained',default='outputs/jepa_pretrain/best.pt')
p.add_argument('--out',default='outputs/jepa_finetune')
p.add_argument('--device',default='auto')
p.add_argument('--epochs',type=int)
p.add_argument('--head',choices=['fresh','loaded','none'],default='fresh',help='fresh=body only + reinit head (primary); loaded=full ckpt (contamination control); none=scratch')
p.add_argument('--seed',type=int,default=None,help='override cfg.seed (default: cfg seed)')
a=p.parse_args()

cfg=copy.deepcopy(load_config(a.config))
if a.seed is not None: cfg['seed']=int(a.seed)
if a.epochs is not None: cfg['train']['epochs']=int(a.epochs)
cfg['jepa']['physical_weight']=float(cfg['jepa'].get('physical_weight',1.) or 1.)
set_seed(cfg['seed'])
dev=device_from_arg(a.device)
_,_,ds,_,_=prepare(cfg,training_mask=True); ld=loaders_from_ds(ds,cfg)

if a.head=='none': m=build_jepa(cfg,True); audit={'note':'scratch, no checkpoint loaded','weights_changed':False,'missing_keys':[],'unexpected_keys':[]}
elif a.head=='fresh': m,audit=load_jepa_body_fresh_head(a.pretrained,cfg,'cpu')
else: m,obj=load_jepa_checkpoint(a.pretrained,cfg,'cpu'); audit=obj['load_audit']
audit['head_mode']=a.head; audit['seed']=cfg['seed']; audit['pretrained']=str(a.pretrained)

save_config(cfg,Path(a.out)/'config.yaml')
Path(a.out).mkdir(parents=True,exist_ok=True); (Path(a.out)/'load_audit.json').write_text(json.dumps(audit,indent=2,default=str),encoding='utf-8')
train_jepa(m,ld['source_train'],ld['source_val'],cfg,dev,a.out,pretrain_only=False,max_epochs=a.epochs)
print(json.dumps({k:audit[k] for k in ('head_mode','weights_changed','missing_keys','unexpected_keys') if k in audit},indent=2,default=str))
print(Path(a.out)/'best.pt')
