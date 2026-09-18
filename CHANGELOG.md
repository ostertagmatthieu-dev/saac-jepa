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
