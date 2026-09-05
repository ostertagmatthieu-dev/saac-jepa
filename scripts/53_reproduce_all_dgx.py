from _common import *
import argparse,subprocess
p=argparse.ArgumentParser(); p.add_argument('--config',default='configs/base.yaml'); p.add_argument('--gpus',default='0,1,2,3,4,5,6,7'); p.add_argument('--execute',action='store_true'); a=p.parse_args(); cmds=[
 f'python scripts/00_validate_dataset.py --config {a.config}', f'python scripts/02_build_protocol_splits.py --config {a.config}',
 f'python scripts/10_pretrain_jepa_from_scratch.py --config {a.config} --device cuda:0', f'python scripts/11_finetune_jepa_forecaster.py --config {a.config} --device cuda:0',
 f'python scripts/20_train_supervised_dynamics_baselines.py --config {a.config} --device cuda:1', f'python scripts/21_train_masked_mae_baseline.py --config {a.config} --device cuda:2',
 f'python scripts/22_train_simmtm_style_baseline.py --config {a.config} --device cuda:3', f'python scripts/23_train_patchformer_style_baseline.py --config {a.config} --device cuda:4',
 f'python scripts/24_train_emit_style_baseline.py --config {a.config} --device cuda:5', f'python scripts/25_train_mmr_wavelet_style_baseline.py --config {a.config} --device cuda:6',
 f'python scripts/26_train_lomar_ts_style_baseline.py --config {a.config} --device cuda:7', f'python scripts/40_generate_20_random_methods.py --config {a.config}',
 f'python scripts/42_run_20_random_methods_dgx.py --gpus {a.gpus}', 'python scripts/43_rank_methods_validation_only.py', 'python scripts/44_lock_best_method.py', 'python scripts/45_test_locked_method_ds03.py']
for c in cmds: print(c); subprocess.run(c,shell=True,check=True) if a.execute else None
