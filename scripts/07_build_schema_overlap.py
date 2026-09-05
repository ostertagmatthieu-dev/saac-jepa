from _common import *
import argparse,json
from cncjepa.config import load_config
p=argparse.ArgumentParser(); p.add_argument('--config',default='configs/base.yaml'); a=p.parse_args(); c=load_config(a.config); s=c['schema']; allc=s['sensors']; sub=s['transfer_sensors']; print(json.dumps({'source_channels':len(allc),'target_transfer_channels':len(sub),'overlap_fraction':len(set(allc)&set(sub))/len(allc),'missing_on_target':[x for x in allc if x not in sub]},indent=2))
