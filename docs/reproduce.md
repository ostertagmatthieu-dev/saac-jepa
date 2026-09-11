# Reproduce

Three commands get you from a clean checkout to the full pipeline. Everything below assumes you
run from the **repository root** — every script starts with `from _common import *`, which puts
`src/` on `sys.path` relative to the repository, and nothing resolves correctly from elsewhere.

---

## 1. Hardware

All reported experiments ran on **one NVIDIA DGX Spark, a single GB10 GPU (`cuda:0`)**, for
**about six GPU-days** in total. `scripts/61_run_all_spark.py` is written for exactly that
shape: one GPU, phases run in order, a small job pool inside each non-serial phase.

The CPU path — `make setup`, `make smoke`, `make test` — needs no GPU and finishes in minutes on
a laptop. It exercises the code, not the science.

## 2. Environment

```bash
make setup
source .venv/bin/activate
```

`make setup` creates a `uv` virtual environment on Python 3.12, installs a **CPU** build of
PyTorch from `https://download.pytorch.org/whl/cpu`, then installs this package with its dev
extras. On a GPU host, skip the CPU index line and install the CUDA build appropriate to the
machine — or use the DGX's installed CUDA/PyTorch stack if it is newer and compatible — then
`uv pip install -e ".[dev]"`.

Check the install:

```bash
make smoke      # synthetic data -> validate -> pretrain -> fine-tune -> evaluate, prints SMOKE_CORE_OK
make test       # pytest suite, including the P3-FIX invariants and the triple review
make lint       # ruff
```

## 3. Ingest the real data

Download both datasets and lay them out as [data.md](data.md) describes, then:

```bash
python scripts/60_ingest_real_data.py --config configs/real.yaml
```

This writes `data/cnc.parquet` and `outputs/etl_audit.json`, and exits non-zero on any
provenance or schema violation — including if DS03 does not contain exactly 7 runs. Read the
printed audit, in particular the two unit-mismatch tables, before training anything.

## 4. Run the pipeline

```bash
python scripts/61_run_all_spark.py --config configs/real.yaml --dry-run   # print every command
python scripts/61_run_all_spark.py --config configs/real.yaml             # run it
```

Phases execute in this order, and **a failure inside a gate phase aborts the entire run**:

```
p2_audits -> p3_core -> p3fix_gate -> p4_ablations -> p5_baselines -> p6_evals -> p7_search -> p8_adapt -> p10_revin -> p9_reports
```

| Phase | Scripts | Serial | Gate | Produces |
|---|---|---|---|---|
| `p2_audits` | 00, 01, 02, 03, 04, 05, 06, 07, 08, 09 | yes | **yes** | Dataset validation, the group-disjoint splits, train-only normalizers, the window- and normalization-leakage audits, the 17→10 schema overlap, the corruption manifest, and the power analysis at `--n 7`. |
| `p3_core` | 10, 12, 11 | no | no | SSL pretraining from random init (10), the schema-adaptive variant (12), then the physical forecast head fine-tuned on the pretrained body (11, depends on 10). |
| `p3fix_gate` | 62, 63, `tests/test_p3fix.py` | yes | **yes** | Checkpoint/latent diagnostics, the A/B/C scratch-vs-pretraining experiment over five seeds, and the protocol regression tests. The taskbook forbids running the search or any target evaluation before this passes. |
| `p4_ablations` | 13–19 | no | no | Action conditioning, mask policy, latent weight, VICReg, LayerNorm, horizon aggregation and EMA ablations. |
| `p5_baselines` | 20–28, 29 | no | no | Supervised dynamics baselines, the masked-reconstruction and `-style` SSL baselines, the RSSM world model, the capacity sweep, and the export of identical windows for the official repositories. |
| `p6_evals` | 30–38 | yes | no | Multi-horizon evaluation, DS01→DS03 transfer, per-channel/per-run metrics, normalizer sensitivity, schema stress, corruptions, calibration, action conditioning, CEM planning. |
| `p7_search` | 40, 42, 43, 64, 64 (again), 44, 45 | yes | no | The architecture search: generate, run 20 candidates × 4 seeds, rank on source validation, confirm the top-5 at 5 seeds, extend to 7 seeds, lock with SHA-256, then the single DS03 test. |
| `p8_adapt` | 46, 47, 50, 56, 58, 59, 57, 39 | no | no | Few-shot and online adaptation, the component factorial, baseline per-channel export, source group CV, target-run bootstrap, sampling-rate sensitivity, and the run-level statistical tests (39 depends on 56). |
| `p10_revin` | 68 `train`, 68 `summarize`, 68 `ds03` | no | no | The post-lock RevIN ablation (paper App. H). Runs after the lock and the single target test, and never gates them. |
| `p9_reports` | 51, 52, 65 | yes | no | Main result tables, the reviewer-response matrix, and the consolidated `outputs/FULL_REPORT.md`. |

Serial phases run one job at a time. Non-serial phases run up to `--max-concurrent` jobs (3 by
default), respecting the declared dependencies.

### Flags

| Flag | Default | Meaning |
|---|---|---|
| `--config` | `configs/real.yaml` | Passed through to every job that takes one. |
| `--phase` | `all` | A comma-separated subset of the phase names above. Unknown names exit with status 2. |
| `--max-concurrent` | `3` | Job pool size inside non-serial phases. |
| `--dry-run` | off | Print every phase, job, dependency and command line; run nothing. |
| `--python` | `sys.executable` | Interpreter handed to job subprocesses — set this if you are not launching from inside the venv. |
| `--continue-on-error` | off | Keep going after a failed job instead of aborting the phase. Gate phases still abort the run. |

### Status and logs

```
outputs/orchestrator/status.json      # per-phase, per-job: state, return code, seconds
outputs/orchestrator/<phase>/<job>.log  # stdout+stderr of each job
```

`status.json` is rewritten after every job transition, so it is safe to tail during a run. The
orchestrator prints a summary table at the end and exits non-zero if anything failed; a fully
clean run ends with `ORCHESTRATOR_OK`.

### Running one phase

```bash
python scripts/61_run_all_spark.py --config configs/real.yaml --phase p7_search
python scripts/61_run_all_spark.py --config configs/real.yaml --phase p4_ablations,p5_baselines
```

Phases are not self-contained: `p3fix_gate` needs `p3_core`'s checkpoints, `p6_evals` needs
`outputs/jepa_finetune/best.pt`, `p7_search` needs the audits and normalizers from `p2_audits`,
and `p8_adapt`'s job 39 needs job 56 from the same phase.

`scripts/53_reproduce_all_dgx.py` is the **superseded** 8-GPU launcher from the first iteration.
It is kept for the record. Use `scripts/61` for anything current.

---

## 5. Per-command recipes

Everything the orchestrator does can be run by hand. `--device` is `cuda:0` on the single-GPU
Spark; use `cpu` for a smoke run.

### First audited run

```bash
python scripts/00_validate_dataset.py --config configs/real.yaml
python scripts/01_audit_sessions_channels.py --config configs/real.yaml
python scripts/05_window_leakage_audit.py --config configs/real.yaml
python scripts/08_normalization_leakage_audit.py --config configs/real.yaml
```

Inspect these outputs before any model training.

### JEPA from scratch

```bash
python scripts/10_pretrain_jepa_from_scratch.py --config configs/real.yaml --out outputs/jepa_pretrain --device cuda:0
python scripts/11_finetune_jepa_forecaster.py --config configs/real.yaml --pretrained outputs/jepa_pretrain/best.pt --out outputs/jepa_finetune --device cuda:0
```

Script 11 defaults to `--head fresh`: only the SSL body is loaded and the physical head is
reinitialised. `--head loaded` is the contamination control and `--head none` the scratch arm.

### Ablations

```bash
python scripts/13_train_action_ablation.py --config configs/real.yaml --device cuda:0
python scripts/14_train_mask_policy_ablation.py --config configs/real.yaml --device cuda:0
python scripts/15_train_latent_weight_ablation.py --config configs/real.yaml --device cuda:0
python scripts/16_train_vicreg_ablation.py --config configs/real.yaml --device cuda:0
python scripts/17_train_layernorm_ablation.py --config configs/real.yaml --device cuda:0
python scripts/18_train_horizon_aggregation_ablation.py --config configs/real.yaml --device cuda:0
python scripts/19_train_ema_ablation.py --config configs/real.yaml --device cuda:0
```

### Baselines

```bash
python scripts/20_train_supervised_dynamics_baselines.py --config configs/real.yaml --device cuda:0
python scripts/21_train_masked_mae_baseline.py --config configs/real.yaml --device cuda:0
python scripts/22_train_simmtm_style_baseline.py --config configs/real.yaml --device cuda:0
python scripts/23_train_patchformer_style_baseline.py --config configs/real.yaml --device cuda:0
python scripts/24_train_emit_style_baseline.py --config configs/real.yaml --device cuda:0
python scripts/25_train_mmr_wavelet_style_baseline.py --config configs/real.yaml --device cuda:0
python scripts/26_train_lomar_ts_style_baseline.py --config configs/real.yaml --device cuda:0
python scripts/27_train_rssm_world_model_baseline.py --config configs/real.yaml --device cuda:0
python scripts/28_train_forecasting_capacity_sweep.py --config configs/real.yaml --device cuda:0
python scripts/29_export_official_baseline_inputs.py --config configs/real.yaml
```

Scripts 22–26 are in-house approximations, not reproductions. The official comparison is
separate: clone the pinned repositories listed in `third_party/README.md`, then

```bash
python scripts/66_run_official_baselines.py --dry-run        # print every command
python scripts/66_run_official_baselines.py --verify         # CPU preflight, no training
python scripts/66_run_official_baselines.py --device cuda:0
```

`--methods patchtst itransformer simmtm` selects the subset; `--channels`, `--impute`,
`--epochs`, `--batch-size` and `--patience` control the run.

### Transfer reporting

```bash
python scripts/31_eval_transfer_ds01_to_ds03.py --config configs/real.yaml --ckpt outputs/jepa_finetune/best.pt --device cuda:0
python scripts/32_eval_per_channel_per_run.py --config configs/real.yaml --ckpt outputs/jepa_finetune/best.pt --device cuda:0
python scripts/33_eval_normalization_sensitivity.py --config configs/real.yaml --ckpt outputs/jepa_finetune/best.pt --device cuda:0
python scripts/34_eval_missing_sensor_schema.py --config configs/real.yaml --ckpt outputs/jepa_finetune/best.pt --device cuda:0
python scripts/36_eval_uncertainty_calibration.py --config configs/real.yaml --ckpt outputs/jepa_finetune/best.pt --device cuda:0
python scripts/37_eval_action_conditioning.py --config configs/real.yaml --ckpt outputs/jepa_finetune/best.pt --device cuda:0
python scripts/56_eval_baseline_per_channel_run.py --config configs/real.yaml --ckpt outputs/baselines_supervised/transformer/best.pt --model transformer --device cuda:0
python scripts/39_statistical_tests_run_level.py --jepa outputs/per_channel_run.csv --baseline outputs/baseline_per_channel_run.csv
python scripts/57_sampling_rate_sensitivity_train_eval.py --config configs/real.yaml --device cuda:0
```

`scripts/39_statistical_tests_run_level.py` does run-level paired tests over the **7** real DS03
runs. It was called `39_statistical_tests_n6.py` until the synthetic-vs-real run count was
corrected.

### Architecture search

The paper's 20 candidates are `configs/search_v2/M00..M19.yaml`, indexed by
`configs/search_v2/manifest.json`. `configs/random_methods/` is the abandoned V1 sample; it is
kept for the record and is **not** used by the paper.

```bash
python scripts/40_generate_20_random_methods.py --config configs/real.yaml
python scripts/42_run_20_random_methods_dgx.py --manifest configs/search_v2/manifest.json --gpus 0,0,0 --seeds 0,1,2,3 --dry-run
python scripts/42_run_20_random_methods_dgx.py --manifest configs/search_v2/manifest.json --gpus 0,0,0 --seeds 0,1,2,3
python scripts/43_rank_methods_validation_only.py
python scripts/64_confirm_top5.py --manifest configs/search_v2/manifest.json --gpus 0,0,0 --top 5 --seeds 0,1,2,3,4
python scripts/64_confirm_top5.py --manifest configs/search_v2/manifest.json --gpus 0,0,0 --top 5 --seeds 0,1,2,3,4,5,6
python scripts/44_lock_best_method.py
```

`--gpus 0,0,0` means three slots on the single GB10. The second `scripts/64` invocation runs only
the seeds that are missing and re-ranks — that is the "refuse to lock, add seeds" step of the
selection protocol (see [protocol.md](protocol.md#6-the-search-and-the-refused-lock)).

Only after the lock file exists:

```bash
python scripts/45_test_locked_method_ds03.py --device cuda:0
```

`scripts/67_reeval_common_space.py` re-emits `val_metrics.json` for already-trained search runs
in the fixed reference space, without training; it exists to repair the metric-scale leak of the
robust-normalisation candidates.

### Adaptation

```bash
python scripts/46_fewshot_target_adaptation.py --config configs/real.yaml --ckpt outputs/jepa_finetune/best.pt --device cuda:0
python scripts/47_online_causal_adaptation.py --config configs/real.yaml --ckpt outputs/jepa_finetune/best.pt --device cuda:0
python scripts/48_predict_any_input.py --config configs/real.yaml --ckpt outputs/jepa_finetune/best.pt --input <window.csv> --device cuda:0
python scripts/49_predict_variable_sensor_schema.py --config configs/real.yaml --ckpt outputs/jepa_finetune/best.pt --input <window.csv> --device cuda:0
python scripts/50_novelty_component_factorial.py --config configs/real.yaml --device cuda:0
```

48 and 49 are single-inference demos and require `--input`; the orchestrator excludes them for
that reason.

### Post-lock RevIN ablation

```bash
python scripts/68_revin_ablation.py train --seeds 0,1,2 --device cuda:0
python scripts/68_revin_ablation.py summarize
python scripts/68_revin_ablation.py ds03
```

Six sequential runs on one GB10, roughly 72 minutes each. `--slots > 1` exists for multi-GPU
hosts only: on the GB10 the model already saturates the GPU at batch 128 and packing three slots
measured about 20 % slower. The `ds03` stage is the **second, declared read of the target
machine** — see [results.md](results.md#post-lock-revin-ablation-paper-app-h) for what it found
and [protocol.md](protocol.md#7-the-second-ds03-read) for the declaration.

### Reports

```bash
python scripts/51_build_main_result_tables.py
python scripts/52_build_reviewer_response_matrix.py
python scripts/65_build_full_report.py
```

`scripts/65` consolidates every pipeline output into `outputs/FULL_REPORT.md` and is safe to
re-run at any time.

### Figures

```bash
make figures-zip    # rebuild paper/figures_meta_tikz.zip and paper/figures_meta_tikz_en.zip
```

The TikZ sources compile standalone with `pdflatex`; see
[`paper/figures/README.md`](../paper/figures/README.md).
