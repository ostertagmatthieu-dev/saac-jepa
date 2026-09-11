from __future__ import annotations
import numpy as np
import torch
import torch.nn as nn
try:
    import pywt
except Exception:
    pywt=None

class SSLTransformer(nn.Module):
    def __init__(self,C,A,H,d=256,nhead=8,layers=4):
        super().__init__(); self.C=C; self.H=H; self.inp=nn.Linear(C,d); enc=nn.TransformerEncoderLayer(d,nhead,4*d,batch_first=True,norm_first=True); self.enc=nn.TransformerEncoder(enc,layers); self.recon=nn.Linear(d,C); self.ap=nn.Linear(A,d); self.forecast=nn.Linear(d,C)
    def encode(self,x): return self.enc(self.inp(x))
    def reconstruct(self,x): return self.recon(self.encode(x))
    def predict(self,x,fa):
        z=self.encode(x)[:,-1]; return self.forecast(z[:,None]+self.ap(fa))

def point_mask_torch(x,ratio): return torch.rand_like(x)<ratio

def block_mask_torch(x,ratio,block=8):
    B,T,C=x.shape; m=torch.zeros_like(x,dtype=torch.bool); n=max(1,int(T*ratio/block))
    for _ in range(n):
        starts=torch.randint(0,max(1,T-block+1),(B,C),device=x.device)
        for b in range(B):
            for c in range(C): m[b,starts[b,c]:starts[b,c]+block,c]=True
    return m

def event_mask_torch(x,ratio=.3):
    g=torch.abs(torch.diff(x,dim=1,prepend=x[:,:1])); flat=g.flatten(1); k=max(1,int(flat.shape[1]*ratio)); idx=torch.topk(flat,k,dim=1).indices; m=torch.zeros_like(flat,dtype=torch.bool); m.scatter_(1,idx,True); return m.view_as(x)

def local_patch_mask_torch(x,ratio=.5,patch=4,local_window=3):
    B,T,C=x.shape; m=torch.zeros_like(x,dtype=torch.bool); n=T//patch; npatch=max(1,int(n*ratio))
    for b in range(B):
        centers=torch.randperm(n,device=x.device)[:npatch]
        for q in centers:
            s=int(q)*patch; m[b,s:s+patch,:]=True
    return m

def wavelet_array(x):
    arr=x.detach().cpu().numpy(); out=np.zeros_like(arr)
    if pywt is not None:
        for b in range(arr.shape[0]):
            for c in range(arr.shape[2]):
                coeffs=pywt.wavedec(arr[b,:,c],'db2',mode='periodization')
                a,_=pywt.coeffs_to_array(coeffs); a=a[:arr.shape[1]] if len(a)>=arr.shape[1] else np.pad(a,(0,arr.shape[1]-len(a)))
                out[b,:,c]=a
    else:
        # Dependency-free Haar-like multiscale fallback for smoke/reproducibility.
        # Scientific runs may install PyWavelets for db2 coefficients.
        for b in range(arr.shape[0]):
            for c in range(arr.shape[2]):
                v=arr[b,:,c]; feats=[]; cur=v.copy()
                while len(cur)>=2:
                    if len(cur)%2: cur=np.pad(cur,(0,1),mode='edge')
                    avg=(cur[0::2]+cur[1::2])/np.sqrt(2.0); diff=(cur[0::2]-cur[1::2])/np.sqrt(2.0)
                    feats.extend(diff.tolist()); cur=avg
                feats.extend(cur.tolist()); a=np.asarray(feats,dtype=arr.dtype); a=a[:arr.shape[1]] if len(a)>=arr.shape[1] else np.pad(a,(0,arr.shape[1]-len(a)))
                out[b,:,c]=a
    return torch.as_tensor(out,device=x.device,dtype=x.dtype)

def ssl_loss(model,x,method='mae',ratio=.4):
    method=method.lower()
    base=wavelet_array(x) if method=='mmr_wavelet' else x
    if method in ('mae','patchformer_style','mmr_wavelet'): m=block_mask_torch(base,ratio,block=4 if method!='patchformer_style' else 8)
    elif method=='emit_style': m=event_mask_torch(base,ratio)
    elif method=='lomar_ts_style': m=local_patch_mask_torch(base,ratio,patch=4)
    elif method=='simmtm_style':
        losses=[]
        for _ in range(4):
            m=point_mask_torch(base,ratio); xin=base.masked_fill(m,0); r=model.reconstruct(xin); losses.append(((r-base).pow(2)*m.float()).sum()/(m.sum()+1e-6))
        return torch.stack(losses).mean()
    else: m=point_mask_torch(base,ratio)
    xin=base.masked_fill(m,0); r=model.reconstruct(xin); return ((r-base).pow(2)*m.float()).sum()/(m.sum()+1e-6)
