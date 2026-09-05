from _common import *
import argparse,json,torch,numpy as np
from torch.utils.data import DataLoader
from cncjepa.config import load_config
from cncjepa.data import load_table,resample_dataframe,deterministic_group_split,WindowDataset,collate,target_support_query_split
from cncjepa.normalization import Normalizer
from cncjepa.factory import build_jepa
from cncjepa.trainers import evaluate_jepa
from cncjepa.utils import device_from_arg
p=argparse.ArgumentParser(); p.add_argument('--config',default='configs/base.yaml'); p.add_argument('--ckpt',default='outputs/jepa_finetune/best.pt'); p.add_argument('--device',default='auto'); p.add_argument('--out',default='outputs/normalization_sensitivity.json'); a=p.parse_args(); c=load_config(a.config); s=c['schema']; df=resample_dataframe(load_table(c['paths']['data']),c); sp=deterministic_group_split(df,c); tr=sp['source_train']; tgt=sp['target_all']; source=Normalizer('zscore').fit(tr[s['sensors']]); an=Normalizer('zscore').fit(tr[s['actions']]); dev=device_from_arg(a.device); model=build_jepa(c,True); model.load_state_dict(torch.load(a.ckpt,map_location='cpu')['model'],strict=False); model.to(dev); rep={}
conditions={'source_zscore':source,'source_robust':Normalizer('robust').fit(tr[s['sensors']]),'target_oracle_DIAGNOSTIC':Normalizer('zscore').fit(tgt[s['sensors']])}
sup,_=target_support_query_split(tgt,c,.1)
if len(sup): conditions['target_10pct_support']=Normalizer('zscore').fit(sup[s['sensors']])
for name,norm in conditions.items():
 ds=WindowDataset(tgt,c,norm,an,training=False); ld=DataLoader(ds,batch_size=c['train']['batch_size'],collate_fn=collate); rep[name]=evaluate_jepa(model,ld,dev)[0]
rep['warning']='Only source_zscore is the audited zero-shot setting. Target-oracle uses forbidden full-target statistics and is diagnostic only.'; Path(a.out).parent.mkdir(parents=True,exist_ok=True); Path(a.out).write_text(json.dumps(rep,indent=2)); print(json.dumps(rep,indent=2))
