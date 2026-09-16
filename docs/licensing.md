# Licensing

What this repository grants, what it does not, and which obligations follow the two external
datasets. The short version: **the MIT licence covers everything in this repository; it covers
neither dataset, and the target dataset (DS03) is restricted to non-commercial use.**

---

## 1. This repository

`LICENSE` (MIT, © 2026 Ayoub Louaye Bouaziz, Matthieu Ostertag, Anton Demasles) applies to every
file tracked here unless a file says otherwise: `src/`, `scripts/`, `tests/`, `examples/`,
`configs/`, `third_party/cnc_adapter/`, the Markdown docs, the project page under `docs/`, the
TikZ sources and rendered figures under `paper/figures/`, and the result records under
`paper/results/`.

Two clarifications, because MIT was written for software and this repository is not only software:

- **`docs/paper.pdf` is the preprint.** It is redistributed here for convenience; the version of
  record is [arXiv:2609.16071](https://arxiv.org/abs/2609.16071) and it carries whichever licence
  was selected at submission on arXiv, not MIT.
- **No trained weights are distributed.** `*.pt` / `*.pth` / `*.ckpt` are gitignored. A checkpoint
  trained on DS03 would inherit DS03's restriction (§2); none leaves this repository.

## 2. The two datasets — neither is redistributed here

`data/` is gitignored and the ETL reads files you download yourself. This repository therefore
**redistributes no dataset content**; what it ships are aggregate result records (RMSE, R²,
calibration, per-seed metrics), which are measurements about the data, not the data.

| | Source (DS01) | Target (DS03) |
|---|---|---|
| Dataset | THWS five-axis CNC milling | FH JOANNEUM CNC machining data repository |
| DOI | [10.5281/zenodo.14094887](https://doi.org/10.5281/zenodo.14094887) | [10.17632/gtvvwmz7r7.2](https://doi.org/10.17632/gtvvwmz7r7.2) |
| Host | Zenodo | Mendeley Data |
| Licence | CC BY 4.0 | **CC BY-NC — non-commercial use only** |
| Commercial use | permitted, with attribution | **not permitted** |
| Attribution | required | required |
| Indicate changes | required | required |

**What the DS03 restriction means in practice.** Every use of DS03 in this project — the ETL, the
sealed locked evaluation, the post-lock RevIN ablation, the numbers in the paper and on the project
page — is academic research and is within the licence. What is *outside* it, for anyone reusing
this work:

- training, fine-tuning or evaluating on DS03 as part of a commercial product or service;
- distributing a checkpoint trained or fine-tuned on DS03 for commercial use;
- selling, or bundling into a paid offering, any derivative of the DS03 files.

The MIT licence on the code does not change this. The code is not a derivative of the data, so it
stays MIT and can be used commercially — **on your own data**. Point it at DS03 commercially and
the DS03 licence, not MIT, decides.

**Changes we make to both datasets** (CC BY and CC BY-NC both require that adaptations be flagged;
all of them are performed at ETL time by `scripts/60_ingest_real_data.py` and are declared in
`configs/real.yaml`, full detail in [data.md](data.md)):

- renaming native columns to a single canonical 17-sensor / 4-action schema;
- unit corrections applied to DS03 — spindle and Z power W→kW (×0.001), commanded feeds mm/s→mm/min
  (×60), spindle deg/s→rpm (÷6);
- resampling DS01 onto a 1 Hz grid and DS03 from the Sinumerik IPO cycle (assumed 2 ms);
- segmenting DS01 into sessions at program changes and at gaps > 5 s, dropping sessions shorter
  than 64 rows, and filtering to program-running rows (`Program_status == 3.0`, `MA_JOG_STEP1`
  excluded);
- setting the seven channels DS03 does not expose to NaN, carried as *absent* indicators rather
  than imputed.

Cite both datasets when you use them; the entries are in the preprint's reference list and the
DOIs above resolve to the publishers' own citation blocks.

## 3. Official baseline repositories

Pinned clones under `third_party/` are gitignored and never redistributed here; the licences below
govern anyone who follows [third_party/README.md](../third_party/README.md) and clones them.

| Repository | Upstream licence (checked 2026-09-16) |
|---|---|
| [yuqinie98/PatchTST](https://github.com/yuqinie98/PatchTST) | Apache-2.0 |
| [thuml/iTransformer](https://github.com/thuml/iTransformer) | MIT |
| [thuml/SimMTM](https://github.com/thuml/SimMTM) | **none declared** — no `LICENSE` file, so default copyright applies |

SimMTM being unlicensed constrains reuse, not this comparison: we clone it, patch the working tree
locally, report the numbers, and redistribute none of its code. The shims we wrote against all
three (`third_party/cnc_adapter/`, the `data_loader_cnc.py` files and the `data_factory.py`
registrations described in `third_party/README.md`) are ours and are MIT; they contain no copied
upstream code.

## 4. Python dependencies

All runtime dependencies are permissively licensed and compatible with MIT redistribution of this
code: PyTorch, NumPy, pandas, scikit-learn and SciPy under BSD-3-Clause; PyYAML, PyWavelets and
einops under MIT; pyarrow under Apache-2.0; Matplotlib under its BSD-compatible PSF-style licence.
None is copyleft. No dependency is vendored.

## 5. Verification status

| Claim | Status |
|---|---|
| Repository content is MIT | verified — `LICENSE`, `pyproject.toml`, `CITATION.cff` agree |
| No dataset content is committed | verified — `data/` gitignored, `paper/results/` holds metrics only |
| No upstream baseline code is committed | verified — `third_party/` clones gitignored, `cnc_adapter/` is original |
| Baseline upstream licences | verified 2026-09-16 against the GitHub repository metadata |
| DS03 is non-commercial | **to confirm against the Mendeley record**: the exact CC BY-NC version (3.0 vs 4.0) is not yet recorded here. Fill it in above once checked. |
| DS01 is CC BY 4.0 | as published on the Zenodo record; re-confirm at the same time |

**Known inconsistency to fix outside this repository.** The preprint's data-availability sentence
reads "Both datasets are public under CC BY 4.0" and names both DOIs. If DS03 is non-commercial,
that sentence is wrong in arXiv v1 and needs correcting in the next version.
