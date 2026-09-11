from _common import *
import ast,compileall,json,subprocess,sys
root=ROOT; report={}
# Pass 1: compile every Python file
report['pass1_compileall']=all(compileall.compile_dir(str(root/d),quiet=1) for d in ['src','scripts','examples','tests','third_party/cnc_adapter'])
# Pass 2: AST/import hygiene and forbidden obvious target-search leakage in random selection scripts
issues=[]
for f in list((root/'scripts').glob('*.py'))+list((root/'src').rglob('*.py')):
 try: ast.parse(f.read_text())
 except Exception as e: issues.append(f'{f}: {e}')
# Every script that participates in choosing/locking the architecture must be target-blind.
for f in [root/'scripts/41_train_one_random_candidate.py',root/'scripts/43_rank_methods_validation_only.py',root/'scripts/44_lock_best_method.py',root/'scripts/64_confirm_top5.py',root/'scripts/_search_common.py']:
 txt=f.read_text()
 if 'target_all' in txt: issues.append(f'{f.name}: target_all referenced before locked test')
report['pass2_ast_and_leakage']={'ok':not issues,'issues':issues}
# Pass 3: protocol invariants from config and synthetic dataset audit
from cncjepa.config import load_config
from cncjepa.data import load_table,resample_dataframe,deterministic_group_split
cfg=load_config(root/'configs/smoke.yaml'); s=cfg['schema']; sp=deterministic_group_split(resample_dataframe(load_table(root/cfg['paths']['data']),cfg),cfg); tr=set(sp['source_train'][s['session']].astype(str)); va=set(sp['source_val'][s['session']].astype(str)); te=set(sp['source_test'][s['session']].astype(str)); inv={'source_target_distinct':s['source_machine']!=s['target_machine'],'17_sensors':len(s['sensors'])==17,'10_transfer_sensors':len(s['transfer_sensors'])==10,'split_disjoint':not(tr&va or tr&te or va&te),'target_runs':int(sp['target_all'][s['run']].nunique())==6}
report['pass3_protocol_invariants']={'ok':all(inv.values()),'checks':inv}; print(json.dumps(report,indent=2)); assert report['pass1_compileall'] and report['pass2_ast_and_leakage']['ok'] and report['pass3_protocol_invariants']['ok']; print('TRIPLE_REVIEW_OK')
