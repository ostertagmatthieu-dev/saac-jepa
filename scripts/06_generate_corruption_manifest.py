from _common import *
import argparse,json
p=argparse.ArgumentParser(); p.add_argument('--out',default='outputs/corruption_manifest.json'); a=p.parse_args(); rep={'corruptions':{k:[.05,.1,.2,.4] for k in ['random_mask','gaussian','spike','drift','step','missing_block','sensor_bias','mixed']},'rule':'corrupt context only; never corrupt target labels unless explicitly testing label noise'}; Path(a.out).parent.mkdir(parents=True,exist_ok=True); Path(a.out).write_text(json.dumps(rep,indent=2)); print(a.out)
