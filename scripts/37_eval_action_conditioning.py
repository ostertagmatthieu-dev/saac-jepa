from _common import *
import argparse,json,torch,numpy as np
from cncjepa.config import load_config
from cncjepa.pipeline import prepare,loaders_from_ds,batch_to
from cncjepa.factory import build_jepa
from cncjepa.metrics import rmse
from cncjepa.utils import device_from_arg
p=argparse.ArgumentParser(); p.add_argument('--config',default='configs/base.yaml'); p.add_argument('--ckpt',default='outputs/jepa_finetune/best.pt'); p.add_argument('--device',default='auto'); p.add_argument('--out',default='outputs/action_conditioning.json'); a=p.parse_args(); c=load_config(a.config); _,_,ds,_,_=prepare(c,training_mask=False); ld=loaders_from_ds(ds,c,False)['target_all']; dev=device_from_arg(a.device); m=build_jepa(c,True); m.load_state_dict(torch.load(a.ckpt,map_location='cpu')['model'],strict=False); m.to(dev).eval(); modes=['true','zero','shuffle']; rep={}
for mode in modes:
 ys=[]; ps=[]; ms=[]
 with torch.no_grad():
  for b in ld:
   b=batch_to(b,dev); fa=b['future_actions']
   if mode=='zero': fa=torch.zeros_like(fa)
   elif mode=='shuffle': fa=fa[torch.randperm(fa.size(0),device=dev)]
   o=m(b['x'],b['past_actions'],fa,b['present'],b['schema'],y=None); ys.append(b['y'].cpu().numpy()); ps.append(o['mu'].cpu().numpy()); ms.append(b['target_present'].cpu().numpy())
 y=np.concatenate(ys); pr=np.concatenate(ps); mk=np.concatenate(ms).astype(bool); rep[mode]=rmse(np.where(mk,y,np.nan),np.where(mk,pr,np.nan))
rep['action_gain_vs_zero']=rep['zero']-rep['true']; rep['action_gain_vs_shuffle']=rep['shuffle']-rep['true']; Path(a.out).parent.mkdir(parents=True,exist_ok=True); Path(a.out).write_text(json.dumps(rep,indent=2)); print(json.dumps(rep,indent=2))
