"""Shared validation metric bundle for architecture-search V2 (scripts 41 and 59).

This is the post-finetune evaluation block of script 41, extracted verbatim so an eval-only
re-run (script 59) is protocol-identical by construction: same loaders, same eval_seed-pinned
action-shuffle generator and loader-order consumption, same determinism check.

metric_affine=(gain, offset) maps the model's normalized target space into the FIXED reference
space (the canonical source_zscore fit on the same source_train slice, see Normalizer.affine_to)
before every RMSE/MAE/R2 metric. For zscore candidates the map is the identity bitwise, so their
historical numbers are unchanged; for robust candidates it removes the degenerate-IQR scale leak.

anchor_rmse is the reference-space RMSE of the trivial zero predictor (= predict the source_train
mean) on the clean validation targets. By construction it must be ~1.0 whatever the candidate's
own normalization; a wildly different anchor means the metric space is broken and the run must be
flagged, never silently ranked (invalid_reason 'metric_scale_anomaly').
"""
from _common import *
import numpy as np, torch
from torch.utils.data import DataLoader
from scipy.stats import norm
from cncjepa.data import collate
from cncjepa.pipeline import batch_to
from cncjepa.trainers import evaluate_jepa, evaluate_jepa_ssl
from cncjepa.metrics import rmse
from cncjepa.utils import make_generator, seed_worker

WEAK_ACTION_RATIO = 1.02   # shuffled/true RMSE below this => actions barely matter
DET_CHECK_BATCHES = 8      # batches replayed to prove the masked validation is deterministic
ANCHOR_BOUNDS = (0.5, 2.0) # sane range for the trivial-predictor anchor in the reference space


def _rmse_over(model,dev,loader,max_batches=None,action_mode='true',gen=None,metric_affine=None):
    """RMSE of mu against y over `loader`. action_mode: true | zero | shuffle | time_shuffle."""
    ys=[];ps=[];ms=[]
    with torch.no_grad():
        for bi,b in enumerate(loader):
            if max_batches is not None and bi>=max_batches: break
            b=batch_to(b,dev); fa=b['future_actions']
            if action_mode=='zero': fa=torch.zeros_like(fa)
            elif action_mode=='shuffle' and fa.size(0)>1:
                perm=torch.randperm(fa.size(0),generator=gen)
                if bool((perm==torch.arange(fa.size(0))).all()): perm=torch.roll(perm,1,0)
                fa=fa[perm.to(fa.device)]
            elif action_mode=='time_shuffle' and fa.size(1)>1:
                perm=torch.randperm(fa.size(1),generator=gen)
                if bool((perm==torch.arange(fa.size(1))).all()): perm=torch.roll(perm,1,0)
                fa=fa[:,perm.to(fa.device)]
            o=model(b['x'],b['past_actions'],fa,b['present'],b['schema'],y=None)
            ys.append(b['y'].float().cpu().numpy()); ps.append(o['mu'].float().cpu().numpy()); ms.append(b['target_present'].bool().cpu().numpy())
    if not ys: return float('nan')
    y=np.concatenate(ys); pr=np.concatenate(ps); mk=np.concatenate(ms)
    if metric_affine is not None:
        gain,offset=metric_affine; y=y*gain+offset; pr=pr*gain+offset
    return rmse(np.where(mk,y,np.nan),np.where(mk,pr,np.nan))


def compute_validation_bundle(model,cfg,dev,ld,ld_msk,ld_sch,ds,metric_affine=None):
    """Everything script 41 measures after fine-tuning, as one dict. `model` must already be
    in eval mode on `dev` with the finetune/best.pt weights loaded."""
    clean,raw=evaluate_jepa(model,ld['source_val'],dev,metric_affine=metric_affine)
    ph={k:v['rmse'] for k,v in (clean.get('per_horizon') or {}).items()}
    long_horizon_rmse=float(max(ph.values())) if ph else float('nan')
    last_horizon_rmse=float(ph[sorted(ph,key=lambda k:int(k))[-1]]) if ph else float('nan')

    # coverage/calibration from the model-space raw dict, DELIBERATELY: coverage is a probability
    # (scale-free across candidates by nature) computed with the standard +/-8 logvar clip in the
    # model's own space -- exactly what every historical run reports. It is NOT re-projected to
    # the reference space: with an extreme gain the clip would bind differently there, and the
    # number would measure the clip convention rather than calibration.
    sd=np.exp(.5*np.clip(raw['logvar'],-8,8)); mk=raw['mask']
    cov={}
    for lvl in (.5,.8,.9,.95):
        z=float(norm.ppf((1+lvl)/2)); inside=((raw['y']>=raw['pred']-z*sd)&(raw['y']<=raw['pred']+z*sd))&mk
        cov[str(lvl)]=float(inside.sum()/max(1,int(mk.sum())))
    calibration_penalty=abs(cov['0.9']-.9)

    # trivial-predictor anchor in the reference space: metric-space sanity, model-independent
    gain,offset=metric_affine if metric_affine is not None else (1.0,0.0)
    y_ref=raw['y']*gain+offset
    anchor_rmse=rmse(np.where(mk,y_ref,np.nan),np.where(mk,np.zeros_like(y_ref),np.nan))
    anchor_ok=bool(np.isfinite(anchor_rmse) and ANCHOR_BOUNDS[0]<anchor_rmse<ANCHOR_BOUNDS[1])

    masked_rmse=_rmse_over(model,dev,ld_msk['source_val'],metric_affine=metric_affine)
    schema_drop_rmse=_rmse_over(model,dev,ld_sch['source_val'],metric_affine=metric_affine)

    # action diagnostic on a SHUFFLED source_val loader: batches must mix distant windows or the
    # "shuffled" actions would just be a temporal neighbour's near-identical actions.
    act_loader=DataLoader(ds['source_val'],batch_size=int(cfg['train']['batch_size']),shuffle=True,
                          num_workers=int(cfg['train'].get('num_workers',0)),collate_fn=collate,
                          generator=make_generator(cfg['eval_seed']),
                          worker_init_fn=(seed_worker if int(cfg['train'].get('num_workers',0))>0 else None))
    gen=make_generator(cfg['eval_seed'])
    act={m_:_rmse_over(model,dev,act_loader,action_mode=m_,gen=gen,metric_affine=metric_affine) for m_ in ('true','zero','shuffle','time_shuffle')}
    action_sensitivity=float(act['shuffle']/act['true']) if act['true'] and np.isfinite(act['true']) and act['true']>0 else float('nan')
    weak_action=int(not np.isfinite(action_sensitivity) or action_sensitivity<WEAK_ACTION_RATIO)

    ft_ssl=evaluate_jepa_ssl(model,ld['source_val'],cfg,dev)
    eff_rank_frac=float(min(ft_ssl['zpred_eff_rank_frac'],ft_ssl['ztgt_eff_rank_frac']))
    std_min=float(min(ft_ssl['zpred_std_min'],ft_ssl['ztgt_std_min']))
    offdiag_corr=float(max(ft_ssl['zpred_offdiag_corr'],ft_ssl['ztgt_offdiag_corr']))
    ft_collapse=int(ft_ssl.get('collapse',0))

    return {'clean':clean,'raw':raw,'long_horizon_rmse':long_horizon_rmse,'last_horizon_rmse':last_horizon_rmse,
            'cov':cov,'calibration_penalty':float(calibration_penalty),
            'anchor_rmse':float(anchor_rmse),'anchor_ok':anchor_ok,
            'masked_rmse':float(masked_rmse),'schema_drop_rmse':float(schema_drop_rmse),
            'act':act,'action_sensitivity':action_sensitivity,'weak_action':weak_action,
            'ft_ssl':ft_ssl,'eff_rank_frac':eff_rank_frac,'std_min':std_min,'offdiag_corr':offdiag_corr,
            'ft_collapse':ft_collapse}


def determinism_check(model,dev,ds_msk,ld_msk,metric_affine=None):
    """Identical masks on re-read AND an identical replayed metric (script 41's det check)."""
    dsv=ds_msk['source_val']
    mask_stable=(dsv.mask_rng_seed is not None) and torch.equal(dsv[0]['aug_mask'],dsv[0]['aug_mask']) and float(dsv[0]['aug_mask'].sum())>0
    r1=_rmse_over(model,dev,ld_msk['source_val'],max_batches=DET_CHECK_BATCHES,metric_affine=metric_affine)
    r2=_rmse_over(model,dev,ld_msk['source_val'],max_batches=DET_CHECK_BATCHES,metric_affine=metric_affine)
    det_ok=bool(mask_stable and np.isfinite(r1) and abs(r1-r2)<1e-9)
    return {'mask_stable':bool(mask_stable),'replay_rmse':[r1,r2],'ok':det_ok}
