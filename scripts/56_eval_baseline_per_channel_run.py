from _common import *
import argparse,torch,numpy as np,pandas as pd
from cncjepa.config import load_config
from cncjepa.pipeline import prepare,loaders_from_ds
from cncjepa.factory import build_forecaster
from cncjepa.trainers import evaluate_forecaster
from cncjepa.metrics import rmse,mae
from cncjepa.utils import device_from_arg
p=argparse.ArgumentParser(); p.add_argument('--config',default='configs/base.yaml'); p.add_argument('--ckpt',required=True); p.add_argument('--model',required=True); p.add_argument('--device',default='auto'); p.add_argument('--out',default='outputs/baseline_per_channel_run.csv'); a=p.parse_args(); c=load_config(a.config); _,_,ds,sn,_=prepare(c,training_mask=False); ld=loaders_from_ds(ds,c,False); dev=device_from_arg(a.device); m=build_forecaster(a.model,c); m.load_state_dict(torch.load(a.ckpt,map_location='cpu')['model']); m.to(dev); _,raw=evaluate_forecaster(m,ld['target_all'],dev); y,pred,mask=raw['y'],raw['pred'],raw['mask']; yp=sn.inverse(y); pp=sn.inverse(pred); rows=[]
for run in sorted(set(r for _,_,r in raw['meta'])):
 idx=np.array([r==run for _,_,r in raw['meta']])
 for ci,ch in enumerate(c['schema']['sensors']):
  mk=mask[idx,:,ci]
  if mk.any(): rows.append({'run':run,'channel':ch,'rmse_z':rmse(np.where(mk,y[idx,:,ci],np.nan),np.where(mk,pred[idx,:,ci],np.nan)),'rmse_physical':rmse(np.where(mk,yp[idx,:,ci],np.nan),np.where(mk,pp[idx,:,ci],np.nan))})
pd.DataFrame(rows).to_csv(a.out,index=False); print(a.out)
