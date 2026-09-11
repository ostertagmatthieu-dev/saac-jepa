# Paper figures — Meta AI / FAIR style (I-JEPA / V-JEPA visual language)

Standalone TikZ sources (`\documentclass[tikz]{standalone}`), compilable with pdflatex
(Overleaf: drag the folder in as it is; locally, TinyTeX is enough).

| File | Contents | Suggested use |
|---|---|---|
| `fig1_saacjepa_architecture.tex` | The complete SAAC-JEPA architecture: sensor grids (masked channels), the RevIN block (variant, dashed green, post-lock ablation) ahead of both encoders, the context encoder, the action-conditioned causal predictor, the EMA target encoder (dashed), the losses, and the stop-gradient mark | Figure 1 of the paper |
| `fig2_schema_consistency.tex` | The two mechanisms of the winner M03: schema consistency (full view against amputated view, two RevIN blocks (variant, dashed green) in front of each of the two passes of the shared encoder, penalty on latents) plus action recovery | Method section |
| `fig3_selection_pipeline.tex` | The leakage-safe selection pipeline: 20 candidates → composite → top-5 → refused lock (instability) → seeds 6–7 → SHA-256 lock → single DS03 test, with the "DS03 under seal" line | Protocol section |
| `fig4_masking_actions.tex` | The 5 masking modes (winning channel mode boxed) plus the 3 action injections (token / FiLM / cross-attention) with the measured RMSE values | Ablations section / appendix |

Each figure exists twice: `figX_*.tex` (French labels) and `figX_*_en.tex` (English labels).
The PDFs and the 110 dpi PNG previews are provided next to the sources.

`meta_style.tex` is the shared style: the FAIR palette (context blue `#BDD7EE`, target salmon
`#F8CBAD`, predictor green `#C6E0B4`, action yellow `#FFE699`, emerald green `#1E8C50` = the
RevIN variant — a dashed block, post-lock ablation, absent from the locked model), Helvetica,
7 pt rounded blocks, thin arrows, EMA in dashed salmon, and `\sgmark{x,y}` for the stop-gradient
mark (`//`).

Local compilation:

```bash
~/.TinyTeX/bin/*/pdflatex -interaction=nonstopmode figX.tex
```

The JPG contact sheets that used to sit here (`planche_*.jpg`, `figures_sheet_en*.jpg`) were
removed: they predated the RevIN additions and were stale. For Overleaf, drag this folder in
directly, or run `make figures-zip` to rebuild the two archives
(`paper/figures_meta_tikz.zip` and `paper/figures_meta_tikz_en.zip`) from the sources.
