from __future__ import annotations
import numpy as np

def corrupt(x,kind,severity=.2,seed=0):
    rng=np.random.default_rng(seed); y=np.array(x,copy=True); B,T,C=y.shape
    if kind=='random_mask': y[rng.random(y.shape)<severity]=np.nan
    elif kind=='gaussian': y += rng.normal(0,severity,size=y.shape)
    elif kind=='spike':
        m=rng.random(y.shape)<severity*.05; y[m]+=rng.normal(0,5*severity+1,size=m.sum())
    elif kind=='drift':
        drift=np.linspace(0,severity,T)[None,:,None]*rng.normal(0,1,(B,1,C)); y+=drift
    elif kind=='step':
        for b in range(B):
            t=int(rng.integers(max(1,T//4),max(2,3*T//4))); y[b,t:]+=rng.normal(0,severity,(1,C))
    elif kind=='missing_block':
        L=max(1,int(T*severity));
        for b in range(B):
            c=int(rng.integers(C)); s=int(rng.integers(max(1,T-L+1))); y[b,s:s+L,c]=np.nan
    elif kind=='sensor_bias': y += rng.normal(0,severity,(B,1,C))
    elif kind=='mixed':
        for k in ['random_mask','gaussian','spike','drift','missing_block']: y=corrupt(y,k,severity/2,seed+hash(k)%1000)
    else: raise ValueError(kind)
    return y
