from _common import *
import argparse,json,torch,numpy as np,pandas as pd
from cncjepa.config import load_config
from cncjepa.pipeline import prepare,loaders_from_ds
from cncjepa.factory import build_jepa
from cncjepa.trainers import evaluate_jepa
from cncjepa.metrics import rmse,mae
from cncjepa.utils import device_from_arg
p=argparse.ArgumentParser(); p.add_argument('--config',default='configs/base.yaml'); p.add_argument('--ckpt',default='outputs/jepa_finetune/best.pt'); p.add_argument('--device',default='auto'); p.add_argument('--out',default='outputs/per_channel_run.csv'); a=p.parse_args(); c=load_config(a.config); _,_,ds,sn,_=prepare(c,training_mask=False); ld=loaders_from_ds(ds,c,False); dev=device_from_arg(a.device); m=build_jepa(c,True); m.load_state_dict(torch.load(a.ckpt,map_location='cpu')['model'],strict=False); m.to(dev); _,raw=evaluate_jepa(m,ld['target_all'],dev); y,pred,mask=raw['y'],raw['pred'],raw['mask']; yphys=sn.inverse(y); pphys=sn.inverse(pred); names=c['schema']['sensors']; rows=[]
for run in sorted(set(r for _,_,r in raw['meta'])):
 idx=np.array([r==run for _,_,r in raw['meta']])
 for ci,ch in enumerate(names):
  msk=mask[idx,:,ci]
  if not msk.any(): continue
  yz=np.where(msk,y[idx,:,ci],np.nan); pz=np.where(msk,pred[idx,:,ci],np.nan); yp=np.where(msk,yphys[idx,:,ci],np.nan); pp=np.where(msk,pphys[idx,:,ci],np.nan)
  rows.append({'run':run,'channel':ch,'rmse_z':rmse(yz,pz),'mae_z':mae(yz,pz),'rmse_physical':rmse(yp,pp),'mae_physical':mae(yp,pp),'n':int(msk.sum())})
pd.DataFrame(rows).to_csv(a.out,index=False); print(a.out)
