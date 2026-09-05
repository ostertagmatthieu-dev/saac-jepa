"""Freeze the winning architecture before the first target-machine evaluation.

Input defaults to confirmed_top5.csv (script 64) when it exists, otherwise ranked_methods.csv
(script 43). The winner is rank-1 of that table. Everything needed to reproduce it is copied
and hashed:

  * full config copy         -> <lockdir>/config.yaml (+ SHA-256)
  * fine-tuned checkpoint    -> SHA-256 of <root>/<winner>/seed_<k>/finetune/best.pt
  * SSL pretrain checkpoint  -> SHA-256 of .../pretrain/best.pt
  * normalizers.json         -> SHA-256
  * code hash                -> SHA-256 over sorted src/**/*.py + scripts/*.py (path + bytes);
                                there is no git repo here, so the tree itself is the revision
  * seeds list, per-seed composites, load audit, validation metric bundle
  * timestamps taken from artifact mtimes (plus the wall clock of the lock itself)

Refuses to lock (exit 1) when the winner has a collapse flag, a weak-action flag, fewer than
--min-valid-seeds valid seeds, or an unstable rank-1 per confirmation_report.json.
--force overrides with a visible warning recorded inside the lock file.

Selection is DS01 validation only; the target machine is not read anywhere in this script.
Script 45 verifies these hashes before the single target evaluation.
"""
from _common import *
from _search_common import COMPONENTS, FORMULA, METRICS_NAME
import argparse, hashlib, json, shutil, sys, time
import pandas as pd

CODE_GLOBS=[('src','**/*.py'),('scripts','*.py')]

p=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
p.add_argument('--ranking',default=None,help='default: confirmed_top5.csv if present else ranked_methods.csv')
p.add_argument('--search-root',default='outputs/random_search')
p.add_argument('--out',default='outputs/random_search/LOCKED_BEST.json')
p.add_argument('--lockdir',default='outputs/random_search/locked')
p.add_argument('--normalizers',default='outputs/normalizers.json')
p.add_argument('--seed-pick',choices=['best','median'],default='best',help='which seed checkpoint to freeze')
p.add_argument('--min-valid-seeds',type=int,default=5)
p.add_argument('--force',action='store_true',help='lock despite failed gates (recorded in the lock file)')
a=p.parse_args()

root=Path(a.search_root)
ranking=Path(a.ranking) if a.ranking else next((q for q in (root/'confirmed_top5.csv',root/'ranked_methods.csv') if q.exists()),None)
if ranking is None or not Path(ranking).exists():
    print(f'ERROR: no ranking table. Looked for {root/"confirmed_top5.csv"} and {root/"ranked_methods.csv"}.\n'
          f'       Run scripts/43 (and ideally scripts/64) first.',file=sys.stderr); sys.exit(2)
ranking=Path(ranking)
df=pd.read_csv(ranking)
if 'ranked' in df.columns: df=df[df['ranked']==1]
if len(df)==0: print(f'ERROR: {ranking} has no ranked candidate.',file=sys.stderr); sys.exit(2)
df=df.sort_values('composite_mean').reset_index(drop=True)
row=df.iloc[0]; winner=str(row['candidate'])
stage='confirmation' if ranking.name=='confirmed_top5.csv' else 'discovery'
print(f'ranking table : {ranking} ({stage} stage)\nwinner        : {winner}  composite {float(row["composite_mean"]):+.5f} over {int(row["n_valid_seeds"])} valid seeds')

# ---------------------------------------------------------------- per-seed rows for the winner
per_seed_csv=ranking.with_name('confirmed_top5_all_seeds.csv' if stage=='confirmation' else 'ranked_methods_all_seeds.csv')
seed_rows=pd.DataFrame()
if per_seed_csv.exists():
    s=pd.read_csv(per_seed_csv); seed_rows=s[(s['candidate'].astype(str)==winner)&(s['usable'].astype(str).str.lower().isin(('true','1')))].copy()
if len(seed_rows)==0:
    print(f'ERROR: no usable per-seed rows for {winner} in {per_seed_csv}.',file=sys.stderr); sys.exit(2)
seed_rows=seed_rows.sort_values('composite').reset_index(drop=True)
seeds=[int(x) for x in seed_rows['seed'].tolist()]
pick=seed_rows.iloc[0] if a.seed_pick=='best' else seed_rows.iloc[len(seed_rows)//2]
pick_seed=int(pick['seed'])
run_dir=root/winner/f'seed_{pick_seed}'
print(f'seed pick     : {a.seed_pick} -> seed {pick_seed} (composite {float(pick["composite"]):+.5f}); valid seeds {sorted(seeds)}')

# ---------------------------------------------------------------- gates
conf_path=root/'confirmation_report.json'
conf=json.loads(conf_path.read_text(encoding='utf-8')) if conf_path.exists() else {}
gates={'no_collapse':int(row.get('any_collapse',0))==0,
       'no_weak_action':int(row.get('any_weak_action',0))==0,
       f'at_least_{a.min_valid_seeds}_valid_seeds':int(row['n_valid_seeds'])>=int(a.min_valid_seeds),
       'winner_stable_across_seeds':bool(conf.get('winner_stable',True)),
       'confirmation_stage_used':stage=='confirmation'}
failed=[k for k,v in gates.items() if not v]
for k,v in gates.items(): print(f"  gate {'OK  ' if v else 'FAIL'} {k}")
if failed and not a.force:
    print(f'\nREFUSING TO LOCK {winner}: failed gates {failed}.\n'
          f'Taskbook: a candidate with latent collapse, a weak action diagnostic, an unstable rank-1 or\n'
          f'fewer than {a.min_valid_seeds} valid seeds is not lockable. Fix the search or pass --force.',file=sys.stderr)
    sys.exit(1)
if failed: print(f'\n!! WARNING: --force used; locking {winner} despite failed gates {failed}.')

# ---------------------------------------------------------------- artifacts
cfg_src=run_dir/'config.yaml'; ckpt=run_dir/'finetune'/'best.pt'; pre_ckpt=run_dir/'pretrain'/'best.pt'
metrics=run_dir/METRICS_NAME; audit=run_dir/'load_audit.json'; norm=Path(a.normalizers)
for q in (cfg_src,ckpt,metrics):
    if not q.exists(): print(f'ERROR: required artifact missing: {q}',file=sys.stderr); sys.exit(2)
lockdir=Path(a.lockdir); lockdir.mkdir(parents=True,exist_ok=True)
cfg_lock=lockdir/'config.yaml'; shutil.copy2(cfg_src,cfg_lock)
if audit.exists(): shutil.copy2(audit,lockdir/'load_audit.json')
shutil.copy2(metrics,lockdir/'val_metrics.json')
seed_rows.to_csv(lockdir/'winner_per_seed.csv',index=False)

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def mtime(path):
    t=Path(path).stat().st_mtime; return {'epoch':t,'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime(t))}

def code_hash():
    h=hashlib.sha256(); files=[]
    for sub,pat in CODE_GLOBS:
        for f in sorted((ROOT/sub).glob(pat)):
            if '__pycache__' in f.parts: continue
            rel=f.relative_to(ROOT).as_posix(); files.append(rel)
            h.update(rel.encode()); h.update(b'\0'); h.update(f.read_bytes()); h.update(b'\0')
    return h.hexdigest(),files

code_sha,code_files=code_hash()
mv=json.loads(metrics.read_text(encoding='utf-8'))
payload={
 'method':winner,                                   # keys 'method'/'config'/'checkpoint'/'*_sha256' are the script-45 contract
 'candidate':winner,'description':str(row.get('description',mv.get('description',''))),
 'selection_stage':stage,'ranking_table':str(ranking),'per_seed_table':str(per_seed_csv),
 'composite_formula':FORMULA,'composite_mean':float(row['composite_mean']),
 'composite_sd':(None if row['composite_sd']!=row['composite_sd'] else float(row['composite_sd'])),
 'raw_component_means':{k:(None if row.get(f'{k}_mean')!=row.get(f'{k}_mean') else float(row[f'{k}_mean'])) for k in COMPONENTS if f'{k}_mean' in row},
 'seeds':sorted(seeds),'n_valid_seeds':int(row['n_valid_seeds']),'seed_pick':a.seed_pick,'selected_seed':pick_seed,
 'selected_run':str(run_dir),'selected_run_composite':float(pick['composite']),
 'per_seed_composites':{str(int(r['seed'])):float(r['composite']) for _,r in seed_rows.iterrows()},
 'config':str(cfg_lock),'config_sha256':sha(cfg_lock),'config_source':str(cfg_src),
 'checkpoint':str(ckpt),'checkpoint_sha256':sha(ckpt),
 'pretrain_checkpoint':(str(pre_ckpt) if pre_ckpt.exists() else None),
 'pretrain_checkpoint_sha256':(sha(pre_ckpt) if pre_ckpt.exists() else None),
 'normalizers':str(norm) if norm.exists() else None,
 'normalizers_sha256':(sha(norm) if norm.exists() else None),
 'code_sha256':code_sha,'code_files':len(code_files),'code_globs':[f'{s}/{p_}' for s,p_ in CODE_GLOBS],
 'validation_metrics':{k:mv.get(k) for k in COMPONENTS+['action_sensitivity','weak_action','collapse','eff_rank_frac','std_min','offdiag_corr','n_params','ft_head','eval_seed']},
 'flags':{'any_collapse':int(row.get('any_collapse',0)),'any_weak_action':int(row.get('any_weak_action',0)),
          'n_invalid_seeds':int(row.get('n_invalid_seeds',0)),'winner_stable':bool(conf.get('winner_stable',True))},
 'gates':gates,'gates_failed':failed,'forced':bool(a.force and failed),
 'timestamps':{'config':mtime(cfg_lock),'checkpoint':mtime(ckpt),
               'pretrain_checkpoint':(mtime(pre_ckpt) if pre_ckpt.exists() else None),
               'normalizers':(mtime(norm) if norm.exists() else None),
               'ranking_table':mtime(ranking),
               'locked_at':{'epoch':time.time(),'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}},
 'selection':'Architecture chosen on DS01 source validation only, by the taskbook composite over '
             'clean/schema-drop/masked/long-horizon/calibration/SSL-latent components with collapse and '
             'weak-action penalties. The target machine was not read during the search. Script 45 verifies '
             'these hashes before the single target evaluation.'}
Path(a.out).parent.mkdir(parents=True,exist_ok=True)
Path(a.out).write_text(json.dumps(payload,indent=2,default=str),encoding='utf-8')
print(json.dumps({k:payload[k] for k in ('method','selection_stage','selected_seed','seeds','composite_mean','config','config_sha256',
                                         'checkpoint','checkpoint_sha256','normalizers_sha256','code_sha256','gates_failed','forced')},indent=2,default=str))
print(f'\nwrote {a.out} (frozen copies in {lockdir})')
