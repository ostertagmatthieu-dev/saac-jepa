from __future__ import annotations
import copy, math
import torch
import torch.nn as nn
import torch.nn.functional as F

class FlexibleSensorEncoder(nn.Module):
    """Order-aware-by-ID but subset-flexible encoder for a fixed global sensor vocabulary.
    Missing/absent sensors are masked, so DS03 may expose only 10/17 known channels.
    """
    def __init__(self,n_sensors,action_dim,d_model=256,nhead=8,layers=4,ff=1024,dropout=.1,layernorm='pre',max_len=512):
        super().__init__(); self.n_sensors=n_sensors; self.d_model=d_model
        self.value_proj=nn.Sequential(nn.Linear(3,d_model),nn.GELU(),nn.Linear(d_model,d_model))
        self.channel_emb=nn.Parameter(torch.randn(n_sensors,d_model)*.02)
        sensor_layer=nn.TransformerEncoderLayer(d_model,nhead,ff,dropout,batch_first=True,norm_first=(layernorm=='pre'))
        self.sensor_encoder=nn.TransformerEncoder(sensor_layer,num_layers=2)
        self.action_proj=nn.Linear(action_dim,d_model)
        self.time_emb=nn.Parameter(torch.randn(max_len,d_model)*.01)
        time_layer=nn.TransformerEncoderLayer(d_model,nhead,ff,dropout,batch_first=True,norm_first=(layernorm=='pre'))
        self.temporal=nn.TransformerEncoder(time_layer,num_layers=layers)
        self.out_norm=nn.LayerNorm(d_model) if layernorm!='none' else nn.Identity()
    def forward(self,x,present=None,schema=None,actions=None):
        B,T,C=x.shape; assert C==self.n_sensors
        if present is None: present=torch.isfinite(x).float()
        if schema is None: schema=torch.ones(B,C,device=x.device,dtype=x.dtype)
        x=torch.nan_to_num(x)
        sch=schema[:,None,:].expand(B,T,C)
        feat=torch.stack([x,present,sch],dim=-1) # B,T,C,3
        tok=self.value_proj(feat)+self.channel_emb[None,None,:,:]
        tok=tok.reshape(B*T,C,self.d_model)
        valid=(present*sch).reshape(B*T,C)>0
        # avoid all-masked rows
        no_valid=~valid.any(dim=1)
        if no_valid.any(): valid[no_valid,0]=True
        tok=self.sensor_encoder(tok,src_key_padding_mask=~valid)
        w=valid.float().unsqueeze(-1)
        time_tok=(tok*w).sum(1)/(w.sum(1)+1e-6)
        time_tok=time_tok.reshape(B,T,self.d_model)
        if actions is not None: time_tok=time_tok+self.action_proj(actions)
        time_tok=time_tok+self.time_emb[:T][None]
        z=self.temporal(time_tok)
        return self.out_norm(z)

class ActionConditionedPredictor(nn.Module):
    def __init__(self,action_dim,d_model=256,nhead=8,layers=4,ff=1024,dropout=.1,max_h=64,mode='token'):
        super().__init__(); self.mode=mode; self.d_model=d_model
        self.action_proj=nn.Linear(action_dim,d_model)
        self.horizon_emb=nn.Parameter(torch.randn(max_h,d_model)*.02)
        self.ctx_proj=nn.Linear(d_model,d_model)
        if mode=='film': self.film=nn.Linear(action_dim,2*d_model)
        layer=nn.TransformerEncoderLayer(d_model,nhead,ff,dropout,batch_first=True,norm_first=True)
        self.net=nn.TransformerEncoder(layer,num_layers=layers)
        self.norm=nn.LayerNorm(d_model)
    def forward(self,z_context,future_actions):
        B,H,A=future_actions.shape
        ctx=self.ctx_proj(z_context)[:,None,:].expand(B,H,self.d_model)
        if self.mode=='token': x=ctx+self.action_proj(future_actions)+self.horizon_emb[:H][None]
        elif self.mode=='film':
            gb=self.film(future_actions); g,b=gb.chunk(2,-1); x=ctx*(1+torch.tanh(g))+b+self.horizon_emb[:H][None]
        elif self.mode=='cross_attn':
            # lightweight cross-conditioning: action token plus globally projected context
            x=self.action_proj(future_actions)+self.horizon_emb[:H][None]+ctx
        else: raise ValueError(self.mode)
        mask=torch.triu(torch.ones(H,H,device=x.device,dtype=torch.bool),diagonal=1)
        return self.norm(self.net(x,mask=mask))

class ActionConditionedJEPA(nn.Module):
    def __init__(self,n_sensors,action_dim,cfg):
        super().__init__(); m=cfg['model']; j=cfg['jepa']; d=m['d_model']
        self.n_sensors=n_sensors; self.action_dim=action_dim; self.ema=float(j['ema']); self.cfg=cfg
        self.context_encoder=FlexibleSensorEncoder(n_sensors,action_dim,d,m['nhead'],m['encoder_layers'],m['dim_feedforward'],m['dropout'],m.get('layernorm','pre'))
        self.target_encoder=copy.deepcopy(self.context_encoder)
        for p in self.target_encoder.parameters(): p.requires_grad=False
        self.predictor=ActionConditionedPredictor(action_dim,d,m['nhead'],m['predictor_layers'],m['dim_feedforward'],m['dropout'],max_h=128,mode=m.get('action_injection','token'))
        self.physical_mu=nn.Linear(d,n_sensors)
        self.physical_logvar=nn.Linear(d,n_sensors)
        self.action_recovery=nn.Sequential(nn.Linear(2*d,d),nn.GELU(),nn.Linear(d,action_dim))
    @torch.no_grad()
    def update_target(self):
        for pt,po in zip(self.target_encoder.parameters(),self.context_encoder.parameters()): pt.data.mul_(self.ema).add_(po.data,alpha=1-self.ema)
    def encode_context(self,x,present,schema,past_actions):
        zseq=self.context_encoder(x,present,schema,past_actions)
        return zseq[:,-1],zseq
    @torch.no_grad()
    def encode_target(self,y,schema,target_present=None):
        B,H,C=y.shape; present=(torch.isfinite(y).float() if target_present is None else target_present.float()); zero_actions=torch.zeros(B,H,self.action_dim,device=y.device,dtype=y.dtype)
        z=self.target_encoder(y,present,schema,zero_actions)
        return z.detach()
    def forward(self,x,past_actions,future_actions,present=None,schema=None,y=None,target_present=None):
        B,T,C=x.shape
        if present is None: present=torch.isfinite(x).float()
        if schema is None: schema=torch.ones(B,C,device=x.device,dtype=x.dtype)
        zc,zseq=self.encode_context(x,present,schema,past_actions)
        zp=self.predictor(zc,future_actions)
        mu=self.physical_mu(zp); logvar=self.physical_logvar(zp)
        # z_context_pool: per-window pooled encoder output, the 'context' latent for VICReg placement.
        out={'z_context':zc,'z_context_seq':zseq,'z_context_pool':zseq.mean(1),'z_pred':zp,'mu':mu,'logvar':logvar}
        if y is not None:
            zt=self.encode_target(y,schema,target_present); out['z_target']=zt
            act_hat=self.action_recovery(torch.cat([zc[:,None,:].expand_as(zt),zt],dim=-1))
            out['action_hat']=act_hat
        return out

VICREG_PLACEMENTS=('predictor','context','target','context_target')

def vicreg_latents(lat,placement='predictor'):
    """Select which latents the anti-collapse term acts on.

    `lat` maps 'predictor'/'context'/'target' -> [B,H,d] tensors (already given the same
    latent-LayerNorm treatment as the JEPA latent loss). 'target' latents are detached by
    construction (EMA encoder runs under no_grad), so variance/covariance on them is a pure
    diagnostic-plus-regulariser on the target branch and carries no gradient.
    Default 'predictor' reproduces the pre-P3-FIX behaviour exactly.
    """
    if placement not in VICREG_PLACEMENTS: raise ValueError(f'vicreg_placement must be one of {VICREG_PLACEMENTS}, got {placement}')
    keys=('context','target') if placement=='context_target' else (placement,)
    return [lat[k] for k in keys if lat.get(k) is not None]

class SchemaAdaptiveJEPA(ActionConditionedJEPA):
    """JEPA plus utilities for random schema views. Training code applies consistency loss."""
    def schema_view(self,x,present,schema,keep_prob=.7):
        B,C=schema.shape; keep=(torch.rand(B,C,device=x.device)<keep_prob).float()*schema
        # ensure at least one sensor
        bad=keep.sum(1)==0
        if bad.any(): keep[bad,0]=1
        xp=x*keep[:,None,:]; pp=present*keep[:,None,:]
        return xp,pp,keep
