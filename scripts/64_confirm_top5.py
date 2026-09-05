"""Confirmation stage of architecture search V2: rerun the top-5 discovery candidates to 5
seeds and re-rank them (taskbook 'Discovery schedule' + 'What counts as the best architecture').

  1. read ranked_methods.csv, take the top --top candidates that were actually ranked;
  2. run the MISSING seeds for them via script 42's slot pool (one 42 invocation per missing
     seed, with a manifest restricted to the candidates that still need it, so completed runs
     are never repeated);
  3. re-score the top-5 pool over all --seeds with the same composite, with the z-statistics
     recomputed inside the confirmation pool;
  4. report the confirmed winner and warn when rank-1 changed between the 3-seed and the
     5-seed ranking -- taskbook decision rule: an unstable winner must not be locked.

Outputs: confirmed_top5.csv, confirmed_top5_all_seeds.csv, confirmation_report.json
DS01 validation only; nothing here reads the target machine.
"""
from _common import *
from _search_common import *
import argparse, json, subprocess, sys

p=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
p.add_argument('--ranked',default='outputs/random_search/ranked_methods.csv')
p.add_argument('--manifest',default='configs/search_v2/manifest.json')
p.add_argument('--root',default='outputs/random_search')
p.add_argument('--out',default='outputs/random_search/confirmed_top5.csv')
p.add_argument('--top',type=int,default=5)
p.add_argument('--seeds',default='0,1,2,3,4',help='full confirmation seed set')
p.add_argument('--gpus',default='0,0,0',help='slot pool passed to script 42 (repeat an id to pack one GPU)')
p.add_argument('--min-seeds',type=int,default=2,help='valid seeds needed to appear in the confirmed table')
p.add_argument('--dry-run',action='store_true',help='print the script-42 invocations and re-rank what already exists')
p.add_argument('--skip-run',action='store_true',help='do not launch anything, only re-rank existing runs')
a=p.parse_args()

ranked=Path(a.ranked)
if not ranked.exists():
    print(f'ERROR: {ranked} not found. Run scripts/43_rank_methods_validation_only.py first.',file=sys.stderr); sys.exit(2)
import pandas as pd
disc=pd.read_csv(ranked)
if 'ranked' in disc.columns: disc=disc[disc['ranked']==1]
if len(disc)==0:
    print(f'ERROR: {ranked} contains no ranked candidate (all had too few valid seeds).',file=sys.stderr); sys.exit(2)
top=disc.sort_values('composite_mean').head(int(a.top))['candidate'].astype(str).tolist()
disc_winner=top[0]
seeds=[int(s) for s in a.seeds.split(',') if s.strip()!='']
print(f'discovery top-{len(top)}: {top}\ndiscovery rank-1: {disc_winner}\nconfirmation seeds: {seeds}')

man={m['name']:m for m in json.loads(Path(a.manifest).read_text(encoding='utf-8'))}
missing=[m for m in top if m not in man]
if missing: print(f'ERROR: candidates {missing} are absent from {a.manifest}',file=sys.stderr); sys.exit(2)

# ---------------------------------------------------------------- run the missing seeds
root=Path(a.root); root.mkdir(parents=True,exist_ok=True)
todo={s:[m for m in top if not (root/m/f'seed_{s}'/METRICS_NAME).exists()] for s in seeds}
n_todo=sum(len(v) for v in todo.values())
print('\nmissing runs: '+(', '.join(f'seed {s}: {v}' for s,v in todo.items() if v) or 'none'))
rc_fail=[]
if n_todo and not a.skip_run:
    for s in seeds:
        if not todo[s]: continue
        mpath=root/f'confirm_manifest_seed_{s}.json'
        mpath.write_text(json.dumps([man[m] for m in todo[s]],indent=2),encoding='utf-8')
        cmd=[sys.executable,'scripts/42_run_20_random_methods_dgx.py','--manifest',str(mpath),
             '--gpus',a.gpus,'--out',str(root),'--seeds',str(s)]+(['--dry-run'] if a.dry_run else [])
        print('\n$ '+' '.join(cmd))
        rc=subprocess.run(cmd,cwd=str(ROOT)).returncode
        if rc!=0: rc_fail.append((s,rc)); print(f'   script 42 returned {rc} for seed {s}',file=sys.stderr)
elif a.skip_run:
    print('--skip-run: not launching anything')

# ---------------------------------------------------------------- re-rank the confirmation pool
runs=load_runs(root,candidates=top,seeds=seeds)
if len(runs)==0:
    print(f'ERROR: no {METRICS_NAME} found for {top} under {root}.',file=sys.stderr); sys.exit(2)
scored=score_pool(runs)
out=Path(a.out); out.parent.mkdir(parents=True,exist_ok=True)
scored.to_csv(out.with_name('confirmed_top5_all_seeds.csv'),index=False)
bad=report_invalid(scored)
agg=aggregate(scored,min_seeds=a.min_seeds)
agg.to_csv(out,index=False)

print(f'\nformula: {FORMULA}')
print(f'z-statistics recomputed over {int(scored["usable"].sum())} valid rows inside the top-{len(top)} confirmation pool')
print_table(agg,title=f'confirmed ranking (top-{len(top)}, seeds {seeds}, DS01 validation only)')

conf=agg[agg['ranked']==1] if 'ranked' in agg.columns else agg
conf_winner=str(conf.iloc[0]['candidate']) if len(conf) else None
stable=bool(conf_winner==disc_winner)
w=conf.iloc[0] if len(conf) else None
margin_ok=True
if w is not None and len(conf)>1:
    r2=conf.iloc[1]
    sd=float(w['composite_sd']) if w['composite_sd']==w['composite_sd'] else 0.
    margin_ok=bool(float(r2['composite_mean'])-float(w['composite_mean'])>sd)

print('\n'+'='*78+'\nCONFIRMATION VERDICT (DS01 validation only)\n'+'='*78)
if w is not None:
    print(f"  confirmed winner : {conf_winner}  composite {float(w['composite_mean']):+.5f} +/- "
          f"{float(w['composite_sd']) if w['composite_sd']==w['composite_sd'] else float('nan'):.5f} over {int(w['n_valid_seeds'])} valid seeds")
    print(f"  flags            : collapse={int(w['any_collapse'])} weak_action={int(w['any_weak_action'])} invalid_seeds={int(w['n_invalid_seeds'])}")
if not stable:
    print(f'  !! SEED-STABILITY WARNING: rank-1 changed {disc_winner} (3 seeds) -> {conf_winner} (5 seeds).')
    print( '     Taskbook decision rule: "If the winner changes drastically across seeds, do not lock it yet."')
    print( '     Increase seeds or simplify the search space; script 44 will refuse to lock without --force.')
else:
    print(f'  rank-1 stable across the 3-seed and 5-seed rankings ({disc_winner}).')
if not margin_ok:
    print('  !! rank-1 and rank-2 composites are within one seed-SD of each other: the margin is not decisive.')
if w is not None and int(w['n_valid_seeds'])<len(seeds):
    print(f"  !! winner has {int(w['n_valid_seeds'])}/{len(seeds)} valid seeds; script 44 requires 5.")
if rc_fail: print(f'  !! script 42 reported non-zero exit for seeds {[s for s,_ in rc_fail]}')

rep={'discovery_ranking':str(ranked),'discovery_top':top,'discovery_winner':disc_winner,
     'confirmed_winner':conf_winner,'winner_stable':stable,'margin_exceeds_seed_sd':margin_ok,
     'seeds':seeds,'formula':FORMULA,'n_valid_rows':int(scored['usable'].sum()),
     'n_invalid_rows':int(len(bad)),'invalid':bad[['candidate','seed','invalid_reasons']].to_dict('records') if len(bad) else [],
     'launcher_failures':rc_fail,'dry_run':bool(a.dry_run),'skip_run':bool(a.skip_run),
     'winner_row':({k:(None if w[k]!=w[k] else w[k]) for k in conf.columns} if w is not None else None),
     'note':'DS01 source validation only. The target machine is not read anywhere in this script.'}
(out.with_name('confirmation_report.json')).write_text(json.dumps(rep,indent=2,default=str),encoding='utf-8')
print(f'\nwrote {out}, {out.with_name("confirmed_top5_all_seeds.csv")}, {out.with_name("confirmation_report.json")}')
