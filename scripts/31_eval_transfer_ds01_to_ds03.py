from _common import *
import argparse,json,torch
from torch.utils.data import DataLoader
from cncjepa.config import load_config
from cncjepa.pipeline import prepare
from cncjepa.data import target_support_query_split,WindowDataset,collate
from cncjepa.factory import build_jepa
from cncjepa.adaptation import adapt_jepa
from cncjepa.trainers import evaluate_jepa
from cncjepa.utils import device_from_arg
p=argparse.ArgumentParser(); p.add_argument('--config',default='configs/base.yaml'); p.add_argument('--ckpt',default='outputs/jepa_finetune/best.pt'); p.add_argument('--device',default='auto'); p.add_argument('--out',default='outputs/transfer_ds01_ds03.json'); a=p.parse_args(); c=load_config(a.config); _,sp,_,sn,an=prepare(c,training_mask=False); dev=device_from_arg(a.device); base=build_jepa(c,True); base.load_state_dict(torch.load(a.ckpt,map_location='cpu')['model'],strict=False); base.to(dev); rep={}
for frac in c['protocol']['target_support_fractions']:
 sup,q=target_support_query_split(sp['target_all'],c,float(frac)); qds=WindowDataset(q,c,sn,an,training=False); ql=DataLoader(qds,batch_size=c['train']['batch_size'],collate_fn=collate)
 model=base; adapted=False
 if float(frac)>0 and len(sup)>=c['protocol']['context_len']+max(c['protocol']['horizons']):
  sds=WindowDataset(sup,c,sn,an,training=False)
  # Short support prefixes can yield zero windows (runs are ~200-600 s at 1 Hz); fall back to zero-shot.
  if len(sds)>0:
   sl=DataLoader(sds,batch_size=min(c['train']['batch_size'],len(sds)),shuffle=True,collate_fn=collate); model=adapt_jepa(base,sl,dev,steps=50,lr=1e-4,mode='predictor'); adapted=True
 r=evaluate_jepa(model,ql,dev)[0] if len(qds)>0 else {'rmse':None}
 r['adapted']=adapted; rep[str(frac)]=r
Path(a.out).parent.mkdir(parents=True,exist_ok=True); Path(a.out).write_text(json.dumps(rep,indent=2)); print(json.dumps(rep,indent=2))
