from __future__ import annotations
import numpy as np
from scipy.stats import wilcoxon, kendalltau

def _flat(a): return np.asarray(a,float).reshape(-1)
def rmse(y,p):
    d=_flat(y)-_flat(p); return float(np.sqrt(np.nanmean(d*d)))
def mae(y,p): return float(np.nanmean(np.abs(_flat(y)-_flat(p))))
def r2(y,p):
    y=_flat(y); p=_flat(p); ss=np.nansum((y-p)**2); den=np.nansum((y-np.nanmean(y))**2); return float(1-ss/(den+1e-12))
def nrmse(y,p):
    y=np.asarray(y,float); return rmse(y,p)/(float(np.nanstd(y))+1e-12)
def per_channel_metrics(y,p,names=None):
    y=np.asarray(y); p=np.asarray(p); C=y.shape[-1]; names=names or [f'c{i}' for i in range(C)]
    return {names[c]:{'rmse':rmse(y[...,c],p[...,c]),'mae':mae(y[...,c],p[...,c]),'r2':r2(y[...,c],p[...,c])} for c in range(C)}
def per_horizon_metrics(y,p):
    H=y.shape[-2]; return {str(h+1):{'rmse':rmse(y[...,h,:],p[...,h,:]),'mae':mae(y[...,h,:],p[...,h,:]),'r2':r2(y[...,h,:],p[...,h,:])} for h in range(H)}
def paired_exact_signflip(diff):
    d=np.asarray(diff,float); n=len(d)
    obs=abs(np.mean(d)); vals=[]
    for mask in range(1<<n):
        s=np.array([1 if (mask>>i)&1 else -1 for i in range(n)])
        vals.append(abs(np.mean(d*s)))
    return float((np.sum(np.asarray(vals)>=obs)+1)/(len(vals)+1))
def paired_bootstrap_ci(a,b,n_boot=20000,seed=0):
    a=np.asarray(a,float); b=np.asarray(b,float); rng=np.random.default_rng(seed); n=len(a); ds=[]
    for _ in range(n_boot):
        idx=rng.integers(0,n,n); ds.append(np.mean(a[idx]-b[idx]))
    return tuple(np.quantile(ds,[.025,.5,.975]).tolist())
def paired_stats(a,b):
    a=np.asarray(a,float); b=np.asarray(b,float); d=a-b
    try: w=wilcoxon(d,zero_method='wilcox',alternative='two-sided').pvalue
    except Exception: w=np.nan
    return {'mean_diff':float(np.mean(d)),'median_diff':float(np.median(d)),'wilcoxon_p':float(w) if np.isfinite(w) else None,'exact_signflip_p':paired_exact_signflip(d),'bootstrap_95':paired_bootstrap_ci(a,b)}
def kendall(y,p):
    r=kendalltau(_flat(y),_flat(p)); return {'tau':float(r.statistic),'p':float(r.pvalue)}
