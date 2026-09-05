from _common import *
import argparse,json,torch,numpy as np
from cncjepa.config import load_config
from cncjepa.pipeline import prepare
from cncjepa.factory import build_jepa
from cncjepa.utils import device_from_arg
p=argparse.ArgumentParser(); p.add_argument('--config',default='configs/base.yaml'); p.add_argument('--ckpt',default='outputs/jepa_finetune/best.pt'); p.add_argument('--input',required=True); p.add_argument('--device',default='auto'); a=p.parse_args(); c=load_config(a.config); _,_,_,sn,an=prepare(c,training_mask=False); d=json.loads(Path(a.input).read_text()); x=np.asarray(d['states'],np.float32); pa=np.asarray(d.get('past_actions',np.zeros((len(x),len(c['schema']['actions'])))),np.float32); fa=np.asarray(d['future_actions'],np.float32); assert x.shape==(c['protocol']['context_len'],len(c['schema']['sensors'])); assert fa.shape==(len(c['protocol']['horizons']),len(c['schema']['actions'])); present=np.isfinite(x).astype(np.float32); x=sn.transform(np.nan_to_num(x)).astype(np.float32); pa=an.transform(pa).astype(np.float32); fa=an.transform(fa).astype(np.float32); schema=(present.any(0)).astype(np.float32); dev=device_from_arg(a.device); m=build_jepa(c,True); m.load_state_dict(torch.load(a.ckpt,map_location='cpu')['model'],strict=False); m.to(dev).eval()
with torch.no_grad(): o=m(torch.tensor(x)[None].to(dev),torch.tensor(pa)[None].to(dev),torch.tensor(fa)[None].to(dev),torch.tensor(present)[None].to(dev),torch.tensor(schema)[None].to(dev),y=None); mu=sn.inverse(o['mu'][0].cpu().numpy()); sd=o['logvar'][0].mul(.5).exp().cpu().numpy()*sn.scale
print(json.dumps({'horizons':c['protocol']['horizons'],'sensor_names':c['schema']['sensors'],'mean':mu.tolist(),'std':sd.tolist()},indent=2))
