"""Rank the architecture-search V2 candidates on DS01 validation only (discovery stage).

Reads outputs/random_search/<candidate>/seed_*/val_metrics.json written by script 41 and
applies the taskbook composite (see scripts/_search_common.py for the exact formula). Runs that
script 41 marked invalid -- NaN metric, checkpoint-load failure, SSL latent collapse or a
deterministic-validation failure -- are dropped and listed, never silently ranked. A candidate
needs at least --min-seeds valid seeds to be ranked at all.

Raw component means are published alongside the composite: the composite is only a selection
mechanism, not a result. Nothing here reads the target machine.

Outputs: ranked_methods.csv, ranked_methods_all_seeds.csv, ranked_methods_invalid.csv
"""
from _common import *
from _search_common import *
import argparse, sys

p=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
p.add_argument('--root',default='outputs/random_search')
p.add_argument('--out',default='outputs/random_search/ranked_methods.csv')
p.add_argument('--min-seeds',type=int,default=2,help='valid seeds a candidate needs to be ranked')
p.add_argument('--top',type=int,default=10,help='rows printed')
a=p.parse_args()

root=Path(a.root)
if not root.exists():
    print(f'ERROR: search root {root} does not exist. Run scripts/40 then scripts/42 first.',file=sys.stderr); sys.exit(2)
runs=load_runs(root)
if len(runs)==0:
    print(f'ERROR: no {METRICS_NAME} found under {root}/<candidate>/seed_*/.\n'
          f'       Expected layout: {root}/M00/seed_0/{METRICS_NAME}\n'
          f'       Run: python scripts/42_run_20_random_methods_dgx.py --manifest configs/search_v2/manifest.json --gpus 0,0,0',
          file=sys.stderr)
    sys.exit(2)

scored=score_pool(runs)
out=Path(a.out); out.parent.mkdir(parents=True,exist_ok=True)
scored.to_csv(out.with_name('ranked_methods_all_seeds.csv'),index=False)
bad=report_invalid(scored); bad.to_csv(out.with_name('ranked_methods_invalid.csv'),index=False)

agg=aggregate(scored,min_seeds=a.min_seeds)
agg.to_csv(out,index=False)
print(f'\nformula: {FORMULA}')
print(f'z-statistics computed over {int(scored["usable"].sum())} valid candidate-seed rows from {scored["candidate"].nunique()} candidates')
print_table(agg,top=a.top,title='discovery ranking (DS01 validation only)')
unranked=agg[agg['ranked']==0]['candidate'].tolist() if 'ranked' in agg.columns else []
if unranked: print(f'\nnot ranked (<{a.min_seeds} valid seeds): {unranked}')
print(f'\nwrote {out}, {out.with_name("ranked_methods_all_seeds.csv")}, {out.with_name("ranked_methods_invalid.csv")}')

n_ranked=int((agg['ranked']==1).sum()) if 'ranked' in agg.columns else len(agg)
if n_ranked==0:
    print(f'\nERROR: no candidate has {a.min_seeds}+ valid seeds -- there is nothing to confirm or lock.\n'
          f'       {len(bad)} of {len(scored)} runs were invalid; see {out.with_name("ranked_methods_invalid.csv")}.\n'
          f'       Fix the failing runs (collapse / NaN / checkpoint load) before scripts 64 and 44.',file=sys.stderr)
    sys.exit(1)
