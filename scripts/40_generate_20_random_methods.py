"""Generate the 20 architecture-search V2 candidates M00-M19 (taskbook, '20 candidate architectures').

This is NOT a random sampler any more: it is a deterministic transcription of the taskbook
table, so the same 20 configs come out of every machine and every run. The table deliberately
spans action injection, masking, anti-collapse, latent weight, EMA, normalization, model scale
and schema adaptation while the target machine stays hidden.

Column -> config key:
  Mask        -> masking.mode                Ratio      -> masking.ratio
  Action      -> model.action_injection      Latent LN  -> jepa.latent_layernorm
  VICReg      -> jepa.vicreg_mode (+ jepa.vicreg_placement; 'none' also zeroes vicreg_weight)
  lam_latent  -> jepa.latent_weight          Target     -> jepa.target_aggregation
  lam_schema  -> jepa.schema_consistency_weight
  lam_arec    -> jepa.action_recovery_weight
  EMA         -> jepa.ema (fixed) | jepa.ema_schedule={start,end,kind} (scheduled)
  d / Layers  -> model.d_model / model.encoder_layers (predictor_layers = max(2, layers-2),
                 nhead = 8 for d in {256,384,512} and 4 for d=128, dim_feedforward = 4*d)
  Norm        -> normalization.mode          FT head    -> search.ft_head (fresh|loaded)

`seed` is left at the base config's value for every candidate on purpose: script 41 pins the
DS01 split and the deterministic validation masks to it (cfg.eval_seed) so all 20 candidates x
all seeds are scored on exactly the same validation folds, as the taskbook requires.

Outputs: configs/search_v2/M00.yaml .. M19.yaml + configs/search_v2/manifest.json
"""
from _common import *
import argparse, copy, json
from cncjepa.config import load_config, save_config

# id, description, mask, ratio, action, latent_ln, vicreg, lam_latent, target, lam_schema, lam_arec, ema, d, layers, norm, ft_head
PH='per_horizon_context_target'; POOL='pooled_context_target'; FIX='fixed_0.996'; SCH='schedule_0.99_0.9999'
TABLE=[
 ('M00','Plain JEPA control',              'mixed',  .35,'token',     False,'none',1.00,'per_horizon',0.00,0.00,FIX,256,6,'source_zscore','fresh'),
 ('M01','JEPA + per-horizon VICReg',       'mixed',  .35,'token',     False,PH,   1.00,'per_horizon',0.00,0.00,FIX,256,6,'source_zscore','fresh'),
 ('M02','Schema-adaptive latent consistency','channel',.35,'token',   False,PH,   1.00,'per_horizon',0.10,0.00,FIX,256,6,'source_zscore','fresh'),
 ('M03','Schema + action recovery',        'channel',.35,'token',     False,PH,   1.00,'per_horizon',0.10,0.05,FIX,256,6,'source_zscore','fresh'),
 ('M04','FiLM action injection',           'mixed',  .35,'film',      False,PH,   1.00,'per_horizon',0.10,0.05,FIX,256,6,'source_zscore','fresh'),
 ('M05','Cross-attention action injection','mixed',  .35,'cross_attn',False,PH,   1.00,'per_horizon',0.10,0.05,FIX,256,6,'source_zscore','fresh'),
 ('M06','Event masking',                   'event',  .35,'cross_attn',False,PH,   1.00,'per_horizon',0.10,0.05,FIX,256,6,'source_zscore','fresh'),
 ('M07','Heavy channel masking',           'channel',.50,'cross_attn',False,PH,   1.00,'per_horizon',0.20,0.05,FIX,256,6,'source_zscore','fresh'),
 ('M08','Light mixed masking',             'mixed',  .20,'cross_attn',False,PH,   1.00,'per_horizon',0.10,0.05,FIX,256,6,'source_zscore','fresh'),
 ('M09','Latent LayerNorm ON',             'mixed',  .35,'cross_attn',True, PH,   1.00,'per_horizon',0.10,0.05,FIX,256,6,'source_zscore','fresh'),
 ('M10','Pooled VICReg/target',            'mixed',  .35,'cross_attn',False,POOL, 1.00,'pooled',     0.10,0.05,FIX,256,6,'source_zscore','fresh'),
 ('M11','Low latent weight',               'mixed',  .35,'cross_attn',False,PH,   0.50,'per_horizon',0.10,0.05,FIX,256,6,'source_zscore','fresh'),
 ('M12','High latent weight',              'mixed',  .35,'cross_attn',False,PH,   2.00,'per_horizon',0.10,0.05,FIX,256,6,'source_zscore','fresh'),
 ('M13','Scheduled EMA',                   'mixed',  .35,'cross_attn',False,PH,   1.00,'per_horizon',0.10,0.05,SCH,256,6,'source_zscore','fresh'),
 ('M14','Robust source normalization',     'mixed',  .35,'cross_attn',False,PH,   1.00,'per_horizon',0.10,0.05,SCH,256,6,'source_robust','fresh'),
 ('M15','Compact model',                   'mixed',  .35,'cross_attn',False,PH,   1.00,'per_horizon',0.10,0.05,SCH,128,4,'source_zscore','fresh'),
 ('M16','Medium-wide model',               'mixed',  .35,'cross_attn',False,PH,   1.00,'per_horizon',0.10,0.05,SCH,384,6,'source_zscore','fresh'),
 ('M17','Large model',                     'mixed',  .35,'cross_attn',False,PH,   1.00,'per_horizon',0.10,0.05,SCH,512,8,'source_zscore','fresh'),
 ('M18','Head-contamination control',      'mixed',  .35,'cross_attn',False,PH,   1.00,'per_horizon',0.10,0.05,SCH,256,6,'source_zscore','loaded'),
 ('M19','SAAC-JEPA full candidate',        'mixed',  .35,'cross_attn',False,PH,   1.00,'per_horizon',0.20,0.10,SCH,384,6,'source_robust','fresh'),
]
FIELDS=('name','description','mask','ratio','action','latent_ln','vicreg','latent_weight','target_aggregation','schema_weight','action_recovery_weight','ema','d_model','layers','normalization','ft_head')
VICREG={'none':('none',None),PH:('per_horizon','context_target'),POOL:('pooled','context_target')}


def nhead_for(d):
    """d_model % nhead == 0 for every table row; 8 heads for 256/384/512, 4 for 128."""
    n=4 if d==128 else 8
    assert d%n==0, f'nhead {n} does not divide d_model {d}'
    return n


def apply_row(base,row):
    r=dict(zip(FIELDS,row)); c=copy.deepcopy(base)
    c['masking']['mode']=r['mask']; c['masking']['ratio']=float(r['ratio'])
    c['model']['action_injection']=r['action']
    c['jepa']['latent_layernorm']=bool(r['latent_ln'])
    mode,placement=VICREG[r['vicreg']]
    c['jepa']['vicreg_mode']=mode
    if placement is None: c['jepa']['vicreg_weight']=0.0; c['jepa'].pop('vicreg_placement',None)
    else: c['jepa']['vicreg_placement']=placement
    c['jepa']['latent_weight']=float(r['latent_weight'])
    c['jepa']['target_aggregation']=r['target_aggregation']
    c['jepa']['schema_consistency_weight']=float(r['schema_weight'])
    c['jepa']['action_recovery_weight']=float(r['action_recovery_weight'])
    if r['ema']==FIX: c['jepa']['ema']=0.996; c['jepa'].pop('ema_schedule',None)
    else:
        s,e=0.99,0.9999
        c['jepa']['ema']=s   # fallback used before the first ema_at() call
        c['jepa']['ema_schedule']={'start':s,'end':e,'kind':'linear'}
    d=int(r['d_model']); c['model']['d_model']=d; c['model']['nhead']=nhead_for(d)
    c['model']['encoder_layers']=int(r['layers']); c['model']['predictor_layers']=max(2,int(r['layers'])-2)
    c['model']['dim_feedforward']=4*d
    c['normalization']['mode']=r['normalization']
    c.setdefault('search',{})['ft_head']=r['ft_head']
    c['search']['candidate']=r['name']; c['search']['description']=r['description']
    return r,c


p=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
p.add_argument('--config',default='configs/real.yaml',help='base config every candidate is derived from')
p.add_argument('--outdir',default='configs/search_v2')
a=p.parse_args()

base=load_config(a.config); out=Path(a.outdir); out.mkdir(parents=True,exist_ok=True)
seen={}; manifest=[]
for row in TABLE:
    r,c=apply_row(base,row)
    key=tuple(row[2:])   # every dimension except id/description
    assert key not in seen, f"duplicate candidate: {r['name']} has the same dimensions as {seen[key]}"
    seen[key]=r['name']
    path=out/f"{r['name']}.yaml"; save_config(c,path)
    manifest.append({'name':r['name'],'config':str(path),'description':r['description'],
                     'id':int(r['name'][1:]),'spec':{k:r[k] for k in FIELDS if k not in ('name','description')},
                     'nhead':c['model']['nhead'],'predictor_layers':c['model']['predictor_layers'],'base_config':str(a.config)})
assert len(manifest)==len(TABLE)==20, f'expected 20 candidates, produced {len(manifest)}'
(out/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print(f'wrote {len(manifest)} candidate configs to {out} (base {a.config}); all dimension tuples unique')
for m in manifest:
    s=m['spec']
    print(f"  {m['name']:<4} {m['description']:<34} {s['mask']:<7} r={s['ratio']:<4} {s['action']:<10} ln={str(s['latent_ln']):<5} "
          f"vicreg={s['vicreg']:<26} lam={s['latent_weight']:<4} {s['target_aggregation']:<11} sch={s['schema_weight']:<4} "
          f"arec={s['action_recovery_weight']:<4} {s['ema']:<20} d={s['d_model']:<3} L={s['layers']} {s['normalization']:<13} head={s['ft_head']}")
