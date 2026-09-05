"""P3-FIX diagnostics on existing checkpoints.

Runs the three probes the P3-FIX gate requires on source_val (never DS03):
  1. LOAD AUDIT   - missing/unexpected keys and a weights_changed proof for each checkpoint.
  2. MU PROBE     - std of the predicted mu vs std of the targets, per channel. A pretrained
                    checkpoint whose physical head was never trained shows mu_std ~ 0 and a
                    ratio ~ 0: the head predicts a constant. That is the P3 symptom.
  3. LATENT HEALTH- std/off-diagonal correlation/effective rank/collapse flag on z_pred and
                    z_target, plus the held-out SSL objective.

Writes outputs/p3fix_diagnostics.json and prints a human-readable report.
"""
from _common import *
import argparse,json
import numpy as np, torch
from cncjepa.config import load_config
from cncjepa.pipeline import prepare,loaders_from_ds,batch_to
from cncjepa.checkpoint import load_jepa_checkpoint
from cncjepa.trainers import evaluate_jepa,evaluate_jepa_ssl,latent_health,COLLAPSE_STD_MIN,COLLAPSE_EFF_RANK_FRAC
from cncjepa.utils import device_from_arg,set_seed

p=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
p.add_argument('--config',default='configs/real.yaml')
p.add_argument('--ckpts',default='outputs/jepa_pretrain/best.pt,outputs/jepa_finetune/best.pt')
p.add_argument('--split',default='source_val')
p.add_argument('--device',default='cuda:0')
p.add_argument('--max-batches',type=int,default=None,help='cap the probe pass (default: whole split)')
p.add_argument('--out',default='outputs/p3fix_diagnostics.json')
a=p.parse_args()

cfg=load_config(a.config); set_seed(cfg['seed']); dev=device_from_arg(a.device)
_,_,ds,_,_=prepare(cfg,training_mask=True)      # deterministic per-index seeds on non-train splits
ld=loaders_from_ds(ds,cfg,shuffle_train=False)[a.split]
names=cfg['schema']['sensors']
rep={'config':a.config,'split':a.split,'device':str(dev),'seed':cfg['seed'],
     'collapse_thresholds':{'std_min':COLLAPSE_STD_MIN,'eff_rank_frac':COLLAPSE_EFF_RANK_FRAC},'checkpoints':{}}

def mu_probe(model,loader,max_batches=None):
    """Per-channel std(mu) vs std(y). ratio<<1 => the head outputs a near-constant."""
    model.eval(); mus=[]; ys=[]; ms=[]
    with torch.no_grad():
        for bi,b in enumerate(loader):
            if max_batches is not None and bi>=max_batches: break
            b=batch_to(b,dev); o=model(b['x'],b['past_actions'],b['future_actions'],b['present'],b['schema'],y=None)
            mus.append(o['mu'].float().cpu().numpy()); ys.append(b['y'].float().cpu().numpy()); ms.append(b['target_present'].bool().cpu().numpy())
    mu=np.concatenate(mus); y=np.concatenate(ys); m=np.concatenate(ms)
    mu=np.where(m,mu,np.nan); y=np.where(m,y,np.nan)
    ms_=np.nanstd(mu.reshape(-1,mu.shape[-1]),axis=0); ys_=np.nanstd(y.reshape(-1,y.shape[-1]),axis=0)
    ratio=ms_/(ys_+1e-12)
    return {'per_channel':{names[c]:{'mu_std':float(ms_[c]),'y_std':float(ys_[c]),'ratio':float(ratio[c])} for c in range(len(ms_))},
            'mu_std_mean':float(np.nanmean(ms_)),'y_std_mean':float(np.nanmean(ys_)),'ratio_mean':float(np.nanmean(ratio)),
            'ratio_min':float(np.nanmin(ratio)),'ratio_max':float(np.nanmax(ratio)),
            'dead_head':bool(np.nanmean(ratio)<0.05)}

for path in [s.strip() for s in a.ckpts.split(',') if s.strip()]:
    if not Path(path).exists(): print(f'[skip] {path} not found'); rep['checkpoints'][path]={'present':False}; continue
    print(f'\n=== {path} ===')
    model,obj=load_jepa_checkpoint(path,cfg,dev)
    entry={'present':True,'load_audit':obj['load_audit'],
           'ckpt_meta':{k:obj.get(k) for k in ('epoch','best','select_on') if k in obj}}
    entry['mu_probe']=mu_probe(model,ld,a.max_batches)
    entry['latent_health']=evaluate_jepa_ssl(model,ld,cfg,dev,max_batches=a.max_batches)
    met,_=evaluate_jepa(model,ld,dev); entry['physical']={k:met[k] for k in ('rmse','mae','r2','nll')}
    rep['checkpoints'][path]=entry

Path(a.out).parent.mkdir(parents=True,exist_ok=True); Path(a.out).write_text(json.dumps(rep,indent=2,default=str),encoding='utf-8')

print('\n'+'='*78+'\nP3-FIX DIAGNOSTIC REPORT\n'+'='*78)
for path,e in rep['checkpoints'].items():
    print(f'\n{path}')
    if not e.get('present'): print('  MISSING -- not evaluated'); continue
    au=e['load_audit']; print(f"  load: missing={len(au['missing_keys'])} unexpected={len(au['unexpected_keys'])} weights_changed={au['weights_changed']}  meta={e['ckpt_meta']}")
    mp=e['mu_probe']; print(f"  mu probe: mean std(mu)={mp['mu_std_mean']:.4f} vs std(y)={mp['y_std_mean']:.4f}  ratio mean={mp['ratio_mean']:.4f} [min {mp['ratio_min']:.4f}, max {mp['ratio_max']:.4f}]")
    print(f"            -> {'DEAD HEAD: mu is near-constant, physical predictions are meaningless' if mp['dead_head'] else 'head produces varying predictions'}")
    lh=e['latent_health']
    print(f"  latent z_pred : std_mean={lh['zpred_std_mean']:.4f} std_min={lh['zpred_std_min']:.4f} offdiag_corr={lh['zpred_offdiag_corr']:.4f} eff_rank={lh['zpred_eff_rank']:.1f} ({lh['zpred_eff_rank_frac']*100:.1f}% of d)")
    print(f"  latent z_tgt  : std_mean={lh['ztgt_std_mean']:.4f} std_min={lh['ztgt_std_min']:.4f} offdiag_corr={lh['ztgt_offdiag_corr']:.4f} eff_rank={lh['ztgt_eff_rank']:.1f} ({lh['ztgt_eff_rank_frac']*100:.1f}% of d)")
    print(f"  collapse flag : {'COLLAPSED' if lh['collapse'] else 'ok'}   val_ssl={lh['val_ssl']:.5f} (latent={lh['val_latent']:.5f} vicreg={lh['val_vicreg']:.5f})")
    ph=e['physical']; print(f"  physical      : rmse={ph['rmse']:.4f} mae={ph['mae']:.4f} r2={ph['r2']:.4f} nll={ph['nll']:.4f}")
    worst=sorted(mp['per_channel'].items(),key=lambda kv:kv[1]['ratio'])[:3]
    print('  lowest mu/y std ratios: '+', '.join(f'{k}={v["ratio"]:.3f}' for k,v in worst))
print(f'\nwrote {a.out}')
