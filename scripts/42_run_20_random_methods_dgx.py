from _common import *
import argparse,json,subprocess,time,yaml
p=argparse.ArgumentParser()
p.add_argument('--manifest',default='configs/search_v2/manifest.json')
p.add_argument('--gpus',default='0,1,2,3,4,5,6,7')
p.add_argument('--out',default='outputs/random_search')
p.add_argument('--seeds',default='0,1,2')
p.add_argument('--dry-run',action='store_true')
a=p.parse_args(); methods=json.loads(Path(a.manifest).read_text()); seeds=[int(x) for x in a.seeds.split(',')]; gpus=a.gpus.split(',')
# 20 methods x N seeds of independent source-validation runs on DGX; the pipeline runner
# (scripts/61_run_all_spark.py) passes --seeds 0,1,2,3, i.e. four discovery seeds (80 runs).
# Slot-based pool: duplicate gpu ids (e.g. --gpus 0,0,0) pack several jobs on one GPU.
slots=list(enumerate(gpus))
queue=[(m,seed) for m in methods for seed in seeds]; procs=[]; Path(a.out).mkdir(parents=True,exist_ok=True)
while queue or procs:
    used={slot for _,_,slot,_ in procs}; free=[(i,g) for i,g in slots if i not in used]
    while queue and free:
        m,seed=queue.pop(0); slot,gpu=free.pop(0); out=str(Path(a.out)/m['name']/f'seed_{seed}')
        cmd=[sys.executable,'scripts/41_train_one_random_candidate.py','--config',m['config'],'--out',out,'--device',f'cuda:{gpu}','--seed',str(seed)]
        print(' '.join(cmd))
        if not a.dry_run: procs.append((subprocess.Popen(cmd),f"{m['name']}/seed_{seed}",slot,gpu))
    if a.dry_run:
        if not queue: break
        continue
    time.sleep(2); alive=[]
    for pr,name,slot,gpu in procs:
        if pr.poll() is None: alive.append((pr,name,slot,gpu))
        elif pr.returncode!=0: print('FAILED',name,pr.returncode)
    procs=alive
