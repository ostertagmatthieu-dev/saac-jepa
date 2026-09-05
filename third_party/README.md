# third_party/ — official baseline repositories

Pinned upstream clones used for the SOTA comparison. **These working trees are
modified.** Run `git -C <repo> diff` for the authoritative record; every hunk is
comment-tagged `ADDED` or `PATCHED`.

| Dir | Upstream | Commit |
|---|---|---|
| `PatchTST/` | github.com/yuqinie98/PatchTST | `204c21efe0b39603ad6e2ca640ef5896646ab1a9` |
| `iTransformer/` | github.com/thuml/iTransformer | `c2426e68ca13f74aaec08045c5c724d8ad328124` |
| `SimMTM/` | github.com/thuml/SimMTM | `169513bef74fb676e48d98a0e30f8823793f691c` |

`cnc_adapter/` is ours, not upstream:

* `cnc_dataset.py` — `Dataset_CNC`, a drop-in `Dataset_Custom` replacement that windows
  per session (never across), applies `outputs/normalizers.json` instead of refitting a
  scaler, and returns the repos' expected `(seq_x, seq_y, seq_x_mark, seq_y_mark)`.
  Shared by all three repos so the baselines provably see identical windows.
* `predict_cnc.py` — uniform prediction harness. Run as a subprocess with `cwd` set to a
  repo dir (the three repos have colliding top-level `utils`/`layers`/`models` packages,
  so only one can be imported per interpreter). Also provides `--smoke`.

Each repo has one added `data_provider/data_loader_cnc.py` shim and a few-line
registration in `data_provider/data_factory.py`.

Driver: `scripts/66_run_official_baselines.py`
Full rationale, deviations and verification: `outputs/official_baselines/PREP_NOTES.md`

Do not `git pull` these repos — the comparison is pinned to the SHAs above.
