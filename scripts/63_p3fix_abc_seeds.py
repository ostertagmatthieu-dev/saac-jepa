"""P3-FIX gate experiment: does SSL pretraining actually help? A/B/C over matched seeds.

  A  scratch    : JEPA in forecaster mode from random init, physical head on, no SSL pretrain.
  B  fresh head : pretrained body (encoders + predictor) + REINITIALISED physical head.  <- primary
  C  loaded head: full pretrained checkpoint including the head.                          <- contamination control

All three arms use the same data, the same loaders, the same seed and the same epoch budget,
so the only difference is the initialisation. Persistence and linear-drift are evaluated on the
identical validation split: if no arm beats them, the forecasting formulation is the problem and
no transfer claim is admissible (taskbook decision rule 1).

Comparisons are paired at the SEED level (n = number of seeds) with an exact sign-flip test.
With 5 seeds the smallest attainable two-sided p is 1/33 = 0.030 -- treat this as a screen, not
as proof, and never read DS03 to break a tie.

Outputs: outputs/p3fix_abc/{A,B,C}/seed_k/{best.pt,history.csv,latent_health.csv} and
         outputs/p3fix_abc/abc_summary.csv + abc_report.json
"""
from _common import *
import argparse,copy,csv,json
import numpy as np, torch
from cncjepa.config import load_config,save_config
from cncjepa.pipeline import prepare,loaders_from_ds
from cncjepa.factory import build_jepa,build_forecaster
from cncjepa.checkpoint import load_jepa_checkpoint,load_jepa_body_fresh_head
from cncjepa.trainers import train_jepa,evaluate_jepa,evaluate_forecaster
from cncjepa.metrics import paired_exact_signflip
from cncjepa.utils import device_from_arg,set_seed

ARMS={'A':'scratch (random init, no SSL)','B':'pretrained body + fresh head','C':'full pretrained checkpoint (loaded head)'}

p=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
p.add_argument('--config',default='configs/real.yaml')
p.add_argument('--pretrained',default='outputs/jepa_pretrain/best.pt')
p.add_argument('--seeds',default='0,1,2,3,4')
p.add_argument('--arms',default='A,B,C')
p.add_argument('--epochs',type=int,default=None,help='matched budget for every arm (default: cfg.train.epochs)')
p.add_argument('--device',default='cuda:0')
p.add_argument('--out',default='outputs/p3fix_abc')
a=p.parse_args()

seeds=[int(s) for s in a.seeds.split(',') if s.strip()!='']
arms=[s.strip().upper() for s in a.arms.split(',') if s.strip()]
base=load_config(a.config); dev=device_from_arg(a.device); out=Path(a.out); out.mkdir(parents=True,exist_ok=True)
epochs=int(a.epochs or base['train']['epochs'])
need_ckpt=any(x in arms for x in ('B','C'))
if need_ckpt and not Path(a.pretrained).exists(): raise SystemExit(f'--pretrained {a.pretrained} not found; run scripts/10 first (arms B/C need it)')

def make_model(arm,cfg):
    if arm=='A': return build_jepa(cfg,True),{'note':'scratch, no checkpoint loaded','weights_changed':False,'missing_keys':[],'unexpected_keys':[]}
    if arm=='B':
        m,au=load_jepa_body_fresh_head(a.pretrained,cfg,'cpu'); return m,au
    m,obj=load_jepa_checkpoint(a.pretrained,cfg,'cpu'); return m,obj['load_audit']

rows=[]; audits={}
for seed in seeds:
    # one prepare/loader set per seed: identical data order for every arm at that seed
    cfg=copy.deepcopy(base); cfg['seed']=int(seed); cfg['train']['epochs']=epochs
    cfg['jepa']['physical_weight']=float(cfg['jepa'].get('physical_weight',1.) or 1.)
    set_seed(seed); _,_,ds,_,_=prepare(cfg,training_mask=True); ld=loaders_from_ds(ds,cfg)
    for arm in arms:
        rdir=out/arm/f'seed_{seed}'; rdir.mkdir(parents=True,exist_ok=True)
        print(f'\n===== arm {arm} ({ARMS[arm]})  seed {seed}  epochs {epochs} =====')
        set_seed(seed)                      # same init RNG state for every arm
        m,au=make_model(arm,cfg); audits[f'{arm}/seed_{seed}']=au
        save_config(cfg,rdir/'config.yaml'); (rdir/'load_audit.json').write_text(json.dumps(au,indent=2,default=str),encoding='utf-8')
        train_jepa(m,ld['source_train'],ld['source_val'],cfg,dev,rdir,pretrain_only=False,max_epochs=epochs)
        best,_=load_jepa_checkpoint(rdir/'best.pt',cfg,dev)
        met,_=evaluate_jepa(best,ld['source_val'],dev)
        rows.append({'arm':arm,'seed':seed,'rmse':met['rmse'],'mae':met['mae'],'nll':met['nll'],'r2':met['r2'],
                     'weights_changed':au.get('weights_changed'),'n_missing_keys':len(au.get('missing_keys',[])),'n_unexpected_keys':len(au.get('unexpected_keys',[]))})
        print(f"  -> arm {arm} seed {seed}: rmse={met['rmse']:.5f} mae={met['mae']:.5f} nll={met['nll']:.5f}")
        del m,best; torch.cuda.empty_cache()

# ---- no-learn references on the identical validation split (seed-independent)
cfg0=copy.deepcopy(base); cfg0['seed']=seeds[0]; set_seed(seeds[0])
_,_,ds0,_,_=prepare(cfg0,training_mask=True); ld0=loaders_from_ds(ds0,cfg0,shuffle_train=False)
baselines={}
for nm in ('persistence','drift'):
    bm,_=evaluate_forecaster(build_forecaster(nm,cfg0).to(dev),ld0['source_val'],dev)
    baselines[nm]={'rmse':bm['rmse'],'mae':bm['mae'],'r2':bm['r2']}
    rows.append({'arm':nm,'seed':'-','rmse':bm['rmse'],'mae':bm['mae'],'nll':'','r2':bm['r2'],'weights_changed':'','n_missing_keys':'','n_unexpected_keys':''})
    print(f"  -> baseline {nm}: rmse={bm['rmse']:.5f} mae={bm['mae']:.5f}")

keys=list(rows[0])
with (out/'abc_summary.csv').open('w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=keys); w.writeheader(); [w.writerow({k:r.get(k,'') for k in keys}) for r in rows]

# ---- paired seed-level comparisons
by={arm:{r['seed']:r for r in rows if r['arm']==arm} for arm in arms}
def paired(x,y,metric):
    common=[s for s in seeds if s in by.get(x,{}) and s in by.get(y,{})]
    if len(common)<2: return None
    d=np.array([by[x][s][metric]-by[y][s][metric] for s in common],float)
    return {'metric':metric,'n_seeds':len(common),'mean_diff':float(d.mean()),'sd_diff':float(d.std(ddof=1)) if len(d)>1 else 0.,
            'exact_signflip_p':paired_exact_signflip(d),'wins_for_first':int((d<0).sum()),'per_seed_diff':d.tolist()}
pairs=[(x,y) for x,y in (('B','A'),('C','A'),('B','C')) if x in arms and y in arms]
comp={f'{x}_minus_{y}':{m:paired(x,y,m) for m in ('rmse','mae','nll')} for x,y in pairs}

def agg(arm,m):
    v=[by[arm][s][m] for s in seeds if s in by.get(arm,{})]
    return {'mean':float(np.mean(v)),'sd':float(np.std(v,ddof=1)) if len(v)>1 else 0.,'n':len(v)} if v else None
summary={arm:{m:agg(arm,m) for m in ('rmse','mae','nll')} for arm in arms}
rep={'config':a.config,'pretrained':a.pretrained,'epochs':epochs,'seeds':seeds,'arms':{k:ARMS[k] for k in arms},
     'per_run':rows,'summary':summary,'paired':comp,'baselines':baselines,'load_audits':audits}
(out/'abc_report.json').write_text(json.dumps(rep,indent=2,default=str),encoding='utf-8')

print('\n'+'='*78+'\nP3-FIX A/B/C VERDICT  (source_val only -- DS03 untouched)\n'+'='*78)
for arm in arms:
    s_=summary[arm]
    if s_['rmse']: print(f"  {arm} {ARMS[arm]:<44} rmse {s_['rmse']['mean']:.5f} +/- {s_['rmse']['sd']:.5f}  mae {s_['mae']['mean']:.5f}  nll {s_['nll']['mean']:.5f}  (n={s_['rmse']['n']})")
for nm,v in baselines.items(): print(f"  -- baseline {nm:<47} rmse {v['rmse']:.5f}  mae {v['mae']:.5f}")
print()
for name,d in comp.items():
    r=d['rmse']
    if r: print(f"  {name} rmse: mean diff {r['mean_diff']:+.5f} (sd {r['sd_diff']:.5f}), first arm better in {r['wins_for_first']}/{r['n_seeds']} seeds, exact sign-flip p={r['exact_signflip_p']:.4f}")
print()
best_arm=min((arm for arm in arms if summary[arm]['rmse']),key=lambda k:summary[k]['rmse']['mean'],default=None)
best_base=min(baselines,key=lambda k:baselines[k]['rmse']) if baselines else None
if best_base and best_arm and summary[best_arm]['rmse']['mean']>=baselines[best_base]['rmse']:
    print(f"  VERDICT: no arm beats {best_base} (rmse {baselines[best_base]['rmse']:.5f}). Taskbook decision rule 1 applies:")
    print( "           STOP and fix the forecasting formulation before making any transfer claim.")
elif 'B_minus_A' in comp:
    r=comp['B_minus_A']['rmse']
    if r and r['mean_diff']<0 and r['exact_signflip_p']<=0.05: print(f"  VERDICT: pretraining (B) beats scratch (A) by {abs(r['mean_diff']):.5f} rmse, p={r['exact_signflip_p']:.4f}. Pretraining is supported on source clean RMSE.")
    elif r: print(f"  VERDICT: no significant scratch-vs-pretrained difference on source clean RMSE (mean diff {r['mean_diff']:+.5f}, p={r['exact_signflip_p']:.4f}).")
    print( "           Per taskbook: source clean RMSE is a diagnostic. Judge JEPA on schema-drop / few-shot / DS03 transfer next.")
if 'B_minus_C' in comp and comp['B_minus_C']['rmse']:
    r=comp['B_minus_C']['rmse']
    print(f"  HEAD CONTAMINATION: B(fresh) - C(loaded) = {r['mean_diff']:+.5f} rmse, p={r['exact_signflip_p']:.4f}. " + ('Fresh head is the correct primary.' if r['mean_diff']<=0 else 'Loaded head looks better -- report B as primary anyway and C as the ablation.'))
print(f"\nwrote {out/'abc_summary.csv'} and {out/'abc_report.json'}")
