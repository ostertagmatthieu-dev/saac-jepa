# Contributing

This is research code that accompanies a paper. It is released so the protocol and the results
can be inspected and re-run, not as a general-purpose library, and the bar for changes differs
sharply by what you are changing.

**Welcome, straight to a pull request:** documentation fixes, packaging and CI improvements,
portability fixes, genuine bugs with a reproduction, and clearer error messages.

**Open an issue first:** anything scientific. A change to a model, a loss, a metric, the split
logic, the normalizers, the masking policy, the selection score, or any configuration under
`configs/` changes what the paper's numbers mean. Describe what you want to change and why
before writing the code, so we can agree on whether the result would still be comparable.

---

## Setup

```bash
make setup                 # uv venv on Python 3.12, CPU torch, then -e ".[dev]"
source .venv/bin/activate
make smoke                 # synthetic data end to end on CPU, a few minutes, prints SMOKE_CORE_OK
make test                  # the pytest suite
make lint                  # ruff
```

`make help` lists every target. If you prefer pip: `python -m venv .venv && source
.venv/bin/activate && pip install -r requirements.txt && pip install -e ".[dev]"`.

Pre-commit is available as a dev dependency:

```bash
pre-commit install
pre-commit run --all-files
```

CI runs on CPU only. A pull request that needs a GPU to be checked cannot be validated by CI,
so say so in the description and state what you ran locally.

## Rules inherited from the protocol

These are not style preferences. They are what keeps the published numbers meaningful.

1. **Never reference `target_all` in `scripts/41`, `scripts/43`, `scripts/44`, `scripts/64` or
   `scripts/_search_common.py`.** Those five files decide and lock the architecture, and they
   must be blind to the target machine. `scripts/55_triple_review.py` greps for the string and
   **fails the build** if it appears. If you genuinely need target data in a selection script,
   you need a different design, not an exception.
2. **Everything runs from the repository root.** Every numbered script begins with
   `from _common import *`, a `sys.path` shim resolved relative to the repository. Do not add
   `os.chdir`, and do not "fix" a path by making it relative to the script.
3. **New scripts are numbered, start with `from _common import *`, and carry a docstring.**
   Take the next free number in the right decade (see [docs/scripts.md](docs/scripts.md) for the
   grouping) and say in the docstring what the script produces and where.
4. **The compact one-line style in `scripts/` and `src/` is intentional.** Semicolon-separated
   statements, one-line `if`s and assigned lambdas are deliberate choices of this scientific
   code. The ruff configuration ignores `E401`, `E701`, `E702`, `E703` and `E731` for exactly
   that reason.
5. **Never run a formatter over `scripts/` or `src/`.** `make format-check` is deliberately
   scoped to a short list of newer files in the Makefile's `FORMAT_PATHS`. A repository-wide
   reformat would produce an unreviewable diff over code whose line-by-line form is part of the
   audit trail.
6. **Do not edit `third_party/` clones or change their pinned commits.** The official-baseline
   comparison is pinned to the SHAs in `third_party/README.md`. `third_party/cnc_adapter/` is
   ours and may be changed with an issue first.
7. **`docs/internal/` is historical.** Those documents record what was decided and when. Do not
   retro-edit their substance to match a later state of the world; add to the current docs
   instead. Repointing a renamed file path, or adding a dated clarifying note at the top, is fine.

## Numbers

If a change makes a headline number move, the number has to move everywhere at once.

- `docs/index.html` is the source of truth for headline numbers and is served by GitHub Pages.
- **[`docs/UPDATING.md` §2](docs/UPDATING.md) lists every place each headline number appears.**
  If you touch a number that the project page states, update that inventory in the same pull
  request — otherwise the next person will change five of the six occurrences.
- `README.md` and the pages under `docs/` must agree with the project page. Do not introduce a
  number that is not traceable to `docs/index.html`, `paper/results/`, or a script's output.
- Uncertainty travels with the number. `0.546` is one sealed pass; `0.822 ± 0.009` is seven
  seeds. Write the seed count when there is one.

## Pull requests

- One logical change per pull request.
- Run `make lint` and `make test` before opening it.
- **Add a `CHANGELOG.md` entry** under `## [Unreleased]`, in the Keep a Changelog category that
  fits (Added / Changed / Deprecated / Removed / Fixed / Security).
- Fill in the pull-request template. If the change is scientific, link the issue where the
  approach was agreed.
- Describe what you ran, on what hardware, and what you did not run.

## Reporting a bug

Use the bug-report issue template. Include the command line, the configuration file, the Python
and PyTorch versions, whether you were on CPU or GPU, and the full traceback. If the bug is in
the reproduction path, say which phase of `scripts/61_run_all_spark.py` it happened in and
attach the relevant `outputs/orchestrator/<phase>/<job>.log`.

## Questions about the results

Use the reproduction-question issue template. [docs/protocol.md](docs/protocol.md) covers the
audit and the selection procedure, [docs/results.md](docs/results.md) the numbers and their
definitions, and [docs/reproduce.md](docs/reproduce.md) the commands.

## Licence

By contributing you agree that your contribution is licensed under the MIT licence, as in
[LICENSE](LICENSE).
