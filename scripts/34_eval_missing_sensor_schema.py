from _common import *
import argparse,json,torch,copy
from cncjepa.config import load_config
from cncjepa.pipeline import prepare,loaders_from_ds
from cncjepa.factory import build_jepa
from cncjepa.trainers import evaluate_jepa
from cncjepa.utils import device_from_arg
p=argparse.ArgumentParser(); p.add_argument('--config',default='configs/base.yaml'); p.add_argument('--ckpt',default='outputs/jepa_finetune/best.pt'); p.add_argument('--device',default='auto'); p.add_argument('--out',default='outputs/schema_sensitivity.json'); a=p.parse_args(); c=load_config(a.config); dev=device_from_arg(a.device); model=build_jepa(c,True); model.load_state_dict(torch.load(a.ckpt,map_location='cpu')['model'],strict=False); model.to(dev); rep={}; sensors=c['schema']['sensors']; transfer=c['schema']['transfer_sensors']
for k,subset in [('17',sensors),('10_transfer',transfer),('8',transfer[:8]),('6',transfer[:6]),('4',transfer[:4])]:
 _,_,ds,_,_=prepare(c,sensor_subset=subset,training_mask=False); ld=loaders_from_ds(ds,c,False); rep[k]=evaluate_jepa(model,ld['target_all'],dev)[0]
Path(a.out).parent.mkdir(parents=True,exist_ok=True); Path(a.out).write_text(json.dumps(rep,indent=2)); print(json.dumps(rep,indent=2))
