from _common import *
import argparse,json,pandas as pd
p=argparse.ArgumentParser(); p.add_argument('--root',default='outputs'); p.add_argument('--out',default='outputs/main_tables.xlsx'); a=p.parse_args(); root=Path(a.root); sheets={}
for name,file in [('multihorizon','eval_multihorizon.json'),('normalization','normalization_sensitivity.json'),('calibration','calibration.json'),('action','action_conditioning.json'),('transfer','transfer_ds01_ds03.json')]:
 f=root/file
 if f.exists(): sheets[name]=pd.json_normalize(json.loads(f.read_text()),sep='.')
pr=root/'per_channel_run.csv'
if pr.exists(): sheets['per_channel_run']=pd.read_csv(pr)
with pd.ExcelWriter(a.out,engine='openpyxl') as w:
 for n,df in sheets.items(): df.to_excel(w,sheet_name=n[:31],index=False)
print(a.out)
