from _common import *
import argparse,json
from cncjepa.config import load_config,save_config
from cncjepa.pipeline import prepare,loaders_from_ds
from cncjepa.factory import build_forecaster
from cncjepa.trainers import train_forecaster
from cncjepa.utils import device_from_arg,set_seed
p=argparse.ArgumentParser(); p.add_argument('--config',default='configs/base.yaml'); p.add_argument('--models',default='persistence,drift,dlinear,mlp,gru,lstm,tcn,transformer,tsmixer,patchtst,itransformer,rssm',help='persistence and drift are mandatory no-learn references and run first'); p.add_argument('--out',default='outputs/baselines_supervised'); p.add_argument('--device',default='auto'); a=p.parse_args(); cfg=load_config(a.config); set_seed(cfg['seed']); _,_,ds,_,_=prepare(cfg,training_mask=False); ld=loaders_from_ds(ds,cfg); dev=device_from_arg(a.device); rep={}
for name in a.models.split(','):
 out=Path(a.out)/name; save_config(cfg,out/'config.yaml'); rep[name]=train_forecaster(build_forecaster(name,cfg),ld['source_train'],ld['source_val'],cfg,dev,out)
Path(a.out).mkdir(parents=True,exist_ok=True); (Path(a.out)/'summary.json').write_text(json.dumps(rep,indent=2)); print(rep)
