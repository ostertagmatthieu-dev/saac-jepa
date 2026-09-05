"""Re-emit val_metrics.json for ALREADY TRAINED search-V2 runs, with every RMSE component
computed in the fixed reference space (source_zscore fit on source_train) -- eval-only, loads
<run>/finetune/best.pt and never trains. Purpose: repair the metric-scale leak of robust-
normalization candidates (M14/M19), whose historical val_metrics.json reported RMSE in their own
robust-transform space (~453, dominated by the degenerate z_power IQR) and were therefore
incommensurable with the zscore pool (~0.82).

Protocol identity: the data views, eval_seed-pinned loaders/generators and the metric bundle are
the exact objects script 41 uses (scripts/_val_bundle.py). The model input/target transform must
be byte-identical to what the checkpoint was trained with, so the effective robust-scale floor is
resolved per run, in order: (1) normalization.rel_floor recorded in the run's config.yaml (written
by the post-fix script 41), (2) metric_space.model_rel_floor recorded in val_metrics.json by a
previous re-metric, (3) 0.0 -- the legacy pre-floor behaviour, correct for checkpoints trained
before the fix. The scale repair happens only in the metric affine, never in the model transform.
On --apply the resolved value is also written back into the run's config.yaml so every OTHER
eval script (30-38/46-49/56...) that calls prepare() on that config reproduces the training-time
transform instead of silently inheriting the new 0.05 default. For zscore candidates the affine
is the identity, so re-running this script on them must reproduce their existing numbers exactly
-- that property is the regression check for the shared bundle refactor (--check prints deltas).

Non-RMSE fields that do not depend on the metric space are carried over from the original
val_metrics.json: ssl_latent_val (+ pretrain history fields), ssl_collapse, timings, load audit.

Writes <run>/val_metrics_commonspace.json always. With --apply, first backs up the original
val_metrics.json to val_metrics_modelspace.json (once, never overwritten), then replaces
val_metrics.json so scripts 43/44 pick up the comparable numbers.
DS01 source_val only -- the target machine is never opened.
"""
from _common import *
from _val_bundle import compute_validation_bundle, determinism_check, ANCHOR_BOUNDS
import argparse, json, time
import numpy as np, torch
from cncjepa.config import load_config, save_config
from cncjepa.normalization import Normalizer
from cncjepa.pipeline import prepare, loaders_from_ds
from cncjepa.factory import build_jepa
from cncjepa.trainers import evaluate_jepa  # noqa: F401  (kept import parity with _val_bundle)
from cncjepa.utils import device_from_arg, set_seed, count_parameters

KEY_COMPONENTS=('clean_rmse','schema_drop_rmse','masked_rmse','long_horizon_rmse',
                'calibration_penalty','action_sensitivity')

p=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
p.add_argument('runs',nargs='+',help='run dirs, e.g. outputs/random_search/M14/seed_0')
p.add_argument('--device',default='auto')
p.add_argument('--apply',action='store_true',help='replace val_metrics.json (original backed up to val_metrics_modelspace.json)')
p.add_argument('--check',action='store_true',help='print old-vs-new deltas for the key components')
a=p.parse_args()
dev=device_from_arg(a.device)

for run in a.runs:
    out=Path(run); t0=time.time()
    base=json.loads((out/'val_metrics.json').read_text(encoding='utf-8'))
    cfg=load_config(out/'config.yaml')
    cfg['eval_seed']=int(cfg.get('eval_seed',cfg.get('seed',0))); cfg['seed']=int(cfg.get('seed',0))
    # training-time transform: config.yaml > previous re-metric record > legacy unfloored (0.0)
    rf=cfg.get('normalization',{}).get('rel_floor')
    if rf is None: rf=(base.get('metric_space') or {}).get('model_rel_floor')
    if rf is None: rf=0.0
    cfg.setdefault('normalization',{})['rel_floor']=float(rf)
    set_seed(cfg['seed'])
    print(f"[{out}] candidate={base.get('candidate')} seed={cfg['seed']} norm={cfg['normalization'].get('mode','source_zscore')} rel_floor={float(rf)}")

    # data: the same three views of one split as script 41
    frame,split,ds,sn,_= prepare(cfg,training_mask=True)
    _,_,ds_msk,_,_= prepare(cfg,training_mask=True,val_mask=True,resampled_df=frame)
    transfer=list(cfg['schema']['transfer_sensors']); dropped=[s for s in cfg['schema']['sensors'] if s not in set(transfer)]
    _,_,ds_sch,_,_= prepare(cfg,sensor_subset=transfer,training_mask=False,resampled_df=frame)
    ld=loaders_from_ds(ds,cfg); ld_msk=loaders_from_ds(ds_msk,cfg,shuffle_train=False); ld_sch=loaders_from_ds(ds_sch,cfg,shuffle_train=False)

    ref_sn=Normalizer('zscore').fit(split['source_train'][cfg['schema']['sensors']].to_numpy(float))
    metric_affine=sn.affine_to(ref_sn)

    model=build_jepa(cfg,True); n_params=count_parameters(model)
    ft_best=torch.load(out/'finetune'/'best.pt',map_location='cpu',weights_only=False)
    model.load_state_dict(ft_best['model'],strict=False); model.to(dev).eval()

    B=compute_validation_bundle(model,cfg,dev,ld,ld_msk,ld_sch,ds,metric_affine=metric_affine)
    det=determinism_check(model,dev,ds_msk,ld_msk,metric_affine=metric_affine)

    components={'clean_rmse':float(B['clean']['rmse']) if B['clean']['rmse'] is not None else float('nan'),
                'schema_drop_rmse':B['schema_drop_rmse'],'masked_rmse':B['masked_rmse'],
                'long_horizon_rmse':B['long_horizon_rmse'],'calibration_penalty':B['calibration_penalty'],
                'ssl_latent_val':float(base.get('ssl_latent_val',float('nan')))}
    ssl_collapse=int(base.get('ssl_collapse',0)); load_ok=bool((base.get('detail') or {}).get('load_audit',{}).get('load_ok',True))
    reasons=[f'nan_{k}' for k,v in components.items() if not np.isfinite(v)]
    if not load_ok: reasons.append('checkpoint_load_failure')
    if ssl_collapse: reasons.append('ssl_latent_collapse')
    if not det['ok']: reasons.append('nondeterministic_validation')
    if not B['anchor_ok']: reasons.append('metric_scale_anomaly')

    detail=dict(base.get('detail') or {})
    detail.update({'clean':{k:B['clean'][k] for k in ('rmse','mae','r2','nll')},'per_horizon':B['clean'].get('per_horizon'),
                   'last_horizon_rmse':B['last_horizon_rmse'],'coverage':B['cov'],'action_rmse':B['act'],
                   'ft_latent_health':{k:v for k,v in B['ft_ssl'].items() if k.startswith(('zpred_','ztgt_'))},
                   'ft_val_ssl':B['ft_ssl']['val_ssl'],'determinism':det})
    rep=dict(base)
    rep.update({**components,
                'action_sensitivity':B['action_sensitivity'],'weak_action':B['weak_action'],
                'eff_rank_frac':B['eff_rank_frac'],'std_min':B['std_min'],'offdiag_corr':B['offdiag_corr'],
                'collapse':int(bool(ssl_collapse or B['ft_collapse'])),'ssl_collapse':ssl_collapse,'ft_collapse':B['ft_collapse'],
                'eval_space_anchor_rmse':B['anchor_rmse'],
                'metric_space':{'reference':'source_zscore on source_train (fixed across candidates)',
                                'model_normalization':sn.mode,'model_rel_floor':sn.rel_floor,
                                'affine_is_identity':bool(np.allclose(metric_affine[0],1.0) and np.allclose(metric_affine[1],0.0)),
                                'anchor_bounds':list(ANCHOR_BOUNDS)},
                'invalid':bool(reasons),'invalid_reasons':reasons,'n_params':int(n_params),'detail':detail,
                'remetric':{'script':'67_reeval_common_space.py','reeval_only':True,
                            'reeval_seconds':round(time.time()-t0,1),
                            'original_backup':'val_metrics_modelspace.json',
                            'note':'RMSE components re-computed in the fixed reference space from finetune/best.pt; '
                                   'ssl_latent_val, timings and load audit carried over from the original run.'}})

    (out/'val_metrics_commonspace.json').write_text(json.dumps(rep,indent=2,default=str),encoding='utf-8')
    if a.check:
        print('  component            old (model space)   new (reference space)')
        for k in KEY_COMPONENTS:
            print(f'  {k:20s} {float(base.get(k,float("nan"))):>18.6f} {float(rep[k]):>20.6f}')
        print(f'  anchor_rmse {B["anchor_rmse"]:.6f} (bounds {ANCHOR_BOUNDS}) affine_identity={rep["metric_space"]["affine_is_identity"]}'
              f' invalid={rep["invalid"]} reasons={reasons}')
    if a.apply:
        bak=out/'val_metrics_modelspace.json'
        if not bak.exists(): bak.write_text(json.dumps(base,indent=2,default=str),encoding='utf-8')
        (out/'val_metrics.json').write_text(json.dumps(rep,indent=2,default=str),encoding='utf-8')
        # Persist the resolved training-time floor into the run config so every other prepare()-
        # based eval script reproduces the checkpoint's transform (guards against the 0.05 default).
        save_config(cfg,out/'config.yaml')
        print(f'  applied -> {out}/val_metrics.json (original preserved in {bak.name}; rel_floor={float(rf)} persisted in config.yaml)')
    else:
        print(f'  wrote {out}/val_metrics_commonspace.json (dry run, val_metrics.json untouched)')
