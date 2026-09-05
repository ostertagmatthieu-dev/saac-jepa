from _common import *
import argparse,json,copy,torch,numpy as np
import torch.nn.functional as F
from cncjepa.config import load_config
from cncjepa.pipeline import prepare,batch_to
from cncjepa.data import WindowDataset,collate
from torch.utils.data import DataLoader
from cncjepa.factory import build_jepa
from cncjepa.adaptation import set_trainable
from cncjepa.metrics import rmse
from cncjepa.utils import device_from_arg
p=argparse.ArgumentParser(); p.add_argument('--config',default='configs/base.yaml'); p.add_argument('--ckpt',default='outputs/jepa_finetune/best.pt'); p.add_argument('--device',default='auto'); p.add_argument('--out',default='outputs/online_adaptation.json'); a=p.parse_args(); c=load_config(a.config); _,sp,_,sn,an=prepare(c,training_mask=False); dev=device_from_arg(a.device); rep={}
for rid,g in sp['target_all'].groupby(c['schema']['run'],sort=False):
 ds=WindowDataset(g,c,sn,an,training=False); ld=DataLoader(ds,batch_size=1,shuffle=False,collate_fn=collate); m=build_jepa(c,True); m.load_state_dict(torch.load(a.ckpt,map_location='cpu')['model'],strict=False); m.to(dev); set_trainable(m,'predictor'); opt=torch.optim.AdamW([p for p in m.parameters() if p.requires_grad],lr=5e-5); ys=[]; ps=[]; ms=[]
 for b in ld:
  b=batch_to(b,dev); m.eval()
  with torch.no_grad(): o=m(b['x'],b['past_actions'],b['future_actions'],b['present'],b['schema'],y=None)
  ys.append(b['y'].cpu().numpy()); ps.append(o['mu'].cpu().numpy()); ms.append(b['target_present'].cpu().numpy())
  m.train(); opt.zero_grad(); o=m(b['x'],b['past_actions'],b['future_actions'],b['present'],b['schema'],y=None); mk=b['target_present']; loss=((o['mu']-b['y']).pow(2)*mk).sum()/(mk.sum()+1e-8); loss.backward(); opt.step()
 y=np.concatenate(ys); pr=np.concatenate(ps); mk=np.concatenate(ms).astype(bool); rep[str(rid)]={'prequential_rmse':rmse(np.where(mk,y,np.nan),np.where(mk,pr,np.nan)),'n_windows':len(ds)}
Path(a.out).parent.mkdir(parents=True,exist_ok=True); Path(a.out).write_text(json.dumps(rep,indent=2)); print(json.dumps(rep,indent=2))
