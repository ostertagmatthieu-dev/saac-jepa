# Handoff — 2026-09-10 — RevIN drawn into every architecture diagram

## What was done (uncommitted in both worktrees)
- Decision with the user: RevIN appears as a DASHED GREEN block labelled "variant" (post-lock ablation, Sec. 4.4 / App. H), never as part of the locked M03. Emerald green distinct from the FAIR predictor green: web `--green #1E7A4A`, meta_style `mnorm #CDEFD9 / mnormL #1F9D55` + `nrm` style, fig1_saac_jepa `normC RGB(30,140,80)`, figure2 `cNorm #1E8C50`, slides `revgreen RGB(30,140,80)`.
- saac-jepa worktree `.claude/worktrees/revin-schemas-717dd0` (branch `claude/revin-schemas-717dd0`): `docs/index.html` FIG. 1 (two RevIN pills on the SENSORS→encoder and FUTURE WINDOW→target-encoder wires, `<desc>`, caption, 5th legend entry, new §03 paragraph), `docs/styles.css` (`--green`, `.f1__box--norm`, `.f1__lab--norm`, `.f1__sub--norm`, `.legend__swatch--norm`; the `--norm` label rules must stay AFTER `.f1__lab`/`.f1__sub` in the cascade), `README.md` Core architecture, `docs/UPDATING.md` (FIG. 1 RevIN block note; sweep re-baselined to `5 5 3 4 2 2 3 3`, drift was pre-existing on HEAD), `docs/paper.pdf` refreshed, `paper/figures/` fig1+fig2 FR/EN + meta_style + README + PNGs + both zips (contact-sheet JPGs NOT regenerated, no montage tool).
- Draft-CNCWM worktree `world-models-arxiv-prep-b7d1a6`: `figures/fig1_saac_jepa.tex` (vertical RevIN bar spanning both input rows), `fig_schema_action_mechanisms.tex`, `figure2_cnc_world_model{,_compact}.tex` (RevIN / RevIN⁻¹ tags on encoder/decoder arrows), `meta_style.tex`, `Main.tex` (one caption sentence on fig:overview, fig:worldmodel, fig:mechanisms), `presentation/slides_{ayoub,ponce}.tex` (RevIN box above the encoder, page 6). Main.pdf rebuilt: 22 pages, 0 Overfull; `arxiv/saac_jepa_arxiv.tar.gz` rebuilt.

## Open items
- Nothing committed or pushed (user did not ask). Paper changes are v2 material (v1 already on arXiv).
- deep-reasoner review done and applied (world-model note moved off the NOW divider, fig1 paper mask+RevIN bars adjacent, fig2 FR/EN note trimmed to "variant, not in the locked model", greens unified to #1E8C50 in TikZ; web keeps text-safe #1E7A4A).
- Contact sheets `paper/figures/planche_*.jpg`, `figures_sheet_en*.jpg` still show the pre-RevIN figures.
- Earlier open items unchanged: RevIN calibration fix is future work; collapse gate `zpred_std_min<0.05` scale-dependent.
