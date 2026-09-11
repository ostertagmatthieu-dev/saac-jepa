# Results

Every number on this page is in **z units of the source-train normalizer**, lower is better
unless stated otherwise. Two evaluation sets recur and they are not interchangeable:

- **Source** — DS01. The SAAC-JEPA rows are means over seeds on `source_val` (3,423 windows);
  the official baselines are scored on the `source_test` split (5,189 windows, 17 sensors).
  **The source column therefore does not compare like with like.**
- **Target** — DS03, the 10 shared channels over 7 independent runs, **2,457 windows**.

DS03 has been read exactly twice: the single sealed pass of the locked model, and the declared
post-lock RevIN ablation described below. See [protocol.md](protocol.md) for how the lock works.

---

## 1. Main table

### Does pretraining help on the source machine?

| Setting | Source RMSE | Target zero-shot RMSE | Notes |
|---|---|---|---|
| Scratch | 0.811 ± 0.022 | — | five matched seeds |
| Pretrained body + fresh head | 0.813 ± 0.022 | — | p = 0.76 vs scratch |
| Complete pretrained checkpoint | 0.812 ± 0.012 | — | third matched control |

No. Under a matched budget, matched loaders and matched seeds, SSL pretraining does not improve
clean-source forecasting over training from scratch. This is the P3-FIX gate's A/B/C experiment
(`scripts/63`); arm C exists to rule out a contaminated head explaining arm B.

### Does it transfer to an unseen machine?

| Setting | Source RMSE | Target zero-shot RMSE | Notes |
|---|---|---|---|
| Persistence | 1.135 | 0.654 | trivial floor; 1.135 on source validation, 1.128 on the source test split |
| Linear drift | 0.928 | — | trivial reference |
| PatchTST (official, RevIN) | 0.804 | 0.503 | deterministic, single run |
| iTransformer (official, RevIN) | 0.822 | 0.498 | deterministic, single run |
| **SAAC-JEPA (locked, M03)** | **0.822 ± 0.009** | **0.546** | probabilistic (mean and log-variance head); NLL 0.52; R² 0.012; single declared pass |
| SAAC-JEPA + RevIN (post-lock) | 0.766 ± 0.001 | 0.495 ± 0.004 | same architecture, instance normalisation on; NLL 20.6; three seeds; diagnostic |

Row definitions:

- **Persistence** — repeat the last observed value across the horizon. The 0.654 target figure
  comes from the same sealed pass as the locked model.
- **Linear drift** — extrapolate the last observed slope.
- **PatchTST / iTransformer (official)** — the authors' repositories, pinned to the commits in
  `third_party/README.md`, driven through their own run scripts on our exported windows
  (`scripts/29` exports, `scripts/66` runs). Both ship RevIN-style instance normalisation.
  Single deterministic run each, repository defaults, no hyper-parameter sweep.
- **SAAC-JEPA (locked, M03)** — `configs/search_v2/M03.yaml`, the candidate selected on source
  validation alone and frozen under a SHA-256 lock. Source figure is the seven-seed mean ± SD on
  source validation; target figure is the single confirmatory pass.
- **SAAC-JEPA + RevIN (post-lock)** — `configs/revin/M03_revin.yaml`, byte-identical to M03 plus
  `model.revin.enabled: true`. Three seeds; the second, declared read of DS03.

Two further source-validation references, for scale: **RSSM 0.759** and **MLP 0.771**, both
better than the locked candidate's 0.822 on the source machine. Ordinary supervised baselines
are stronger on source. The claim here is narrower — the locked model beats persistence on a
machine it has never seen, having lost 7 of 17 channels, with its configuration chosen on source
data alone.

## 2. Per-horizon target R²

| Horizon | 1 s | 2 s | 4 s | 8 s | 16 s |
|---|---|---|---|---|---|
| Target R² | 0.035 | 0.055 | 0.052 | −0.023 | −0.059 |

The locked model explains variance only at short horizons. At 8 s and 16 s it is **below the
pooled target-mean predictor**. Pooled over all horizons the target R² is 0.012 — barely above
zero, and that is the honest reading of a 0.546 RMSE against a 0.654 persistence floor.

## 3. Few-shot target adaptation (pre-lock model)

| Target support | 0 % | 5 % | 10 % | 20 % |
|---|---|---|---|---|
| Target RMSE | 0.612 | 0.611 | 0.540 | 0.520 |

Additional metrics where the project page states them: 0 % support gives MAE 0.401 and
R² = −0.244; 10 % gives R² = 0.046; 20 % gives MAE 0.299 and R² = 0.167.

Three caveats, all of which matter:

- This curve was measured on the **pre-lock** model, not the locked one. It is diagnostic.
- At 5 % support there is no complete 48-step support window, so that point is effectively
  zero-shot — it is not an adaptation failure.
- Each point is evaluated on the query windows left after the support fraction is removed, so
  the evaluation set shrinks along the curve. The persistence reference of 0.654 comes from the
  separate sealed 2,457-window pass and is not directly commensurable with the query subsets.

Re-running this sweep on the locked model is the obvious next step and has not been done.

## 4. Calibration

The locked model has a probabilistic head (mean and log-variance per channel). On the pre-lock
model, predictive intervals at a **nominal 90 % covered 67 %** empirically — over-confident.
The locked model reports target NLL 0.52 on its sealed pass; interval coverage has not been
re-measured on it.

## 5. Latent health

The P3-FIX change of regulariser placement raised target-encoder **effective rank from roughly
5 % to 58 %** of the latent dimensionality. Before the fix the latent loss was being minimised
against a nearly constant target; see [protocol.md](protocol.md#4-the-p3-fix-gate).

In the post-lock ablation runs, measured on source validation, the control arm shows
`eff_rank_frac` 0.427 ± 0.072 after fine-tuning and the RevIN arm 0.463 ± 0.006.

## 6. Action conditioning

On the pre-lock model, shuffling the future actions moved target RMSE by **less than 0.005**.
That is a weak signal, and it has not been re-measured on the locked model. Whether the
transferred latent actually uses the control input is an open question in this work, not a
settled one. On source validation the post-lock ablation does measure a shuffle/true ratio of
1.064 ± 0.024 for the control arm and 1.179 ± 0.001 with RevIN, so the action channel is not
inert on the source machine.

---

## Post-lock RevIN ablation (paper App. H)

The locked model normalises with a fixed source-train z-score. The official PatchTST and
iTransformer baselines use RevIN, per-window instance normalisation. This ablation isolates
exactly that difference: `configs/search_v2/M03.yaml` (control, verbatim) against
`configs/revin/M03_revin.yaml` (identical plus `model.revin.enabled: true`), three paired seeds
each through `scripts/41`, then a second, declared read of DS03 on all six runs with no
selection on the target.

`src/cncjepa/models/revin.py` (`MaskedRevIN`) is presence-aware: statistics are computed per
(window, channel) on the **context rows only** and over **present entries only** — masked
entries are zero in `data.py`, so a naive mean would be biased. A channel never observed in the
window falls back to the identity, which preserves V1 behaviour for the 7 channels DS03 does not
have. The future window is normalised with context statistics, never with its own. The Gaussian
head is de-normalised (`mu·σ + μ`, `logvar + 2 log σ`), so the whole V1 metric space is
unchanged — the trivial-predictor anchor is 0.9575 on both arms, bitwise. Settings mirror the
official baselines in `scripts/66`: `affine = 0`, `subtract_last = 0`, `eps = 1e-5`. With the
flag absent or false the code path is bitwise V1, verified by `tests/test_p3fix.py` section (i).

### Source validation, three paired seeds, common eval space

| Component | M03 (control) | M03 + RevIN | Δ (RevIN − control) | Bootstrap 95 % | RevIN wins |
|---|---|---|---|---|---|
| clean RMSE | 0.8190 ± 0.0103 | **0.7663 ± 0.0012** | −0.0527 | [−0.0640, −0.0457] | 3/3 |
| schema-drop RMSE | 0.9180 ± 0.0047 | **0.8867 ± 0.0034** | −0.0313 | [−0.0357, −0.0248] | 3/3 |
| masked RMSE | 0.8272 ± 0.0096 | **0.7862 ± 0.0023** | −0.0409 | [−0.0508, −0.0335] | 3/3 |
| long-horizon RMSE | 0.8683 ± 0.0073 | **0.8487 ± 0.0039** | −0.0196 | [−0.0234, −0.0167] | 3/3 |
| calibration penalty | 0.1242 ± 0.0270 | **0.0349 ± 0.0022** | −0.0892 | [−0.1201, −0.0691] | 3/3 |
| SSL latent validation loss | 1.1874 ± 0.0189 | **1.0640 ± 0.0214** | −0.1234 | [−0.1660, −0.0952] | 3/3 |
| action sensitivity (higher better) | 1.0639 ± 0.0243 | **1.1790 ± 0.0013** | +0.1151 | [+0.1004, +0.1426] | 3/3 |
| effective rank fraction (higher better) | 0.4266 ± 0.0717 | 0.4626 ± 0.0062 | +0.0360 | [−0.0028, +0.1118] | 1/3 |
| eval-space anchor RMSE | 0.9575 ± 0.0000 | 0.9575 ± 0.0000 | +0.0000 | [+0.0000, +0.0000] | — |

Source-validation NLL in model space: control 3.018, RevIN 1.490. Empirical coverage at a
nominal 90 %: 0.776 against 0.865. On source validation, RevIN is better on every headline RMSE
component and on calibration.

With **n = 3 paired seeds the exact sign-flip test cannot go below p = 0.125**; read the
bootstrap intervals and the per-seed wins, not the p-values.

**One reservation, declared.** All three RevIN runs are flagged `invalid: ssl_latent_collapse`
by the `trainers.latent_health` gate, on the single sub-criterion `zpred_std_min < 0.05`
(0.040–0.041; the control sits at 0.059–0.061, itself near the threshold). That threshold is in
raw latent units — M03 has no latent LayerNorm — so it depends on the input scale, which is
exactly what RevIN changes. The scale-free criterion, effective rank, is twice as good with
RevIN (0.45–0.49 against 0.22–0.23 after SSL), and post-fine-tune latent health is
indistinguishable between arms. The gate is considered not meaningful here; **it was not
modified**, and it should be made scale-insensitive before any future selection is re-run.

### Target, second declared read, per seed

| Arm | Seed | RMSE | MAE | R² | NLL |
|---|---|---|---|---|---|
| M03 (control) | 0 | 0.5456 | 0.3524 | +0.0118 | 0.516 |
| M03 (control) | 1 | 0.5716 | 0.3682 | −0.0847 | −0.002 |
| M03 (control) | 2 | 0.5470 | 0.3496 | +0.0067 | 2.147 |
| **M03 mean ± SD (n = 3)** | | **0.5547 ± 0.0146** | | | 0.89 |
| M03 + RevIN | 0 | 0.4994 | 0.2796 | +0.1720 | 22.48 |
| M03 + RevIN | 1 | 0.4924 | 0.2722 | +0.1950 | 15.07 |
| M03 + RevIN | 2 | 0.4928 | 0.2753 | +0.1937 | 24.35 |
| **M03 + RevIN mean ± SD (n = 3)** | | **0.4949 ± 0.0039** | | | 20.6 |
| Persistence | — | 0.6540 | 0.3162 | −0.4200 | — |

Paired differences, RevIN minus control: **−0.046, −0.079, −0.054** (3/3). All six runs pass the
checkpoint load audit (`weights_changed: true`, no missing or unexpected keys), and each is
scored on the full 2,457 target windows.

Note that the V1 locked pass reports 0.546 — that is seed 0 of the lock, and it reappears here as
the control arm's seed 0 (0.5456). The three-seed control mean, 0.555 ± 0.015, is the right
spread to keep in mind around the single locked number.

At 0.495 ± 0.004 the RevIN arm is level with PatchTST (0.503) and iTransformer (0.498). **The
~8 % gap to the official baselines closes, and it closes on normalisation, not on architecture.**
That is the finding. It is still not a SOTA claim: the baselines are single-seed at repository
defaults with no hyper-parameter sweep.

### The calibration collapse

Target NLL rises from **0.9 to 20.6**, and empirical coverage at nominal 90 % falls from 0.953
to 0.874. The diagnosis, on seed 0 and per channel: **11.5 % of RevIN predictions sit on the
variance floor** `logvar = −8` (σ = 0.018) against 0 % for the control. Per-channel NLL is
concentrated in four channels — spindle torque 89, z power 51, spindle current 40, spindle power
28.

The mechanism is a degenerate instance scale. When the context window is stationary — spindle
stopped, power flat — the per-window standard deviation collapses to `√eps ≈ 0.003`. The
de-normalisation `logvar + 2 log σ` then drives the predicted log-variance sharply negative, the
predicted variance is crushed, and a spindle start anywhere inside the horizon costs hundreds of
nats. RMSE is protected from this because the mean is de-normalised symmetrically; the variance
is not. This is the degenerate case flagged at implementation time in
`MaskedRevIN._degenerate_policy`, and the analogue of the `z_power` IQR pathology that made the
robust-normalisation candidates incommensurable in the first place.

Where the RMSE gain comes from, per channel: `z_current` 0.84 → 0.20 dominates; `z_torque` and
the X/Y channels are stable; `spindle_current` and `spindle_torque` get slightly **worse**
(0.37 → 0.43 and 0.60 → 0.67).

### What this changes about the locked result

Nothing. **M03 without RevIN remains the locked model and the reference result of the paper.**
The RevIN arm is a post-lock, pre-declared diagnostic that explains the gap to the official
baselines; it was not selected on the target, and its calibration failure makes it unusable as a
probabilistic world model without a fix. Candidate fixes — a floor on the window scale in z
units, a fade toward the identity when context variance is low, or computing the log-variance in
the global space outside the instance norm — all deviate from the pure RevIN the baselines use,
and would have to be described as such.

---

## Raw artifacts

Everything on this page traces to files in the repository or to the project page.

| Artifact | Contents |
|---|---|
| [`paper/results/revin_ablation/summary.json`](../paper/results/revin_ablation/summary.json) | Per-arm component means, per-seed collapse detail, paired statistics, validation verdict. |
| [`paper/results/revin_ablation/summary.md`](../paper/results/revin_ablation/summary.md) | The source-validation component table (French original of §Source validation above). |
| [`paper/results/revin_ablation/ds03_test.json`](../paper/results/revin_ablation/ds03_test.json) | The declaration, the per-seed target metrics, load audits, paired differences. |
| [`paper/results/revin_ablation/RAPPORT_REVIN_V2.md`](../paper/results/revin_ablation/RAPPORT_REVIN_V2.md) | Full analysis note, in French, including the per-channel calibration diagnosis. |
| `paper/results/revin_ablation/{M03,M03_revin}/seed_{0,1,2}/val_metrics.json` | Per-run validation metrics as emitted by `scripts/41`. |
| [Project page](https://ostertagmatthieu-dev.github.io/saac-jepa/) | Source of truth for the headline numbers in §1–§5. |

Regenerate the ablation with `python scripts/68_revin_ablation.py {train,summarize,ds03}` — see
[reproduce.md](reproduce.md).
