PY ?= python
UV ?= uv
RUFF ?= uvx ruff@0.14.0
SYNTH := data/synthetic_ds01_ds03.csv
FORMAT_PATHS := src/cncjepa/__init__.py tests/conftest.py tests/test_smoke.py tests/test_version.py

.PHONY: help setup data-synth smoke test test-fast lint format-check review reproduce-dry figures-zip clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | sed 's/:.*## /\t/'

setup: ## Create a CPU venv and install the package with dev extras
	$(UV) venv --python 3.12 .venv
	$(UV) pip install --python .venv/bin/python --index-url https://download.pytorch.org/whl/cpu "torch>=2.3"
	$(UV) pip install --python .venv/bin/python -e ".[dev]"
	@echo "Activate with: source .venv/bin/activate"

data-synth: $(SYNTH) ## Generate the synthetic DS01/DS03 dataset

$(SYNTH):
	$(PY) examples/make_synthetic_ds01_ds03.py

smoke: $(SYNTH) ## Run the core CPU smoke test
	$(PY) scripts/54_smoke_test_core.py

test: ## Run the full test suite
	$(PY) -m pytest

test-fast: ## Run the test suite, skipping slow end-to-end tests
	$(PY) -m pytest -m "not slow"

lint: ## Lint the repository with ruff
	$(RUFF) check .

format-check: ## Check formatting of new files with ruff
	$(RUFF) format --check --diff $(FORMAT_PATHS)

review: $(SYNTH) ## Run the triple review checks
	$(PY) scripts/55_triple_review.py

reproduce-dry: ## Dry-run the full reproduction pipeline
	$(PY) scripts/61_run_all_spark.py --config configs/real.yaml --dry-run

figures-zip: ## Package the paper's TikZ figures into zip archives
	cd paper/figures && zip -q ../figures_meta_tikz_en.zip meta_style.tex fig?_*_en.tex && zip -q ../figures_meta_tikz.zip meta_style.tex $$(ls fig?_*.tex | grep -v _en)

clean: ## Remove generated artifacts and caches
	rm -rf outputs/smoke_pre outputs/smoke_ft outputs/smoke_eval.json $(SYNTH) .pytest_cache .ruff_cache paper/figures_meta_tikz*.zip dist build
	find . -type d -name __pycache__ -exec rm -rf {} +
