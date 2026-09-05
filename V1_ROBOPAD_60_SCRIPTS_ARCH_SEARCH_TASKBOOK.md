# V1 RoboPAD — 60-script implementation and architecture-search taskbook

## Purpose

This file is the execution specification for the local LLM. It covers all 60 numbered scripts of the V1 RoboPAD pipeline and a corrected architecture-search protocol after the P3 JEPA diagnosis.

The local LLM should modify or regenerate code to satisfy this specification. Do not run P4–P9 or any DS03 architecture selection until the P3-FIX gate is passed.

## Non-negotiable scientific rules

- DS03 is a final target evaluation domain. Never use DS03 test metrics to choose architecture, masking, normalization, loss weights or seeds.
- All source splits are group-disjoint by session. All target statistics are run-level for inference and significance testing.
- During JEPA pretraining, `best.pt` must be selected on a real held-out SSL validation objective, never training loss.
- Validation masks/corruptions must be deterministic for model selection.
- Log representation health: latent std, covariance, effective rank and collapse flags.
- During pure SSL, schema consistency acts on latent predictions/representations, not on an untrained physical `mu` head.
- Checkpoint loading must report `missing_keys` and `unexpected_keys` and verify that intended weights changed.
- Persistence and linear-drift baselines are mandatory before claiming forecasting gains.
- Report global, per-horizon, per-channel and per-run metrics. Never rely on one aggregated z-RMSE.
- Use matched training budgets/seeds for scratch vs pretrained comparisons.
- Separate clean and robust protocols so baseline comparisons are fair.
- Select among architecture candidates on DS01 validation only. Lock and hash the winner before first DS03 test.
- Finding the best of 20 candidates means best among tested candidates, not automatically SOTA.

## P3-FIX gate before architecture search

- [ ] Audit checkpoint loading in scripts 11/12.
- [ ] Run `mu.std` probe and latent-health diagnostics on the P3 checkpoint.
- [ ] Persist true held-out JEPA validation metrics and per-horizon metrics.
- [ ] Move schema consistency from `mu` to latent dynamics during SSL.
- [ ] Compare A: scratch, B: pretrained body + fresh physical head, C: full pretrained checkpoint.
- [ ] Seed Python/NumPy/PyTorch/CUDA/DataLoader workers.
- [ ] Add persistence and linear-drift baselines.
- [ ] Run at least 5 matched seeds for scratch vs pretraining confirmation.
- [ ] Add tests for split leakage, masking determinism, EMA, target no-grad and metric aggregation.

## Scripts 00–59

### 00 — `00_validate_dataset.py`
- Goal: Validate the real CNC table and fail on missing required columns, wrong dtypes, impossible timestamps, duplicated rows, or invalid machine/session/run IDs.
- Inputs: data/cnc.csv + configs/base.yaml
- Required output: Dataset validation report. No model training is allowed if this fails.

### 01 — `01_audit_sessions_channels.py`
- Goal: Audit DS01/DS03 scale, session/run counts, channel availability, missingness and action coverage.
- Inputs: Validated dataset
- Required output: outputs/audit_sessions_channels.json. Confirm DS01≈30 sessions, DS03≈6 independent runs and real channel coverage.

### 02 — `02_build_protocol_splits.py`
- Goal: Create deterministic group-disjoint source_train/source_val/source_test and target partitions. Split by session/run, never by windows.
- Inputs: Validated/resampled dataset
- Required output: outputs/split_manifest.json with zero session overlap.

### 03 — `03_resample_sensitivity_data.py`
- Goal: Prepare/inspect 0.5, 1, 2 and 5 Hz variants while preserving physical time meaning.
- Inputs: Dataset + timestamps
- Required output: outputs/resample_sensitivity.json and resampled manifests.

### 04 — `04_fit_normalizers.py`
- Goal: Fit sensor/action normalizers using source_train only. Support source z-score and source robust scaling.
- Inputs: source_train only
- Required output: outputs/normalizers.json. Target statistics must never enter the primary normalizer.

### 05 — `05_window_leakage_audit.py`
- Goal: Audit temporal windows and prove that no window or session leaks between train/val/test.
- Inputs: Split manifest
- Required output: Leakage report with zero train-val-test overlap.

### 06 — `06_generate_corruption_manifest.py`
- Goal: Define corruption suite applied to context only: random mask, Gaussian noise, spikes, drift, step, missing blocks, sensor bias and mixed corruption.
- Inputs: Config
- Required output: outputs/corruption_manifest.json.

### 07 — `07_build_schema_overlap.py`
- Goal: Audit the real source/target sensor vocabularies and construct 17→10 plus synthetic 17→8/6/4 schema subsets.
- Inputs: Schema config
- Required output: Schema overlap report and explicit missing-on-target list.

### 08 — `08_normalization_leakage_audit.py`
- Goal: Demonstrate that target statistics are not used accidentally. Prepare diagnostic target-support and target-oracle scalers only for sensitivity experiments.
- Inputs: Splits + normalizers
- Required output: Leakage audit report.

### 09 — `09_transfer_power_analysis.py`
- Goal: Quantify statistical limitations of n=6 target runs and define allowed run-level tests.
- Inputs: n target runs
- Required output: Power report, exact sign-flip resolution and warning against window-level pseudo-replication.

### 10 — `10_pretrain_jepa_from_scratch.py`
- Goal: Pretrain action-conditioned JEPA from random initialization. P3-FIX REQUIRED: true held-out SSL validation, deterministic val masking, anti-collapse logging, scheduled/controlled EMA and best checkpoint selected on val SSL rather than train loss.
- Inputs: source_train/source_val
- Required output: outputs/jepa_pretrain/{best.pt,last.pt,history.csv,latent_health.csv,config.yaml}.

### 11 — `11_finetune_jepa_forecaster.py`
- Goal: Fine-tune JEPA for physical probabilistic forecasting. P3-FIX REQUIRED: explicit checkpoint-load audit, fixed seeds, matched budget and separate RMSE/MAE/NLL logging.
- Inputs: Pretrained JEPA + source_train/source_val
- Required output: outputs/jepa_finetune. Must report missing/unexpected checkpoint keys.

### 12 — `12_train_schema_adaptive_jepa.py`
- Goal: Train SAAC-JEPA with flexible sensor tokenizer and latent schema consistency. P3-FIX REQUIRED: schema consistency must act on latent dynamics, not an untrained physical head during SSL.
- Inputs: Source data with multiple sensor views
- Required output: outputs/saac_jepa. Must support variable known sensor subsets without changing input layer.

### 13 — `13_train_action_ablation.py`
- Goal: Ablate action conditioning: correct actions, no actions, token, FiLM, cross-attention and/or shuffled actions under matched budgets.
- Inputs: source_train/source_val
- Required output: Action-ablation checkpoints and validation table.

### 14 — `14_train_mask_policy_ablation.py`
- Goal: Compare random, block, channel, event and mixed masking at matched mask ratios and budgets.
- Inputs: source_train/source_val
- Required output: Mask-policy validation table.

### 15 — `15_train_latent_weight_ablation.py`
- Goal: Sweep JEPA latent-loss weight after P3-FIX.
- Inputs: source_train/source_val
- Required output: Validation table for latent_weight, with latent-health metrics.

### 16 — `16_train_vicreg_ablation.py`
- Goal: Compare no VICReg, pooled VICReg, per-horizon VICReg and placement on context/target/predictor latents.
- Inputs: source_train/source_val
- Required output: Anti-collapse ablation table including std, covariance and effective rank.

### 17 — `17_train_layernorm_ablation.py`
- Goal: Separate latent LayerNorm ON/OFF from Transformer pre/post norm. Audit interaction with VICReg variance target.
- Inputs: source_train/source_val
- Required output: LayerNorm × VICReg results.

### 18 — `18_train_horizon_aggregation_ablation.py`
- Goal: Compare pooled target latent versus per-horizon future latent targets.
- Inputs: source_train/source_val
- Required output: Horizon aggregation table.

### 19 — `19_train_ema_ablation.py`
- Goal: Compare fixed EMA 0.99/0.996/0.999+ and scheduled 0.99→0.9999. Log target-online parameter distance and representation health.
- Inputs: source_train/source_val
- Required output: EMA ablation table.

### 20 — `20_train_supervised_dynamics_baselines.py`
- Goal: Train fair supervised dynamics baselines: persistence and linear drift first, then MLP, GRU, LSTM, TCN, DLinear, Transformer, TSMixer, PatchTST-like, iTransformer-like. Use matched clean and robust protocols.
- Inputs: source_train/source_val
- Required output: Baseline checkpoints and per-horizon/per-channel validation results.

### 21 — `21_train_masked_mae_baseline.py`
- Goal: Train masked-reconstruction autoencoder baseline under the same data, masks and budgets as JEPA where applicable.
- Inputs: source_train/source_val
- Required output: MAE-style SSL checkpoint and frozen/fine-tuned results.

### 22 — `22_train_simmtm_style_baseline.py`
- Goal: Train controlled SimMTM-inspired baseline. Label it style/inspired unless official repo is reproduced.
- Inputs: source_train/source_val
- Required output: SimMTM-style results.

### 23 — `23_train_patchformer_style_baseline.py`
- Goal: Train hierarchical/block masked PatchFormer-inspired baseline.
- Inputs: source_train/source_val
- Required output: PatchFormer-style results.

### 24 — `24_train_emit_style_baseline.py`
- Goal: Train event-informed masking/reconstruction baseline inspired by EMIT.
- Inputs: source_train/source_val
- Required output: EMIT-style results.

### 25 — `25_train_mmr_wavelet_style_baseline.py`
- Goal: Train multiscale/wavelet masked reconstruction baseline. Keep fallback if PyWavelets is unavailable.
- Inputs: source_train/source_val
- Required output: MMR-style results.

### 26 — `26_train_lomar_ts_style_baseline.py`
- Goal: Train local masked reconstruction baseline adapted to time series.
- Inputs: source_train/source_val
- Required output: LoMaR-style results.

### 27 — `27_train_rssm_world_model_baseline.py`
- Goal: Train a non-JEPA latent dynamics/world-model baseline such as RSSM under the same horizons/actions.
- Inputs: source_train/source_val
- Required output: RSSM checkpoint and forecasting/action-conditioned metrics.

### 28 — `28_train_forecasting_capacity_sweep.py`
- Goal: Match capacity across major supervised forecasters so wins are not explained only by parameter count.
- Inputs: source_train/source_val
- Required output: Capacity vs performance table.

### 29 — `29_export_official_baseline_inputs.py`
- Goal: Export identical windows, splits, masks and metadata for official external baseline repositories.
- Inputs: Audited prepared data
- Required output: Portable baseline-input package and manifest.

### 30 — `30_eval_jepa_multihorizon.py`
- Goal: Evaluate clean source validation/test forecasting. Save global, per-horizon, per-channel and physical-unit metrics. Include persistence/drift.
- Inputs: Frozen checkpoint
- Required output: outputs/eval_multihorizon.*

### 31 — `31_eval_transfer_ds01_to_ds03.py`
- Goal: Evaluate locked source model on DS03 zero-shot and approved support fractions. Never use target test for model selection.
- Inputs: Locked checkpoint + DS03
- Required output: outputs/transfer_ds01_ds03.*

### 32 — `32_eval_per_channel_per_run.py`
- Goal: Export metrics for every channel × horizon × target run in z and physical units.
- Inputs: Predictions
- Required output: outputs/per_channel_run.csv.

### 33 — `33_eval_normalization_sensitivity.py`
- Goal: Compare source-zscore, source-robust, target-support adaptation and target-oracle diagnostic scaling.
- Inputs: Checkpoint + normalizers
- Required output: outputs/normalization_sensitivity.*. Oracle must not be primary result.

### 34 — `34_eval_missing_sensor_schema.py`
- Goal: Stress 17/10/8/6/4 sensor schemas, persistent missing sensors and sensor failure during an episode.
- Inputs: Checkpoint
- Required output: Schema robustness curves.

### 35 — `35_eval_random_masks_anomalies.py`
- Goal: Evaluate masks, Gaussian noise, spikes, drift, step shifts, missing blocks, bias and mixed anomalies.
- Inputs: Checkpoint + corruption manifest
- Required output: Robustness table/curves.

### 36 — `36_eval_uncertainty_calibration.py`
- Goal: Evaluate Gaussian NLL, calibration, 50/90% coverage, interval width and mean-prediction RMSE separately.
- Inputs: Probabilistic checkpoint
- Required output: Calibration report.

### 37 — `37_eval_action_conditioning.py`
- Goal: Test correct, zeroed, sample-shuffled and time-shuffled future actions. Measure forecast degradation and counterfactual ranking.
- Inputs: Checkpoint
- Required output: Action-identifiability report.

### 38 — `38_eval_cem_planning.py`
- Goal: Use the world model inside CEM/MPC. Apply temperature/wear constraints in physical units, not z units.
- Inputs: Checkpoint + normalizers
- Required output: Planning metrics: energy, wear, violations, deadline success, regret.

### 39 — `39_statistical_tests_n6.py`
- Goal: Perform target-run-level paired tests: exact sign-flip/permutation, Wilcoxon when meaningful, bootstrap CI. No window-level p-values.
- Inputs: Per-run results
- Required output: Statistical report for n=6.

### 40 — `40_generate_20_random_methods.py`
- Goal: Generate the 20 architecture candidates defined in this taskbook. Enforce uniqueness and save every full config.
- Inputs: Base config
- Required output: configs/search_v2/M00…M19 + manifest.json.

### 41 — `41_train_one_random_candidate.py`
- Goal: Train one candidate with one seed on DS01 only. Must implement all P3-FIX validation/anti-collapse safeguards.
- Inputs: Candidate config
- Required output: Candidate checkpoint, validation history and diagnostics.

### 42 — `42_run_20_random_methods_dgx.py`
- Goal: Launch 20 candidates × 3 discovery seeds = 60 DGX jobs. Never touch DS03.
- Inputs: Manifest + GPUs
- Required output: 60 source-only jobs and status manifest.

### 43 — `43_rank_methods_validation_only.py`
- Goal: Rank candidates using the source-validation composite defined below. Exclude collapsed/invalid runs before ranking.
- Inputs: 60 source-validation results
- Required output: ranked_methods.csv with mean, SD and failure flags.

### 44 — `44_lock_best_method.py`
- Goal: Select winner without DS03, freeze full config, code commit/hash, normalizer, seeds and checkpoint SHA-256.
- Inputs: Ranking
- Required output: locked_method.json + cryptographic hashes.

### 45 — `45_test_locked_method_ds03.py`
- Goal: First target-machine evaluation of the locked winner. No further architecture changes based on DS03.
- Inputs: Locked method
- Required output: Final zero-shot DS03 result used for V1.

### 46 — `46_fewshot_target_adaptation.py`
- Goal: Adapt only approved lightweight parameters using 1/2/3/6 runs or predefined fractions. Keep evaluation runs disjoint.
- Inputs: Locked method + target support
- Required output: Few-shot adaptation curves.

### 47 — `47_online_causal_adaptation.py`
- Goal: Perform causal prequential adaptation using only outcomes observed so far.
- Inputs: Locked method + ordered target stream
- Required output: Online adaptation curve and failure analysis.

### 48 — `48_predict_any_input.py`
- Goal: Inference API for one valid arbitrary CNC context with known sensor vocabulary, missing values allowed and future actions supplied.
- Inputs: JSON input + checkpoint
- Required output: Physical-unit mean/std predictions.

### 49 — `49_predict_variable_sensor_schema.py`
- Goal: Inference wrapper for named subsets of known sensors. Unknown sensors must fail loudly unless explicitly remapped.
- Inputs: Named sensor-series JSON
- Required output: Expanded masked input and predictions.

### 50 — `50_novelty_component_factorial.py`
- Goal: Factorial study of the claimed novelty: plain JEPA → anti-collapse → masking → action identifiability → schema adaptation → full SAAC-JEPA.
- Inputs: source_train/source_val, then locked evaluation rules
- Required output: Component contribution table.

### 51 — `51_build_main_result_tables.py`
- Goal: Build paper-ready tables from audited outputs, including per-horizon/per-channel/run summaries.
- Inputs: Output files
- Required output: Main result workbook/CSV/LaTeX tables.

### 52 — `52_build_reviewer_response_matrix.py`
- Goal: Map every reviewer concern to experiment, script, result and manuscript location.
- Inputs: Reviewer points + outputs
- Required output: reviewer_response_matrix.csv.

### 53 — `53_reproduce_all_dgx.py`
- Goal: Reproduction launcher with explicit phases. Must stop if P3-FIX gate fails or if lock is missing before DS03.
- Inputs: Config + GPUs
- Required output: Reproducible command log.

### 54 — `54_smoke_test_core.py`
- Goal: Fast CPU/GPU smoke test for data, JEPA forward/backward, checkpointing, metrics, baselines, adaptation and planning.
- Inputs: Synthetic data
- Required output: Pass/fail smoke report.

### 55 — `55_triple_review.py`
- Goal: Automated three-pass audit: syntax/imports, execution/smoke, scientific-protocol/leakage checks.
- Inputs: Repository
- Required output: REVIEW_STATUS.md.

### 56 — `56_eval_baseline_per_channel_run.py`
- Goal: Produce the same per-channel/per-horizon/per-run export for every baseline as for SAAC-JEPA.
- Inputs: Baseline checkpoints
- Required output: Comparable baseline CSVs.

### 57 — `57_sampling_rate_sensitivity_train_eval.py`
- Goal: Retrain/evaluate at 0.5/1/2/5 Hz while preserving approximate physical context and forecast durations.
- Inputs: Dataset + config
- Required output: Sampling-rate sensitivity table.

### 58 — `58_source_group_cv.py`
- Goal: Grouped cross-validation across DS01 sessions to quantify source-session variability and avoid dependence on one split.
- Inputs: DS01 sessions
- Required output: Grouped CV manifest and metrics.

### 59 — `59_target_run_bootstrap.py`
- Goal: Bootstrap independent DS03 runs to quantify uncertainty in aggregate transfer gains.
- Inputs: Per-run target results
- Required output: Bootstrap CI distributions and summary.

## Architecture search V2

### Why this search is different from the old random search

The original random search mixed many dimensions before the P3 protocol was trustworthy. The revised search only starts after P3-FIX. It deliberately spans action injection, masking, anti-collapse, latent weight, EMA, normalization, model scale and schema adaptation while keeping the final target hidden.

### Candidate dimensions

- Mask mode: random, block, channel, event, mixed
- Mask ratio: 0.20, 0.35, 0.50
- Action injection: token, FiLM, cross-attention
- Transformer norm: pre (primary), post/none only in dedicated ablation
- Latent LayerNorm: ON/OFF
- VICReg: none, pooled, per-horizon; log placement on context/target/predictor
- Latent loss weight: 0.5, 1.0, 2.0 after initial coarse audit
- Target aggregation: pooled, per-horizon
- Schema consistency: 0, 0.1, 0.2 on latent predictions
- Action recovery: 0, 0.05, 0.10
- EMA: fixed controls and scheduled 0.99→0.9999
- Model size: d_model 128/256/384/512 and depth 4/6/8
- Normalizer: source z-score, source robust
- Physical head at fine-tune: fresh primary; loaded head only as contamination control

### 20 candidate architectures

| ID | Description | Mask | Ratio | Action | Latent LN | VICReg | λlatent | Target | λschema | λaction-rec | EMA | d | Layers | Norm | FT head |
|---|---|---:|---:|---|---|---|---:|---|---:|---:|---|---:|---:|---|---|
| M00 | Plain JEPA control | mixed | 0.35 | token | False | none | 1.00 | per_horizon | 0.00 | 0.00 | fixed_0.996 | 256 | 6 | source_zscore | fresh |
| M01 | JEPA + per-horizon VICReg | mixed | 0.35 | token | False | per_horizon_context_target | 1.00 | per_horizon | 0.00 | 0.00 | fixed_0.996 | 256 | 6 | source_zscore | fresh |
| M02 | Schema-adaptive latent consistency | channel | 0.35 | token | False | per_horizon_context_target | 1.00 | per_horizon | 0.10 | 0.00 | fixed_0.996 | 256 | 6 | source_zscore | fresh |
| M03 | Schema + action recovery | channel | 0.35 | token | False | per_horizon_context_target | 1.00 | per_horizon | 0.10 | 0.05 | fixed_0.996 | 256 | 6 | source_zscore | fresh |
| M04 | FiLM action injection | mixed | 0.35 | film | False | per_horizon_context_target | 1.00 | per_horizon | 0.10 | 0.05 | fixed_0.996 | 256 | 6 | source_zscore | fresh |
| M05 | Cross-attention action injection | mixed | 0.35 | cross_attn | False | per_horizon_context_target | 1.00 | per_horizon | 0.10 | 0.05 | fixed_0.996 | 256 | 6 | source_zscore | fresh |
| M06 | Event masking | event | 0.35 | cross_attn | False | per_horizon_context_target | 1.00 | per_horizon | 0.10 | 0.05 | fixed_0.996 | 256 | 6 | source_zscore | fresh |
| M07 | Heavy channel masking | channel | 0.50 | cross_attn | False | per_horizon_context_target | 1.00 | per_horizon | 0.20 | 0.05 | fixed_0.996 | 256 | 6 | source_zscore | fresh |
| M08 | Light mixed masking | mixed | 0.20 | cross_attn | False | per_horizon_context_target | 1.00 | per_horizon | 0.10 | 0.05 | fixed_0.996 | 256 | 6 | source_zscore | fresh |
| M09 | Latent LayerNorm ON | mixed | 0.35 | cross_attn | True | per_horizon_context_target | 1.00 | per_horizon | 0.10 | 0.05 | fixed_0.996 | 256 | 6 | source_zscore | fresh |
| M10 | Pooled VICReg/target | mixed | 0.35 | cross_attn | False | pooled_context_target | 1.00 | pooled | 0.10 | 0.05 | fixed_0.996 | 256 | 6 | source_zscore | fresh |
| M11 | Low latent weight | mixed | 0.35 | cross_attn | False | per_horizon_context_target | 0.50 | per_horizon | 0.10 | 0.05 | fixed_0.996 | 256 | 6 | source_zscore | fresh |
| M12 | High latent weight | mixed | 0.35 | cross_attn | False | per_horizon_context_target | 2.00 | per_horizon | 0.10 | 0.05 | fixed_0.996 | 256 | 6 | source_zscore | fresh |
| M13 | Scheduled EMA | mixed | 0.35 | cross_attn | False | per_horizon_context_target | 1.00 | per_horizon | 0.10 | 0.05 | schedule_0.99_0.9999 | 256 | 6 | source_zscore | fresh |
| M14 | Robust source normalization | mixed | 0.35 | cross_attn | False | per_horizon_context_target | 1.00 | per_horizon | 0.10 | 0.05 | schedule_0.99_0.9999 | 256 | 6 | source_robust | fresh |
| M15 | Compact model | mixed | 0.35 | cross_attn | False | per_horizon_context_target | 1.00 | per_horizon | 0.10 | 0.05 | schedule_0.99_0.9999 | 128 | 4 | source_zscore | fresh |
| M16 | Medium-wide model | mixed | 0.35 | cross_attn | False | per_horizon_context_target | 1.00 | per_horizon | 0.10 | 0.05 | schedule_0.99_0.9999 | 384 | 6 | source_zscore | fresh |
| M17 | Large model | mixed | 0.35 | cross_attn | False | per_horizon_context_target | 1.00 | per_horizon | 0.10 | 0.05 | schedule_0.99_0.9999 | 512 | 8 | source_zscore | fresh |
| M18 | Head-contamination control | mixed | 0.35 | cross_attn | False | per_horizon_context_target | 1.00 | per_horizon | 0.10 | 0.05 | schedule_0.99_0.9999 | 256 | 6 | source_zscore | loaded |
| M19 | SAAC-JEPA full candidate | mixed | 0.35 | cross_attn | False | per_horizon_context_target | 1.00 | per_horizon | 0.20 | 0.10 | schedule_0.99_0.9999 | 384 | 6 | source_robust | fresh |

### Discovery schedule

- [ ] Generate M00–M19 with script 40.
- [ ] Run each candidate with seeds 0, 1, 2 on DS01 only: 20 × 3 = 60 jobs.
- [ ] Each candidate must output clean validation, schema-drop validation, masked validation, per-horizon RMSE, action-use diagnostic, calibration and latent-health metrics.
- [ ] Any run with checkpoint-load failure, NaNs, latent collapse or deterministic-validation failure is marked invalid, not silently ranked.
- [ ] Rank by the validation composite below.
- [ ] Take the top 5 candidates and rerun them with 5 seeds total for confirmation.
- [ ] Use paired source-validation comparisons and parameter-count/compute reporting.
- [ ] Choose one final configuration.
- [ ] Freeze config, code hash, normalizer and checkpoint hash with script 44.
- [ ] Only after the lock exists, run script 45 on DS03.

### Validation-only selection score

Use lower-is-better standardized terms computed on source validation only:

`score = 0.30*clean_RMSE + 0.25*schema_drop_RMSE + 0.15*masked_RMSE + 0.10*long_horizon_RMSE + 0.10*calibration_penalty + 0.10*SSL_latent_val + collapse_penalty + weak_action_penalty`

Rules:
- `collapse_penalty` is large if effective rank/variance falls below audited thresholds.
- `weak_action_penalty` is applied if shuffling future actions barely changes predictions or counterfactual ranking.
- Normalize score components across candidates using the same DS01 validation folds.
- Do not include DS03 zero-shot or few-shot metrics in this score.
- Also publish the raw metrics. The composite is only a selection mechanism.

### What counts as the best architecture

- Best discovery candidate: lowest mean composite score across the 3 discovery seeds.
- Best confirmed candidate: top candidate after top-5 rerun with 5 seeds, provided it has no collapse and no major action-identifiability failure.
- Best V1 method: locked candidate evaluated once on DS03 plus its predefined few-shot/robustness experiments.
- Do not redesign the method after seeing DS03. Any later redesign belongs to a new experiment/version.
- Do not call it SOTA unless it beats fair official/reproduced baselines under the same audited protocol.

## Required result matrix for the winning model

- [ ] DS01 clean: persistence, drift, supervised baselines, reconstruction SSL, JEPA variants.
- [ ] DS01 schema-drop: 17→10/8/6/4 sensors.
- [ ] DS01 corruptions: mask/noise/spike/drift/step/missing-block/bias.
- [ ] DS03 zero-shot: per run, per channel, per horizon.
- [ ] DS03 few-shot: 1/2/3/6 runs or fixed disjoint support fractions.
- [ ] Action diagnostic: true vs zero vs sample-shuffled vs time-shuffled actions.
- [ ] Uncertainty: RMSE/MAE/NLL/coverage.
- [ ] Planning: energy, temperature violations, wear, deadline success and oracle regret.
- [ ] Statistical report: exact paired test and bootstrap over independent DS03 runs.

## Decision rules after the 60-job search

- If no candidate beats persistence/drift on meaningful horizons, stop and fix forecasting formulation before transfer claims.
- If JEPA does not improve source clean RMSE but improves schema-drop, few-shot or DS03 transfer, keep JEPA and make transfer the central claim.
- If the physical head is harmful after SSL, always reinitialize it for the primary method and keep loaded-head results only as an ablation.
- If cross-attention improves action-identifiability but not RMSE, judge it on the V1 claim, which includes controllable/action-conditioned dynamics.
- If the large model only wins by capacity, compare matched-parameter baselines before claiming methodological superiority.
- If the winner changes drastically across seeds, do not lock it yet. Increase seeds or simplify the search space.

## Final V1 RoboPAD claim to test

> Does schema-adaptive, action-conditioned JEPA pretraining learn transferable latent dynamics that remain useful under cross-machine shift, partial sensor overlap, limited target support and corrupted observations?

Source-machine clean RMSE is a diagnostic, not the only success criterion.
