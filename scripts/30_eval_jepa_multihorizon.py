from _common import *
import argparse,json,torch
from cncjepa.config import load_config
from cncjepa.pipeline import prepare,loaders_from_ds
from cncjepa.factory import build_jepa
from cncjepa.trainers import evaluate_jepa
from cncjepa.utils import device_from_arg
p=argparse.ArgumentParser(); p.add_argument('--config',default='configs/base.yaml'); p.add_argument('--ckpt',default='outputs/jepa_finetune/best.pt'); p.add_argument('--device',default='auto'); p.add_argument('--out',default='outputs/eval_multihorizon.json'); a=p.parse_args(); c=load_config(a.config); _,_,ds,_,_=prepare(c,training_mask=False); ld=loaders_from_ds(ds,c,False); dev=device_from_arg(a.device); m=build_jepa(c,True); m.load_state_dict(torch.load(a.ckpt,map_location='cpu')['model'],strict=False); m.to(dev); rep={k:evaluate_jepa(m,ld[k],dev)[0] for k in ['source_test','target_all']}; Path(a.out).parent.mkdir(parents=True,exist_ok=True); Path(a.out).write_text(json.dumps(rep,indent=2)); print(json.dumps(rep,indent=2))
