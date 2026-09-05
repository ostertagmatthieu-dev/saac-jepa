from _common import *
import argparse,copy,json
from cncjepa.config import load_config,save_config
from cncjepa.pipeline import prepare,loaders_from_ds
from cncjepa.factory import build_jepa
from cncjepa.trainers import train_jepa
from cncjepa.utils import device_from_arg
p=argparse.ArgumentParser(); p.add_argument('--config',default='configs/base.yaml'); p.add_argument('--out',default='outputs/novelty_factorial'); p.add_argument('--device',default='auto'); a=p.parse_args(); base=load_config(a.config); variants={
'plain_jepa':{'schema':0.,'arec':0.,'mask':'random','vicreg':'pooled'},
'+per_horizon_anticollapse':{'schema':0.,'arec':0.,'mask':'random','vicreg':'per_horizon'},
'+event_mixed_mask':{'schema':0.,'arec':0.,'mask':'mixed','vicreg':'per_horizon'},
'+action_identifiability':{'schema':0.,'arec':.1,'mask':'mixed','vicreg':'per_horizon'},
'SAAC_JEPA_full':{'schema':.2,'arec':.1,'mask':'mixed','vicreg':'per_horizon'}}
for name,v in variants.items():
 c=copy.deepcopy(base); c['jepa']['schema_consistency_weight']=v['schema']; c['jepa']['action_recovery_weight']=v['arec']; c['masking']['mode']=v['mask']; c['jepa']['vicreg_mode']=v['vicreg']; _,_,ds,_,_=prepare(c,training_mask=True); ld=loaders_from_ds(ds,c); out=Path(a.out)/name; save_config(c,out/'config.yaml'); train_jepa(build_jepa(c,True),ld['source_train'],ld['source_val'],c,device_from_arg(a.device),out)
print('Factorial complete. Evaluate all variants with scripts 30-39.')
