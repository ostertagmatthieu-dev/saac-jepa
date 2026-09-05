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
p=argparse.ArgumentParser(); p.add_argument('--config',default='configs/base.yaml'); p.add_argument('--ckpt',default='outputs/jepa_finetune/best.pt'); p.add_argument('--device',default='auto'); p.add_argument('--out',default='outputs/fewshot_adaptation.json'); a=p.parse_args(); c=load_config(a.config); _,sp,_,sn,an=prepare(c,training_mask=False); dev=device_from_arg(a.device); base=build_jepa(c,True); base.load_state_dict(torch.load(a.ckpt,map_location='cpu')['model'],strict=False); base.to(dev); rep={}
for frac in [0.02,0.05,0.1,0.2,0.4]:
 sup,q=target_support_query_split(sp['target_all'],c,frac); sds=WindowDataset(sup,c,sn,an,training=False); qds=WindowDataset(q,c,sn,an,training=False)
 if len(sds)==0 or len(qds)==0: continue
 sl=DataLoader(sds,batch_size=min(c['train']['batch_size'],len(sds)),shuffle=True,collate_fn=collate); ql=DataLoader(qds,batch_size=c['train']['batch_size'],collate_fn=collate); rep[str(frac)]={}
 for mode in ['head','predictor','sensor_embeddings','full']:
  mm=adapt_jepa(base,sl,dev,steps=100,lr=1e-4,mode=mode); rep[str(frac)][mode]=evaluate_jepa(mm,ql,dev)[0]
Path(a.out).parent.mkdir(parents=True,exist_ok=True); Path(a.out).write_text(json.dumps(rep,indent=2)); print(a.out)
