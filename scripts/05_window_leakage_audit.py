from _common import *
import argparse, json
from cncjepa.config import load_config
from cncjepa.pipeline import prepare
p=argparse.ArgumentParser(); p.add_argument('--config',default='configs/base.yaml'); a=p.parse_args(); cfg=load_config(a.config); _,sp,ds,_,_=prepare(cfg,training_mask=False); ids={k:set(sp[k][cfg['schema']['session']].astype(str)) for k in ['source_train','source_val','source_test']}; rep={'train_val_overlap':sorted(ids['source_train']&ids['source_val']),'train_test_overlap':sorted(ids['source_train']&ids['source_test']),'val_test_overlap':sorted(ids['source_val']&ids['source_test']),'window_counts':{k:len(v) for k,v in ds.items()}}; print(json.dumps(rep,indent=2)); assert not any(rep[k] for k in ['train_val_overlap','train_test_overlap','val_test_overlap'])
