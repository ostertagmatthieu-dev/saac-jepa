from __future__ import annotations
import torch
import torch.nn as nn
import torch.nn.functional as F

class PersistenceForecaster(nn.Module):
    """No-learn baseline: predict the last observed value of each channel for every horizon.
    Mandatory reference -- a forecaster that does not beat this has not learned dynamics.
    Uses `present` to pick the last VALID sample per channel so masked/missing tails do not
    turn into a prediction of 0 (which would flatter the baseline's competitors)."""
    def __init__(self,C,H): super().__init__(); self.C=C; self.H=H
    def forward(self,x,pa,fa,present=None,**kw):
        B,T,C=x.shape
        if present is None: present=torch.isfinite(x).float()
        idx=(present>0).float()*torch.arange(1,T+1,device=x.device,dtype=x.dtype)[None,:,None]
        last=idx.argmax(1,keepdim=True).clamp(min=0)                    # B,1,C
        val=torch.gather(torch.nan_to_num(x),1,last)                     # B,1,C
        val=torch.where(idx.amax(1,keepdim=True)>0,val,torch.zeros_like(val))
        return val.expand(B,self.H,C)

class LinearDriftForecaster(nn.Module):
    """No-learn baseline: per-channel least-squares linear trend fit on the context window,
    extrapolated to each horizon offset. Catches 'the model only learned to follow the ramp'."""
    def __init__(self,C,H,horizons=None): super().__init__(); self.C=C; self.H=H; self.horizons=list(horizons or range(1,H+1))
    def forward(self,x,pa,fa,present=None,**kw):
        B,T,C=x.shape; xx=torch.nan_to_num(x)
        w=(torch.isfinite(x).float() if present is None else present.float())
        t=torch.arange(T,device=x.device,dtype=xx.dtype)[None,:,None].expand(B,T,C)
        sw=w.sum(1).clamp(min=1e-6); tb=(w*t).sum(1)/sw; xb=(w*xx).sum(1)/sw
        dt=t-tb[:,None,:]; num=(w*dt*(xx-xb[:,None,:])).sum(1); den=(w*dt*dt).sum(1)
        slope=torch.where(den>1e-6,num/den.clamp(min=1e-6),torch.zeros_like(num))
        slope=torch.where(sw>=2,slope,torch.zeros_like(slope))
        h=torch.tensor([float(T-1+k)  for k in self.horizons],device=x.device,dtype=xx.dtype)[None,:,None]
        return xb[:,None,:]+slope[:,None,:]*(h-tb[:,None,:])

class MLPForecaster(nn.Module):
    def __init__(self,C,A,T,H,d=256):
        super().__init__(); self.H=H; self.C=C
        self.net=nn.Sequential(nn.Linear(T*(C+A)+H*A,d),nn.GELU(),nn.Linear(d,d),nn.GELU(),nn.Linear(d,H*C))
    def forward(self,x,pa,fa,**kw): return self.net(torch.cat([x.flatten(1),pa.flatten(1),fa.flatten(1)],1)).view(x.size(0),self.H,self.C)

class RNNForecaster(nn.Module):
    def __init__(self,C,A,H,d=256,kind='gru',layers=2):
        super().__init__(); self.H=H; self.C=C
        cls=nn.GRU if kind=='gru' else nn.LSTM
        self.rnn=cls(C+A,d,layers,batch_first=True,dropout=.1 if layers>1 else 0)
        self.action=nn.Linear(A,d); self.head=nn.Linear(d,C)
    def forward(self,x,pa,fa,**kw):
        _,h=self.rnn(torch.cat([x,pa],-1)); h=h[0][-1] if isinstance(h,tuple) else h[-1]
        z=h[:,None,:]+self.action(fa); return self.head(torch.tanh(z))

class TCNForecaster(nn.Module):
    def __init__(self,C,A,H,d=256,layers=5):
        super().__init__(); self.C=C; self.H=H
        mods=[]; inp=C+A
        for i in range(layers): mods += [nn.Conv1d(inp,d,3,padding=2**i,dilation=2**i),nn.GELU()]; inp=d
        self.net=nn.Sequential(*mods); self.ap=nn.Linear(A,d); self.head=nn.Linear(d,C)
    def forward(self,x,pa,fa,**kw):
        z=torch.cat([x,pa],-1).transpose(1,2)
        for layer in self.net:
            z=layer(z)
            if isinstance(layer,nn.Conv1d): z=z[...,:x.size(1)]
        ctx=z[:,:,-1]; return self.head(ctx[:,None,:]+self.ap(fa))

class TransformerForecaster(nn.Module):
    def __init__(self,C,A,H,d=256,nhead=8,layers=4):
        super().__init__(); self.C=C; self.H=H
        self.inp=nn.Linear(C+A,d); enc=nn.TransformerEncoderLayer(d,nhead,4*d,batch_first=True,norm_first=True)
        self.enc=nn.TransformerEncoder(enc,layers); self.ap=nn.Linear(A,d); self.head=nn.Linear(d,C)
    def forward(self,x,pa,fa,**kw):
        z=self.enc(self.inp(torch.cat([x,pa],-1)))[:,-1]; return self.head(z[:,None]+self.ap(fa))

class DLinearForecaster(nn.Module):
    def __init__(self,C,A,T,H):
        super().__init__(); self.C=C; self.H=H; self.lin=nn.Linear(T,H); self.act=nn.Linear(A,C)
    def forward(self,x,pa,fa,**kw): return self.lin(x.transpose(1,2)).transpose(1,2)+self.act(fa)

class TSMixerForecaster(nn.Module):
    def __init__(self,C,A,T,H,d=256,blocks=4):
        super().__init__(); self.C=C; self.H=H; self.T=T
        self.inp=nn.Linear(C+A,d); self.blocks=nn.ModuleList([nn.Sequential(nn.LayerNorm(d),nn.Linear(d,2*d),nn.GELU(),nn.Linear(2*d,d)) for _ in range(blocks)])
        self.time=nn.Linear(T,H); self.head=nn.Linear(d,C); self.act=nn.Linear(A,d)
    def forward(self,x,pa,fa,**kw):
        z=self.inp(torch.cat([x,pa],-1))
        for b in self.blocks: z=z+b(z)
        z=self.time(z.transpose(1,2)).transpose(1,2)+self.act(fa); return self.head(z)

class PatchTSTLike(nn.Module):
    def __init__(self,C,A,T,H,d=256,nhead=8,layers=4,patch=4):
        super().__init__(); self.C=C; self.H=H; self.patch=patch
        self.proj=nn.Linear(patch*C+patch*A,d); enc=nn.TransformerEncoderLayer(d,nhead,4*d,batch_first=True,norm_first=True); self.enc=nn.TransformerEncoder(enc,layers)
        self.ap=nn.Linear(A,d); self.head=nn.Linear(d,C)
    def forward(self,x,pa,fa,**kw):
        B,T,C=x.shape; P=self.patch; n=T//P; x=x[:,-n*P:].reshape(B,n,P*C); a=pa[:,-n*P:].reshape(B,n,P*pa.size(-1)); z=self.enc(self.proj(torch.cat([x,a],-1)))[:,-1]
        return self.head(z[:,None]+self.ap(fa))

class ITransformerLike(nn.Module):
    def __init__(self,C,A,T,H,d=256,nhead=8,layers=4):
        super().__init__(); self.C=C; self.H=H; self.T=T
        self.varproj=nn.Linear(T,d); enc=nn.TransformerEncoderLayer(d,nhead,4*d,batch_first=True,norm_first=True); self.enc=nn.TransformerEncoder(enc,layers)
        self.out=nn.Linear(d,H); self.action=nn.Linear(A,C)
    def forward(self,x,pa,fa,**kw):
        z=self.enc(self.varproj(x.transpose(1,2))); y=self.out(z).transpose(1,2); return y+self.action(fa)

class RSSMForecaster(nn.Module):
    def __init__(self,C,A,H,d=256,stoch=64):
        super().__init__(); self.C=C; self.H=H; self.enc=nn.Linear(C,d); self.gru=nn.GRUCell(stoch+A,d); self.prior=nn.Linear(d,2*stoch); self.post=nn.Linear(d+C,2*stoch); self.dec=nn.Linear(d+stoch,C)
    def forward(self,x,pa,fa,**kw):
        B=x.size(0); h=torch.zeros(B,self.gru.hidden_size,device=x.device); z=torch.zeros(B,self.prior.out_features//2,device=x.device)
        for t in range(x.size(1)):
            h=self.gru(torch.cat([z,pa[:,t]],-1),h); stats=self.post(torch.cat([h,x[:,t]],-1)); mu,lv=stats.chunk(2,-1); z=mu
        ys=[]
        for t in range(fa.size(1)):
            h=self.gru(torch.cat([z,fa[:,t]],-1),h); mu,lv=self.prior(h).chunk(2,-1); z=mu; ys.append(self.dec(torch.cat([h,z],-1)))
        return torch.stack(ys,1)

class MaskedReconstructionModel(nn.Module):
    def __init__(self,C,d=256,nhead=8,layers=4):
        super().__init__(); self.inp=nn.Linear(C,d); enc=nn.TransformerEncoderLayer(d,nhead,4*d,batch_first=True,norm_first=True); self.enc=nn.TransformerEncoder(enc,layers); self.head=nn.Linear(d,C)
    def forward(self,x): return self.head(self.enc(self.inp(x)))

MODEL_REGISTRY={
 'persistence':PersistenceForecaster,'drift':LinearDriftForecaster,
 'mlp':MLPForecaster,'gru':RNNForecaster,'lstm':RNNForecaster,'tcn':TCNForecaster,'transformer':TransformerForecaster,'dlinear':DLinearForecaster,
 'tsmixer':TSMixerForecaster,'patchtst':PatchTSTLike,'itransformer':ITransformerLike,'rssm':RSSMForecaster
}
