# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
