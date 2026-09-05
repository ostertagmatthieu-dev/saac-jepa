"""Session-aware CNC dataset for the official PatchTST / iTransformer / SimMTM repos.

Why this file exists
--------------------
The upstream ``Dataset_Custom`` classes in all three repositories treat a CSV as ONE
continuous series and slice windows over the whole row range.  Our export is a
concatenation of independent machining sessions with fabricated gaps between them, so
upstream windowing would silently manufacture windows that straddle a session boundary
(context from the end of session A, target from the start of session B).  They also
re-fit a ``StandardScaler`` on whatever the first 70% of the file happens to be, which
is not our audited source_train z-scoring.

``Dataset_CNC`` fixes both while keeping the exact ``(seq_x, seq_y, seq_x_mark,
seq_y_mark)`` contract the repos' exp loops expect, so no upstream training code needs
to change.

Contract
--------
* windows are generated PER (machine_id, session_id, run_id) group only -- never across
* values are z-scored with OUR normalizers (fit on source_train), never re-fit here
* ``seq_x_mark`` / ``seq_y_mark`` are zero-WIDTH ``(L, 0)`` float32 arrays.  PatchTST and
  SimMTM ignore marks entirely; iTransformer's ``DataEmbedding_inverted`` concatenates
  marks as extra variate tokens, and a zero-width mark makes that path numerically
  identical to the ``x_mark is None`` path.  Calendar features are meaningless here
  (1 Hz inside minutes-long episodes), so injecting them would only add noise tokens.

Configuration is by environment variable because the repos' argparse surfaces have no
place to put it and we do not want to edit their run scripts:

  CNC_EXPORT_DIR   dir holding source_{train,val,test}.csv + target_all.csv
  CNC_NORMALIZERS  path to outputs/normalizers.json
  CNC_CHANNELS     "21" (17 sensors + 4 actions, default) or "17" (sensors only)
  CNC_TEST_SPLIT   which file backs flag='test': "source_test" (default) or "target_all"
  CNC_IMPUTE       "zspace_zero" (default) or "raw_zero" -- see below

Imputation of absent channels (target_all only)
----------------------------------------------
target_all (machine DS03) is missing 7 of the 17 sensors entirely.  Two conventions:

  zspace_zero  z-score first, then fill NaN with 0.  A missing channel reads as the
               source_train MEAN.  This is the standard, charitable imputation for a
               model with no missingness mechanism, and is the DEFAULT.
  raw_zero     fill NaN with 0 in RAW units, then z-score.  This reproduces
               ``cncjepa.data.WindowDataset`` exactly (it calls ``nan_to_num`` before
               ``sn.transform``), which drives absent channels to roughly -11 sigma.
               Our own model tolerates that because it additionally receives
               ``present``/``schema`` masks; the official models receive no such signal,
               so this mode exists only as a sensitivity check.

Either way the ground-truth mask ``mask_y`` is computed on the RAW array before any
filling, so metrics are only ever scored on channels that actually exist.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
from torch.utils.data import Dataset

# Column order is load-bearing: it must match outputs/normalizers.json, which stores
# 17 sensor stats followed by 4 action stats, in exactly this order.
SENSORS = [
    "spindle_current", "spindle_torque", "spindle_power",
    "x_current", "x_torque", "y_current", "y_torque",
    "z_current", "z_torque", "z_power",
    "spindle_motor_temp", "x_motor_temp", "y_motor_temp", "z_motor_temp",
    "spindle_dc_voltage", "spindle_mod_depth", "ambient_temp",
]
ACTIONS = ["a_spindle_speed", "a_feed_x", "a_feed_y", "a_feed_z"]

# The 10 sensors that also exist on the DS03 target machine.
TRANSFER_SENSORS = [
    "spindle_current", "spindle_torque", "spindle_power",
    "x_current", "x_torque", "y_current", "y_torque",
    "z_current", "z_torque", "z_power",
]

GROUP_KEYS = ["machine_id", "session_id", "run_id"]
TIMESTAMP = "timestamp"
EPS = 1e-6  # matches cncjepa.normalization.Normalizer.transform

FLAG_TO_SPLIT = {"train": "source_train", "val": "source_val"}

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_EXPORT = _REPO_ROOT / "outputs" / "official_baseline_export"
_DEFAULT_NORMALIZERS = _REPO_ROOT / "outputs" / "normalizers.json"


def resolve_config():
    """Env-var configuration, resolved once so callers can log exactly what was used."""
    return {
        "export_dir": Path(os.environ.get("CNC_EXPORT_DIR", _DEFAULT_EXPORT)),
        "normalizers": Path(os.environ.get("CNC_NORMALIZERS", _DEFAULT_NORMALIZERS)),
        "channels": int(os.environ.get("CNC_CHANNELS", "21")),
        "test_split": os.environ.get("CNC_TEST_SPLIT", "source_test"),
        "impute": os.environ.get("CNC_IMPUTE", "zspace_zero"),
    }


def channel_names(n_channels):
    if n_channels == 21:
        return SENSORS + ACTIONS
    if n_channels == 17:
        return list(SENSORS)
    raise ValueError(f"CNC_CHANNELS must be 17 or 21, got {n_channels}")


def load_normalizer(path, n_channels):
    """Return (center, scale) vectors aligned with ``channel_names(n_channels)``."""
    nz = json.loads(Path(path).read_text())
    center = list(nz["sensor"]["center"])
    scale = list(nz["sensor"]["scale"])
    if n_channels == 21:
        center += list(nz["action"]["center"])
        scale += list(nz["action"]["scale"])
    center = np.asarray(center, dtype=np.float64)
    scale = np.asarray(scale, dtype=np.float64)
    assert center.shape == (n_channels,), (center.shape, n_channels)
    return center, scale


class Dataset_CNC(Dataset):
    """Drop-in replacement for ``Dataset_Custom`` with session-bounded windows.

    The ``**kwargs`` tail absorbs repo-specific extras (``seasonal_patterns`` in SimMTM,
    ``percent`` in some forks) so one class satisfies all three ``data_provider``
    call sites unchanged.

    ``scale`` from the caller is deliberately IGNORED: normalization is always our
    source_train z-scoring.  Honouring ``scale=True`` would mean re-fitting a scaler
    per split, which is precisely the leak this adapter exists to prevent.
    """

    def __init__(self, root_path=None, flag="train", size=None, features="M",
                 data_path=None, target=None, scale=True, timeenc=0, freq="s",
                 seasonal_patterns=None, **kwargs):
        assert flag in ("train", "val", "test"), flag
        if size is None:
            raise ValueError("Dataset_CNC requires size=[seq_len, label_len, pred_len]")
        self.seq_len, self.label_len, self.pred_len = (int(v) for v in size)
        self.flag = flag
        self.features = features

        cfg = resolve_config()
        # An explicit root_path from the repo's --root_path wins over the env default,
        # so a caller can point one run at a different export without re-exporting env.
        if root_path:
            rp = Path(root_path)
            if rp.is_dir():
                cfg["export_dir"] = rp
        self.cfg = cfg

        self.n_channels = cfg["channels"]
        self.cols = channel_names(self.n_channels)
        self.impute = cfg["impute"]
        if self.impute not in ("zspace_zero", "raw_zero"):
            raise ValueError(f"CNC_IMPUTE must be zspace_zero|raw_zero, got {self.impute}")

        # iTransformer's exp_long_term_forecasting.test() branches on `test_data.scale`
        # to decide whether to inverse-transform predictions before scoring. False is the
        # honest answer: no repo-managed scaler was fitted, and our metrics are DEFINED in
        # z-units, so predictions must stay in z-space. (`scale_vec` below is the
        # normalizer's per-channel sigma -- a different thing despite the similar name.)
        self.scale = False
        self.split = FLAG_TO_SPLIT.get(flag, cfg["test_split"])
        self.center, self.scale_vec = load_normalizer(cfg["normalizers"], self.n_channels)
        self.__read_data__()

    # ------------------------------------------------------------------ loading
    def __read_data__(self):
        csv_path = self.cfg["export_dir"] / f"{self.split}.csv"
        if not csv_path.exists():
            raise FileNotFoundError(csv_path)
        df = pd.read_csv(csv_path)

        missing = [c for c in self.cols + GROUP_KEYS + [TIMESTAMP] if c not in df.columns]
        if missing:
            raise ValueError(f"{csv_path} is missing columns: {missing}")

        span = self.seq_len + self.pred_len
        self.arrays, self.masks, self.meta = [], [], []
        self.index = []
        # sort=False + dropna=False mirrors cncjepa.data.WindowDataset's grouping so the
        # window inventory is identical to our pipeline's.
        for key, g in df.groupby(GROUP_KEYS, sort=False, dropna=False):
            g = g.sort_values(TIMESTAMP)
            if len(g) < span:
                continue  # too short for even one window -- same rule as our pipeline
            raw = g[self.cols].to_numpy(dtype=np.float64)
            mask = np.isfinite(raw)  # computed BEFORE any imputation
            if self.impute == "raw_zero":
                z = (np.nan_to_num(raw, nan=0.0) - self.center) / (self.scale_vec + EPS)
            else:
                z = (raw - self.center) / (self.scale_vec + EPS)
                z = np.nan_to_num(z, nan=0.0)
            gi = len(self.arrays)
            self.arrays.append(z.astype(np.float32))
            self.masks.append(mask)
            self.meta.append(tuple(str(k) for k in key))
            for s in range(0, len(g) - span + 1):
                self.index.append((gi, s))

        if not self.index:
            raise ValueError(
                f"{csv_path}: no session yields a {span}-step window "
                f"(seq_len={self.seq_len} + pred_len={self.pred_len})"
            )
        # Zero-width marks, shared by every item -- see module docstring.
        self._mark_x = np.zeros((self.seq_len, 0), dtype=np.float32)
        self._mark_y = np.zeros((self.label_len + self.pred_len, 0), dtype=np.float32)

    # ------------------------------------------------------------------ access
    def __len__(self):
        return len(self.index)

    def __getitem__(self, i):
        gi, s = self.index[i]
        arr = self.arrays[gi]
        s_end = s + self.seq_len
        r_begin = s_end - self.label_len
        r_end = r_begin + self.label_len + self.pred_len
        return arr[s:s_end], arr[r_begin:r_end], self._mark_x, self._mark_y

    # ------------------------------------ helpers for our own metric conversion
    def target_mask(self, i):
        """(pred_len, C) bool: which ground-truth entries actually exist."""
        gi, s = self.index[i]
        s_end = s + self.seq_len
        return self.masks[gi][s_end:s_end + self.pred_len]

    def target_true(self, i):
        """(pred_len, C) float32 z-space ground truth (imputed entries are masked)."""
        gi, s = self.index[i]
        s_end = s + self.seq_len
        return self.arrays[gi][s_end:s_end + self.pred_len]

    def window_meta(self, i):
        gi, s = self.index[i]
        m = self.meta[gi]
        return {"machine": m[0], "session": m[1], "run": m[2], "start": int(s)}

    def inverse_transform(self, data):
        return np.asarray(data) * (self.scale_vec + EPS) + self.center

    def summary(self):
        return {
            "split": self.split,
            "csv": str(self.cfg["export_dir"] / f"{self.split}.csv"),
            "n_windows": len(self.index),
            "n_sessions_used": len(self.arrays),
            "channels": self.n_channels,
            "column_order": self.cols,
            "impute": self.impute,
            "seq_len": self.seq_len,
            "label_len": self.label_len,
            "pred_len": self.pred_len,
        }
