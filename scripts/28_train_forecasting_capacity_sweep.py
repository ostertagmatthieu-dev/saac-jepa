from _common import *
import argparse,copy,json
from cncjepa.config import load_config,save_config
from cncjepa.pipeline import prepare,loaders_from_ds
from cncjepa.factory import build_forecaster
from cncjepa.trainers import train_forecaster
from cncjepa.utils import device_from_arg
p=argparse.ArgumentParser(); p.add_argument('--config',default='configs/base.yaml'); p.add_argument('--device',default='auto'); p.add_argument('--out',default='outputs/capacity_sweep'); a=p.parse_args(); base=load_config(a.config); rep={}
for name in ['transformer','patchtst','itransformer']:
 for d in [64,128,256,512]:
  c=copy.deepcopy(base); c['model']['d_model']=d; c['model']['nhead']=min(8,max(1,d//32)); _,_,ds,_,_=prepare(c,training_mask=False); ld=loaders_from_ds(ds,c); out=Path(a.out)/f'{name}_d{d}'; save_config(c,out/'config.yaml'); rep[f'{name}_d{d}']=train_forecaster(build_forecaster(name,c),ld['source_train'],ld['source_val'],c,device_from_arg(a.device),out)
Path(a.out).mkdir(parents=True,exist_ok=True); (Path(a.out)/'summary.json').write_text(json.dumps(rep,indent=2)); print(rep)
