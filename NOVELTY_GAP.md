# Candidate novelty and research gap

Provisional method name: SAAC-JEPA, Schema-Adaptive Action-Conditioned JEPA.

## What is not novel enough

JEPA for time series or sensors alone is not a defensible novelty. Recent work already applies JEPA-style predictive representation learning to multivariate time series, sensing, activity recognition, and other physical signals. Masked reconstruction is also a strong alternative, including SimMTM, EMIT, and PatchFormer-style approaches.

## Gap this code tests

The defensible hypothesis is narrower:

Can an action-conditioned JEPA learn cross-machine industrial dynamics when the target machine exposes only a partially overlapping sensor schema, and can the learned latent state retain action sensitivity while adapting from few target runs?

The proposed contribution is the combination of:

1. Action-conditioned latent future prediction for CNC dynamics.
2. Sensor-ID/presence/schema tokens so a single encoder accepts subsets of a known global sensor vocabulary.
3. Schema dropout and schema-consistency learning during source pretraining.
4. Explicit anti-collapse ablations under a fixed audited protocol.
5. DS01 to DS03 transfer with 17 source channels and 10 overlapping target channels.
6. Few-shot and causal online adaptation on the target machine.
7. Decision-level evaluation through action shuffling and CEM planning, not RMSE only.
8. Per-channel/per-run reporting and run-level statistics so quasi-static channels and pseudo-replication do not hide the transfer result.

## Claims that must not be made before experiments

Do not claim state of the art from the random search alone.
Do not call the SimMTM/PatchFormer/EMIT/MMR/LoMaR-inspired code an official reproduction.
Do not claim the one-source/one-target scale limitation is solved. It is only audited more carefully.
Do not select the best random method after observing DS03 test metrics.

## Decision rule

Use scripts 40 to 44 to search only on DS01 validation. Lock the winning method and checkpoint hash. Only then run script 45 once on DS03. Compare against official or carefully reproduced baselines under the same split and preprocessing before any SOTA claim.
