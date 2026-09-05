from __future__ import annotations
import numpy as np
import torch


def random_point_mask(x, ratio, rng=None):
    rng=np.random.default_rng() if rng is None else rng
    return rng.random(x.shape) < ratio

def block_mask(x, ratio, block_min=2, block_max=12, rng=None):
    rng=np.random.default_rng() if rng is None else rng
    B,T,C=x.shape; m=np.zeros((B,T,C),bool)
    target=int(B*T*C*ratio); n=0
    while n<target:
        b=rng.integers(B); c=rng.integers(C); L=int(rng.integers(block_min, block_max+1)); s=int(rng.integers(max(1,T-L+1)))
        prev=m[b,s:s+L,c].sum(); m[b,s:s+L,c]=True; n += L-prev
    return m

def channel_mask(x, prob=0.15, rng=None):
    rng=np.random.default_rng() if rng is None else rng
    B,T,C=x.shape; drop=rng.random((B,C))<prob
    return np.broadcast_to(drop[:,None,:], (B,T,C)).copy()

def event_mask(x, ratio=0.2, quantile=0.8, rng=None):
    rng=np.random.default_rng() if rng is None else rng
    grad=np.abs(np.diff(x,axis=1,prepend=x[:,:1]))
    score=np.nan_to_num(grad,nan=0.0)
    thresh=np.quantile(score, quantile, axis=1, keepdims=True)
    cand=score>=thresh
    keep=rng.random(x.shape)<min(1.0,ratio/max(1e-6,1-quantile))
    return cand & keep

def mixed_mask(x, ratio=.35, block_min=2, block_max=12, channel_drop_prob=.15, event_quantile=.8, rng=None):
    rng=np.random.default_rng() if rng is None else rng
    m1=random_point_mask(x, ratio*0.35, rng)
    m2=block_mask(x, ratio*0.30, block_min, block_max, rng)
    m3=channel_mask(x, channel_drop_prob, rng)
    m4=event_mask(x, ratio*0.20, event_quantile, rng)
    return m1|m2|m3|m4

def apply_mask(x, mask, fill=0.0):
    y=np.array(x,copy=True); y[mask]=fill; return y

def torch_random_mask(x, ratio):
    return torch.rand_like(x) < ratio
