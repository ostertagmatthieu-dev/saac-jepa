from _common import *
import argparse,json,torch,numpy as np
from cncjepa.config import load_config
from cncjepa.pipeline import prepare,loaders_from_ds,batch_to
from cncjepa.factory import build_jepa
from cncjepa.planner import cem_plan
from cncjepa.utils import device_from_arg
p=argparse.ArgumentParser(); p.add_argument('--config',default='configs/base.yaml'); p.add_argument('--ckpt',default='outputs/jepa_finetune/best.pt'); p.add_argument('--device',default='auto'); p.add_argument('--n',type=int,default=10); p.add_argument('--out',default='outputs/cem_plans.json'); a=p.parse_args(); c=load_config(a.config); _,sp,ds,sn,an=prepare(c,training_mask=False); ld=loaders_from_ds(ds,c,False)['target_all']; dev=device_from_arg(a.device); m=build_jepa(c,True); m.load_state_dict(torch.load(a.ckpt,map_location='cpu')['model'],strict=False); m.to(dev).eval(); acts=sp['source_train'][c['schema']['actions']].to_numpy(float); lo=an.transform(np.nanpercentile(acts,1,axis=0)); hi=an.transform(np.nanpercentile(acts,99,axis=0)); rows=[]
for b in ld:
 b=batch_to(b,dev)
 for i in range(min(b['x'].size(0),a.n-len(rows))):
  plan=cem_plan(m,b['x'][i:i+1],b['past_actions'][i:i+1],b['present'][i:i+1],b['schema'][i:i+1],lo,hi,c,dev,sensor_normalizer=sn); rows.append({'run':b['run'][i],'plan_normalized':plan.detach().cpu().tolist()})
 if len(rows)>=a.n: break
Path(a.out).parent.mkdir(parents=True,exist_ok=True); Path(a.out).write_text(json.dumps(rows,indent=2)); print(a.out)
