# Script catalogue

73 files in `scripts/`: 69 numbered entry points `00`–`68` and four helper modules.

**Every script must be run from the repository root.** Each one starts with
`from _common import *`, a four-line shim that resolves `src/` relative to the repository and
prepends it to `sys.path`; run from anywhere else and the import fails.

Three flags recur and are not repeated in the tables below unless the default matters:
`--config` (default `configs/real.yaml` for 60–63, `configs/base.yaml` or explicit elsewhere),
`--out` (an output path under `outputs/`) and `--device` (`cuda:0`, or `cpu`).

Command lines for the common workflows are in [reproduce.md](reproduce.md).

---

## 00–09 · Protocol and leakage audit

| # | File | Purpose | Main flags |
|---|---|---|---|
| 00 | `00_validate_dataset.py` | Validate the dataset against the declared schema | `--config` |
| 01 | `01_audit_sessions_channels.py` | Audit machines, sessions, runs and channel coverage | `--config --out` |
| 02 | `02_build_protocol_splits.py` | Create the group-disjoint protocol splits | `--config --out` |
| 03 | `03_resample_sensitivity_data.py` | Inspect resampling rates | `--config --rates --out` |
| 04 | `04_fit_normalizers.py` | Fit train-only normalizers | `--config --out` |
| 05 | `05_window_leakage_audit.py` | Audit window leakage across splits | `--config` |
| 06 | `06_generate_corruption_manifest.py` | Define the corruption suite | `--out` |
| 07 | `07_build_schema_overlap.py` | Audit the 17 → 10 schema overlap | `--config` |
| 08 | `08_normalization_leakage_audit.py` | Audit target-statistic leakage in normalization | `--config` |
| 09 | `09_transfer_power_analysis.py` | Quantify the weak statistical power of the target run count | `--n --effect` |

## 10–19 · JEPA from scratch and ablations

| # | File | Purpose | Main flags |
|---|---|---|---|
| 10 | `10_pretrain_jepa_from_scratch.py` | Pretrain the action-conditioned JEPA from random initialization (pure SSL) | `--out --epochs --seed --val-mask --ema-schedule` |
| 11 | `11_finetune_jepa_forecaster.py` | Fine-tune the physical probabilistic forecast head | `--pretrained --head {fresh,loaded,none} --epochs --seed` |
| 12 | `12_train_schema_adaptive_jepa.py` | Train schema-adaptive action-conditioned JEPA | `--epochs --seed --supervised --val-mask` |
| 13 | `13_train_action_ablation.py` | Action-conditioning ablation | `--out` |
| 14 | `14_train_mask_policy_ablation.py` | Masking-policy ablation | `--out` |
| 15 | `15_train_latent_weight_ablation.py` | Latent-loss-weight ablation | `--out` |
| 16 | `16_train_vicreg_ablation.py` | VICReg: none vs pooled vs per-horizon | `--out` |
| 17 | `17_train_layernorm_ablation.py` | Latent LayerNorm on/off plus encoder pre/post norm | `--out` |
| 18 | `18_train_horizon_aggregation_ablation.py` | Per-horizon vs pooled latent target | `--out` |
| 19 | `19_train_ema_ablation.py` | EMA target-encoder ablation | `--out` |

## 20–29 · Non-JEPA and reconstruction baselines

| # | File | Purpose | Main flags |
|---|---|---|---|
| 20 | `20_train_supervised_dynamics_baselines.py` | DLinear, MLP, GRU, LSTM, TCN, Transformer, TSMixer, PatchTST-like, iTransformer-like and RSSM | `--models --out` |
| 21 | `21_train_masked_mae_baseline.py` | Masked autoencoding baseline | `--out` |
| 22 | `22_train_simmtm_style_baseline.py` | SimMTM-**inspired** reconstruction baseline | `--out` |
| 23 | `23_train_patchformer_style_baseline.py` | PatchFormer-**inspired** hierarchical/block masked baseline | `--out` |
| 24 | `24_train_emit_style_baseline.py` | EMIT-**inspired** event-masked baseline | `--out` |
| 25 | `25_train_mmr_wavelet_style_baseline.py` | MMR-**inspired** multiscale/wavelet masked baseline | `--out` |
| 26 | `26_train_lomar_ts_style_baseline.py` | LoMaR-**inspired** local reconstruction baseline for time series | `--out` |
| 27 | `27_train_rssm_world_model_baseline.py` | RSSM world-model baseline | `--out` |
| 28 | `28_train_forecasting_capacity_sweep.py` | Forecasting capacity sweep | `--out` |
| 29 | `29_export_official_baseline_inputs.py` | Export identical splits and windows for the official external implementations | `--out` |

> **`-style` / `-inspired` warning.** Scripts 22–26 are controlled in-house approximations,
> written for ablation and engineering comparison under an identical protocol. They are **not**
> reproductions of the published methods and must be called `-style` or `-inspired` wherever
> they appear. The same applies to `PatchTSTLike` and `ITransformerLike` in script 20's sweep.
> The official comparison is `scripts/66` against the pinned repositories in
> `third_party/README.md`, fed by script 29.

## 30–39 · Audited evaluation

All of 30–38 take `--ckpt` in addition to `--config --device --out`.

| # | File | Purpose | Main flags |
|---|---|---|---|
| 30 | `30_eval_jepa_multihorizon.py` | Source and target multi-horizon evaluation | `--ckpt` |
| 31 | `31_eval_transfer_ds01_to_ds03.py` | Zero-/few-shot DS01 → DS03 transfer | `--ckpt` |
| 32 | `32_eval_per_channel_per_run.py` | Per-channel/per-run metrics in z and physical units | `--ckpt` |
| 33 | `33_eval_normalization_sensitivity.py` | Source-normalizer sensitivity | `--ckpt` |
| 34 | `34_eval_missing_sensor_schema.py` | Missing-sensor/schema stress at 17/10/8/6/4 channels | `--ckpt` |
| 35 | `35_eval_random_masks_anomalies.py` | Random masks, noise, spikes, drift, step shifts, missing blocks, bias | `--ckpt` |
| 36 | `36_eval_uncertainty_calibration.py` | Probabilistic calibration | `--ckpt` |
| 37 | `37_eval_action_conditioning.py` | True vs zero vs shuffled future actions | `--ckpt` |
| 38 | `38_eval_cem_planning.py` | CEM planning with physical-unit temperature/wear constraints | `--ckpt --n` |
| 39 | `39_statistical_tests_run_level.py` | Run-level paired statistical tests over the 7 target runs | `--jepa --baseline --out` |

## 40–45 · Twenty-method search without test leakage

| # | File | Purpose | Main flags |
|---|---|---|---|
| 40 | `40_generate_20_random_methods.py` | Generate 20 unique JEPA designs | `--config --outdir` |
| 41 | `41_train_one_random_candidate.py` | Train one candidate on source data only, under the P3-FIX protocol, and emit its validation bundle | `--out --seed --pretrain-epochs --ft-epochs --epochs` |
| 42 | `42_run_20_random_methods_dgx.py` | Run the candidate × seed job grid across GPU slots | `--manifest --gpus --seeds --dry-run` |
| 43 | `43_rank_methods_validation_only.py` | Rank methods by the composite source-validation score | `--root --min-seeds --top` |
| 44 | `44_lock_best_method.py` | Lock the winning method and checkpoint with SHA-256 | `--ranking --search-root --lockdir --normalizers --seed-pick --min-valid-seeds --force` |
| 45 | `45_test_locked_method_ds03.py` | Evaluate the locked model on the target machine, once | `--lock --device --out` |

The search varies mask type and ratio, action injection, encoder norm, latent LayerNorm, VICReg
mode and weight, latent weight, horizon aggregation, schema consistency, action recovery, EMA,
model scale and source normalizer. It is a **discovery** procedure; it does not establish SOTA.
Scripts 41, 43, 44, 64 and `_search_common.py` are target-blind by construction, and
`scripts/55` fails the build if any of them so much as mentions `target_all`.

## 46–50 · Adaptation and the proposed novelty

| # | File | Purpose | Main flags |
|---|---|---|---|
| 46 | `46_fewshot_target_adaptation.py` | Few-shot target adaptation | `--ckpt` |
| 47 | `47_online_causal_adaptation.py` | Causal online adaptation | `--ckpt` |
| 48 | `48_predict_any_input.py` | Predict a new input, with an optional support set | `--ckpt --input` (required) |
| 49 | `49_predict_variable_sensor_schema.py` | Inference with a variable known sensor subset | `--ckpt --input` (required) |
| 50 | `50_novelty_component_factorial.py` | Component-factorial experiment for SAAC-JEPA | `--out` |

## 51–59 · Paper and reviewer outputs

| # | File | Purpose | Main flags |
|---|---|---|---|
| 51 | `51_build_main_result_tables.py` | Main result tables | `--root --out` |
| 52 | `52_build_reviewer_response_matrix.py` | Reviewer concern → script mapping | `--out` |
| 53 | `53_reproduce_all_dgx.py` | **Superseded** 8-GPU reproduction launcher; use `scripts/61` | `--config --gpus --execute` |
| 54 | `54_smoke_test_core.py` | CPU core smoke test; prints `SMOKE_CORE_OK` | none |
| 55 | `55_triple_review.py` | Three-pass review: compile everything, AST and target-blindness hygiene, protocol invariants; prints `TRIPLE_REVIEW_OK` | none |
| 56 | `56_eval_baseline_per_channel_run.py` | Baseline per-channel/per-run export | `--ckpt --model` |
| 57 | `57_sampling_rate_sensitivity_train_eval.py` | Full sampling-rate retrain and evaluation sensitivity | `--rates --epochs` |
| 58 | `58_source_group_cv.py` | Grouped source-session CV manifest | `--folds` |
| 59 | `59_target_run_bootstrap.py` | Target-run bootstrap uncertainty | `--csv --metric --samples --seed` |

## 60–68 · Real data, orchestration, gates, confirmation, official baselines

| # | File | Purpose | Main flags |
|---|---|---|---|
| 60 | `60_ingest_real_data.py` | Real-data ETL: DS01 1 Hz process log + DS03 IPO-cycle traces → one canonical parquet. Hard-fails on any provenance or schema violation; writes a full audit JSON and a human report. No GPU. | `--config --out-data --audit-out --keep-idle` |
| 61 | `61_run_all_spark.py` | Phased single-GPU orchestrator for the DGX Spark (one GB10, `cuda:0`). Stdlib only; job subprocesses get the real interpreter via `--python`. | `--config --phase --max-concurrent --dry-run --python --continue-on-error` |
| 62 | `62_p3fix_diagnostics.py` | P3-FIX diagnostics on existing checkpoints: load audit, mean-spread probe, latent health (std, off-diagonal correlation, effective rank, collapse flag) plus the held-out SSL objective, on source validation only. | `--ckpts --split --max-batches --out` |
| 63 | `63_p3fix_abc_seeds.py` | P3-FIX gate experiment: A scratch / B pretrained body + fresh head / C full pretrained checkpoint, over matched seeds, paired at seed level with an exact sign-flip test. Persistence and linear drift on the identical split. | `--pretrained --seeds --arms --epochs --out` |
| 64 | `64_confirm_top5.py` | Confirmation stage of the search: rerun the top-N discovery candidates at more seeds, re-score inside the confirmation pool, and warn when rank 1 changed. | `--ranked --manifest --root --top --seeds --gpus --min-seeds --dry-run --skip-run` |
| 65 | `65_build_full_report.py` | Consolidate every pipeline output into `outputs/FULL_REPORT.md`. Stdlib only, safe to re-run. | `--out` |
| 66 | `66_run_official_baselines.py` | Train the **official** PatchTST / iTransformer / SimMTM repositories on our audited export, driven through their own run scripts. Only the dataset class and the evaluation are substituted. | `--methods --channels --impute --device --epochs --batch-size --patience --out --python --dry-run --verify --smoke-train` |
| 67 | `67_reeval_common_space.py` | Re-emit `val_metrics.json` for already-trained search runs in the fixed reference space. Eval-only; never trains. Repairs the metric-scale leak of the robust-normalization candidates. | `runs --device --apply --check` |
| 68 | `68_revin_ablation.py` | Paired post-lock RevIN ablation on M03: `train`, `summarize`, `ds03`. The `ds03` stage is the second, declared read of the target machine. | `stage {train,summarize,ds03} --seeds --device --slots --epochs --out --force --dry-run` |

## Helper modules

| File | Role |
|---|---|
| `_common.py` | The `sys.path` shim. Four lines: resolve the repository root, prepend `src/`. Every numbered script starts with `from _common import *`, which is why everything must run from the root. |
| `_search_common.py` | The validation-only composite score shared by 43, 44 and 64: component weights, the collapse and weak-action penalties, pool-relative z-scoring, and the invalid-run bookkeeping. Reads nothing from the target machine. |
| `_ssl_common.py` | Shared SSL training utilities for the reconstruction baselines. |
| `_val_bundle.py` | The post-fine-tune validation metric block of script 41, extracted verbatim so an eval-only re-run is protocol-identical: same loaders, same `eval_seed`-pinned action-shuffle generator, same determinism check, and the affine map into the fixed reference space. |

## Configuration directories

| Path | What it is |
|---|---|
| `configs/base.yaml` | Template with **placeholder** sensor and action names. Not a claim about any real dataset. |
| `configs/smoke.yaml` | Tiny CPU configuration consuming `data/synthetic_ds01_ds03.csv`. |
| `configs/real.yaml` | The DS01/DS03 configuration, including the whole `etl:` section. |
| `configs/search_v2/M00..M19.yaml` | **The paper's 20 candidates**, indexed by `manifest.json`. `M03` is the locked winner. |
| `configs/revin/M03_revin.yaml` | The post-lock RevIN ablation arm: M03 plus `model.revin.enabled: true`. |
| `configs/random_methods/` | **Abandoned V1 random sample.** Kept for the record; not used by the paper. |
