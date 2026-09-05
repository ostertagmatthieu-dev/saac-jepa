from _common import *
import argparse,json,torch,numpy as np
from scipy.stats import norm
from cncjepa.config import load_config
from cncjepa.pipeline import prepare,loaders_from_ds
from cncjepa.factory import build_jepa
from cncjepa.trainers import evaluate_jepa
from cncjepa.utils import device_from_arg
p=argparse.ArgumentParser(); p.add_argument('--config',default='configs/base.yaml'); p.add_argument('--ckpt',default='outputs/jepa_finetune/best.pt'); p.add_argument('--device',default='auto'); p.add_argument('--out',default='outputs/calibration.json'); a=p.parse_args(); c=load_config(a.config); _,_,ds,_,_=prepare(c,training_mask=False); ld=loaders_from_ds(ds,c,False)['target_all']; dev=device_from_arg(a.device); m=build_jepa(c,True); m.load_state_dict(torch.load(a.ckpt,map_location='cpu')['model'],strict=False); m.to(dev); _,r=evaluate_jepa(m,ld,dev); y,mu,lv,mask=r['y'],r['pred'],r['logvar'],r['mask']; sd=np.exp(.5*np.clip(lv,-8,8)); rep={}
for level in [.5,.8,.9,.95]:
 z=norm.ppf((1+level)/2); inside=(y>=mu-z*sd)&(y<=mu+z*sd)&mask; rep[str(level)]={'coverage':float(inside.sum()/max(1,mask.sum())),'mean_width_z':float((2*z*sd)[mask].mean())}
rep['gaussian_nll']=float((.5*(np.clip(lv,-8,8)+(y-mu)**2*np.exp(-np.clip(lv,-8,8))))[mask].mean()); Path(a.out).parent.mkdir(parents=True,exist_ok=True); Path(a.out).write_text(json.dumps(rep,indent=2)); print(json.dumps(rep,indent=2))
