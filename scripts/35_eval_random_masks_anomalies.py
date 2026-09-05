from _common import *
import argparse,json,torch,numpy as np
from cncjepa.config import load_config
from cncjepa.pipeline import prepare,loaders_from_ds,batch_to
from cncjepa.factory import build_jepa
from cncjepa.metrics import rmse
from cncjepa.corruptions import corrupt
from cncjepa.utils import device_from_arg
p=argparse.ArgumentParser(); p.add_argument('--config',default='configs/base.yaml'); p.add_argument('--ckpt',default='outputs/jepa_finetune/best.pt'); p.add_argument('--device',default='auto'); p.add_argument('--out',default='outputs/corruption_eval.json'); a=p.parse_args(); c=load_config(a.config); _,_,ds,_,_=prepare(c,training_mask=False); ld=loaders_from_ds(ds,c,False)['target_all']; dev=device_from_arg(a.device); m=build_jepa(c,True); m.load_state_dict(torch.load(a.ckpt,map_location='cpu')['model'],strict=False); m.to(dev).eval(); rep={}
for kind in ['random_mask','gaussian','spike','drift','step','missing_block','sensor_bias','mixed']:
 rep[kind]={}
 for sev in [.05,.1,.2,.4]:
  ys=[]; ps=[]; ms=[]
  with torch.no_grad():
   for bi,b in enumerate(ld):
    b=batch_to(b,dev); xc=corrupt(b['x'].cpu().numpy(),kind,sev,seed=1000+bi); pc=torch.as_tensor(np.isfinite(xc),device=dev,dtype=b['present'].dtype)*b['present']; xc=torch.as_tensor(xc,device=dev,dtype=b['x'].dtype); o=m(xc,b['past_actions'],b['future_actions'],pc,b['schema'],y=None); ys.append(b['y'].cpu().numpy()); ps.append(o['mu'].cpu().numpy()); ms.append(b['target_present'].cpu().numpy())
  y=np.concatenate(ys); pr=np.concatenate(ps); mk=np.concatenate(ms).astype(bool); rep[kind][str(sev)]=rmse(np.where(mk,y,np.nan),np.where(mk,pr,np.nan))
Path(a.out).parent.mkdir(parents=True,exist_ok=True); Path(a.out).write_text(json.dumps(rep,indent=2)); print(a.out)
