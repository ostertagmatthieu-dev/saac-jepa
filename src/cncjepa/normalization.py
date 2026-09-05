from __future__ import annotations
import numpy as np

class Normalizer:
    def __init__(self, mode='zscore', eps=1e-6, rel_floor=0.05):
        # rel_floor: robust mode only. IQR/1.349 degenerates on spike-dominated channels whose
        # bulk is constant (e.g. an axis idling at ~0 power >75% of the time): the IQR sees the
        # informative spikes as outliers and collapses, amplifying the channel by orders of
        # magnitude. The absolute eps clamp cannot catch a *relatively* tiny-but-finite IQR, so
        # the scale is floored at rel_floor*std per channel. rel_floor=0 reproduces the legacy
        # (unfloored) behaviour, which eval-only re-runs of legacy checkpoints require.
        self.mode=mode; self.eps=eps; self.rel_floor=float(rel_floor); self.center=None; self.scale=None
    def fit(self, x):
        x=np.asarray(x, dtype=np.float64)
        if self.mode in ('zscore','source_zscore','target_support'):
            self.center=np.nanmean(x, axis=0)
            self.scale=np.nanstd(x, axis=0)
        elif self.mode in ('robust','source_robust'):
            self.center=np.nanmedian(x, axis=0)
            q1=np.nanpercentile(x,25,axis=0); q3=np.nanpercentile(x,75,axis=0)
            self.scale=(q3-q1)/1.349
            if self.rel_floor>0:
                floor=self.rel_floor*np.nanstd(x, axis=0)
                self.scale=np.where(np.isfinite(floor), np.maximum(self.scale,floor), self.scale)
        elif self.mode=='none':
            self.center=np.zeros(x.shape[-1]); self.scale=np.ones(x.shape[-1])
        else:
            raise ValueError(f'Unknown normalization mode: {self.mode}')
        self.scale=np.where(np.isfinite(self.scale) & (np.abs(self.scale)>self.eps), self.scale, 1.0)
        self.center=np.where(np.isfinite(self.center), self.center, 0.0)
        return self
    def transform(self,x): return (np.asarray(x)-self.center)/(self.scale+self.eps)
    def inverse(self,x): return np.asarray(x)*(self.scale+self.eps)+self.center
    def affine_to(self,ref):
        """Per-channel affine (gain, offset) mapping THIS normalizer's transformed space into
        `ref`'s: x_ref = gain*x_self + offset. Exact, because transform/inverse are per-channel
        affine maps; two identically fitted normalizers give gain=1, offset=0 bitwise, so
        applying the map to a candidate already in the reference space is the identity."""
        gain=(self.scale+self.eps)/(ref.scale+ref.eps)
        offset=(self.center-ref.center)/(ref.scale+ref.eps)
        return gain, offset
    def state_dict(self): return {'mode':self.mode,'eps':self.eps,'rel_floor':self.rel_floor,'center':self.center.tolist(),'scale':self.scale.tolist()}
    @classmethod
    def from_state_dict(cls,d):
        o=cls(d['mode'],d.get('eps',1e-6),d.get('rel_floor',0.0)); o.center=np.asarray(d['center']); o.scale=np.asarray(d['scale']); return o

class AdaptiveEMANormalizer:
    def __init__(self, center, scale, alpha=0.01, eps=1e-6):
        self.center=np.array(center,dtype=float); self.scale=np.array(scale,dtype=float); self.alpha=alpha; self.eps=eps
    def update(self,x):
        x=np.asarray(x,float)
        m=np.nanmean(x,axis=0); s=np.nanstd(x,axis=0)
        ok=np.isfinite(m); self.center[ok]=(1-self.alpha)*self.center[ok]+self.alpha*m[ok]
        ok=np.isfinite(s)&(s>self.eps); self.scale[ok]=(1-self.alpha)*self.scale[ok]+self.alpha*s[ok]
    def transform(self,x): return (np.asarray(x)-self.center)/(self.scale+self.eps)
