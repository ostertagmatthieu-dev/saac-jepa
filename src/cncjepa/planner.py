from __future__ import annotations
import numpy as np
import torch

def _channel_index(names, keywords, fallback=None):
    low=[str(x).lower() for x in names]
    for k in keywords:
        for i,n in enumerate(low):
            if k in n: return i
    return fallback

def cem_plan(model,x,pa,present,schema,action_low,action_high,cfg,device,sensor_normalizer=None):
    """CEM planning using the world model.

    If sensor_normalizer is provided, costs/constraints are computed in physical units.
    This is the audited path. A normalized fallback remains only for generic external use.
    """
    pop=int(cfg['planning']['cem_population']); elites=int(cfg['planning']['cem_elites']); iters=int(cfg['planning']['cem_iters']); H=len(cfg['protocol']['horizons']); A=len(action_low)
    low=torch.as_tensor(action_low,device=device,dtype=x.dtype); high=torch.as_tensor(action_high,device=device,dtype=x.dtype); mean=(low+high)/2; std=(high-low)/2
    mean=mean[None,:].repeat(H,1); std=std[None,:].repeat(H,1)
    x=x.to(device); pa=pa.to(device); present=present.to(device); schema=schema.to(device)
    names=cfg['schema']['sensors']; eidx=_channel_index(names,['power','energy'],0); tidx=_channel_index(names,['temperature','temp'],1); widx=_channel_index(names,['wear'],None); pidx=_channel_index(names,['production_rate','production','throughput'],None)
    temp_lim=float(cfg['planning'].get('temperature_limit',75.0)); wear_lim=float(cfg['planning'].get('wear_limit',1.0))
    best=None
    for _ in range(iters):
        acts=(mean[None]+std[None]*torch.randn(pop,H,A,device=device,dtype=x.dtype)).clamp(low,high)
        xb=x.expand(pop,-1,-1); pab=pa.expand(pop,-1,-1); pb=present.expand(pop,-1,-1); sb=schema.expand(pop,-1)
        with torch.no_grad():
            o=model(xb,pab,acts,pb,sb,y=None); y=o['mu']
        if sensor_normalizer is not None:
            center=torch.as_tensor(sensor_normalizer.center,device=device,dtype=y.dtype)
            scale=torch.as_tensor(sensor_normalizer.scale,device=device,dtype=y.dtype)
            ycost=y*(scale+float(sensor_normalizer.eps))+center
            energy=ycost[...,eidx].mean(1)
            temp=ycost[...,tidx].max(1).values
            # Wear constraint only binds when the schema actually has a wear channel.
            wear_pen=20.0*torch.relu((ycost[...,widx].max(1).values-wear_lim)/max(.05,wear_lim)) if widx is not None else 0.0
            # Reward production to avoid the trivial low-energy/zero-throughput plan.
            production=ycost[...,pidx].mean(1) if pidx is not None else torch.zeros_like(energy)
            # Robust scaling avoids one physical unit dominating solely by magnitude.
            e_scale=max(1e-6,float(abs(sensor_normalizer.scale[eidx])))
            p_scale=max(1e-6,float(abs(sensor_normalizer.scale[pidx]))) if pidx is not None else 1.0
            cost=(energy/e_scale) + 20.0*torch.relu((temp-temp_lim)/max(1.0,temp_lim)) + wear_pen - .5*(production/p_scale) + .01*acts.pow(2).mean((1,2))
        else:
            # Generic fallback. Do not use this path for physical constraint claims.
            energy=y[...,eidx].mean(1); temp=y[...,tidx].max(1).values
            wear_pen=5*torch.relu(y[...,widx].max(1).values-2.5) if widx is not None else 0.0
            cost=energy+5*torch.relu(temp-2.5)+wear_pen+.01*acts.pow(2).mean((1,2))
        idx=torch.topk(-cost,k=min(elites,pop)).indices; elite=acts[idx]; mean=elite.mean(0); std=elite.std(0).clamp_min(.02); best=elite[0]
    return best
