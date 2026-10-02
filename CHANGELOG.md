# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `cncjepa.utils.torch_load_checkpoint`, the single door every checkpoint now enters through.
  It loads with `weights_only=True` and refuses a file that needs more, with a test
  (`tests/test_checkpoint_loading.py`) asserting that each payload the trainers write stays
  inside what the restricted unpickler accepts, so a numpy scalar smuggled into a metrics row
  fails in CI rather than at somebody's `--ckpt` argument.

- A build for the project page, `tools/site/build.py` (`make site`; `make site-check` writes nothing
  and fails when anything is stale). It inlines `docs/fonts/faces.css` and `docs/styles.css`,
  minified, into one `<style>` in `docs/index.html`, minifies `docs/main.js` into
  `docs/main.min.js`, loaded with a content-hash query string, and writes the Content-Security-Policy
  with the loader's hash. Generated markup stays between `<!-- build:… -->` markers; `main.js` and
  `styles.css` remain the hand-edited sources. The check also compares the three BibTeX copies,
  validates the JSON-LD, and requires the four "last modified" dates to agree.
- A `site` job in CI that runs `make site-check` and `node --check` on both scripts. The lint job
  calls `make format-check`, so the list of formatted files lives only in the Makefile.
- A "Pause animations" button under the hero strip that stops its scrolling loop and the CSS
  animations (WCAG 2.2.2); it stays hidden when the visitor asks for reduced motion.
- Three read-only WebMCP tools on the project page (`get_citation`, `get_links`,
  `get_key_results`) for in-browser agents; browsers without WebMCP ignore them.
- `docs/UPDATING.md` §6: the build, the security policy, the fonts pipeline, the GitHub Pages
  limits and how to enable the WebMCP origin trial.

- The locked model on Replicate, [ostertagmatthieu-dev/saac-jepa-world-model](https://replicate.com/ostertagmatthieu-dev/saac-jepa-world-model),
  packaged with Cog in `replicate/` and linked from a README badge, the `## Demo` section, the
  project-page footer and `docs/llms.txt`. It serves the same ONNX export as the Space on CPU. A
  JSON window goes in (any subset of the 17 sensors over 32 s, the four commands over the next
  16 s, optional hidden sensors) and a mean, standard deviation and interval per sensor and horizon
  come out. `fetch_weights.py` pins the Space revision and the SHA-256 of every artefact, and the
  container checks the locked hashes again at startup. Through the predictor, the 2,457 target
  windows give RMSE 0.545579 and MAE 0.352358, the sealed values, and the five PyTorch reference
  windows of the Space agree within 6·10⁻⁶. No dataset content goes into the image.

- An interactive demo on Hugging Face Spaces,
  [mostertag/saac-jepa-world-model](https://huggingface.co/spaces/mostertag/saac-jepa-world-model),
  linked from a README badge and a `## Demo` section, from a Demo button in the project-page hero
  and its footer, and from `docs/llms.txt`. The Space serves the sealed M03 checkpoint (seed 0,
  SHA-256 `ceb88ac2…`), exported to ONNX and run in the browser: pick a target window, hide
  shared sensors, scale the future commands, and compare the forecast with the truth and with
  persistence. Before the export was published it was checked against PyTorch on all 2,457
  target windows, including windows with hidden sensors, and its outputs stay within
  3.2·10⁻⁵ of PyTorch. The page re-runs the sealed target evaluation client-side and reproduces
  RMSE 0.545579 and MAE 0.352358. The Space redistributes a derived 1 Hz copy of DS03 under
  CC BY 4.0; `docs/licensing.md` and the README's data section record that exception.

- A `SECURITY.md` that describes what a security report means for research code: only `main` is
  supported (the project is pre-release at `0.1.0` with no tags), reports go through GitHub's
  private advisory form rather than a public issue, and the scope section names the hazards that
  survive in a repository with no network surface.

- `docs/licensing.md`, a single map of what each licence covers: MIT over the repository contents,
  CC BY 4.0 over both datasets, the changes that licence requires us to declare, the upstream
  licences of the three baseline repositories (PatchTST Apache-2.0, iTransformer MIT, SimMTM none
  declared) and of the runtime dependencies. It ends with a verification table recording what was
  checked, against which record, and when. It also names the trap that prompted the audit: on
  Mendeley Data the deposit and its *Data in Brief* article carry separate licences, the DS03
  article is non-commercial while the deposit is CC BY 4.0, and at least one published paper has
  propagated the article's restriction onto the dataset.
- The DataCite DOI arXiv minted on announcement, `10.48550/arXiv.2609.16071`, now sits beside the
  bare identifier everywhere the paper is cited: all three BibTeX copies (`README.md`,
  `docs/main.js`, `docs/index.html`) carry a `doi` field, `CITATION.cff` carries it as
  `preferred-citation.doi` and as a second `identifiers` entry, and the project page exposes it
  through the Google Scholar `citation_doi` tag and the JSON-LD `identifier` array. A DOI is what
  ORCID, DataCite and HAL resolve against, so it is the field that lets the preprint be claimed
  without retyping its metadata.
- Author ORCID iDs on all three authors, in both author blocks of `CITATION.cff` and as the
  schema.org `@id` of each author on the project page, so harvesters attach the work to the right
  person rather than to a name string.
- An `Attribution` workflow (`.github/workflows/attribution.yml`) that fails when a pull request,
  or a push to `main`, contains a commit authored by a bot or carrying a `Co-authored-by`,
  `Signed-off-by` or `Claude-Session` line that names Claude, Anthropic or a bot account. Such lines
  put extra accounts in the GitHub Contributors graph, and removing them afterwards means
  rewriting `main`.

### Changed

- All 19 `torch.load` call sites (3 in `src/cncjepa/checkpoint.py`, 16 under `scripts/`) now call
  `torch_load_checkpoint` instead. Five passed `weights_only=False` explicitly; the other
  fourteen passed nothing and so inherited a default that is `False` on the `torch>=2.3`
  floor and `True` from 2.6 on, which meant whether a checkpoint was executed depended on
  which torch happened to be installed. `CNCJEPA_TRUST_CHECKPOINT=1` restores the old
  unrestricted behaviour for a checkpoint you produced yourself.

- The project page serves its own fonts instead of loading Google Fonts: four OFL subsets of
  Barlow Condensed, Source Serif 4 and JetBrains Mono (about 77 KiB in all, against roughly
  388 KiB before), renamed SAAC Display, SAAC Serif and SAAC Mono, with metric-matched fallback
  faces so the swap moves no text. `tools/site/fonts.py` (`make fonts`) builds them reproducibly
  from pinned upstream files, and the check fails when the page uses a character a subset lacks.
- The page arrives as one HTML response with all its CSS inline; the two fonts of the
  above-the-fold text are preloaded and `main.min.js` loads after the content is parsed.
- Scroll reveals no longer hide content unless the script can reveal it: without JavaScript,
  with reduced motion, in a background tab or in a crawler, everything is visible.
- Structured data: the `FAQPage` is removed (Google requires FAQ markup to match questions and
  answers shown as such, and the key-finding cards are not an FAQ), the two `Dataset` nodes gain
  `identifier`, `isAccessibleForFree` and `includedInDataCatalog` (DS03 also `version`),
  `dateModified` follows the page, and the JSON-LD block moves to the end of `<body>`.
  `docs/UPDATING.md` §3 is re-baselined for the copies the FAQ answers held.

- The project page no longer calls the pretraining objective a loss. Its four terms all contain a
  stop-gradient, so the weighted sum L_SSL was not a function whose gradient training follows. The
  "Loss" row of §03 becomes "Training": a per-step function J_k with the EMA weights and a frozen
  copy of the current weights as explicit arguments, the AdamW step and the EMA update, read as a
  semi-gradient iteration. The variance-covariance term is no longer called VICReg (it has no
  invariance term) and is shown with half its weight, since the target half of the logged term
  carries no gradient. The SSL validation value becomes a selection score, the surrogate caveat
  and the figure 3 label follow, and `docs/llms.txt` and `docs/protocol.md` use the same wording.

- The project page is restructured for readers who know world models, in seven sections instead of
  nine, with each headline number stated once in prose. §01 opens with three key-finding cards,
  each a question, a one-line answer and an animated micro-bar chart; the abstract is folded
  underneath. §02 shows the two sensor schemas as chip grids, the seven channels the target lacks
  dropping out on scroll. §03 adds the formal object, the factorized model and the loss with its
  locked weights (native MathML, no script), three caveats taken from the paper (surrogate loss,
  product of per-horizon marginals, one-pass prediction), the model specification, and a table
  placing the model among PLDM, EB-JEPA and LeWorldModel. §05 replaces the long results paragraph
  with three responsive charts (zero-shot RMSE against persistence, R² by horizon, command
  sensitivity and calibration) and three numbered notes; the full table is folded. Fig. 2 is badged
  as a schematic. The page now says "commands" throughout, uses `f_θe`, labels the command-recovery
  head, explains that NLL 0.52 is the locked seed and 0.89 the control arm of the paired ablation,
  and counts three reads of the target, as the paper does (README and `docs/results.md` too).
  Animations: signal packets synchronised with the latent pulse in the hero strip, a data flow
  along Fig. 1's wires after it is built, and scroll reveals, all paused off screen and disabled
  under reduced motion. Old section anchors still resolve. The compute acknowledgement is removed
  from the page footer and the README, as the paper carries none.
- Search and AI indexing: the `<title>` and social titles lead with the paper's keywords; the
  JSON-LD becomes one `@graph` (article with abstract, keywords and datasets, source code, datasets,
  authors by ORCID, and an FAQ that mirrors the visible key findings); Scholar tags gain ORCID,
  dates and keywords; `llms.txt` summarizes the paper and links the Markdown docs; the sitemap lists
  the PDF, `llms.txt` and the docs. `docs/UPDATING.md` records every place a number now lives and
  adds a section on these surfaces.
- The paper is retitled *World Models for Cross-Machine CNC Transfer under Partial Sensor Overlap*
  (revised arXiv version 2609.16071v2 of the same V1 paper, announced 2026-09-24), after Jean Ponce's review: the method acronym
  SAAC-JEPA leaves the paper and stays only as the code name of this repository. The new title is
  applied to `CITATION.cff`, `pyproject.toml`, the package docstring, the README, the three BibTeX
  copies and the project page; the page abstract mirrors the rewritten abstract, result rows read
  "World model (locked, M03)", `docs/paper.pdf` is the build of 2609.16071v2 and `docs/og.png` shows the new
  title. arXiv derives the BibTeX key from the title, so the key changes from
  `bouaziz2026schemaadaptiveactionconditionedjepacrossmachine` to `bouaziz2026worldmodelscrossmachinecnc`, copied from the abs
  page of 2609.16071v2. The identifier, the DOI `10.48550/arXiv.2609.16071` and the abs URL do not change:
  arXiv mints one DOI per identifier, not per version.
- `README.md`, `docs/data.md` and the project-page footer now state explicitly that the MIT licence
  covers the repository contents and reaches neither dataset, that neither dataset is
  redistributed here, and that both CC BY 4.0 licences oblige us to declare the ETL changes we
  make. The licences themselves are unchanged: DS01 and DS03 are both CC BY 4.0, as
  [10.17632/gtvvwmz7r7.2](https://doi.org/10.17632/gtvvwmz7r7.2) states on its Mendeley record.
- `third_party/README.md` gains an upstream-licence column, which records that SimMTM ships no
  licence file at all.
- The three BibTeX copies (`README.md`, `docs/main.js`, `docs/index.html`) now follow the entry
  arXiv exports for 2609.16071: `@misc` instead of `@article`, arXiv's citation key
  `bouaziz2026schemaadaptiveactionconditionedjepacrossmachine` instead of `bouaziz2026saacjepa`,
  authors in arXiv's order and form, and no `journal = {arXiv preprint}` field, which is not a
  journal and which `@misc` does not define. The `doi` field is kept on top of arXiv's export.
  Anyone who copies the entry from arXiv or from this repository now gets the same key, so
  merged bibliographies do not carry the paper twice.
- `CITATION.cff` follows suit: `preferred-citation.type` is `generic` instead of `article` and the
  `journal: "arXiv preprint"` line is gone, so GitHub's "Cite this repository" button now emits
  `@misc` as well. CFF has no field for a citation key, so that button still generates its own.
- arXiv v1 was announced on 2026-09-13 as [arXiv:2609.16071](https://arxiv.org/abs/2609.16071). The identifier now
  replaces the pending-announcement placeholders everywhere it appears: the README badge
  and its BibTeX block, `CITATION.cff`, and the project page (`docs/main.js`,
  `docs/index.html` — Google Scholar `citation_arxiv_id`, the JSON-LD `identifier`, the
  static BibTeX copy, the arXiv button and the cite note). The three BibTeX copies now
  cite `url = {https://arxiv.org/abs/2609.16071}` instead of the project page.

### Fixed

- Accessibility of the project page: section numbers are hidden from screen readers so headings
  read as their titles, the key-finding questions and boxed notes are headings, wide figures and
  tables become focusable named regions only when they actually scroll, low-contrast text
  colours are darkened, and "Copy BibTeX" reports its outcome through a live region.

### Security

- `third_party/cnc_adapter/predict_cnc.py`, the prediction harness for the official PatchTST,
  iTransformer and SimMTM baselines, was the one `torch.load` left outside the
  `torch_load_checkpoint` sweep, and it passed `weights_only=False` outright. It now goes
  through the same door. Nothing it reads needs more: the only file it loads is the
  `checkpoint.pth` that each repository's `EarlyStopping` writes as a bare
  `model.state_dict()`, and all three, built from the arguments
  `scripts/66_run_official_baselines.py` passes, load identically under `weights_only=True` on
  torch 2.3.1 and 2.14.1. The harness puts `src/` on its own `sys.path`, since script 66 can
  run it under a `--python` that does not have the package installed.

- The project page carries a Content-Security-Policy (as a `<meta>`, since GitHub Pages sends no
  custom headers) with Trusted Types: the only script allowed is a hashed one-line loader, which
  inserts `main.min.js` through the single permitted policy; everything else is same-origin, with
  no plugins, `<base>` or form submission. `docs/404.html` gets its own policy with no script.

## [0.1.0] - 2026-09-11

First public release, accompanying arXiv v1 of *Schema-Adaptive Action-Conditioned JEPA for
Cross-Machine CNC Transfer under Partial Sensor Overlap*.

### Added

- Public release of the pipeline, configuration files, the twenty candidate specifications and
  the audit scripts used for the paper.
- Packaging as the distribution `saac-jepa` with the import package `cncjepa`, exposing
  `__version__`, installable with `pip install -e ".[dev]"`.
- Continuous integration on CPU, a `Makefile` with `setup` / `smoke` / `test` / `lint` /
  `reproduce-dry` / `figures-zip` targets, a pytest wrapper around the existing checks, and
  issue and pull-request templates.
- Documentation subpages under `docs/`: the audited protocol, the full results, the datasets and
  ETL, the reproduction recipes, and the script catalogue.
- Post-lock RevIN ablation (paper App. H): `src/cncjepa/models/revin.py` (`MaskedRevIN`,
  presence-aware), `scripts/68_revin_ablation.py`, `configs/revin/M03_revin.yaml`, and the
  results under `paper/results/revin_ablation/`.

### Changed

- `scripts/39_statistical_tests_n6.py` renamed to `scripts/39_statistical_tests_run_level.py`,
  and the `n=6` strings corrected throughout: the real target machine DS03 has **7** independent
  runs. The stale 6 came from the synthetic dataset in `examples/make_synthetic_ds01_ds03.py`.
- `scripts/09_transfer_power_analysis.py`: `--n` now defaults to 7 and the printed note reports
  the value actually used (the orchestrator already passed `--n 7`).
- Internal working documents moved from the repository root to `docs/internal/`.
- `CITATION.cff` rewritten as valid CFF 1.2.0.
- `scripts/55_triple_review.py`: `compileall` scoped to the project directories.

### Removed

- The dead `src/cncjepa/cli.py`.
- Tracked LaTeX `.aux` artifacts.
- The two tracked TikZ archives `paper/figures_meta_tikz.zip` and
  `paper/figures_meta_tikz_en.zip` — regenerate them with `make figures-zip`.
- The stale JPG contact sheets under `paper/figures/`, which predated the RevIN additions.

[Unreleased]: https://github.com/ostertagmatthieu-dev/saac-jepa/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/ostertagmatthieu-dev/saac-jepa/releases/tag/v0.1.0
