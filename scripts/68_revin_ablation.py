"""Paired RevIN ablation on the locked V1 method M03 (V2, RoboPAD).

Stages (run in this order):
  train      -- {M03 (control), M03_revin} x seeds, each through scripts/41 (SSL pretrain ->
                physical fine-tune -> validation bundle in the common eval space). Runs are
                SEQUENTIAL on one device by default: on the DGX Spark (GB10) the model already
                saturates the GPU at batch 128 and packing 3 slots costs ~20% (measured), so
                --slots>1 is kept only for multi-GPU hosts.
  summarize  -- mean +/- std per component for each arm, per-seed paired differences,
                paired stats (bootstrap CI; n=3 seeds -> the exact sign-flip p is coarse and
                said so). Writes summary.json + summary.md.
  ds03       -- EXPLICIT re-opening of the locked target test: zero-shot DS03 for every run of
                both arms with the exact protocol of scripts/45 (evaluate_jepa on target_all,
                model rebuilt from the run's own config.yaml). Writes ds03_test.json carrying a
                `declaration` field. Never used for selection; run it only after `summarize`
                shows the validation verdict.

Nothing here reads DS03 before the `ds03` stage. The control arm re-uses
configs/search_v2/M03.yaml verbatim (revin key absent => bitwise V1 code path).
"""
from _common import *
import argparse, json, subprocess, time, datetime
import numpy as np

CONTROL = 'configs/search_v2/M03.yaml'
TREATED = 'configs/revin/M03_revin.yaml'
ARMS = {'M03': CONTROL, 'M03_revin': TREATED}
COMPONENTS = ('clean_rmse', 'schema_drop_rmse', 'masked_rmse', 'long_horizon_rmse', 'calibration_penalty',
              'ssl_latent_val', 'action_sensitivity', 'eff_rank_frac', 'eval_space_anchor_rmse')
LOWER_IS_BETTER = {'clean_rmse', 'schema_drop_rmse', 'masked_rmse', 'long_horizon_rmse', 'calibration_penalty', 'ssl_latent_val'}


def run_dir(out, arm, seed): return Path(out) / arm / f'seed_{seed}'


def stage_train(a):
    seeds = [int(s) for s in a.seeds.split(',')]
    # interleave control/treated per seed so a partial run still yields complete pairs
    queue = [(arm, s) for s in seeds for arm in ('M03', 'M03_revin')]
    Path(a.out).mkdir(parents=True, exist_ok=True)
    procs = []; log = Path(a.out) / 'train_launcher.log'
    def launch(arm, seed):
        out = run_dir(a.out, arm, seed)
        if (out / 'val_metrics.json').exists() and not a.force:
            print(f'[skip] {arm}/seed_{seed} already has val_metrics.json'); return None
        cmd = [sys.executable, 'scripts/41_train_one_random_candidate.py', '--config', ARMS[arm], '--out', str(out), '--device', a.device, '--seed', str(seed)]
        if a.epochs: cmd += ['--epochs', str(a.epochs)]
        out.mkdir(parents=True, exist_ok=True); lf = (out / 'train.log').open('w', encoding='utf-8')
        line = f"[{datetime.datetime.now().isoformat(timespec='seconds')}] START {arm}/seed_{seed}: {' '.join(cmd)}"
        print(line); log.open('a', encoding='utf-8').write(line + '\n')
        if a.dry_run: lf.close(); return None
        return (subprocess.Popen(cmd, stdout=lf, stderr=subprocess.STDOUT), f'{arm}/seed_{seed}', time.time(), lf)
    failed = []
    while queue or procs:
        while queue and len(procs) < a.slots:
            arm, seed = queue.pop(0); p = launch(arm, seed)
            if p is not None: procs.append(p)
        if a.dry_run and not queue: break
        time.sleep(5); alive = []
        for pr, name, t0, lf in procs:
            if pr.poll() is None: alive.append((pr, name, t0, lf)); continue
            lf.close(); msg = f"[{datetime.datetime.now().isoformat(timespec='seconds')}] END {name} rc={pr.returncode} ({(time.time()-t0)/60:.1f} min)"
            print(msg); log.open('a', encoding='utf-8').write(msg + '\n')
            if pr.returncode != 0: failed.append(name)
        procs = alive
    if failed: raise SystemExit(f'FAILED runs: {failed}')


def _load_runs(out, seeds):
    runs = {}
    for arm in ARMS:
        for s in seeds:
            f = run_dir(out, arm, s) / 'val_metrics.json'
            if f.exists(): runs[(arm, s)] = json.loads(f.read_text(encoding='utf-8'))
    return runs


def _f(v):
    try: return None if v is None else float(v)
    except (TypeError, ValueError): return None


def _mean_std(v):
    v = np.asarray([x for x in v if x is not None and np.isfinite(x)], float)
    return (float(v.mean()), float(v.std(ddof=1)) if len(v) > 1 else float('nan'), int(len(v))) if len(v) else (float('nan'), float('nan'), 0)


def stage_summarize(a):
    from cncjepa.metrics import paired_stats
    seeds = [int(s) for s in a.seeds.split(',')]; runs = _load_runs(a.out, seeds)
    if not runs: raise SystemExit(f'no val_metrics.json under {a.out}')
    per_arm = {}
    for arm in ARMS:
        rows = [runs[(arm, s)] for s in seeds if (arm, s) in runs]
        per_arm[arm] = {'n_runs': len(rows), 'seeds': [s for s in seeds if (arm, s) in runs],
                        'invalid': [r['seed'] for r in rows if r.get('invalid')],
                        'invalid_reasons': {str(r['seed']): r.get('invalid_reasons') for r in rows if r.get('invalid')},
                        'collapse': [int(r.get('collapse', 0)) for r in rows],
                        # which sub-criterion of trainers.latent_health fired (std_min<0.05 is in raw latent units and
                        # therefore input-scale dependent; eff_rank_frac<0.10 is scale-free)
                        'collapse_detail': {str(r['seed']): {'ssl_std_min': _f(r['detail'].get('ssl_latent_health', {}).get('zpred_std_min')),
                                                              'ssl_eff_rank_frac': _f(r['detail'].get('ssl_latent_health', {}).get('zpred_eff_rank_frac')),
                                                              'ft_std_min': _f(r['detail'].get('ft_latent_health', {}).get('zpred_std_min')),
                                                              'ft_eff_rank_frac': _f(r['detail'].get('ft_latent_health', {}).get('zpred_eff_rank_frac')),
                                                              'ssl_collapse': int(r.get('ssl_collapse', 0)), 'ft_collapse': int(r.get('ft_collapse', 0))} for r in rows},
                        'weak_action': [int(r.get('weak_action', 0)) for r in rows],
                        'n_params': rows[0].get('n_params') if rows else None,
                        'components': {k: dict(zip(('mean', 'std', 'n'), _mean_std([r.get(k) for r in rows]))) for k in COMPONENTS},
                        'ds01_nll_modelspace': dict(zip(('mean', 'std', 'n'), _mean_std([r['detail']['clean'].get('nll') for r in rows]))),
                        'coverage_90': dict(zip(('mean', 'std', 'n'), _mean_std([r['detail']['coverage'].get('0.9') for r in rows]))),
                        'total_seconds': dict(zip(('mean', 'std', 'n'), _mean_std([r.get('total_seconds') for r in rows])))}
    paired_seeds = [s for s in seeds if ('M03', s) in runs and ('M03_revin', s) in runs]
    paired = {}
    for k in COMPONENTS:
        c = [runs[('M03', s)].get(k) for s in paired_seeds]; t = [runs[('M03_revin', s)].get(k) for s in paired_seeds]
        ok = [i for i in range(len(c)) if c[i] is not None and t[i] is not None and np.isfinite(c[i]) and np.isfinite(t[i])]
        c = [c[i] for i in ok]; t = [t[i] for i in ok]
        if len(c) >= 2:
            st = paired_stats(t, c)   # treated - control
            wins = sum(1 for x, y in zip(t, c) if (x < y if k in LOWER_IS_BETTER else x > y))
            paired[k] = {'diff_treated_minus_control': [float(x - y) for x, y in zip(t, c)], 'mean_diff': st['mean_diff'],
                         'bootstrap_95': st['bootstrap_95'], 'wilcoxon_p': st['wilcoxon_p'], 'exact_signflip_p': st['exact_signflip_p'],
                         'revin_wins_seeds': f'{wins}/{len(c)}', 'lower_is_better': k in LOWER_IS_BETTER}
        else: paired[k] = {'note': f'{len(c)} valid pairs; no paired statistic'}
    headline = [k for k in ('clean_rmse', 'schema_drop_rmse', 'masked_rmse', 'long_horizon_rmse') if k in paired and 'mean_diff' in paired[k]]
    verdict_wins = [k for k in headline if paired[k]['mean_diff'] < 0]
    verdict = {'headline_components': headline, 'revin_better_on': verdict_wins,
               'revin_better_on_all_headline': bool(headline) and len(verdict_wins) == len(headline),
               'caveat': f'n={len(paired_seeds)} paired seeds: the exact sign-flip p cannot go below {1/(2**max(1,len(paired_seeds))):.3f}; read the bootstrap CI and the per-seed wins, not p-values.'}
    rep = {'ablation': 'M03 vs M03 + RevIN (JEPA-internal, presence-aware, no affine)', 'control_config': CONTROL, 'treated_config': TREATED,
           'metric_space': 'fixed source_zscore reference space (scripts/41 + _val_bundle); NLL/coverage model-space', 'seeds': seeds,
           'paired_seeds': paired_seeds, 'arms': per_arm, 'paired': paired, 'verdict_validation_only': verdict,
           'note': 'DS01 source_val only. DS03 is not read by this stage.', 'generated': datetime.datetime.now().isoformat(timespec='seconds')}
    Path(a.out, 'summary.json').write_text(json.dumps(rep, indent=2, default=str), encoding='utf-8')
    # markdown
    L = ['# Ablation RevIN appariée — M03 vs M03+RevIN (validation DS01, espace commun)', '',
         f"Seeds : {seeds} ; paires complètes : {paired_seeds}. {verdict['caveat']}", '',
         '| composante | M03 (contrôle) | M03+RevIN | Δ (RevIN−ctrl) | IC95 bootstrap | RevIN gagne |', '|---|---|---|---|---|---|']
    for k in COMPONENTS:
        c = per_arm['M03']['components'][k]; t = per_arm['M03_revin']['components'][k]; p = paired.get(k, {})
        d = f"{p['mean_diff']:+.4f}" if 'mean_diff' in p else '—'; ci = f"[{p['bootstrap_95'][0]:+.4f}, {p['bootstrap_95'][2]:+.4f}]" if 'bootstrap_95' in p else '—'
        fmt=lambda m: f"{m['mean']:.4f} ± {m['std']:.4f}" if np.isfinite(m['std']) else f"{m['mean']:.4f} (n={m['n']})"
        L.append(f"| {k} | {fmt(c)} | {fmt(t)} | {d} | {ci} | {p.get('revin_wins_seeds','—')} |")
    L += ['', f"Invalides : contrôle {per_arm['M03']['invalid']} ; RevIN {per_arm['M03_revin']['invalid']}. Collapse : contrôle {per_arm['M03']['collapse']} ; RevIN {per_arm['M03_revin']['collapse']}.",
          '', '| porte collapse (zpred) | seed | std_min SSL | eff_rank SSL | std_min FT | eff_rank FT | ssl/ft collapse |', '|---|---|---|---|---|---|---|']
    for arm in ARMS:
        for sd, cd in per_arm[arm]['collapse_detail'].items():
            g = lambda v: '—' if v is None else f'{v:.3f}'
            L.append(f"| {arm} | {sd} | {g(cd['ssl_std_min'])} | {g(cd['ssl_eff_rank_frac'])} | {g(cd['ft_std_min'])} | {g(cd['ft_eff_rank_frac'])} | {cd['ssl_collapse']}/{cd['ft_collapse']} |")
    L += ['', 'Seuils (trainers.latent_health) : std_min < 0,05 (unités brutes du latent, dépend de l\'échelle des entrées) ou eff_rank_frac < 0,10 (sans échelle).',
          f"NLL DS01 (espace modèle) : contrôle {per_arm['M03']['ds01_nll_modelspace']['mean']:.3f} ; RevIN {per_arm['M03_revin']['ds01_nll_modelspace']['mean']:.3f}. Couverture 90 % : {per_arm['M03']['coverage_90']['mean']:.3f} vs {per_arm['M03_revin']['coverage_90']['mean']:.3f}.",
          '', f"**Verdict validation** : RevIN meilleur sur {verdict['revin_better_on']} parmi {headline}." + (' → critère DS03 rempli (stage `ds03` à déclarer).' if verdict['revin_better_on_all_headline'] else ' → DS03 reste scellé.')]
    Path(a.out, 'summary.md').write_text('\n'.join(L) + '\n', encoding='utf-8')
    print('\n'.join(L))


def stage_ds03(a):
    import torch
    from cncjepa.config import load_config
    from cncjepa.pipeline import prepare, loaders_from_ds
    from cncjepa.checkpoint import load_jepa_checkpoint
    from cncjepa.trainers import evaluate_jepa
    from cncjepa.factory import build_forecaster
    from cncjepa.trainers import evaluate_forecaster
    from cncjepa.utils import device_from_arg
    seeds = [int(s) for s in a.seeds.split(',')]; dev = device_from_arg(a.device)
    declaration = (f"DS03 (target machine) re-opened on {datetime.date.today().isoformat()} for the paired RevIN ablation (V2). "
                   "V1 lock (outputs/random_search/LOCKED_BEST.json) already consumed the single declared test; this is the second, "
                   "declared, opening. Both arms are evaluated on every seed with no selection on DS03; the validation verdict "
                   "(summary.json) was fixed before this stage ran.")
    rep = {'declaration': declaration, 'protocol': 'scripts/45: evaluate_jepa(finetune/best.pt, target_all), model rebuilt from the run config.yaml, source_train normalizers', 'runs': {}}
    frame = None
    for arm in ARMS:
        for s in seeds:
            rd = run_dir(a.out, arm, s); ck = rd / 'finetune' / 'best.pt'
            if not ck.exists(): print(f'[ds03] missing {ck}'); continue
            cfg = load_config(rd / 'config.yaml')
            frame, split, ds, sn, an = prepare(cfg, training_mask=False, resampled_df=frame)
            ld = loaders_from_ds(ds, cfg, False)
            m, obj = load_jepa_checkpoint(ck, cfg, 'cpu'); m.to(dev).eval()
            met, raw = evaluate_jepa(m, ld['target_all'], dev)
            met.pop('per_horizon', None)
            rep['runs'][f'{arm}/seed_{s}'] = {'arm': arm, 'seed': s, 'revin_enabled': bool((cfg['model'].get('revin') or {}).get('enabled', False)),
                                              'target_ds03': met, 'n_windows': int(raw['y'].shape[0]), 'load_audit': {k: obj['load_audit'].get(k) for k in ('weights_changed', 'missing_keys', 'unexpected_keys')}}
            print(f"[ds03] {arm}/seed_{s}: rmse={met['rmse']:.4f} r2={met['r2']:+.4f} nll={met['nll']:.3f}")
            if 'persistence' not in rep:
                pm = build_forecaster('persistence', cfg).to(dev); pmet, _ = evaluate_forecaster(pm, ld['target_all'], dev); pmet.pop('per_horizon', None)
                rep['persistence'] = pmet
    for arm in ARMS:
        r = [v['target_ds03']['rmse'] for k, v in rep['runs'].items() if v['arm'] == arm]
        rep[f'{arm}_rmse_mean_std_n'] = list(_mean_std(r))
    pairs = [(rep['runs'][f'M03_revin/seed_{s}']['target_ds03']['rmse'] - rep['runs'][f'M03/seed_{s}']['target_ds03']['rmse']) for s in seeds
             if f'M03/seed_{s}' in rep['runs'] and f'M03_revin/seed_{s}' in rep['runs']]
    rep['paired_diff_revin_minus_control'] = pairs
    rep['reference'] = {'V1_locked_M03_ds03_rmse': 0.546, 'official_patchtst': 0.503, 'official_itransformer': 0.498, 'note': 'see outputs/random_search/locked_ds03_test.json and outputs/official_baselines/*/metrics.json'}
    Path(a.out, 'ds03_test.json').write_text(json.dumps(rep, indent=2, default=str), encoding='utf-8')
    print(json.dumps({k: rep[k] for k in rep if k != 'runs'}, indent=2, default=str))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('stage', choices=['train', 'summarize', 'ds03'])
    p.add_argument('--out', default='outputs/revin_ablation')
    p.add_argument('--seeds', default='0,1,2')
    p.add_argument('--device', default='cuda:0')
    p.add_argument('--slots', type=int, default=1, help='concurrent runs on --device (1 = sequential; packing costs ~20%% on a GB10)')
    p.add_argument('--epochs', type=int, default=None, help='passthrough to scripts/41 --epochs (smoke only)')
    p.add_argument('--force', action='store_true', help='re-run even if val_metrics.json exists')
    p.add_argument('--dry-run', action='store_true')
    a = p.parse_args()
    {'train': stage_train, 'summarize': stage_summarize, 'ds03': stage_ds03}[a.stage](a)
