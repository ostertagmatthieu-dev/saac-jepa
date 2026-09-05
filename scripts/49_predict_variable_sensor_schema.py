from _common import *
import argparse,json,numpy as np,tempfile,subprocess
from cncjepa.config import load_config
p=argparse.ArgumentParser(); p.add_argument('--config',default='configs/base.yaml'); p.add_argument('--ckpt',default='outputs/jepa_finetune/best.pt'); p.add_argument('--input',required=True); p.add_argument('--device',default='auto'); a=p.parse_args(); c=load_config(a.config); d=json.loads(Path(a.input).read_text()); T=c['protocol']['context_len']; sensors=c['schema']['sensors']; states=np.full((T,len(sensors)),np.nan,np.float32)
for name,vals in d['sensor_series'].items():
 if name not in sensors: raise ValueError(f'Unknown sensor {name}; add metadata/remapping before inference')
 if len(vals)!=T: raise ValueError(f'{name}: expected {T} values')
 states[:,sensors.index(name)]=vals
payload={'states':states.tolist(),'past_actions':d.get('past_actions'), 'future_actions':d['future_actions']}; tmp=Path(a.input).with_suffix('.expanded.json'); tmp.write_text(json.dumps(payload)); cmd=[sys.executable,'scripts/48_predict_any_input.py','--config',a.config,'--ckpt',a.ckpt,'--input',str(tmp),'--device',a.device]; raise SystemExit(subprocess.call(cmd))
