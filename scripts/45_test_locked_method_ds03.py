from _common import *
import argparse,json,hashlib,torch
from cncjepa.config import load_config
from cncjepa.pipeline import prepare,loaders_from_ds
from cncjepa.factory import build_jepa
from cncjepa.trainers import evaluate_jepa
from cncjepa.utils import device_from_arg
p=argparse.ArgumentParser(); p.add_argument('--lock',default='outputs/random_search/LOCKED_BEST.json'); p.add_argument('--device',default='auto'); p.add_argument('--out',default='outputs/random_search/locked_ds03_test.json'); a=p.parse_args(); L=json.loads(Path(a.lock).read_text()); assert hashlib.sha256(Path(L['config']).read_bytes()).hexdigest()==L['config_sha256']; assert hashlib.sha256(Path(L['checkpoint']).read_bytes()).hexdigest()==L['checkpoint_sha256']; c=load_config(L['config']); _,_,ds,_,_=prepare(c,training_mask=False); ld=loaders_from_ds(ds,c,False); dev=device_from_arg(a.device); m=build_jepa(c,True); m.load_state_dict(torch.load(L['checkpoint'],map_location='cpu')['model'],strict=False); m.to(dev); rep={'method':L['method'],'target_ds03':evaluate_jepa(m,ld['target_all'],dev)[0]}; Path(a.out).write_text(json.dumps(rep,indent=2)); print(json.dumps(rep,indent=2))
