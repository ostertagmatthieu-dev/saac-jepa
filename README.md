# SAAC-JEPA: Schema-Adaptive Action-Conditioned JEPA for Cross-Machine CNC Transfer

## Paper

**Schema-Adaptive Action-Conditioned JEPA for Cross-Machine CNC Transfer under Partial Sensor Overlap**

Ayoub Louaye Bouaziz (Universite de Bretagne Occidentale), Matthieu Ostertag (Mines Nancy, Universite de Lorraine), Anton Demasles (Mines Nancy, Universite de Lorraine)

arXiv: link to be added after announcement

Project page with animated schematics: https://ostertagmatthieu-dev.github.io/saac-jepa/

This repository accompanies the arXiv preprint; the pipeline, configuration files, the twenty candidate specifications and the audit scripts are those used for the paper.


From-scratch PyTorch pipeline for action-conditioned JEPA world modeling of CNC sensor dynamics, cross-machine transfer, missing sensors, anomalies, adaptation, and planning.

The code is designed around the reviewer protocol: source DS01 (THWS five-axis CNC milling dataset, 62 NC-program sessions), target DS03 (FH JOANNEUM CNC machining repository, 7 independent runs), evaluation around 1 Hz, 17 source channels and 10 overlapping transfer channels. `configs/base.yaml` ships with explicit placeholder sensor/action names; map them to the real dataset columns (see 'Real database mapping') before scientific runs.

The original CNC proposal is action-conditioned: current machine state and candidate actions predict future production, energy, temperature and wear. This implementation extends that idea into a schema-adaptive JEPA and an audited transfer benchmark.

## Core architecture

`history sensors + past actions -> flexible sensor encoder -> temporal context latent`

`future actions + context latent -> causal JEPA predictor -> future latent sequence`

`future states -> EMA target encoder -> target latent sequence`

Training combines latent prediction, optional per-horizon VICReg, physical probabilistic forecasting, action recovery and schema-consistency losses.

Missing or absent sensors use separate value, presence and schema indicators. A target machine may expose 10 of the 17 known sensors without changing tensor dimensionality or retraining the input layer.

## Numbered scripts

### 00 to 09: protocol and leakage audit

00 validate dataset
01 audit machines, sessions, runs and channel coverage
02 create group-disjoint protocol splits
03 inspect resampling rates
04 fit train-only normalizers
05 audit window leakage
06 define corruption suite
07 audit 17 to 10 schema overlap
08 audit target-statistic leakage
09 quantify the weak statistical power of n=7

### 10 to 19: JEPA from scratch and ablations

10 pretrain action-conditioned JEPA from random initialization
11 fine-tune physical probabilistic forecast head
12 train schema-adaptive action-conditioned JEPA
13 action-conditioning ablation
14 masking-policy ablation
15 latent-loss-weight ablation
16 VICReg none vs pooled vs per-horizon
17 latent LayerNorm on/off plus encoder pre/post norm
18 per-horizon vs pooled latent target
19 EMA target-encoder ablation

### 20 to 29: non-JEPA and reconstruction baselines

20 DLinear, MLP, GRU, LSTM, TCN, Transformer, TSMixer, PatchTST-like, iTransformer-like and RSSM
21 masked autoencoding baseline
22 SimMTM-inspired reconstruction baseline
23 PatchFormer-inspired hierarchical/block masked baseline
24 EMIT-inspired event-masked baseline
25 MMR-inspired multiscale/wavelet masked baseline
26 LoMaR-inspired local reconstruction baseline adapted to time series
27 RSSM world-model baseline
28 forecasting capacity sweep
29 export identical splits/windows for official external baseline implementations

Important: scripts 22 to 26 are controlled in-house approximations for ablation and engineering comparisons. They must be called `-style` or `-inspired` in the paper unless the official implementation is reproduced exactly. Script 29 exists for the official-repository comparison.

### 30 to 39: audited evaluation

30 source and target multi-horizon evaluation
31 zero/few-shot DS01 to DS03 transfer
32 per-channel/per-run metrics in z and physical units
33 source-normalizer sensitivity
34 missing sensor/schema stress 17/10/8/6/4
35 random masks, noise, spikes, drift, step shifts, missing blocks and bias
36 probabilistic calibration
37 true vs zero vs shuffled future actions
38 CEM planning with physical-unit temperature/wear constraints
39 n=7 run-level paired statistical tests

### 40 to 45: 20-method search without test leakage

40 generate 20 unique random JEPA designs
41 train one candidate on DS01 only
42 run 20 methods x 3 seeds = 60 jobs across DGX GPUs
43 rank methods by mean source-validation score across seeds
44 lock the winning method and checkpoint using SHA-256
45 evaluate the locked model on DS03 for the first time

The random search varies mask type/ratio, action injection, encoder norm, latent LayerNorm, VICReg, latent weight, horizon aggregation, schema consistency, action recovery, EMA, model scale and source normalizer.

This procedure is intended for model discovery. It does not prove SOTA. SOTA requires fair official/reproduced baselines under the same audited protocol.

### 46 to 50: adaptation and proposed novelty

46 few-shot target adaptation
47 causal online adaptation
48 predict a new input with optional support set
49 inference with a variable known sensor subset
50 component-factorial experiment for SAAC-JEPA

### 51 to 59: paper/reviewer outputs

51 main tables
52 reviewer-response matrix
53 DGX reproduction launcher
54 core smoke test
55 automated three-pass review
56 baseline per-channel/per-run export
57 full sampling-rate retrain/evaluation sensitivity
58 grouped DS01 session CV manifest
59 target-run bootstrap uncertainty

## Proposed novelty to test

SAAC-JEPA: Schema-Adaptive Action-Conditioned JEPA for cross-machine CNC dynamics.

The novelty should not be phrased as `JEPA for time series`. Existing work already covers that territory. The paper should test whether action-conditioned latent prediction plus explicit sensor-schema modeling improves cross-machine transfer when source and target expose different sensor subsets, especially with few target runs, anomalies and planning.

See `NOVELTY_GAP.md`.

## Reviewer mapping

Run:

```bash
python scripts/52_build_reviewer_response_matrix.py
```

The matrix includes every reviewer concern and the scripts that answer it.

## Data

- THWS five-axis CNC milling dataset: https://doi.org/10.5281/zenodo.14094887 (CC BY 4.0)
- FH JOANNEUM CNC machining repository: https://doi.org/10.17632/gtvvwmz7r7.2 (CC BY 4.0)

## Setup

```bash
pip install -r requirements.txt
```

For a DGX, use the installed CUDA/PyTorch stack if it is newer and compatible.

## Real database mapping

Place the DB at `data/cnc.csv` or change `paths.data` in `configs/base.yaml`.

Map:

- timestamp
- machine ID
- session ID
- run ID
- 17 source sensor columns
- 10 target-overlap sensor columns
- action columns

Do not silently substitute sensor names. The placeholders in the config are not claims about the real dataset.

## First audited run

```bash
python scripts/00_validate_dataset.py --config configs/base.yaml
python scripts/01_audit_sessions_channels.py --config configs/base.yaml
python scripts/05_window_leakage_audit.py --config configs/base.yaml
python scripts/08_normalization_leakage_audit.py --config configs/base.yaml
```

Inspect these outputs before any model training.

## JEPA from scratch

```bash
python scripts/10_pretrain_jepa_from_scratch.py --config configs/base.yaml --out outputs/jepa_pretrain --device cuda:0
python scripts/11_finetune_jepa_forecaster.py --config configs/base.yaml --pretrained outputs/jepa_pretrain/best.pt --out outputs/jepa_finetune --device cuda:0
```

## Main reviewer ablations

```bash
python scripts/15_train_latent_weight_ablation.py --config configs/base.yaml --device cuda:0
python scripts/16_train_vicreg_ablation.py --config configs/base.yaml --device cuda:1
python scripts/17_train_layernorm_ablation.py --config configs/base.yaml --device cuda:2
python scripts/18_train_horizon_aggregation_ablation.py --config configs/base.yaml --device cuda:3
python scripts/19_train_ema_ablation.py --config configs/base.yaml --device cuda:4
```

## Reconstruction and dynamics baselines

```bash
python scripts/20_train_supervised_dynamics_baselines.py --config configs/base.yaml --device cuda:0
python scripts/21_train_masked_mae_baseline.py --config configs/base.yaml --device cuda:1
python scripts/22_train_simmtm_style_baseline.py --config configs/base.yaml --device cuda:2
python scripts/23_train_patchformer_style_baseline.py --config configs/base.yaml --device cuda:3
python scripts/24_train_emit_style_baseline.py --config configs/base.yaml --device cuda:4
python scripts/25_train_mmr_wavelet_style_baseline.py --config configs/base.yaml --device cuda:5
python scripts/26_train_lomar_ts_style_baseline.py --config configs/base.yaml --device cuda:6
python scripts/29_export_official_baseline_inputs.py --config configs/base.yaml
```

## 20 random methods on DGX

The 20 candidate configs are already included in `configs/random_methods`.

Preview 60 jobs:

```bash
python scripts/42_run_20_random_methods_dgx.py --manifest configs/random_methods/manifest.json --gpus 0,1,2,3,4,5,6,7 --dry-run
```

Run:

```bash
python scripts/42_run_20_random_methods_dgx.py --manifest configs/random_methods/manifest.json --gpus 0,1,2,3,4,5,6,7
python scripts/43_rank_methods_validation_only.py
python scripts/44_lock_best_method.py
```

Only after the lock file exists:

```bash
python scripts/45_test_locked_method_ds03.py --device cuda:0
```

## Main transfer reporting

```bash
python scripts/31_eval_transfer_ds01_to_ds03.py --ckpt outputs/jepa_finetune/best.pt --device cuda:0
python scripts/32_eval_per_channel_per_run.py --ckpt outputs/jepa_finetune/best.pt --device cuda:0
python scripts/33_eval_normalization_sensitivity.py --ckpt outputs/jepa_finetune/best.pt --device cuda:0
python scripts/34_eval_missing_sensor_schema.py --ckpt outputs/jepa_finetune/best.pt --device cuda:0
python scripts/37_eval_action_conditioning.py --ckpt outputs/jepa_finetune/best.pt --device cuda:0
python scripts/39_statistical_tests_n6.py --jepa outputs/per_channel_run.csv --baseline <baseline_per_channel_run.csv>
python scripts/57_sampling_rate_sensitivity_train_eval.py --config configs/base.yaml --device cuda:0
```

## Verification

```bash
python scripts/54_smoke_test_core.py
python scripts/55_triple_review.py
```

`REVIEW_STATUS.md` records the checks already executed while building this package.

## Critical scientific limitation

No amount of random architecture search fixes having only one source and one target machine. The 62 source sessions and seven target runs permit a useful audited case study, but broad cross-machine generalization requires more machines or an external dataset. Keep that limitation explicit in the paper.

## License

MIT, see LICENSE.

## Citation

See CITATION.cff.
