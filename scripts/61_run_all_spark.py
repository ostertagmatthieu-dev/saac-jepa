"""Phased single-GPU orchestrator for a DGX Spark (one GB10 GPU, cuda:0).
Stdlib only -- job subprocesses get the real (venv) interpreter via --python.
"""
import argparse, json, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERIAL_PHASES = {'p2_audits', 'p3fix_gate', 'p6_evals', 'p7_search', 'p9_reports'}
# A failure inside a GATE phase aborts the whole run: p2 gates the data/protocol audit, p3fix
# gates the corrected JEPA protocol. The taskbook forbids running the architecture search (p7)
# or any target evaluation before the P3-FIX gate passes.
GATE_PHASES = {'p2_audits', 'p3fix_gate'}
PHASE_ORDER = ['p2_audits', 'p3_core', 'p3fix_gate', 'p4_ablations', 'p5_baselines', 'p6_evals', 'p7_search', 'p8_adapt', 'p9_reports']


def sc(py, script, *args):
    return [py, f'scripts/{script}'] + [str(x) for x in args]


def J(name, cmd, deps=None):
    return {'name': name, 'cmd': cmd, 'deps': deps or []}


def build_jobs(cfg, py):
    ckpt = 'outputs/jepa_finetune/best.pt'
    jobs = {}

    jobs['p2_audits'] = [
        J(n, sc(py, f'{n}_{f}.py', '--config', cfg)) for n, f in [
            ('00', 'validate_dataset'), ('01', 'audit_sessions_channels'), ('02', 'build_protocol_splits'),
            ('03', 'resample_sensitivity_data'), ('04', 'fit_normalizers'), ('05', 'window_leakage_audit'),
            ('07', 'build_schema_overlap'), ('08', 'normalization_leakage_audit'),
        ]
    ]
    # 06 and 09 take no --config (06: corruption manifest; 09: power analysis, n=7 real target runs)
    jobs['p2_audits'].insert(6, J('06', sc(py, '06_generate_corruption_manifest.py')))
    jobs['p2_audits'].append(J('09', sc(py, '09_transfer_power_analysis.py', '--n', '7')))

    jobs['p3_core'] = [
        J('10', sc(py, '10_pretrain_jepa_from_scratch.py', '--config', cfg, '--out', 'outputs/jepa_pretrain', '--device', 'cuda:0')),
        J('12', sc(py, '12_train_schema_adaptive_jepa.py', '--config', cfg, '--device', 'cuda:0')),
        J('11', sc(py, '11_finetune_jepa_forecaster.py', '--config', cfg, '--pretrained', 'outputs/jepa_pretrain/best.pt',
                    '--out', 'outputs/jepa_finetune', '--device', 'cuda:0'), deps=['10']),
    ]

    # P3-FIX gate: diagnostics on the P3 checkpoints, the A/B/C scratch-vs-pretraining
    # experiment over matched seeds, and the protocol regression tests. Serial and gating.
    jobs['p3fix_gate'] = [
        J('62', sc(py, '62_p3fix_diagnostics.py', '--config', cfg, '--device', 'cuda:0')),
        J('63', sc(py, '63_p3fix_abc_seeds.py', '--config', cfg, '--seeds', '0,1,2,3,4', '--device', 'cuda:0'), deps=['62']),
        J('t63', [py, 'tests/test_p3fix.py'], deps=['63']),
    ]

    jobs['p4_ablations'] = [
        J(str(13 + i), sc(py, f'{13+i}_{f}.py', '--config', cfg, '--device', 'cuda:0')) for i, f in enumerate([
            'train_action_ablation', 'train_mask_policy_ablation', 'train_latent_weight_ablation',
            'train_vicreg_ablation', 'train_layernorm_ablation', 'train_horizon_aggregation_ablation', 'train_ema_ablation',
        ])
    ]

    baseline_scripts = [
        '20_train_supervised_dynamics_baselines', '21_train_masked_mae_baseline', '22_train_simmtm_style_baseline',
        '23_train_patchformer_style_baseline', '24_train_emit_style_baseline', '25_train_mmr_wavelet_style_baseline',
        '26_train_lomar_ts_style_baseline', '27_train_rssm_world_model_baseline', '28_train_forecasting_capacity_sweep',
    ]
    jobs['p5_baselines'] = [J(s[:2], sc(py, f'{s}.py', '--config', cfg, '--device', 'cuda:0')) for s in baseline_scripts]
    jobs['p5_baselines'].append(J('29', sc(py, '29_export_official_baseline_inputs.py', '--config', cfg)))

    eval_scripts = [
        '30_eval_jepa_multihorizon', '31_eval_transfer_ds01_to_ds03', '32_eval_per_channel_per_run',
        '33_eval_normalization_sensitivity', '34_eval_missing_sensor_schema', '35_eval_random_masks_anomalies',
        '36_eval_uncertainty_calibration', '37_eval_action_conditioning', '38_eval_cem_planning',
    ]
    jobs['p6_evals'] = [J(s[:2], sc(py, f'{s}.py', '--config', cfg, '--ckpt', ckpt, '--device', 'cuda:0')) for s in eval_scripts]

    # Architecture search V2: 20 candidates x 4 discovery seeds (80 jobs, packed 3-per-GPU),
    # validation-only ranking, top-5 confirmation to 5 seeds, then to 7 seeds because the
    # provisional winner changed under confirmation, lock, then the single target test.
    search_manifest = 'configs/search_v2/manifest.json'
    jobs['p7_search'] = [
        J('40', sc(py, '40_generate_20_random_methods.py', '--config', cfg)),
        J('42', sc(py, '42_run_20_random_methods_dgx.py', '--manifest', search_manifest, '--gpus', '0,0,0', '--seeds', '0,1,2,3'), deps=['40']),
        J('43', sc(py, '43_rank_methods_validation_only.py'), deps=['42']),
        J('64', sc(py, '64_confirm_top5.py', '--manifest', search_manifest, '--gpus', '0,0,0', '--top', '5', '--seeds', '0,1,2,3,4'), deps=['43']),
        # Seeds 5 and 6: script 64 runs only the missing seeds for the top-5 and re-ranks; this is
        # the "refuse to lock, add seeds" step of the paper's selection protocol.
        J('64b', sc(py, '64_confirm_top5.py', '--manifest', search_manifest, '--gpus', '0,0,0', '--top', '5', '--seeds', '0,1,2,3,4,5,6'), deps=['64']),
        J('44', sc(py, '44_lock_best_method.py'), deps=['64b']),
        J('45', sc(py, '45_test_locked_method_ds03.py', '--device', 'cuda:0'), deps=['44']),
    ]

    jobs['p8_adapt'] = [
        J('46', sc(py, '46_fewshot_target_adaptation.py', '--config', cfg, '--ckpt', ckpt, '--device', 'cuda:0')),
        J('47', sc(py, '47_online_causal_adaptation.py', '--config', cfg, '--ckpt', ckpt, '--device', 'cuda:0')),
        J('50', sc(py, '50_novelty_component_factorial.py', '--config', cfg, '--device', 'cuda:0')),
        J('56', sc(py, '56_eval_baseline_per_channel_run.py', '--config', cfg, '--ckpt', 'outputs/baselines_supervised/transformer/best.pt',
                    '--model', 'transformer', '--device', 'cuda:0')),
        J('58', sc(py, '58_source_group_cv.py', '--config', cfg)),
        J('59', sc(py, '59_target_run_bootstrap.py', '--csv', 'outputs/per_channel_run.csv')),
        J('57', sc(py, '57_sampling_rate_sensitivity_train_eval.py', '--config', cfg, '--device', 'cuda:0')),
        J('39', sc(py, '39_statistical_tests_n6.py', '--jepa', 'outputs/per_channel_run.csv', '--baseline', 'outputs/baseline_per_channel_run.csv'), deps=['56']),
    ]
    # 48_predict_any_input / 49_predict_variable_sensor_schema require --input with no default and no
    # upstream artifact produces one -- they are ad-hoc single-inference demos, not batch jobs. Excluded.

    jobs['p9_reports'] = [
        J('51', sc(py, '51_build_main_result_tables.py')),
        J('52', sc(py, '52_build_reviewer_response_matrix.py')),
        J('65', sc(py, '65_build_full_report.py'), deps=['51', '52']),
    ]
    return jobs


def write_status(status_path, status):
    status_path.write_text(json.dumps(status, indent=2))


def run_phase(phase, jobs, concurrency, continue_on_error, status, status_path, log_dir):
    log_dir.mkdir(parents=True, exist_ok=True)
    state = {j['name']: 'pending' for j in jobs}
    start_ts = {}
    running = []  # list of (Popen, name, start_time, logfile_handle)
    aborted = False

    def deps_ok(j):
        return all(state.get(d) == 'ok' for d in j['deps'])

    def deps_failed(j):
        return any(state.get(d) in ('failed', 'skipped') for d in j['deps'])

    while True:
        if not aborted:
            for j in jobs:
                if state[j['name']] != 'pending':
                    continue
                if len(running) >= concurrency:
                    break
                if deps_failed(j):
                    state[j['name']] = 'skipped'
                    status[phase][j['name']] = {'state': 'skipped', 'returncode': None, 'seconds': 0.0}
                    print(f'[{phase}] SKIP {j["name"]} (dependency failed/skipped)')
                    continue
                if not deps_ok(j):
                    continue
                log_path = log_dir / f'{j["name"]}.log'
                logf = open(log_path, 'w')
                print(f'[{phase}] START {j["name"]}: {" ".join(j["cmd"])}')
                p = subprocess.Popen(j['cmd'], cwd=str(ROOT), stdout=logf, stderr=subprocess.STDOUT)
                start_ts[j['name']] = time.time()
                state[j['name']] = 'running'
                status[phase][j['name']] = {'state': 'running', 'returncode': None, 'seconds': 0.0}
                running.append((p, j['name'], logf))
        else:
            for j in jobs:
                if state[j['name']] == 'pending':
                    state[j['name']] = 'skipped'
                    status[phase][j['name']] = {'state': 'skipped', 'returncode': None, 'seconds': 0.0}

        if not running and all(state[n] != 'pending' for n in state):
            break

        time.sleep(5)

        still_running = []
        for p, name, logf in running:
            rc = p.poll()
            if rc is None:
                still_running.append((p, name, logf))
                continue
            logf.close()
            elapsed = time.time() - start_ts[name]
            state[name] = 'ok' if rc == 0 else 'failed'
            status[phase][name] = {'state': state[name], 'returncode': rc, 'seconds': round(elapsed, 1)}
            print(f'[{phase}] END {name} rc={rc} state={state[name]} elapsed={elapsed:.1f}s')
            if rc != 0 and not continue_on_error:
                aborted = True
        running = still_running
        write_status(status_path, status)

    write_status(status_path, status)
    failed = any(state[n] == 'failed' for n in state)
    return state, failed


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--config', default='configs/real.yaml')
    p.add_argument('--phase', default='all')
    p.add_argument('--max-concurrent', type=int, default=3)
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--python', default=sys.executable)
    p.add_argument('--continue-on-error', action='store_true')
    a = p.parse_args()

    all_jobs = build_jobs(a.config, a.python)
    phases = PHASE_ORDER if a.phase == 'all' else [x.strip() for x in a.phase.split(',') if x.strip()]
    for ph in phases:
        if ph not in all_jobs:
            print(f'Unknown phase: {ph}', file=sys.stderr)
            sys.exit(2)

    if a.dry_run:
        for ph in phases:
            print(f'=== {ph} ===')
            for j in all_jobs[ph]:
                deps = f' (deps={j["deps"]})' if j['deps'] else ''
                print(f'  {j["name"]}{deps}: {" ".join(j["cmd"])}')
        return

    out_root = ROOT / 'outputs' / 'orchestrator'
    status_path = out_root / 'status.json'
    out_root.mkdir(parents=True, exist_ok=True)
    status = {ph: {} for ph in phases}

    any_failed = False
    for ph in phases:
        jobs = all_jobs[ph]
        concurrency = 1 if ph in SERIAL_PHASES else a.max_concurrent
        log_dir = out_root / ph
        print(f'\n########## PHASE {ph} (concurrency={concurrency}) ##########')
        state, failed = run_phase(ph, jobs, concurrency, a.continue_on_error, status, status_path, log_dir)
        if failed:
            any_failed = True
        if ph in GATE_PHASES and failed:
            print(f'{ph} is a GATE phase and had a failure -- aborting entire run.')
            print_summary(status)
            sys.exit(1)

    print_summary(status)
    if any_failed:
        sys.exit(1)
    print('ORCHESTRATOR_OK')


def print_summary(status):
    print('\n=== SUMMARY ===')
    print(f'{"job":<6}{"phase":<16}{"state":<10}{"seconds":>10}')
    for phase, jobs in status.items():
        for name, info in jobs.items():
            print(f'{name:<6}{phase:<16}{info["state"]:<10}{info["seconds"]:>10}')


if __name__ == '__main__':
    main()
