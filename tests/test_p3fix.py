"""P3-FIX regression tests. Plain python, no pytest:  python tests/test_p3fix.py

Covers the scientific invariants the taskbook marks non-negotiable:
 (a) split leakage        - sessions disjoint across source_train/val/test
 (b) mask determinism     - seeded val masks reproduce; train masks vary across epochs
 (c) EMA                  - target moves toward online with the right momentum; schedule ramps
 (d) target no-grad       - z_target detached, target encoder never accumulates gradient
 (e) metric aggregation   - per_channel/per_horizon match hand-computed values
 (f) checkpoint audit     - weights_changed / empty unexpected; body-only load reinits the head
"""
from pathlib import Path
import sys, copy, tempfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import numpy as np, torch

from cncjepa.config import load_config
from cncjepa.data import WindowDataset, load_table, resample_dataframe, deterministic_group_split
from cncjepa.pipeline import prepare, loaders_from_ds
from cncjepa.factory import build_jepa, build_forecaster
from cncjepa.checkpoint import load_jepa_checkpoint, load_jepa_body_fresh_head
from cncjepa.metrics import per_channel_metrics, per_horizon_metrics, rmse
from cncjepa.trainers import jepa_step, ema_at, latent_health, evaluate_jepa_ssl
from cncjepa.utils import set_seed, atomic_torch_save
from cncjepa.normalization import Normalizer

FAIL=[]
def check(name,cond,detail=''):
    print(('  PASS ' if cond else '  FAIL ')+name+(f'  [{detail}]' if detail else ''))
    if not cond: FAIL.append(name)

CFG=load_config(ROOT/'configs/smoke.yaml')
if not Path(ROOT/CFG['paths']['data']).exists():
    import subprocess; subprocess.run([sys.executable,str(ROOT/'examples/make_synthetic_ds01_ds03.py')],cwd=ROOT,check=True)
CFG['paths']['data']=str(ROOT/CFG['paths']['data'])
CFG['train']['num_workers']=0


def build_split():
    df=load_table(CFG['paths']['data']); df=resample_dataframe(df,CFG); return deterministic_group_split(df,CFG)


# ------------------------------------------------------------------ (a) leakage
print('(a) split leakage')
sp=build_split(); s=CFG['schema']
sess={k:set(sp[k][s['session']].astype(str)) for k in ('source_train','source_val','source_test')}
check('train/val sessions disjoint', not (sess['source_train']&sess['source_val']), f"overlap={sorted(sess['source_train']&sess['source_val'])}")
check('train/test sessions disjoint', not (sess['source_train']&sess['source_test']))
check('val/test sessions disjoint', not (sess['source_val']&sess['source_test']))
check('all splits non-empty', all(len(v)>0 for v in sess.values()), str({k:len(v) for k,v in sess.items()}))
mach=set(sp['target_all'][s['machine']].astype(str))
check('target machine never in source splits', mach=={str(s['target_machine'])} and not (mach & set(sp['source_train'][s['machine']].astype(str))))


# ------------------------------------------------------------- (b) mask determinism
print('(b) masking determinism')
tr=sp['source_train']; va=sp['source_val']
sn=Normalizer('zscore').fit(tr[s['sensors']].to_numpy(float)); an=Normalizer('zscore').fit(tr[s['actions']].to_numpy(float))
mk=CFG['masking']
def val_ds(seed): return WindowDataset(va,CFG,sn,an,training=False,mask_cfg=mk,mask_rng_seed=seed,force_mask=True)
d1,d2=val_ds(1234),val_ds(1234); d3=val_ds(999)
idxs=[0,1,5,min(11,len(d1)-1)]
same=all(torch.equal(d1[i]['aug_mask'],d2[i]['aug_mask']) for i in idxs)
check('same mask_rng_seed -> identical val masks', same)
check('val masks are actually non-trivial', float(d1[0]['aug_mask'].sum())>0, f"n_masked={float(d1[0]['aug_mask'].sum())}")
check('re-reading the same index is stable', torch.equal(d1[idxs[-1]]['aug_mask'],d1[idxs[-1]]['aug_mask']))
check('different mask_rng_seed -> different val masks', any(not torch.equal(d1[i]['aug_mask'],d3[i]['aug_mask']) for i in idxs))
check('val masks differ across indices', not torch.equal(d1[idxs[0]]['aug_mask'],d1[idxs[1]]['aug_mask']))
# train datasets stay stochastic: two "epochs" over the same index must differ
set_seed(0)
tds=WindowDataset(tr,CFG,sn,an,training=True,mask_cfg=mk,mask_rng_seed=None)
ep1=[tds[i]['aug_mask'].clone() for i in idxs]; ep2=[tds[i]['aug_mask'].clone() for i in idxs]
check('train masks differ across epochs', any(not torch.equal(x,y) for x,y in zip(ep1,ep2)))
# ...but a re-seeded run reproduces the same stream
set_seed(0); tds2=WindowDataset(tr,CFG,sn,an,training=True,mask_cfg=mk,mask_rng_seed=None)
rep=[tds2[i]['aug_mask'] for i in idxs]+[tds2[i]['aug_mask'] for i in idxs]
check('train mask stream reproducible under set_seed', all(torch.equal(a,b) for a,b in zip(ep1+ep2,rep)))
# default (no mask_rng_seed, training=False) leaves validation clean -> backward compatible
check('training=False without force_mask -> no mask', float(WindowDataset(va,CFG,sn,an,training=False,mask_cfg=mk,mask_rng_seed=7)[0]['aug_mask'].sum())==0.)


# ------------------------------------------------------------------- (c) EMA
print('(c) EMA')
c=copy.deepcopy(CFG); c['jepa']['ema']=0.9
m=build_jepa(c,True)
online=dict(m.context_encoder.named_parameters()); target=dict(m.target_encoder.named_parameters())
k=sorted(online)[0]
with torch.no_grad():
    for p in m.context_encoder.parameters(): p.add_(torch.randn_like(p)*0.1)
o0=online[k].detach().clone(); t0=target[k].detach().clone()
m.ema=0.9; m.update_target()
expect=t0*0.9+o0*0.1
check('update_target applies m*t + (1-m)*o', torch.allclose(target[k].detach(),expect,atol=1e-6),
      f'max_err={float((target[k].detach()-expect).abs().max()):.2e}')
check('target moved toward online', float((target[k].detach()-o0).norm())<float((t0-o0).norm()))
sch=copy.deepcopy(CFG); sch['jepa']['ema_schedule']={'start':0.99,'end':0.9999,'kind':'linear'}
e0,e5,e9=ema_at(sch,0,10),ema_at(sch,5,10),ema_at(sch,9,10)
check('scheduled EMA starts at start', abs(e0-0.99)<1e-9)
check('scheduled EMA ends at end', abs(e9-0.9999)<1e-9)
check('scheduled EMA is monotone across epochs', e0<e5<e9, f'{e0:.5f}<{e5:.5f}<{e9:.5f}')
check('cosine schedule also spans start..end', abs(ema_at({'jepa':{'ema_schedule':{'start':.99,'end':.9999,'kind':'cosine'}}},0,10)-0.99)<1e-9)
check('no schedule -> fixed cfg ema', ema_at(c,3,10)==0.9)


# --------------------------------------------------------------- (d) target no-grad
print('(d) target encoder no-grad')
c=copy.deepcopy(CFG); c['jepa']['schema_consistency_weight']=0.1
m=build_jepa(c,True); m.train()
B,T,C,A,H=4,c['protocol']['context_len'],len(s['sensors']),len(s['actions']),len(c['protocol']['horizons'])
b={'x':torch.randn(B,T,C),'past_actions':torch.randn(B,T,A),'future_actions':torch.randn(B,H,A),'y':torch.randn(B,H,C),
   'present':torch.ones(B,T,C),'schema':torch.ones(B,C),'target_present':torch.ones(B,H,C)}
check('target encoder params have requires_grad=False', all(not p.requires_grad for p in m.target_encoder.parameters()))
out=m(b['x'],b['past_actions'],b['future_actions'],b['present'],b['schema'],b['y'],b['target_present'])
check('z_target.requires_grad is False', not out['z_target'].requires_grad)
loss,parts,_=jepa_step(m,b,c,train=True,ssl_mode=True)
loss.backward()
check('no grad accumulated on target encoder', all(p.grad is None for p in m.target_encoder.parameters()))
check('context encoder did receive grad', any(p.grad is not None and float(p.grad.abs().sum())>0 for p in m.context_encoder.parameters()))
check('ssl_mode: physical head receives NO grad', all(p.grad is None for p in list(m.physical_mu.parameters())+list(m.physical_logvar.parameters())),
      'physical_weight forced to 0 -> mu is out of the graph')
check('ssl_mode: physical loss term is exactly 0', float(parts['physical'])==0.)
check('ssl_mode: schema consistency is active and latent-based', float(parts['schema_cons'])>0.)
# supervised mode: head IS trained
m2=build_jepa(c,True); m2.train(); c2=copy.deepcopy(c); c2['jepa']['physical_weight']=1.0
l2,p2,_=jepa_step(m2,b,c2,train=True,ssl_mode=False); l2.backward()
check('supervised mode: physical head receives grad', any(p.grad is not None and float(p.grad.abs().sum())>0 for p in m2.physical_mu.parameters()))
check('supervised mode: physical loss term is non-zero', float(p2['physical'])!=0.)
# vicreg placement stays backward compatible and accepts all documented values
for pl in ('predictor','context','target','context_target'):
    cc=copy.deepcopy(c); cc['jepa']['vicreg_placement']=pl
    lv,pv,_=jepa_step(build_jepa(cc,True),b,cc,train=False,ssl_mode=True)
    check(f'vicreg_placement={pl} runs and is finite', bool(torch.isfinite(lv)) and bool(torch.isfinite(pv['vicreg'])))


# ------------------------------------------------------- (e) metric aggregation
print('(e) metric aggregation')
# hand-built [N=2, H=2, C=2]; errors chosen so every cell is checkable by hand
y=np.array([[[0.,0.],[0.,0.]],[[0.,0.],[0.,0.]]])
p=np.array([[[1.,2.],[3.,4.]],[[1.,2.],[3.,4.]]])
pc=per_channel_metrics(y,p); ph=per_horizon_metrics(y,p)
# channel 0 errors {1,3,1,3} -> rmse sqrt((1+9+1+9)/4)=sqrt(5); mae 2
check('per_channel c0 rmse', abs(pc['c0']['rmse']-np.sqrt(5.))<1e-12, f"{pc['c0']['rmse']}")
check('per_channel c0 mae', abs(pc['c0']['mae']-2.)<1e-12)
# channel 1 errors {2,4,2,4} -> rmse sqrt((4+16+4+16)/4)=sqrt(10); mae 3
check('per_channel c1 rmse', abs(pc['c1']['rmse']-np.sqrt(10.))<1e-12, f"{pc['c1']['rmse']}")
check('per_channel c1 mae', abs(pc['c1']['mae']-3.)<1e-12)
# horizon 1 errors {1,2,1,2} -> rmse sqrt(2.5); horizon 2 errors {3,4,3,4} -> rmse sqrt(12.5)
check('per_horizon h1 rmse', abs(ph['1']['rmse']-np.sqrt(2.5))<1e-12, f"{ph['1']['rmse']}")
check('per_horizon h2 rmse', abs(ph['2']['rmse']-np.sqrt(12.5))<1e-12, f"{ph['2']['rmse']}")
check('global rmse == sqrt(mean of all squared errors)', abs(rmse(y,p)-np.sqrt((1+4+9+16)*2/8.))<1e-12)
check('per_horizon key count == H', len(ph)==2 and len(pc)==2)
# NaN (masked) cells must be ignored, not counted as zero error
ym=y.copy(); ym[1]=np.nan; pm=p.copy(); pm[1]=np.nan
check('masked cells excluded from rmse', abs(per_channel_metrics(ym,pm)['c0']['rmse']-np.sqrt(5.))<1e-12)
# latent health on constructed latents
zc=np.zeros((256,8)); zc[:,0]=np.random.default_rng(0).normal(size=256)   # rank-1 => collapsed
hz=latent_health(zc)
check('collapsed latent flagged', hz['collapse']==1 and hz['eff_rank']<1.5, f"eff_rank={hz['eff_rank']:.3f}")
zi=np.random.default_rng(0).normal(size=(4096,8))                          # isotropic => healthy
hi=latent_health(zi)
check('isotropic latent not flagged', hi['collapse']==0 and hi['eff_rank']>7., f"eff_rank={hi['eff_rank']:.3f}")
check('isotropic offdiag corr near 0', hi['offdiag_corr']<0.1, f"{hi['offdiag_corr']:.4f}")


# ------------------------------------------------------- (f) checkpoint audit
print('(f) checkpoint audit')
with tempfile.TemporaryDirectory() as td:
    ck=Path(td)/'best.pt'
    src=build_jepa(CFG,True)
    with torch.no_grad():
        for pp in src.parameters(): pp.add_(torch.randn_like(pp)*0.05)
    atomic_torch_save({'model':src.state_dict(),'cfg':CFG},ck)
    full,obj=load_jepa_checkpoint(ck,CFG,'cpu'); au=obj['load_audit']
    check('full load: weights_changed True', au['weights_changed'] is True)
    check('full load: no unexpected keys', au['unexpected_keys']==[], str(au['unexpected_keys'][:5]))
    check('full load: no missing keys', au['missing_keys']==[], str(au['missing_keys'][:5]))
    sd=src.state_dict(); fd=full.state_dict()
    check('full load: head weights match checkpoint', torch.allclose(fd['physical_mu.weight'],sd['physical_mu.weight']))
    body,ba=load_jepa_body_fresh_head(ck,CFG,'cpu')
    bd=body.state_dict()
    check('body load: weights_changed True', ba['weights_changed'] is True)
    check('body load: no unexpected keys', ba['unexpected_keys']==[], str(ba['unexpected_keys'][:5]))
    check('body load: encoder weights match checkpoint', torch.allclose(bd['context_encoder.channel_emb'],sd['context_encoder.channel_emb']))
    check('body load: predictor weights match checkpoint', torch.allclose(bd['predictor.horizon_emb'],sd['predictor.horizon_emb']))
    check('body load: physical head REINITIALISED', not torch.allclose(bd['physical_mu.weight'],sd['physical_mu.weight']))
    check('body load: logvar head REINITIALISED', not torch.allclose(bd['physical_logvar.weight'],sd['physical_logvar.weight']))
    check('body load: action head REINITIALISED', not torch.allclose(bd['action_recovery.0.weight'],sd['action_recovery.0.weight']))
    check('body load: missing keys are head-only', ba['missing_keys_are_head_only'] is True, str(ba['missing_keys'][:5]))
    check('body load: reinitialised list is non-empty', len(ba['reinitialised'])>0)
    # a mismatched checkpoint must be reported, not silently swallowed
    bad={**src.state_dict(),'totally_bogus_key':torch.zeros(3)}
    atomic_torch_save({'model':bad,'cfg':CFG},ck)
    _,o2=load_jepa_checkpoint(ck,CFG,'cpu')
    check('unexpected key is reported', o2['load_audit']['unexpected_keys']==['totally_bogus_key'])


# ------------------------------------------- extra: no-learn baselines + ssl eval
print('(g) no-learn baselines and SSL validation')
xb=torch.zeros(2,4,2); xb[0,:,0]=torch.tensor([1.,2.,3.,4.]); xb[0,:,1]=torch.tensor([5.,5.,5.,5.])
xb[1,:,0]=torch.tensor([0.,-1.,-2.,-3.]); xb[1,:,1]=torch.tensor([2.,2.,2.,2.])
cb=copy.deepcopy(CFG); cb['protocol']['horizons']=[1,2]; cb['protocol']['context_len']=4; cb['schema']['sensors']=['a','b']
pers=build_forecaster('persistence',cb)(xb,torch.zeros(2,4,1),torch.zeros(2,2,1),present=torch.ones(2,4,2))
check('persistence repeats last observed value', torch.allclose(pers[0,0],torch.tensor([4.,5.])) and torch.allclose(pers[0,1],torch.tensor([4.,5.])))
check('persistence handles a decreasing series', torch.allclose(pers[1,0],torch.tensor([-3.,2.])))
dr=build_forecaster('drift',cb)(xb,torch.zeros(2,4,1),torch.zeros(2,2,1),present=torch.ones(2,4,2))
# slope +1/step on channel a from t=0..3 -> h=1 lands at t=4 => 5, h=2 at t=5 => 6; flat channel stays 5
check('drift extrapolates the linear trend', torch.allclose(dr[0,0],torch.tensor([5.,5.]),atol=1e-4) and torch.allclose(dr[0,1],torch.tensor([6.,5.]),atol=1e-4), str(dr[0].tolist()))
check('drift handles a negative slope', torch.allclose(dr[1,0],torch.tensor([-4.,2.]),atol=1e-4), str(dr[1,0].tolist()))
check('no-learn baselines have zero trainable params', sum(p.numel() for p in build_forecaster('persistence',cb).parameters())==0 and sum(p.numel() for p in build_forecaster('drift',cb).parameters())==0)
# evaluate_jepa_ssl is deterministic on a deterministic loader and never touches the head
c3=copy.deepcopy(CFG); c3['train']['num_workers']=0
_,_,dsx,_,_=prepare(c3,training_mask=True,val_mask=True); ldx=loaders_from_ds(dsx,c3,shuffle_train=False)
mm=build_jepa(c3,True)
r1=evaluate_jepa_ssl(mm,ldx['source_val'],c3,torch.device('cpu'),max_batches=2)
r2=evaluate_jepa_ssl(mm,ldx['source_val'],c3,torch.device('cpu'),max_batches=2)
check('evaluate_jepa_ssl is deterministic', abs(r1['val_ssl']-r2['val_ssl'])<1e-9, f"{r1['val_ssl']:.8f} vs {r2['val_ssl']:.8f}")
check('evaluate_jepa_ssl reports latent health', {'zpred_eff_rank','ztgt_std_min','collapse'} <= set(r1))
check('evaluate_jepa_ssl val_ssl is finite', np.isfinite(r1['val_ssl']))
check('prepare wires deterministic mask seed on non-train splits', dsx['source_val'].mask_rng_seed==int(c3['seed']) and dsx['source_train'].mask_rng_seed is None)

# (h) metric-scale invariants: robust-IQR floor + exact common-space affine (scripts 41/67)
print('(h) normalization scale-space invariants')
rng=np.random.default_rng(0)
xx=np.stack([rng.normal(2,1.5,8000), np.where(rng.random(8000)<0.7,0.0,rng.normal(0,0.6,8000))],axis=1)  # ch1 spike-dominated
n_leg=Normalizer('robust',rel_floor=0.0).fit(xx); n_flo=Normalizer('robust').fit(xx); n_ref=Normalizer('zscore').fit(xx)
check('robust floor engages on degenerate-IQR channel', n_flo.scale[1]>=0.05*np.nanstd(xx[:,1])-1e-12, f'{n_flo.scale[1]:.4g}')
check('robust floor leaves healthy channel untouched', abs(n_leg.scale[0]-n_flo.scale[0])<1e-12)
g,o=n_ref.affine_to(Normalizer('zscore').fit(xx))
check('affine_to identical fits is exact identity', bool(np.all(g==1.0) and np.all(o==0.0)))
g,o=n_leg.affine_to(n_ref)
xt=n_leg.transform(xx)
check('affine_to equals inverse-then-reference-transform', np.allclose(xt*g+o,n_ref.transform(n_leg.inverse(xt)),atol=1e-12))
check('affine_to lands in the reference space', np.allclose(xt*g+o,n_ref.transform(xx),atol=1e-9))
sd_leg=n_leg.state_dict(); sd_leg.pop('rel_floor')
back=Normalizer.from_state_dict(sd_leg)
check('legacy state_dict (no rel_floor) restores unfloored scales', back.rel_floor==0.0 and np.allclose(back.scale,n_leg.scale))
# evaluate_jepa identity-affine bitwise guarantee on the ranked metrics
from cncjepa.trainers import evaluate_jepa
mm2=build_jepa(c3,True)
mA,_=evaluate_jepa(mm2,ldx['source_val'],torch.device('cpu'))
ident=(np.ones(len(c3['schema']['sensors'])),np.zeros(len(c3['schema']['sensors'])))
mB,_=evaluate_jepa(mm2,ldx['source_val'],torch.device('cpu'),metric_affine=ident)
check('evaluate_jepa identity affine is bitwise on ranked metrics', all(mA[k]==mB[k] for k in ('rmse','mae','r2','nll')) and mA['per_horizon']==mB['per_horizon'])

# (i) RevIN: JEPA-internal, presence-aware instance normalization (V2). Invariants: off = bitwise
#     legacy; norm/denorm round-trip; statistics ignore absent entries; absent channel = identity;
#     shift/scale equivariance of mu (the scientific point); eval contract + checkpoint compat.
print('(i) revin (instance-wise normalization inside the JEPA)')
from cncjepa.models.revin import MaskedRevIN
from cncjepa.checkpoint import BODY_PREFIXES
torch.manual_seed(0)
bi=next(iter(ldx['source_val']))
def _fwd(model,b,**kw):
    model.eval()
    with torch.no_grad(): return model(b['x'],b['past_actions'],b['future_actions'],b['present'],b['schema'],b['y'],b.get('target_present'),**kw)
c_off=copy.deepcopy(c3); c_off['model']['revin']={'enabled':False}
c_abs=copy.deepcopy(c3); c_abs['model'].pop('revin',None)
c_on=copy.deepcopy(c3); c_on['model']['revin']={'enabled':True,'affine':False,'subtract_last':False,'eps':1e-5}
set_seed(1); m_abs=build_jepa(c_abs,True); set_seed(1); m_off=build_jepa(c_off,True); set_seed(1); m_on=build_jepa(c_on,True)
o_abs=_fwd(m_abs,bi); o_off=_fwd(m_off,bi)
check('revin key absent and enabled:false build the same module set', m_abs.revin is None and m_off.revin is None and list(m_abs.state_dict())==list(m_off.state_dict()))
check('revin off is bitwise legacy on mu/logvar/z_pred', all(torch.equal(o_abs[k],o_off[k]) for k in ('mu','logvar','z_pred')) and 'revin_std' not in o_off)
check('revin on adds no parameters without affine', list(m_on.state_dict())==list(m_abs.state_dict()) and isinstance(m_on.revin,MaskedRevIN))
# round trip + mask-awareness on a hand-built window
rv=MaskedRevIN(3,eps=1e-5)
xw=torch.randn(4,8,3)*torch.tensor([0.5,2.0,1.0])+torch.tensor([1.0,-3.0,0.0]); pw=torch.ones(4,8,3)
pw[0,:3,0]=0; xw[0,:3,0]=0.          # masked entries written as 0 (data.py convention)
pw[1,:,2]=0; xw[1,:,2]=0.            # channel 2 fully absent in window 1
cen,sd=rv.stats(xw,pw)
ref_m=xw[0,3:,0].mean(); ref_s=torch.sqrt(xw[0,3:,0].var(unbiased=False)+1e-5)
check('revin statistics ignore absent entries', abs(float(cen[0,0,0]-ref_m))<1e-6 and abs(float(sd[0,0,0]-ref_s))<1e-6, f'{float(cen[0,0,0]):.5f} vs {float(ref_m):.5f}')
check('revin absent channel falls back to identity', float(cen[1,0,2])==0.0 and float(sd[1,0,2])==1.0)
zn=rv.normalize(xw,cen,sd,pw)
check('revin normalize re-zeroes absent entries', bool((zn[0,:3,0]==0).all() and (zn[1,:,2]==0).all()))
mu_n=torch.randn(4,5,3); lv_n=torch.randn(4,5,3)
mu_b,lv_b=rv.denormalize(mu_n,lv_n,cen,sd)
check('revin denormalize inverts normalize', torch.allclose(rv.normalize(mu_b,cen,sd),mu_n,atol=1e-5))
check('revin logvar shifts by 2*log(std)', torch.allclose(lv_b-lv_n,2*torch.log(sd).expand_as(lv_n),atol=1e-6))
# shift/scale equivariance of the full model: x'=a*x+c, y'=a*y+c (per channel, a >> sqrt(eps))
o_on=_fwd(m_on,bi)
a_=torch.tensor([1.0+0.25*i for i in range(bi['x'].shape[-1])]); c_=torch.tensor([(-1)**i*0.7*i for i in range(bi['x'].shape[-1])])
b2=dict(bi); b2['x']=(bi['x']*a_+c_)*bi['present']; b2['y']=(bi['y']*a_+c_)*bi['target_present']
o2=_fwd(m_on,b2)
pres_ch=(bi['present'].sum(1)>0)[:,None,:].expand_as(o_on['mu'])   # channels with context statistics
check('revin: z_pred invariant to per-channel affine shift of the input', torch.allclose(o_on['z_pred'],o2['z_pred'],atol=1e-3,rtol=1e-3), f"max|d|={float((o_on['z_pred']-o2['z_pred']).abs().max()):.2e}")
check('revin: mu equivariant (mu\'=a*mu+c) on observed channels', torch.allclose((o_on['mu']*a_+c_)[pres_ch],o2['mu'][pres_ch],atol=1e-3,rtol=1e-3), f"max|d|={float(((o_on['mu']*a_+c_)-o2['mu'])[pres_ch].abs().max()):.2e}")
# eps breaks exact scale equivariance on near-constant windows (sqrt(a^2 v+eps) != a sqrt(v+eps)):
# check the logvar law only where the window variance dominates eps (std>0.2 => error < 3e-4).
well=pres_ch & (o_on['revin_std'][:,None,:].expand_as(o_on['mu'])>0.2)
check('revin: logvar shifts by 2*log(a) where var >> eps', torch.allclose((o_on['logvar']+2*torch.log(a_))[well],o2['logvar'][well],atol=1e-3,rtol=1e-3), f"max|d|={float(((o_on['logvar']+2*torch.log(a_))-o2['logvar'])[well].abs().max()):.2e} on {int(well.sum())} entries")
o_leg=_fwd(m_abs,bi)
check('revin: legacy model is NOT shift-equivariant (the gap being closed)', not torch.allclose((o_leg['mu']*a_+c_)[pres_ch],_fwd(m_abs,b2)['mu'][pres_ch],atol=1e-2))
# eval contract: finite metrics, model-independent anchor untouched, outputs in loader z-space
mR,rawR=evaluate_jepa(m_on,ldx['source_val'],torch.device('cpu'),metric_affine=ident)
check('revin: evaluate_jepa metrics finite', all(np.isfinite(mR[k]) for k in ('rmse','mae','r2','nll')))
anchor_on=rmse(np.where(rawR['mask'],rawR['y'],np.nan),np.where(rawR['mask'],0.0,np.nan)); _,rawL=evaluate_jepa(m_abs,ldx['source_val'],torch.device('cpu'))
anchor_off=rmse(np.where(rawL['mask'],rawL['y'],np.nan),np.where(rawL['mask'],0.0,np.nan))
check('revin: trivial-predictor anchor unchanged (targets stay in loader z-space)', anchor_on==anchor_off, f'{anchor_on:.6f} vs {anchor_off:.6f}')
# training step runs with the schema-consistency second pass and produces finite gradients
m_tr=build_jepa(c_on,True); m_tr.train(); loss,parts,_=jepa_step(m_tr,bi,c_on,train=True,ssl_mode=False); loss.backward()
check('revin: jepa_step (with schema view) finite loss and grads', torch.isfinite(loss) and all(torch.isfinite(p.grad).all() for p in m_tr.parameters() if p.grad is not None))
# checkpoint compatibility: a V1 checkpoint (no revin key) loads into a revin model with no key delta
with tempfile.TemporaryDirectory() as td:
    ck=Path(td)/'v1.pt'; atomic_torch_save({'model':m_abs.state_dict(),'cfg':c_abs},ck)
    m_ld,obj=load_jepa_checkpoint(ck,c_on,'cpu'); au=obj['load_audit']
    check('revin: V1 checkpoint loads into revin model (no missing/unexpected keys)', au['missing_keys']==[] and au['unexpected_keys']==[] and au['weights_changed'])
    c_aff=copy.deepcopy(c_on); c_aff['model']['revin']['affine']=True
    m_aff=build_jepa(c_aff,True)
    with torch.no_grad(): m_aff.revin.weight.fill_(2.0); m_aff.revin.bias.fill_(0.5)
    ck2=Path(td)/'aff.pt'; atomic_torch_save({'model':m_aff.state_dict(),'cfg':c_aff},ck2)
    m_body,au2=load_jepa_body_fresh_head(ck2,c_aff,'cpu')
    check('revin: affine params are body (kept by body-only load)', 'revin.' in BODY_PREFIXES and any(k.startswith('revin.') for k in m_aff.state_dict()) and float(m_body.revin.weight[0])==2.0 and float(m_body.revin.bias[0])==0.5 and au2['missing_keys_are_head_only'])

print()
if FAIL:
    print(f'P3FIX_TESTS_FAILED ({len(FAIL)}): '+', '.join(FAIL)); sys.exit(1)
print('P3FIX_TESTS_OK')
