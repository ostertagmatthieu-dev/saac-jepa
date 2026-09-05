"""Train the OFFICIAL PatchTST / iTransformer / SimMTM repos on our audited export.

The point of this script is that the three baselines are the AUTHORS' code, pinned to a
commit, driven through their own run scripts -- not our reimplementations (those are
scripts 22-26, and their README explicitly disclaims exact reproduction).  Only two
things are substituted: the dataset class (session-bounded windows + our source_train
z-scoring, see third_party/cnc_adapter/cnc_dataset.py) and the evaluation, which scores
the horizons {1,2,4,8,16} in z-units the way our own protocol does.

Stages per method
    train    -> the repo's own run script, writing a checkpoint under our out dir
    predict  -> third_party/cnc_adapter/predict_cnc.py, once for source_test and once
                for the DS03 target_all zero-shot pass
    convert  -> outputs/official_baselines/<method>/metrics.json in our format

SimMTM is self-supervised, so its train stage is two commands (pretrain, then finetune);
the finetune auto-loads <pretrain_checkpoints>/CNC/ckpt_best.pth.

Usage
    python scripts/66_run_official_baselines.py --dry-run
    python scripts/66_run_official_baselines.py --verify           # CPU only, no training
    python scripts/66_run_official_baselines.py --device cuda:0    # the real run
    python scripts/66_run_official_baselines.py --methods patchtst --channels 17
"""

from _common import *  # noqa: F401,F403  (puts src/ on sys.path, repo convention)

import argparse
import json
import os
import shlex
import subprocess
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
THIRD_PARTY = ROOT / "third_party"
ADAPTER = THIRD_PARTY / "cnc_adapter"
EXPORT_DIR = ROOT / "outputs" / "official_baseline_export"
NORMALIZERS = ROOT / "outputs" / "normalizers.json"
OUT_ROOT = ROOT / "outputs" / "official_baselines"

# Protocol constants -- these mirror configs/real.yaml and must not drift from it.
SEQ_LEN = 32          # protocol.context_len
PRED_LEN = 16         # max(protocol.horizons)
LABEL_LEN = 16        # decoder start token; encoder-only models ignore it
HORIZONS = [1, 2, 4, 8, 16]   # protocol.horizons -- the steps we actually score
BATCH_SIZE = 128      # train.batch_size
TRAIN_EPOCHS = 100    # train.epochs
PATIENCE = 15         # train.early_stop_patience
SEED = 20260820       # cfg.seed

SENSORS = [
    "spindle_current", "spindle_torque", "spindle_power",
    "x_current", "x_torque", "y_current", "y_torque",
    "z_current", "z_torque", "z_power",
    "spindle_motor_temp", "x_motor_temp", "y_motor_temp", "z_motor_temp",
    "spindle_dc_voltage", "spindle_mod_depth", "ambient_temp",
]
ACTIONS = ["a_spindle_speed", "a_feed_x", "a_feed_y", "a_feed_z"]
TRANSFER_SENSORS = SENSORS[:10]   # the 10 channels DS03 also reports

EXPECTED_WINDOWS = {   # independently recomputed in --verify from the CSVs
    "source_train": 18267, "source_val": 3423, "source_test": 5189, "target_all": 2457,
}


# ---------------------------------------------------------------- method specs
def method_specs(channels, out_root, device, epochs, batch_size, patience):
    """Complete argument dicts per method.

    Every argument the repo's Model class might read is present, because the same dict
    both (a) builds the CLI for the repo's run script and (b) is re-hydrated into an
    argparse.Namespace by predict_cnc.py.  Building both from one source makes it
    impossible for the trained model and the evaluated model to disagree.

    Values are the repos' own defaults except where the protocol forces a change; every
    deviation is listed in outputs/official_baselines/PREP_NOTES.md.
    """
    C = channels
    # CUDA_VISIBLE_DEVICES (env_for) renumbers the requested device to 0 inside the
    # child process, so --gpu is always 0 regardless of which physical GPU was asked for.
    gpu = 0
    use_gpu = device.startswith("cuda")
    common = dict(
        data="CNC", root_path=str(EXPORT_DIR), data_path="source_train.csv",
        features="M", target=SENSORS[0], freq="s", embed="timeF",
        seq_len=SEQ_LEN, label_len=LABEL_LEN, pred_len=PRED_LEN,
        enc_in=C, dec_in=C, c_out=C,
        num_workers=4, itr=1, train_epochs=epochs, batch_size=batch_size,
        patience=patience, des="cnc", loss="mse",
        use_amp=False, use_gpu=use_gpu, gpu=gpu, use_multi_gpu=False, devices="0",
        output_attention=False, do_predict=False, distil=True, factor=1,
        moving_avg=25, activation="gelu", d_layers=1,
    )

    patchtst = dict(
        common,
        model="PatchTST", model_id=f"CNC_{SEQ_LEN}_{PRED_LEN}_c{C}",
        is_training=1, random_seed=SEED,
        # PatchTST's default patch_len=16/stride=8 was tuned for a 336-step lookback; at
        # seq_len=32 it yields only 3 patches. 8/4 gives 7 (+1 with padding_patch=end),
        # which is the closest match to our own model's patch_len=4 granularity.
        patch_len=8, stride=4, padding_patch="end",
        revin=1, affine=0, subtract_last=0,          # RevIN: per-window, no cross-split leak
        decomposition=0, kernel_size=25, individual=0, embed_type=0,
        d_model=128, n_heads=8, e_layers=3, d_ff=256,
        dropout=0.2, fc_dropout=0.2, head_dropout=0.0,
        learning_rate=1e-4, lradj="TST", pct_start=0.3, test_flop=False,
        checkpoints=str(out_root / "patchtst" / "ckpt") + os.sep,
    )

    itransformer = dict(
        common,
        model="iTransformer", model_id=f"CNC_{SEQ_LEN}_{PRED_LEN}_c{C}",
        is_training=1,
        d_model=128, n_heads=8, e_layers=3, d_ff=256, dropout=0.1,
        learning_rate=1e-4, lradj="type1",
        use_norm=1,                 # non-stationary instance norm: per-window, no leak
        class_strategy="projection", exp_name="MTSF", channel_independence=False,
        inverse=False, efficient_training=False, partial_start_index=0,
        target_root_path=str(EXPORT_DIR), target_data_path="source_test.csv",
        checkpoints=str(out_root / "itransformer" / "ckpt") + os.sep,
    )

    simmtm = dict(
        common,
        model="SimMTM", model_id=f"CNC_{SEQ_LEN}_{PRED_LEN}_c{C}",
        is_training=1, task_name="finetune",
        d_model=32, n_heads=8, e_layers=3, d_ff=64, dropout=0.1,
        fc_dropout=0.0, head_dropout=0.1, individual=0,
        learning_rate=1e-4, lradj="type1", pct_start=0.3,
        patch_len=8, stride=8,      # unused by models/SimMTM.py (point-wise, not patched)
        top_k=5, num_kernels=3, seasonal_patterns="Monthly", select_channels=1,
        lm=3, positive_nums=3, rbtp=1, temperature=0.2,
        masked_rule="geometric", mask_rate=0.5,
        checkpoints=str(out_root / "simmtm" / "ckpt") + os.sep,
        pretrain_checkpoints=str(out_root / "simmtm" / "pretrain_ckpt") + os.sep,
        transfer_checkpoints="ckpt_best.pth", load_checkpoints=None,
    )

    return {
        "patchtst": dict(kind="patchtst", repo=THIRD_PARTY / "PatchTST" / "PatchTST_supervised",
                         entry="run_longExp.py", args=patchtst, stages=["train"]),
        "itransformer": dict(kind="itransformer", repo=THIRD_PARTY / "iTransformer",
                             entry="run.py", args=itransformer, stages=["train"]),
        "simmtm": dict(kind="simmtm", repo=THIRD_PARTY / "SimMTM" / "SimMTM_Forecasting",
                       entry="run.py", args=simmtm, stages=["pretrain", "train"]),
    }


BOOL_STORE_TRUE = {"use_amp", "output_attention", "do_predict", "test_flop",
                   "use_multi_gpu", "inverse"}

# argparse arguments the repos declare as `type=bool`. argparse calls bool() on the
# RAW STRING, so "--flag False" yields bool("False") == True -- passing these on the
# command line can only ever turn them ON. They are therefore never emitted; the repo's
# own default stands, and TYPE_BOOL_TRAP records what that default is so a mismatch is
# caught loudly instead of silently ignored.
#   use_gpu             -> CPU/GPU is chosen via CUDA_VISIBLE_DEVICES in env_for()
#   channel_independence-> iTransformer, default False
#   efficient_training  -> iTransformer, default False
TYPE_BOOL_TRAP = {"channel_independence": False, "efficient_training": False}
SKIP_ON_CLI = {"kind", "use_gpu"} | set(TYPE_BOOL_TRAP)


def to_argv(args, overrides=None):
    """Render an args dict as the repo's CLI. store_true flags appear only when set;
    store_false flags (--distil) are never emitted so their True default stands."""
    a = dict(args)
    a.update(overrides or {})
    for k, default in TYPE_BOOL_TRAP.items():
        if k in a and bool(a[k]) != default:
            raise ValueError(
                f"{k}={a[k]!r} cannot be set from the CLI: the repo declares it as "
                f"type=bool, so any value parses as True. Edit the repo default or "
                f"patch run.py if this baseline really needs {k}={a[k]!r}."
            )
    argv = []
    for k, v in a.items():
        if k in SKIP_ON_CLI or v is None:
            continue
        if k == "distil":
            continue          # action='store_false', default True -- never pass it
        if k in BOOL_STORE_TRUE:
            if v:
                argv.append(f"--{k}")
            continue
        argv += [f"--{k}", str(int(v) if isinstance(v, bool) else v)]
    return argv


def stage_commands(name, spec, python):
    """(label, argv, cwd) per training stage."""
    cmds = []
    for stage in spec["stages"]:
        if name == "simmtm" and stage == "pretrain":
            ov = {"task_name": "pretrain", "is_training": 1,
                  # SimMTM's own scripts pretrain at a higher lr than they finetune, but 1e-3
                  # diverged to NaN on our 32-step windows (run of 27/08); 3e-4 is the retry value.
                  "learning_rate": 3e-4,
                  "train_epochs": min(50, spec["args"]["train_epochs"])}
        elif name == "simmtm":
            ov = {"task_name": "finetune", "is_training": 1}
        else:
            ov = {}
        cmds.append((f"{name}:{stage}",
                     [python, "-u", spec["entry"]] + to_argv(spec["args"], ov),
                     spec["repo"]))
    return cmds


def env_for(channels, test_split, impute, device="cpu", extra=None):
    e = dict(os.environ)
    e.update({
        "CNC_EXPORT_DIR": str(EXPORT_DIR),
        "CNC_NORMALIZERS": str(NORMALIZERS),
        "CNC_CHANNELS": str(channels),
        "CNC_TEST_SPLIT": test_split,
        "CNC_IMPUTE": impute,
        "PYTHONPATH": os.pathsep.join(filter(None, [str(THIRD_PARTY), os.environ.get("PYTHONPATH", "")])),
        # Sole CPU/GPU switch -- see SKIP_ON_CLI. "" hides every device, so the repos'
        # torch.cuda.is_available() guard puts them on CPU.
        "CUDA_VISIBLE_DEVICES": device.split(":")[-1] if device.startswith("cuda") else "",
    })
    e.update(extra or {})
    return e


# ------------------------------------------------------------------- metrics
def _rmse(d):
    return float(np.sqrt(np.nanmean(d * d))) if d.size else float("nan")


def subset_metrics(pred, true, mask, col_idx, step_idx):
    """RMSE/MAE over the selected channels and prediction steps, ignoring absent truth.

    Matches cncjepa.metrics.rmse/mae: one equally weighted entry per
    (window, horizon, channel), NaN-masked -- not a mean of per-channel RMSEs.
    """
    p = pred[:, step_idx][:, :, col_idx]
    t = true[:, step_idx][:, :, col_idx]
    m = mask[:, step_idx][:, :, col_idx]
    if not m.any():
        return {"rmse": None, "mae": None, "n": 0}
    d = np.where(m, p - t, np.nan)
    return {"rmse": _rmse(d), "mae": float(np.nanmean(np.abs(d))), "n": int(m.sum())}


def compute_metrics(npz_path, channels):
    z = np.load(npz_path, allow_pickle=True)
    pred, true, mask = z["pred"], z["true"], z["mask"].astype(bool)
    cols = [str(c) for c in z["columns"]]

    sensors17 = [cols.index(c) for c in SENSORS]
    transfer10 = [cols.index(c) for c in TRANSFER_SENSORS]
    proto_steps = [h - 1 for h in HORIZONS]     # horizon h -> prediction index h-1
    all_steps = list(range(pred.shape[1]))

    def block(col_idx):
        out = subset_metrics(pred, true, mask, col_idx, proto_steps)
        out["per_horizon"] = {
            str(h): subset_metrics(pred, true, mask, col_idx, [h - 1]) for h in HORIZONS
        }
        out["all_%d_steps" % pred.shape[1]] = subset_metrics(pred, true, mask, col_idx, all_steps)
        out["per_channel"] = {
            cols[c]: subset_metrics(pred, true, mask, [c], proto_steps) for c in col_idx
        }
        return out

    res = {
        "n_windows": int(pred.shape[0]),
        "channels_in_model": channels,
        "column_order": cols,
        "scored_horizons": HORIZONS,
        "sensors_17": block(sensors17),
        "transfer_10": block(transfer10),
    }
    if channels == 21:
        # Reported for completeness only: the 4 action channels are model OUTPUTS in the
        # 21->21 setup but are not part of our headline sensor-forecasting metric.
        res["actions_4"] = block([cols.index(c) for c in ACTIONS])
    return res


# ----------------------------------------------------------------- execution
ENV_KEYS_TO_PRINT = ("CNC_EXPORT_DIR", "CNC_NORMALIZERS", "CNC_CHANNELS",
                     "CNC_TEST_SPLIT", "CNC_IMPUTE", "CUDA_VISIBLE_DEVICES", "PYTHONPATH")


def run(cmd, cwd, env, dry, log=None):
    # The env prefix is part of the command: without CNC_* the adapter silently falls
    # back to defaults, and without CUDA_VISIBLE_DEVICES the CPU/GPU choice is lost.
    prefix = " ".join(f"{k}={shlex.quote(env[k])}" for k in ENV_KEYS_TO_PRINT if k in env)
    printable = (f"cd {shlex.quote(str(cwd))} && {prefix} "
                 + " ".join(shlex.quote(c) for c in map(str, cmd)))
    if dry:
        print(printable + "\n")
        return 0
    print(f"\n$ {printable}\n", flush=True)
    t0 = time.time()
    with subprocess.Popen(cmd, cwd=str(cwd), env=env, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, text=True, bufsize=1) as p:
        lines = []
        for line in p.stdout:
            sys.stdout.write(line)
            lines.append(line)
        rc = p.wait()
    if log:
        Path(log).parent.mkdir(parents=True, exist_ok=True)
        Path(log).write_text("".join(lines))
    print(f"[exit {rc} in {time.time()-t0:.0f}s]", flush=True)
    return rc


def find_checkpoint(root):
    hits = sorted(Path(root).rglob("checkpoint.pth"))
    if not hits:
        raise FileNotFoundError(f"no checkpoint.pth under {root}")
    if len(hits) > 1:
        raise RuntimeError(f"ambiguous checkpoints under {root}: {hits}")
    return hits[0]


# -------------------------------------------------------------------- verify
def verify(specs, channels, impute, python):
    """CPU-only preflight. Proves the adapter is session-correct before any GPU time."""
    import pandas as pd

    sys.path.insert(0, str(THIRD_PARTY))
    from cnc_adapter.cnc_dataset import Dataset_CNC, GROUP_KEYS, TIMESTAMP

    ok = True
    # Self-describing: --verify overwrites this file, so record which configuration
    # produced it rather than leaving the reader to guess.
    report = {"config": {"channels": channels, "impute": impute,
                         "seq_len": SEQ_LEN, "label_len": LABEL_LEN, "pred_len": PRED_LEN,
                         "export_dir": str(EXPORT_DIR), "normalizers": str(NORMALIZERS)}}
    span = SEQ_LEN + PRED_LEN

    print("=" * 72)
    print("1. window inventory: session-bounded vs naive continuous-series")
    for split in EXPECTED_WINDOWS:
        df = pd.read_csv(EXPORT_DIR / f"{split}.csv")
        sizes = df.groupby(GROUP_KEYS, sort=False, dropna=False).size()
        expect = int(sum(max(0, L - span + 1) for L in sizes))
        naive = len(df) - span + 1        # what upstream Dataset_Custom would produce
        phantom = naive - expect
        good = expect == EXPECTED_WINDOWS[split]
        ok &= good
        report[split] = {"windows": expect, "naive_windows": naive,
                         "cross_session_windows_avoided": phantom, "matches_expected": good}
        print(f"  {split:<13} sessions={len(sizes):<3} windows={expect:<6} "
              f"naive={naive:<6} phantom_avoided={phantom:<5} {'OK' if good else 'MISMATCH'}")

    print("=" * 72)
    print("2. Dataset_CNC contract + no cross-session / non-contiguous windows")
    for flag, split in [("train", "source_train"), ("val", "source_val"),
                        ("test", "source_test"), ("test", "target_all")]:
        os.environ.update({"CNC_EXPORT_DIR": str(EXPORT_DIR), "CNC_NORMALIZERS": str(NORMALIZERS),
                           "CNC_CHANNELS": str(channels), "CNC_TEST_SPLIT": split,
                           "CNC_IMPUTE": impute})
        ds = Dataset_CNC(flag=flag, size=[SEQ_LEN, LABEL_LEN, PRED_LEN])
        n_ok = len(ds) == EXPECTED_WINDOWS[split]
        ok &= n_ok
        x, y, xm, ym = ds[0]
        shapes_ok = (x.shape == (SEQ_LEN, channels) and y.shape == (LABEL_LEN + PRED_LEN, channels)
                     and xm.shape == (SEQ_LEN, 0) and ym.shape == (LABEL_LEN + PRED_LEN, 0))
        ok &= shapes_ok

        # Independent re-derivation straight from the CSV: every window's 48 rows must
        # share one session AND be 1 s apart. A boundary-crossing window fails both.
        df = pd.read_csv(EXPORT_DIR / f"{split}.csv")
        groups = [g.sort_values(TIMESTAMP) for _, g in df.groupby(GROUP_KEYS, sort=False, dropna=False)
                  if len(g) >= span]
        rng = np.random.default_rng(0)
        probe = rng.choice(len(ds), size=min(400, len(ds)), replace=False)
        bad_sess = bad_time = 0
        for i in probe:
            gi, s = ds.index[int(i)]
            w = groups[gi].iloc[s:s + span]
            if w["session_id"].nunique(dropna=False) != 1 or w["machine_id"].nunique() != 1:
                bad_sess += 1
            dt = pd.to_datetime(w[TIMESTAMP]).diff().dropna().dt.total_seconds().to_numpy()
            if not np.allclose(dt, 1.0):
                bad_time += 1
        ok &= (bad_sess == 0 and bad_time == 0)

        z = np.stack([ds.arrays[g][s:s + span] for g, s in ds.index[:200]])
        report[f"dataset::{split}"] = {
            "n_windows": len(ds), "matches_expected": n_ok, "shapes_ok": shapes_ok,
            "cross_session_windows": bad_sess, "non_contiguous_windows": bad_time,
            "windows_probed": len(probe),
            "z_mean_first200": float(np.nanmean(z)), "z_std_first200": float(np.nanstd(z)),
            "all_finite": bool(np.isfinite(z).all()),
        }
        print(f"  {split:<13} n={len(ds):<6} {'OK' if n_ok else 'MISMATCH'}  shapes={'OK' if shapes_ok else 'BAD'}"
              f"  cross_session={bad_sess}  non_contiguous={bad_time}"
              f"  z_mean={np.nanmean(z):+.3f} z_std={np.nanstd(z):.3f}")

    # source_train z-stats must be ~(0,1) by construction; drift means a normalizer bug.
    tr = report["dataset::source_train"]
    if abs(tr["z_mean_first200"]) > 1.0 or not (0.2 < tr["z_std_first200"] < 3.0):
        print("  WARNING: source_train z-stats look off (windowed subsample, so not exactly 0/1)")

    print("=" * 72)
    print("3. CPU forward pass, 2 batches per model (tiny d_model)")
    tmp = OUT_ROOT / "_verify"
    tmp.mkdir(parents=True, exist_ok=True)
    for name, spec in specs.items():
        aj = dict(spec["args"])
        aj.update(d_model=16, d_ff=32, e_layers=1, n_heads=2, use_gpu=False, batch_size=8)
        if name == "simmtm":
            aj["task_name"] = "finetune"
        p = tmp / f"{name}_args.json"
        p.write_text(json.dumps(aj, indent=2))
        rc = run([python, "-u", str(ADAPTER / "predict_cnc.py"), "--kind", spec["kind"],
                  "--args-json", str(p), "--smoke", "--batch-size", "8"],
                 spec["repo"], env_for(channels, "source_test", impute, "cpu"), dry=False,
                 log=tmp / f"{name}_smoke.log")
        ok &= (rc == 0)
        report[f"smoke::{name}"] = {"exit_code": rc}

    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    (OUT_ROOT / "verification.json").write_text(json.dumps(report, indent=2))
    print("=" * 72)
    print(f"VERIFY {'PASSED' if ok else 'FAILED'} -> {OUT_ROOT/'verification.json'}")
    return 0 if ok else 1


# ---------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--methods", nargs="+", default=["patchtst", "itransformer", "simmtm"])
    ap.add_argument("--channels", type=int, default=21, choices=[17, 21],
                    help="21 = 17 sensors + 4 actions as extra input/output channels")
    ap.add_argument("--impute", default="zspace_zero", choices=["zspace_zero", "raw_zero"],
                    help="how DS03's 7 absent sensors are filled; see cnc_dataset.py")
    ap.add_argument("--device", default="cuda:0")
    ap.add_argument("--epochs", type=int, default=TRAIN_EPOCHS)
    ap.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    ap.add_argument("--patience", type=int, default=PATIENCE)
    ap.add_argument("--out", default=str(OUT_ROOT))
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--dry-run", action="store_true", help="print every command, run nothing")
    ap.add_argument("--verify", action="store_true", help="CPU preflight only, no training")
    ap.add_argument("--smoke-train", action="store_true",
                    help="end-to-end CPU rehearsal: 1 epoch, tiny model, forces --device cpu. "
                         "Exercises each repo's real run script, checkpoint discovery, "
                         "prediction and metric conversion. Results are meaningless as science.")
    ap.add_argument("--skip-train", action="store_true",
                    help="reuse existing checkpoints; run predict+convert only")
    a = ap.parse_args()

    if a.smoke_train:
        a.device, a.epochs, a.batch_size, a.patience = "cpu", 1, 32, 1
        a.out = a.out if a.out != str(OUT_ROOT) else str(OUT_ROOT / "_smoke_train")

    out_root = Path(a.out)
    specs = method_specs(a.channels, out_root, a.device, a.epochs, a.batch_size, a.patience)
    specs = {k: v for k, v in specs.items() if k in a.methods}
    if a.smoke_train:
        for spec in specs.values():
            spec["args"].update(d_model=16, d_ff=32, e_layers=1, n_heads=2, num_workers=0)

    if a.verify:
        return verify(specs, a.channels, a.impute, a.python)

    failures = []
    for name, spec in specs.items():
        mdir = out_root / name
        if not a.dry_run:
            mdir.mkdir(parents=True, exist_ok=True)
            (mdir / "args.json").write_text(json.dumps(spec["args"], indent=2))

        # ---- train (source_test is the split the repo's own loop will report on)
        env = env_for(a.channels, "source_test", a.impute, a.device)
        if not a.skip_train:
            for label, cmd, cwd in stage_commands(name, spec, a.python):
                rc = run(cmd, cwd, env, a.dry_run, log=mdir / f"{label.replace(':','_')}.log")
                if rc != 0 and not a.dry_run:
                    failures.append(label)
                    break
            if failures and failures[-1].startswith(name):
                continue

        # ---- predict on both splits with the SAME checkpoint
        aj = mdir / "args.json"
        if a.dry_run:
            aj.parent.mkdir(parents=True, exist_ok=True)
            aj.write_text(json.dumps(spec["args"], indent=2))
        ckpt = "<CKPT>" if a.dry_run else find_checkpoint(spec["args"]["checkpoints"])
        for split in ("source_test", "target_all"):
            rc = run([a.python, "-u", str(ADAPTER / "predict_cnc.py"),
                      "--kind", spec["kind"], "--args-json", str(aj), "--ckpt", str(ckpt),
                      "--out", str(mdir / f"pred_{split}.npz"), "--device", a.device],
                     spec["repo"], env_for(a.channels, split, a.impute, a.device), a.dry_run,
                     log=mdir / f"predict_{split}.log")
            if rc != 0 and not a.dry_run:
                failures.append(f"{name}:predict:{split}")

        # ---- convert to our metric format
        if a.dry_run:
            print(f"# then: convert pred_*.npz -> {mdir/'metrics.json'}\n")
            continue
        metrics = {
            "method": name, "channels": a.channels, "impute": a.impute,
            "protocol": {"seq_len": SEQ_LEN, "pred_len": PRED_LEN, "label_len": LABEL_LEN,
                         "horizons": HORIZONS, "units": "z-score (source_train stats)"},
            "commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(spec["repo"]),
                                     capture_output=True, text=True).stdout.strip(),
            "args": spec["args"],
        }
        for split in ("source_test", "target_all"):
            f = mdir / f"pred_{split}.npz"
            if f.exists():
                metrics[split] = compute_metrics(f, a.channels)
        # On target_all the 7 absent sensors have no ground truth at any horizon, so the
        # masked "sensors_17" figure is arithmetically identical to "transfer_10". An
        # UNMASKED all-17 number would score the model against its own imputation and is
        # deliberately not produced.
        if "target_all" in metrics:
            metrics["target_all"]["note"] = (
                "7 of 17 sensors are absent on DS03; they are masked out of every figure, "
                "so sensors_17 == transfer_10 here by construction."
            )
        (mdir / "metrics.json").write_text(json.dumps(metrics, indent=2))
        print(f"\nwrote {mdir/'metrics.json'}")
        for split in ("source_test", "target_all"):
            if split in metrics:
                b = metrics[split]["transfer_10" if split == "target_all" else "sensors_17"]
                print(f"  {split:<12} rmse={b['rmse']:.4f} mae={b['mae']:.4f} (z, horizons {HORIZONS})")

    if failures:
        print("\nFAILED stages: " + ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
