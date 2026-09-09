# Handoff — 2026-09-09 — RevIN added to the arXiv paper

## What was done
- Paper (Draft-CNCWM, worktree `.claude/worktrees/world-models-arxiv-prep-b7d1a6`, branch `claude/world-models-arxiv-prep-b7d1a6`): commit `c7ebdd9` adds the post-lock RevIN ablation. M03 without RevIN stays the locked model (Ayoub's request). New Sec. 4.4, protocol paragraph "Post-lock declared ablation", new results subsection, Table 3 row + Target NLL column, Appendix H (Tables 7-9), Table 6 RevIN block. Build: 22 pages, no overfull boxes. METADATA abstract 1852 chars.
- saac-jepa (this worktree, branch `claude/heuristic-darwin-da1594`): RevIN code ported from cnc-jepa-reviewer-v2 (`revin.py`, `jepa.py`, `checkpoint.py`, configs, `configs/revin/M03_revin.yaml`, `scripts/68`, tests section (i)); results copied to `paper/results/revin_ablation/`; `scripts/61` gains phase `p10_revin`; `docs/paper.pdf`, `docs/index.html`, `docs/UPDATING.md`, README updated.
- Verified: `python tests/test_p3fix.py` green (uv venv with CPU torch 2.14, in the session scratchpad); `68 summarize` on the copied metrics reproduces `summary.json` exactly.

## Numbers (source of truth: cnc-jepa-reviewer-v2/outputs/revin_ablation)
DS01 clean 0.8190->0.7663 (3/3). DS03 RMSE control 0.555+/-0.015, RevIN 0.495+/-0.004, NLL 0.89->20.6, coverage 0.953->0.874. DS03 read twice (declared).

## Open items
- Calibration fix for RevIN (variance floor / blend-to-identity / logvar in global space) is future work; do not run before deciding on a third DS03 read.
- Collapse gate `zpred_std_min<0.05` is scale-dependent; make scale-free before any RevIN-enabled selection.
- Draft-CNCWM branch not pushed; saac-jepa branch not merged to main.
