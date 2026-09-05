"""Train ONE architecture-search V2 candidate under the P3-FIX protocol and emit its
validation-only metric bundle. DS01 source_val only -- the target machine is never opened.

Two stages, both written under <out>/:
  (a) pretrain/  pure SSL, train_jepa(pretrain_only=True). best.pt minimises the held-out
                 SSL objective val_ssl on source_val (never train loss); the physical head
                 gets zero gradient; schema consistency acts on latent predictions; latent
                 health is logged every epoch to pretrain/latent_health.csv.
  (b) finetune/  physical head training per cfg.search.ft_head:
                   fresh  -> load_jepa_body_fresh_head (primary; head reinitialised)
                   loaded -> load_jepa_checkpoint       (head-contamination control)
                 best.pt minimises held-out physical val RMSE.

Then <out>/val_metrics.json carries the taskbook's selection components (all lower-is-better
except action_sensitivity):
  clean_rmse          source_val, no masks, full 17-sensor schema
  schema_drop_rmse    source_val with only the 10 transfer sensors visible (the 7 DS01-only
                      channels get value 0 / presence 0 / schema 0, the same mechanism script
                      34 uses and the same shape the target machine will present). Targets stay
                      all 17 channels, so this isolates input-schema degradation.
  masked_rmse         source_val under the deterministic per-index corruption masks
                      (prepare(val_mask=True))
  long_horizon_rmse   worst per-horizon RMSE from the clean evaluation
  calibration_penalty |empirical 90% central coverage - 0.90| from mu/logvar
  ssl_latent_val      best (minimum) val_ssl reached during stage (a)
  action_sensitivity  RMSE(sample-shuffled future actions) / RMSE(true future actions);
                      weak_action=1 when the ratio is below 1.02
  latent health       eff_rank_frac / std_min / offdiag_corr / collapse, worst of z_pred,z_target
  invalid             1 on NaN metrics, checkpoint-load failure, SSL latent collapse, a
                      deterministic-validation failure or a metric-scale anomaly, with
                      invalid_reasons -- never silently ranked

All RMSE components are computed in a FIXED reference space (source_zscore fit on source_train)
via a per-channel affine from the candidate's own normalization space (_val_bundle). Identity for
zscore candidates; for robust candidates it repairs the degenerate-IQR scale leak that used to
report robust-space RMSE (~453) incommensurable with the zscore pool (~0.82). The trivial
zero-predictor anchor (eval_space_anchor_rmse, ~1.0 by construction) guards the space.

Split and validation masks are pinned to cfg.eval_seed (= the candidate config's own seed) so
every candidate and every --seed is scored on identical DS01 validation folds. --seed drives
model init, batch order and the stochastic training masks only.
"""
from _common import *
from _val_bundle import compute_validation_bundle, determinism_check, WEAK_ACTION_RATIO, DET_CHECK_BATCHES, ANCHOR_BOUNDS
import argparse, copy, csv, json, time
import numpy as np, torch
from cncjepa.config import load_config, save_config
from cncjepa.normalization import Normalizer
from cncjepa.pipeline import prepare, loaders_from_ds
from cncjepa.factory import build_jepa
from cncjepa.checkpoint import load_jepa_checkpoint, load_jepa_body_fresh_head
from cncjepa.trainers import train_jepa
from cncjepa.utils import device_from_arg, set_seed, count_parameters

p=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
p.add_argument('--config',required=True)
p.add_argument('--out',required=True)
p.add_argument('--device',default='auto')
p.add_argument('--seed',type=int,default=None,help='training seed (init/order/train masks); validation folds stay pinned')
p.add_argument('--pretrain-epochs',type=int,default=None,help='default cfg.search.pretrain_epochs or cfg.train.epochs')
p.add_argument('--ft-epochs',type=int,default=None,help='default cfg.search.ft_epochs or cfg.train.epochs')
p.add_argument('--epochs',type=int,default=None,help='shorthand: same budget for both stages')
a=p.parse_args()

cfg=copy.deepcopy(load_config(a.config))
cfg['eval_seed']=int(cfg.get('eval_seed',cfg.get('seed',0)))   # protocol seed: folds + val masks
if a.seed is not None: cfg['seed']=int(a.seed)
cfg['seed']=int(cfg.get('seed',0))
srch=cfg.get('search',{}) or {}
pre_epochs=int(a.epochs or a.pretrain_epochs or srch.get('pretrain_epochs') or cfg['train']['epochs'])
ft_epochs =int(a.epochs or a.ft_epochs      or srch.get('ft_epochs')       or cfg['train']['epochs'])
ft_head=str(srch.get('ft_head','fresh')).lower()
if ft_head not in ('fresh','loaded'): raise SystemExit(f'search.ft_head must be fresh|loaded, got {ft_head!r}')

set_seed(cfg['seed'])
dev=device_from_arg(a.device)
# Resolve the robust-scale floor BEFORE saving the run config, so the transform the checkpoint
# is trained with is recorded on disk and eval-only re-runs (script 67) can reproduce it exactly.
cfg.setdefault('normalization',{})['rel_floor']=float(cfg.get('normalization',{}).get('rel_floor',0.05))
out=Path(a.out); out.mkdir(parents=True,exist_ok=True); save_config(cfg,out/'config.yaml')
t_start=time.time()

# --------------------------------------------------------------- data (DS01 only)
# Three dataset views of ONE split: clean, deterministically masked, transfer-sensor-only. The
# resampled frame is loaded once and reused, so all three share the same split from cfg.eval_seed
# and the same source_train normalizer by construction; only the view differs.
frame,split,ds,sn,_= prepare(cfg,training_mask=True)             # train masked, val clean
_,_,ds_msk,_,_= prepare(cfg,training_mask=True,val_mask=True,resampled_df=frame)
transfer=list(cfg['schema']['transfer_sensors']); dropped=[s for s in cfg['schema']['sensors'] if s not in set(transfer)]
_,_,ds_sch,_,_= prepare(cfg,sensor_subset=transfer,training_mask=False,resampled_df=frame)
ld =loaders_from_ds(ds,cfg)
ld_msk=loaders_from_ds(ds_msk,cfg,shuffle_train=False)
ld_sch=loaders_from_ds(ds_sch,cfg,shuffle_train=False)
print(f"[data] source_val windows={len(ds['source_val'])} schema-drop keeps {len(transfer)}/{len(cfg['schema']['sensors'])} sensors, drops {dropped}")

# Fixed metric reference space: the canonical source_zscore fit on the SAME source_train slice.
# All RMSE components are computed there (Normalizer.affine_to), so candidates whose own
# normalization differs (e.g. source_robust) stay unit-comparable with the zscore pool; for
# zscore candidates the map is the identity bitwise. See _val_bundle for the anchor guard.
ref_sn=Normalizer('zscore').fit(split['source_train'][cfg['schema']['sensors']].to_numpy(float))
metric_affine=sn.affine_to(ref_sn)

# --------------------------------------------------------------- stage (a) pure SSL pretrain
pre=copy.deepcopy(cfg); pre['jepa']['physical_weight']=0.0
set_seed(cfg['seed'])
m=build_jepa(pre,True); n_params=count_parameters(m)
print(f"[pretrain] {ft_head=} d_model={cfg['model']['d_model']} layers={cfg['model']['encoder_layers']} params={n_params} epochs={pre_epochs}")
t0=time.time()
hist_pre=train_jepa(m,ld['source_train'],ld['source_val'],pre,dev,out/'pretrain',pretrain_only=True,max_epochs=pre_epochs)
pretrain_sec=round(time.time()-t0,1)
del m
if dev.type=='cuda': torch.cuda.empty_cache()

ssl_rows=[h for h in hist_pre if h.get('score') is not None and np.isfinite(h['score'])]
if ssl_rows:
    best_pre=min(ssl_rows,key=lambda h:h['score']); ssl_latent_val=float(best_pre['score']); best_ep=int(best_pre['epoch'])
else:
    ssl_latent_val=float('nan'); best_ep=-1
# latent health recorded at the SSL-selected epoch (written by train_jepa)
ssl_health={}
hpath=out/'pretrain'/'latent_health.csv'
if hpath.exists():
    for row in csv.DictReader(hpath.open(encoding='utf-8')):
        if int(row['epoch'])==best_ep: ssl_health={k:(float(v) if v not in ('','None') else float('nan')) for k,v in row.items()}
ssl_collapse=int(ssl_health.get('collapse',0) or 0) if ssl_health else 0
print(f'[pretrain] best val_ssl={ssl_latent_val:.6f} at epoch {best_ep} collapse={ssl_collapse} ({pretrain_sec}s)')

# --------------------------------------------------------------- stage (b) physical fine-tune
ckpt=out/'pretrain'/'best.pt'
set_seed(cfg['seed'])
if ft_head=='loaded': model,obj=load_jepa_checkpoint(ckpt,cfg,'cpu'); audit=obj['load_audit']
else: model,audit=load_jepa_body_fresh_head(ckpt,cfg,'cpu')
audit['ft_head']=ft_head; audit['pretrained']=str(ckpt); audit['seed']=cfg['seed']
load_ok=bool(audit.get('weights_changed')) and not audit.get('unexpected_keys')
if ft_head=='fresh': load_ok=load_ok and bool(audit.get('missing_keys_are_head_only',False))
else: load_ok=load_ok and not audit.get('missing_keys')
audit['load_ok']=load_ok
(out/'load_audit.json').write_text(json.dumps(audit,indent=2,default=str),encoding='utf-8')

t0=time.time()
train_jepa(model,ld['source_train'],ld['source_val'],cfg,dev,out/'finetune',pretrain_only=False,max_epochs=ft_epochs)
ft_sec=round(time.time()-t0,1)
ft_best=torch.load(out/'finetune'/'best.pt',map_location='cpu',weights_only=False)
model.load_state_dict(ft_best['model'],strict=False); model.to(dev).eval()
print(f"[finetune] best val_rmse={ft_best.get('best')} at epoch {ft_best.get('epoch')} ({ft_sec}s)")

# --------------------------------------------------------------- validation metric bundle
# All RMSE metrics are computed in the fixed reference space via metric_affine (see _val_bundle);
# identity for zscore candidates, unit-repair for robust ones.
B=compute_validation_bundle(model,cfg,dev,ld,ld_msk,ld_sch,ds,metric_affine=metric_affine)
clean=B['clean']; long_horizon_rmse=B['long_horizon_rmse']; last_horizon_rmse=B['last_horizon_rmse']
cov=B['cov']; calibration_penalty=B['calibration_penalty']
masked_rmse=B['masked_rmse']; schema_drop_rmse=B['schema_drop_rmse']
act=B['act']; action_sensitivity=B['action_sensitivity']; weak_action=B['weak_action']
ft_ssl=B['ft_ssl']; eff_rank_frac=B['eff_rank_frac']; std_min=B['std_min']; offdiag_corr=B['offdiag_corr']; ft_collapse=B['ft_collapse']
det=determinism_check(model,dev,ds_msk,ld_msk,metric_affine=metric_affine); det_ok=det['ok']

components={'clean_rmse':float(clean['rmse']) if clean['rmse'] is not None else float('nan'),
            'schema_drop_rmse':float(schema_drop_rmse),'masked_rmse':float(masked_rmse),
            'long_horizon_rmse':long_horizon_rmse,'calibration_penalty':float(calibration_penalty),
            'ssl_latent_val':float(ssl_latent_val)}
reasons=[f'nan_{k}' for k,v in components.items() if not np.isfinite(v)]
if not load_ok: reasons.append('checkpoint_load_failure')
if ssl_collapse: reasons.append('ssl_latent_collapse')
if not det_ok: reasons.append('nondeterministic_validation')
if not B['anchor_ok']: reasons.append('metric_scale_anomaly')   # trivial predictor must score ~1.0 in the reference space

rep={'candidate':srch.get('candidate',Path(a.config).stem),'description':srch.get('description',''),
     'config':str(a.config),'out':str(out),'seed':cfg['seed'],'eval_seed':cfg['eval_seed'],'ft_head':ft_head,
     **components,
     'action_sensitivity':action_sensitivity,'weak_action':weak_action,
     'eff_rank_frac':eff_rank_frac,'std_min':std_min,'offdiag_corr':offdiag_corr,
     'collapse':int(bool(ssl_collapse or ft_collapse)),'ssl_collapse':ssl_collapse,'ft_collapse':ft_collapse,
     'eval_space_anchor_rmse':B['anchor_rmse'],
     'metric_space':{'reference':'source_zscore on source_train (fixed across candidates)',
                     'model_normalization':sn.mode,'model_rel_floor':sn.rel_floor,
                     'affine_is_identity':bool(np.allclose(metric_affine[0],1.0) and np.allclose(metric_affine[1],0.0)),
                     'anchor_bounds':list(ANCHOR_BOUNDS)},
     'invalid':bool(reasons),'invalid_reasons':reasons,
     'n_params':int(n_params),'pretrain_seconds':pretrain_sec,'finetune_seconds':ft_sec,'total_seconds':round(time.time()-t_start,1),
     'detail':{'clean':{k:clean[k] for k in ('rmse','mae','r2','nll')},'per_horizon':clean.get('per_horizon'),
               'last_horizon_rmse':last_horizon_rmse,'coverage':cov,'action_rmse':act,
               'schema_drop':{'kept_sensors':transfer,'dropped_sensors':dropped,
                              'mechanism':'sensor_subset -> value 0, presence 0, schema 0 for dropped channels; all 17 target channels still scored'},
               'ssl_best_epoch':best_ep,'ssl_latent_health':ssl_health,'ft_latent_health':{k:v for k,v in ft_ssl.items() if k.startswith(('zpred_','ztgt_'))},
               'ft_val_ssl':ft_ssl['val_ssl'],'determinism':det,
               'load_audit':{k:audit.get(k) for k in ('weights_changed','missing_keys','unexpected_keys','missing_keys_are_head_only','load_ok','ft_head')},
               'epochs':{'pretrain':pre_epochs,'finetune':ft_epochs}},
     'note':'DS01 source_val only. The target machine is not read anywhere in this script.'}
(out/'val_metrics.json').write_text(json.dumps(rep,indent=2,default=str),encoding='utf-8')
print(json.dumps({k:rep[k] for k in ('candidate','seed','clean_rmse','schema_drop_rmse','masked_rmse','long_horizon_rmse',
                                     'calibration_penalty','ssl_latent_val','action_sensitivity','weak_action','collapse',
                                     'eff_rank_frac','eval_space_anchor_rmse','invalid','invalid_reasons','n_params')},indent=2))
