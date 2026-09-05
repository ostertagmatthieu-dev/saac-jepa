"""Shared validation-only scoring for architecture search V2 (scripts 43, 44, 64).

Taskbook 'Validation-only selection score'. Every term is lower-is-better and standardised
across the candidate pool currently being ranked, using the same DS01 validation folds:

    composite = 0.30*z(clean_rmse)
              + 0.25*z(schema_drop_rmse)
              + 0.15*z(masked_rmse)
              + 0.10*z(long_horizon_rmse)
              + 0.10*z(calibration_penalty)
              + 0.10*z(ssl_latent_val)
              + 3.0*collapse_flag
              + 1.0*weak_action_flag

z is taken per component over the valid candidate-seed rows of the pool ((x-mean)/std, ddof=0;
a zero-variance component contributes 0). Discovery ranks the 20-candidate pool; confirmation
re-standardises inside the top-5 x 5-seed pool, so composites from the two stages are not
comparable in absolute value -- only the orderings are.

Runs marked invalid by script 41 (NaN metric, checkpoint-load failure, SSL latent collapse,
deterministic-validation failure) are excluded from the z-statistics and from the ranking, and
reported separately. Nothing here reads the target machine.
"""
from _common import *
import json
import numpy as np, pandas as pd

WEIGHTS=[('clean_rmse',.30),('schema_drop_rmse',.25),('masked_rmse',.15),
         ('long_horizon_rmse',.10),('calibration_penalty',.10),('ssl_latent_val',.10)]
COMPONENTS=[k for k,_ in WEIGHTS]
COLLAPSE_PENALTY=3.0
WEAK_ACTION_PENALTY=1.0
METRICS_NAME='val_metrics.json'
FORMULA=('composite = '+' + '.join(f'{w:.2f}*z({k})' for k,w in WEIGHTS)
         +f' + {COLLAPSE_PENALTY}*collapse + {WEAK_ACTION_PENALTY}*weak_action')
BASE_COLS=['candidate','seed','path','invalid','invalid_reasons','collapse','ssl_collapse','ft_collapse',
           'weak_action','action_sensitivity','eff_rank_frac','std_min','offdiag_corr','n_params']


def load_runs(root,candidates=None,seeds=None):
    """Collect <root>/<candidate>/seed_<k>/val_metrics.json into a per-run DataFrame."""
    rows=[]
    for f in sorted(Path(root).glob(f'*/seed_*/{METRICS_NAME}')):
        cand=f.parent.parent.name; stem=f.parent.name.split('_',1)[-1]
        try: seed=int(stem)
        except ValueError: seed=stem
        if candidates is not None and cand not in set(candidates): continue
        if seeds is not None and seed not in set(seeds): continue
        try: d=json.loads(f.read_text(encoding='utf-8'))
        except Exception as e:
            rows.append({'candidate':cand,'seed':seed,'path':str(f),'invalid':True,'invalid_reasons':f'unreadable_json:{e}'}); continue
        r={'candidate':cand,'seed':seed,'path':str(f),
           'invalid':bool(d.get('invalid',False)),'invalid_reasons':';'.join(d.get('invalid_reasons') or []),
           'collapse':int(bool(d.get('collapse',0))),'ssl_collapse':int(bool(d.get('ssl_collapse',0))),
           'ft_collapse':int(bool(d.get('ft_collapse',d.get('collapse',0)))),'weak_action':int(bool(d.get('weak_action',0))),
           'action_sensitivity':d.get('action_sensitivity'),'eff_rank_frac':d.get('eff_rank_frac'),
           'std_min':d.get('std_min'),'offdiag_corr':d.get('offdiag_corr'),'n_params':d.get('n_params')}
        r.update({k:d.get(k) for k in COMPONENTS})
        rows.append(r)
    df=pd.DataFrame(rows,columns=BASE_COLS+COMPONENTS) if not rows else pd.DataFrame(rows)
    for c in BASE_COLS+COMPONENTS:
        if c not in df.columns: df[c]=np.nan
    return df


def _z(v):
    v=np.asarray(v,float); sd=float(np.std(v))
    return np.zeros_like(v) if not np.isfinite(sd) or sd<=0 else (v-float(np.mean(v)))/sd


def score_pool(df):
    """Add usable/z_*/composite columns. z-statistics come from the usable rows of THIS pool."""
    d=df.copy()
    if len(d)==0:
        for k in COMPONENTS: d[f'z_{k}']=[]
        d['usable']=[]; d['composite']=[]; return d
    for k in COMPONENTS: d[k]=pd.to_numeric(d[k],errors='coerce')
    finite=d[COMPONENTS].apply(np.isfinite).all(axis=1)
    d['invalid']=d['invalid'].fillna(False).astype(bool)
    d.loc[~finite & ~d['invalid'],'invalid_reasons']=(d.loc[~finite & ~d['invalid'],'invalid_reasons'].fillna('')+';missing_component').str.strip(';')
    d['usable']=(~d['invalid']) & finite
    for k in COMPONENTS: d[f'z_{k}']=np.nan
    d['composite']=np.nan
    v=d.index[d['usable']]
    if len(v)==0: return d
    comp=np.zeros(len(v))
    for k,w in WEIGHTS:
        z=_z(d.loc[v,k].to_numpy(float)); d.loc[v,f'z_{k}']=z; comp=comp+w*z
    comp=comp+COLLAPSE_PENALTY*d.loc[v,'ft_collapse'].fillna(0).to_numpy(float)
    comp=comp+WEAK_ACTION_PENALTY*d.loc[v,'weak_action'].fillna(0).to_numpy(float)
    d.loc[v,'composite']=comp
    return d


def aggregate(scored,min_seeds=2):
    """Per-candidate mean +/- SD across seeds; candidates below min_seeds are sorted last."""
    v=scored[scored['usable']] if len(scored) else scored
    if len(v)==0: return pd.DataFrame(columns=['rank','candidate','n_valid_seeds','composite_mean','composite_sd'])
    g=v.groupby('candidate')
    out=pd.DataFrame({'n_valid_seeds':g['composite'].size(),
                      'composite_mean':g['composite'].mean(),
                      'composite_sd':g['composite'].std(ddof=1)})
    for k in COMPONENTS: out[f'{k}_mean']=g[k].mean()
    out['action_sensitivity_mean']=g['action_sensitivity'].mean()
    out['eff_rank_frac_mean']=g['eff_rank_frac'].mean(); out['std_min_mean']=g['std_min'].mean(); out['offdiag_corr_mean']=g['offdiag_corr'].mean()
    out['n_collapse']=g['ft_collapse'].sum().astype(int); out['n_weak_action']=g['weak_action'].sum().astype(int)
    out['any_collapse']=(out['n_collapse']>0).astype(int); out['any_weak_action']=(out['n_weak_action']>0).astype(int)
    out['n_params']=g['n_params'].max()
    out['seeds']=g['seed'].apply(lambda s:','.join(sorted((str(x) for x in s),key=str)))
    bad=scored[~scored['usable']].groupby('candidate').size() if len(scored) else None
    out['n_invalid_seeds']=(bad.reindex(out.index).fillna(0).astype(int) if bad is not None else 0)
    out=out.reset_index()
    out['ranked']=(out['n_valid_seeds']>=int(min_seeds)).astype(int)
    out=out.sort_values(['ranked','composite_mean'],ascending=[False,True]).reset_index(drop=True)
    out.insert(0,'rank',np.arange(1,len(out)+1))
    return out


def print_table(agg,top=None,title='ranking'):
    cols=['rank','candidate','n_valid_seeds','composite_mean','composite_sd']+[f'{k}_mean' for k in COMPONENTS]+['action_sensitivity_mean','any_collapse','any_weak_action','n_invalid_seeds']
    cols=[c for c in cols if c in agg.columns]
    t=agg if top is None else agg.head(int(top))
    print(f'\n=== {title} ({len(agg)} candidates) ===')
    print(t[cols].to_string(index=False,float_format=lambda x:f'{x:,.5f}'))


def report_invalid(scored):
    bad=scored[~scored['usable']] if len(scored) else scored
    if len(bad)==0:
        print('invalid runs: none'); return bad
    print(f'\n!! {len(bad)} run(s) dropped as invalid (taskbook: marked invalid, not silently ranked):')
    for _,r in bad.iterrows():
        print(f"   {r['candidate']}/seed_{r['seed']}: {r['invalid_reasons'] or 'unspecified'}")
    return bad
