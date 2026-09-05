from __future__ import annotations
import copy
import torch
import torch.nn.functional as F
from .pipeline import batch_to

def set_trainable(model,mode='head'):
    for p in model.parameters(): p.requires_grad=False
    names=[]
    for n,p in model.named_parameters():
        ok=False
        if mode=='head': ok=('physical_' in n)
        elif mode=='predictor': ok=('predictor' in n or 'physical_' in n)
        elif mode=='sensor_embeddings': ok=('channel_emb' in n or 'physical_' in n)
        elif mode=='full': ok=True
        if ok: p.requires_grad=True; names.append(n)
    return names

def adapt_jepa(model,loader,device,steps=100,lr=1e-4,mode='head'):
    model=copy.deepcopy(model).to(device); set_trainable(model,mode); params=[p for p in model.parameters() if p.requires_grad]
    if not params: return model
    opt=torch.optim.AdamW(params,lr=lr,weight_decay=1e-4); model.train(); it=iter(loader)
    for _ in range(steps):
        try: b=next(it)
        except StopIteration: it=iter(loader); b=next(it)
        b=batch_to(b,device); opt.zero_grad(); o=model(b['x'],b['past_actions'],b['future_actions'],b['present'],b['schema'],y=None); loss=F.mse_loss(o['mu'],b['y']); loss.backward(); torch.nn.utils.clip_grad_norm_(params,1.); opt.step()
    return model
