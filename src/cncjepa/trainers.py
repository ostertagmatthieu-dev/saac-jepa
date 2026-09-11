from __future__ import annotations
import copy, csv, math, time
from pathlib import Path
import numpy as np
import torch
import torch.nn.functional as F
from .losses import jepa_latent_loss, vicreg, gaussian_nll
from .metrics import rmse,mae,r2,per_horizon_metrics
from .models.jepa import vicreg_latents
from .pipeline import batch_to
from .utils import atomic_torch_save

COLLAPSE_STD_MIN=0.05          # per-dim std floor below which a latent dim is dead
COLLAPSE_EFF_RANK_FRAC=0.10    # effective rank below frac*d => representational collapse
_HEALTH_MAX_ROWS=20000         # SVD subsample cap


def _vicreg_by_mode(z,mode,cfg):
    if mode=='none': return z.new_tensor(0.)
    kw=dict(sim_coeff=cfg['jepa'].get('vicreg_sim',25.),var_coeff=cfg['jepa'].get('vicreg_var',25.),cov_coeff=cfg['jepa'].get('vicreg_cov',1.),target_std=cfg['jepa'].get('variance_target',1.0))
    if mode=='pooled': return vicreg(z.reshape(-1,z.shape[-1]),**kw)
    if mode=='per_horizon': return torch.stack([vicreg(z[:,h],**kw) for h in range(z.shape[1])]).mean()
    raise ValueError(mode)

def _vicreg_term(lat,cfg):
    mode=cfg['jepa'].get('vicreg_mode','per_horizon')
    zs=vicreg_latents(lat,cfg['jepa'].get('vicreg_placement','predictor'))
    if not zs: return next(iter(lat.values())).new_tensor(0.)
    return torch.stack([_vicreg_by_mode(z,mode,cfg) for z in zs]).mean()

def _ln(z,on): return F.layer_norm(z,(z.shape[-1],)) if on else z

def jepa_step(model,b,cfg,train=True,ssl_mode=False):
    """One JEPA optimisation step.

    ssl_mode=True is *pure* SSL pretraining: the physical mu/logvar head is untrained, so
    (a) schema consistency is measured on LATENT predictions rather than on `mu`, and
    (b) the physical term is dropped entirely (weight is forced to 0 by train_jepa) so no
    gradient ever reaches the physical head. Outside ssl_mode the head is being trained and
    the mu-space schema consistency is the meaningful one.
    """
    out=model(b['x'],b['past_actions'],b['future_actions'],b['present'],b['schema'],b['y'],b.get('target_present'))
    ln=cfg['jepa'].get('latent_layernorm', True)
    # Explicit latent-space LayerNorm ablation requested by the reviewer.
    # This is separate from the Transformer's internal pre/post norm choice.
    pred=_ln(out['z_pred'],ln); tgt=_ln(out['z_target'],ln)
    if cfg['jepa'].get('target_aggregation','per_horizon')=='pooled':
        latent=jepa_latent_loss(pred.mean(1),tgt.mean(1),cfg['jepa'].get('latent_loss','smooth_l1'))
    else: latent=jepa_latent_loss(pred,tgt,cfg['jepa'].get('latent_loss','smooth_l1'))
    vr=_vicreg_term({'predictor':pred,'target':tgt,'context':_ln(out['z_context_pool'],ln)[:,None,:]},cfg)
    # train_jepa already overrides cfg.jepa.physical_weight to 0 for pretrain_only (so the
    # saved config is honest about it); this second guard makes ssl_mode self-contained, i.e.
    # "ssl_mode implies the physical head is never trained" holds for direct callers too.
    pw=0. if ssl_mode else float(cfg['jepa'].get('physical_weight',1.0))
    if pw>0:
        phys=gaussian_nll(out['mu'],out['logvar'],b['y'],b.get('target_present')) if cfg['model'].get('probabilistic_head',True) else (((out['mu']-b['y']).pow(2)*b.get('target_present',torch.ones_like(b['y']))).sum()/(b.get('target_present',torch.ones_like(b['y'])).sum()+1e-8))
    else: phys=pred.new_tensor(0.)   # no graph -> physical head receives no gradient at all
    arec=F.mse_loss(out['action_hat'],b['future_actions'])
    schema_cons=pred.new_tensor(0.)
    if cfg['jepa'].get('schema_consistency_weight',0)>0 and hasattr(model,'schema_view') and train:
        x2,p2,s2=model.schema_view(b['x'],b['present'],b['schema'],keep_prob=.65)
        o2=model(x2,b['past_actions'],b['future_actions'],p2,s2,y=None)
        # P3-FIX: during pure SSL the physical head is random, so consistency on `mu` is noise.
        # Penalise the latent trajectory instead, under the same LayerNorm as the main loss.
        if ssl_mode: schema_cons=F.smooth_l1_loss(_ln(o2['z_pred'],ln),pred.detach())
        else: schema_cons=F.smooth_l1_loss(o2['mu'],out['mu'].detach())
    total=cfg['jepa'].get('latent_weight',1.)*latent+cfg['jepa'].get('vicreg_weight',.05)*vr+pw*phys+cfg['jepa'].get('action_recovery_weight',.05)*arec+cfg['jepa'].get('schema_consistency_weight',0.)*schema_cons
    return total,{'loss':total.detach(),'latent':latent.detach(),'vicreg':vr.detach(),'physical':phys.detach(),'action_recovery':arec.detach(),'schema_cons':schema_cons.detach()},out


# ---------------------------------------------------------------- latent health

def latent_health(z,prefix=''):
    """Representation-health metrics for a latent matrix Z (any leading shape, last dim d).

    std_mean/std_min : mean / min over dims of the per-dim standard deviation across samples.
    offdiag_corr     : mean |Pearson correlation| over the d*(d-1) off-diagonal pairs.
                       -> 0 means decorrelated dims, -> 1 means every dim carries one signal.
    eff_rank         : exp(H(p)) with p = singular values of the centred [N,d] matrix
                       normalised to sum 1 and H the Shannon entropy in nats. Equals d for a
                       perfectly isotropic code and 1 for a rank-1 (fully collapsed) code.
    collapse         : std_min < 0.05 or eff_rank < 0.10*d.
    """
    z=np.asarray(z,dtype=np.float64).reshape(-1,np.shape(z)[-1])
    z=z[np.isfinite(z).all(1)]
    d=z.shape[1]
    if z.shape[0]<2: return {f'{prefix}std_mean':float('nan'),f'{prefix}std_min':float('nan'),f'{prefix}offdiag_corr':float('nan'),f'{prefix}eff_rank':float('nan'),f'{prefix}eff_rank_frac':float('nan'),f'{prefix}collapse':1}
    if z.shape[0]>_HEALTH_MAX_ROWS: z=z[np.linspace(0,z.shape[0]-1,_HEALTH_MAX_ROWS).astype(int)]
    std=z.std(0)
    zc=z-z.mean(0)
    den=np.outer(std,std)+1e-12
    corr=((zc.T@zc)/max(1,z.shape[0]-1))/den
    off=float(np.abs(corr[~np.eye(d,dtype=bool)]).mean()) if d>1 else 0.
    sv=np.linalg.svd(zc,compute_uv=False); p=sv/(sv.sum()+1e-12); p=p[p>0]
    eff=float(np.exp(-(p*np.log(p)).sum()))
    return {f'{prefix}std_mean':float(std.mean()),f'{prefix}std_min':float(std.min()),f'{prefix}offdiag_corr':off,
            f'{prefix}eff_rank':eff,f'{prefix}eff_rank_frac':eff/d,
            f'{prefix}collapse':int(std.min()<COLLAPSE_STD_MIN or eff<COLLAPSE_EFF_RANK_FRAC*d)}


# ---------------------------------------------------------------- evaluation

def evaluate_jepa(model,loader,device,metric_affine=None):
    """metric_affine=(gain, offset): optional per-channel affine mapping the model's normalized
    target space into a fixed reference space (Normalizer.affine_to). RMSE/MAE/R2/per-horizon are
    then computed in the reference space so candidates with different normalization modes stay
    unit-comparable. NLL and the returned raw dict stay in the model's OWN space: NLL transformed
    through an extreme gain is dominated by the +/-8 logvar clip and would measure the clip
    convention, not calibration, so it is reported model-space and is not cross-space comparable."""
    model.eval(); ys=[]; ps=[]; lvs=[]; ms=[]; metas=[]
    with torch.no_grad():
        for b in loader:
            b=batch_to(b,device); o=model(b['x'],b['past_actions'],b['future_actions'],b['present'],b['schema'],y=None)
            ys.append(b['y'].cpu().numpy()); ps.append(o['mu'].cpu().numpy()); lvs.append(o['logvar'].cpu().numpy()); ms.append(b.get('target_present',torch.ones_like(b['y'])).cpu().numpy())
            metas.extend(zip(b['machine'],b['session'],b['run']))
    if not ys: return {'rmse':None,'mae':None,'r2':None,'nll':None},None
    y=np.concatenate(ys); p=np.concatenate(ps); lv=np.concatenate(lvs); m=np.concatenate(ms).astype(bool)
    raw={'y':y,'pred':p,'logvar':lv,'mask':m,'meta':metas}
    lvc=np.clip(lv,-8,8); nll=float((.5*(lvc+(y-p)**2*np.exp(-lvc))*m).sum()/(m.sum()+1e-8))   # model space
    if metric_affine is not None:
        gain,offset=metric_affine
        y=y*gain+offset; p=p*gain+offset
    ym=np.where(m,y,np.nan); pm=np.where(m,p,np.nan)
    return {'rmse':rmse(ym,pm),'mae':mae(ym,pm),'r2':r2(ym,pm),'nll':nll,'per_horizon':per_horizon_metrics(ym,pm)}, raw


def evaluate_jepa_ssl(model,loader,cfg,device,max_batches=None):
    """True held-out SSL validation objective + latent health.

    This is the model-selection criterion for pure SSL pretraining: it measures the
    *latent* prediction task (plus the VICReg term) on data the optimiser never saw,
    under deterministic masks. It never touches the physical head. `val_ssl` is the
    quantity minimised; the latent-health fields are diagnostics/gates.
    `max_batches` caps the pass (used for the cheap diagnostic pass during fine-tuning;
    selection during pretraining always runs the full loader).
    """
    model.eval(); ln=cfg['jepa'].get('latent_layernorm',True); agg=cfg['jepa'].get('target_aggregation','per_horizon')
    lw=float(cfg['jepa'].get('latent_weight',1.)); vw=float(cfg['jepa'].get('vicreg_weight',.05))
    nb=min(len(loader),int(max_batches)) if max_batches is not None else len(loader)
    keep=max(1,_HEALTH_MAX_ROWS//max(1,nb))   # uniform latent subsample, bounded memory
    n=0; s_lat=0.; s_vr=0.; s_arec=0.; zp=[]; zt=[]
    with torch.no_grad():
        for bi,b in enumerate(loader):
            if max_batches is not None and bi>=int(max_batches): break
            b=batch_to(b,device)
            o=model(b['x'],b['past_actions'],b['future_actions'],b['present'],b['schema'],b['y'],b.get('target_present'))
            pred=_ln(o['z_pred'],ln); tgt=_ln(o['z_target'],ln)
            lat=jepa_latent_loss(pred.mean(1),tgt.mean(1),cfg['jepa'].get('latent_loss','smooth_l1')) if agg=='pooled' else jepa_latent_loss(pred,tgt,cfg['jepa'].get('latent_loss','smooth_l1'))
            vr=_vicreg_term({'predictor':pred,'target':tgt,'context':_ln(o['z_context_pool'],ln)[:,None,:]},cfg)
            s_lat+=float(lat); s_vr+=float(vr); s_arec+=float(F.mse_loss(o['action_hat'],b['future_actions'])); n+=1
            d=pred.shape[-1]
            zp.append(pred.reshape(-1,d)[:keep].float().cpu().numpy()); zt.append(tgt.reshape(-1,d)[:keep].float().cpu().numpy())
    if n==0: return {'val_ssl':float('nan'),'val_latent':float('nan'),'val_vicreg':float('nan'),'val_action_recovery':float('nan'),'n_batches':0}
    out={'val_latent':s_lat/n,'val_vicreg':s_vr/n,'val_action_recovery':s_arec/n,'n_batches':n}
    out['val_ssl']=lw*out['val_latent']+vw*out['val_vicreg']
    out.update(latent_health(np.concatenate(zp),'zpred_')); out.update(latent_health(np.concatenate(zt),'ztgt_'))
    out['collapse']=int(out['zpred_collapse'] or out['ztgt_collapse'])
    return out


# ---------------------------------------------------------------- training

def ema_at(cfg,ep,epochs):
    """Fixed cfg['jepa']['ema'] unless cfg['jepa']['ema_schedule']={'start','end','kind'} is
    given, in which case the momentum ramps start->end over `epochs` (linear or cosine)."""
    sch=cfg['jepa'].get('ema_schedule')
    if not sch: return float(cfg['jepa'].get('ema',.996))
    s=float(sch.get('start',.99)); e=float(sch.get('end',.9999)); t=0. if epochs<=1 else ep/float(epochs-1)
    t=min(1.,max(0.,t)); t=(1-math.cos(math.pi*t))/2 if str(sch.get('kind','linear')).lower()=='cosine' else t
    return s+(e-s)*t

def _write_csv(path,rows):
    if not rows: return
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with Path(path).open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=keys); w.writeheader()
        for r in rows: w.writerow({k:r.get(k,'') for k in keys})

def train_jepa(model,train_loader,val_loader,cfg,device,out_dir,pretrain_only=False,max_epochs=None):
    """Train the JEPA.

    Selection criterion (P3-FIX):
      pretrain_only=True  -> best.pt minimises `val_ssl` on the held-out SSL loader
                             (latent_weight*latent + vicreg_weight*vicreg), never train loss.
                             The physical head is frozen out via a physical_weight=0 override.
      pretrain_only=False -> best.pt minimises held-out physical val RMSE, as before.
    Early stopping uses the same score. Writes history.csv and latent_health.csv.
    """
    out_dir=Path(out_dir); out_dir.mkdir(parents=True,exist_ok=True); model.to(device)
    if pretrain_only:
        cfg=copy.deepcopy(cfg); cfg['jepa']['physical_weight']=0.0   # config override, not a hardcode
    opt=torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],lr=float(cfg['train']['lr']),weight_decay=float(cfg['train']['weight_decay']))
    scaler=torch.amp.GradScaler('cuda', enabled=bool(cfg['train'].get('amp',True) and device.type=='cuda'))
    epochs=int(max_epochs or cfg['train']['epochs']); best=float('inf'); bad=0; hist=[]; health=[]
    for ep in range(epochs):
        model.ema=ema_at(cfg,ep,epochs)
        model.train(); sums={}; n=0; t0=time.time()
        max_batches=cfg['train'].get('max_batches_per_epoch')
        for bi,b in enumerate(train_loader):
            if max_batches is not None and bi>=int(max_batches): break
            b=batch_to(b,device); opt.zero_grad(set_to_none=True)
            with torch.amp.autocast(device_type=device.type, enabled=scaler.is_enabled()): loss,parts,_=jepa_step(model,b,cfg,train=True,ssl_mode=pretrain_only)
            scaler.scale(loss).backward(); scaler.unscale_(opt); torch.nn.utils.clip_grad_norm_(model.parameters(),float(cfg['train'].get('grad_clip',1.0))); scaler.step(opt); scaler.update(); model.update_target()
            for k,v in parts.items(): sums[k]=sums.get(k,0.)+float(v); n+=1 if k=='loss' else 0
        tr={k:v/max(1,n) for k,v in sums.items()}
        # full pass when it is the selection criterion; capped diagnostic pass otherwise
        ssl=evaluate_jepa_ssl(model,val_loader,cfg,device,max_batches=(None if pretrain_only else cfg['train'].get('val_ssl_max_batches',32)))
        val,_=evaluate_jepa(model,val_loader,device) if not pretrain_only else ({'rmse':None,'mae':None,'r2':None,'nll':None},None)
        score=ssl['val_ssl'] if pretrain_only else (val['rmse'] if val['rmse'] is not None else tr.get('loss',0.))
        row={'epoch':ep,'ema':model.ema,'sec':round(time.time()-t0,1),'select_on':('val_ssl' if pretrain_only else 'val_rmse'),'score':score,
             **{f'train_{k}':v for k,v in tr.items()},
             'val_ssl':ssl['val_ssl'],'val_latent':ssl['val_latent'],'val_vicreg':ssl['val_vicreg'],'val_action_recovery':ssl['val_action_recovery'],
             'val_rmse':val['rmse'],'val_mae':val['mae'],'val_nll':val['nll'],'val_r2':val['r2'],'collapse':ssl.get('collapse')}
        hist.append(row); health.append({'epoch':ep,**{k:v for k,v in ssl.items() if k.startswith(('zpred_','ztgt_'))},'collapse':ssl.get('collapse')})
        _write_csv(out_dir/'history.csv',hist); _write_csv(out_dir/'latent_health.csv',health)
        if score is not None and np.isfinite(score) and score<best:
            best=score; bad=0; atomic_torch_save({'model':model.state_dict(),'cfg':cfg,'epoch':ep,'best':best,'select_on':row['select_on'],'val':row},out_dir/'best.pt')
        else: bad+=1
        if bad>=int(cfg['train'].get('early_stop_patience',15)): break
    atomic_torch_save({'model':model.state_dict(),'cfg':cfg,'history':hist},out_dir/'last.pt')
    return hist

def train_forecaster(model,train_loader,val_loader,cfg,device,out_dir,max_epochs=None):
    out_dir=Path(out_dir); out_dir.mkdir(parents=True,exist_ok=True); model.to(device)
    params=[p for p in model.parameters() if p.requires_grad]
    if not params:   # persistence / linear-drift: no-learn baselines, evaluate once
        met,_=evaluate_forecaster(model,val_loader,device); atomic_torch_save({'model':model.state_dict(),'cfg':cfg,'best':met['rmse']},out_dir/'best.pt'); return met['rmse']
    opt=torch.optim.AdamW(params,lr=float(cfg['train']['lr']),weight_decay=float(cfg['train']['weight_decay'])); best=float('inf'); bad=0
    for ep in range(int(max_epochs or cfg['train']['epochs'])):
        model.train()
        max_batches=cfg['train'].get('max_batches_per_epoch')
        for bi,b in enumerate(train_loader):
            if max_batches is not None and bi>=int(max_batches): break
            b=batch_to(b,device); opt.zero_grad(); pred=model(b['x'],b['past_actions'],b['future_actions'],present=b['present'],schema=b['schema']); mask=b.get('target_present',torch.ones_like(b['y'])); loss=((pred-b['y']).pow(2)*mask).sum()/(mask.sum()+1e-8); loss.backward(); torch.nn.utils.clip_grad_norm_(model.parameters(),1.); opt.step()
        met,_=evaluate_forecaster(model,val_loader,device); score=met['rmse']
        if score<best: best=score; bad=0; atomic_torch_save({'model':model.state_dict(),'cfg':cfg,'best':best},out_dir/'best.pt')
        else: bad+=1
        if bad>=int(cfg['train'].get('early_stop_patience',15)): break
    return best

def evaluate_forecaster(model,loader,device):
    model.eval(); ys=[]; ps=[]; ms=[]; meta=[]
    with torch.no_grad():
        for b in loader:
            b=batch_to(b,device); p=model(b['x'],b['past_actions'],b['future_actions'],present=b['present'],schema=b['schema']); ys.append(b['y'].cpu().numpy()); ps.append(p.cpu().numpy()); ms.append(b.get('target_present',torch.ones_like(b['y'])).cpu().numpy()); meta.extend(zip(b['machine'],b['session'],b['run']))
    y=np.concatenate(ys); p=np.concatenate(ps); m=np.concatenate(ms).astype(bool); ym=np.where(m,y,np.nan); pm=np.where(m,p,np.nan)
    return {'rmse':rmse(ym,pm),'mae':mae(ym,pm),'r2':r2(ym,pm),'per_horizon':per_horizon_metrics(ym,pm)}, {'y':y,'pred':p,'mask':m,'meta':meta}
