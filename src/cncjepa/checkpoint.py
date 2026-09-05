from __future__ import annotations
import torch
from .factory import build_jepa, build_forecaster

BODY_PREFIXES=('context_encoder.','target_encoder.','predictor.')
HEAD_PREFIXES=('physical_mu.','physical_logvar.','action_recovery.')


def _probe(model,k=3):
    """Norms of up to k representative parameter tensors, used to prove a load did something."""
    names=[n for n,p in model.named_parameters() if p.numel()>1]
    picks=[names[0],names[len(names)//2],names[-1]][:k] if names else []
    d=dict(model.named_parameters())
    return {n:float(d[n].detach().float().norm()) for n in picks}


def _audit(model,state,before,ret,note=''):
    after=_probe(model)
    a={'missing_keys':list(ret.missing_keys),'unexpected_keys':list(ret.unexpected_keys),
       'n_ckpt_tensors':len(state),'n_model_tensors':len(model.state_dict()),
       'probe_before':before,'probe_after':after,
       'weights_changed':any(abs(after[n]-before[n])>1e-9 for n in before) if before else False,'note':note}
    print(f"[ckpt-audit]{(' '+note) if note else ''} missing={len(a['missing_keys'])} unexpected={len(a['unexpected_keys'])} weights_changed={a['weights_changed']}")
    if a['missing_keys']: print('  missing_keys:',a['missing_keys'][:20],'...' if len(a['missing_keys'])>20 else '')
    if a['unexpected_keys']: print('  unexpected_keys:',a['unexpected_keys'][:20],'...' if len(a['unexpected_keys'])>20 else '')
    if not a['weights_changed']: print('  WARNING: no probed parameter changed -- the checkpoint may not have been applied.')
    return a


def load_jepa_checkpoint(path,cfg,device='cpu',schema_adaptive=True):
    """Load a full JEPA checkpoint. Returns (model, obj) with obj['load_audit'] carrying
    missing/unexpected keys and a weights_changed proof."""
    obj=torch.load(path,map_location=device,weights_only=False); model=build_jepa(cfg,schema_adaptive=schema_adaptive)
    before=_probe(model); ret=model.load_state_dict(obj['model'],strict=False)
    obj['load_audit']=_audit(model,obj['model'],before,ret,f'jepa full <- {path}')
    model.to(device); return model,obj


def load_forecaster_checkpoint(path,cfg,name,device='cpu'):
    obj=torch.load(path,map_location=device,weights_only=False); model=build_forecaster(name,cfg)
    before=_probe(model); ret=model.load_state_dict(obj['model'],strict=False)
    obj['load_audit']=_audit(model,obj['model'],before,ret,f'forecaster {name} <- {path}')
    model.to(device); return model,obj


def load_jepa_body_fresh_head(path,cfg,device='cpu',schema_adaptive=True):
    """Load ONLY the SSL body (context encoder, EMA target encoder, predictor) and leave the
    physical mu/logvar head and the action-recovery head at their random initialisation.

    This is the P3-FIX primary fine-tuning path: a head trained (or left random) under pure SSL
    is not a valid warm start for physical forecasting, and loading it confounds
    'pretraining helped' with 'the head happened to be pre-fit'. Returns (model, audit); the
    audit lists head keys deliberately dropped under 'reinitialised'.
    """
    obj=torch.load(path,map_location=device,weights_only=False)
    model=build_jepa(cfg,schema_adaptive=schema_adaptive)
    body={k:v for k,v in obj['model'].items() if k.startswith(BODY_PREFIXES)}
    dropped=sorted(k for k in obj['model'] if not k.startswith(BODY_PREFIXES))
    before=_probe(model); ret=model.load_state_dict(body,strict=False)
    audit=_audit(model,body,before,ret,f'jepa body-only <- {path}')
    audit['reinitialised']=dropped; audit['body_keys_loaded']=len(body)
    # 'missing' here is expected and equals the head: report it separately, not as a failure.
    audit['missing_keys_are_head_only']=all(k.startswith(HEAD_PREFIXES) for k in ret.missing_keys)
    print(f'  body-only load: {len(body)} body tensors applied, {len(dropped)} head/other tensors left random')
    model.to(device); return model,audit
