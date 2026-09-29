"""Replicate predictor for the sealed SAAC-JEPA M03 world model.

Runs the ONNX export of the locked checkpoint on CPU. The window encoding mirrors
cncjepa.data.WindowDataset (and the demo Space), so the same window gives the same forecast here,
in the browser demo and in PyTorch:

  * sensors and commands are z-scored with the source-fitted normalizers;
  * a missing value (null, or a sensor left out of the input) is zero with present = 0, and the
    sensor stays in the schema, exactly as the sealed target evaluation treats DS03;
  * a sensor listed in "hidden" is removed from the schema as well, as the demo's hide toggle does;
  * the command fed for horizon h is the mean of the future commands over the next h seconds.

Input (a JSON string), one value per second at 1 Hz:

    {
      "sensors":         {"spindle_current": [32 numbers or null], ...},
      "past_commands":   {"a_spindle_speed": [32 numbers or null], ...},   # optional
      "future_commands": {"a_spindle_speed": [16 numbers], "a_feed_x": [...], "a_feed_y": [...], "a_feed_z": [...]},
      "hidden":          ["z_power"]                                       # optional
    }
"""

import hashlib
import json
from pathlib import Path
from statistics import NormalDist

import numpy as np
import onnxruntime as ort
import yaml
from cog import BaseRunner, Input

WEIGHTS = Path(__file__).resolve().parent / "weights"
ONNX_SHA256 = "21bb2f22b03fa77f3292183f65adeb488af919adfb749832a5675af967eb0a66"


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _series(obj, key, names, length, required):
    """Stack a {name: [values]} mapping into a (length, len(names)) float32 array, NaN where missing."""
    got = obj.get(key) or {}
    if not isinstance(got, dict):
        raise ValueError(f'"{key}" must be an object mapping channel names to lists')
    unknown = sorted(set(got) - set(names))
    if unknown:
        raise ValueError(f'unknown channel(s) in "{key}": {unknown}; expected a subset of {names}')
    missing = [n for n in names if n not in got]
    if required and missing:
        raise ValueError(f'"{key}" is missing {missing}')
    out = np.full((length, len(names)), np.nan, np.float32)
    for j, name in enumerate(names):
        if name not in got:
            continue
        vals = got[name]
        if not isinstance(vals, list) or len(vals) != length:
            raise ValueError(f'"{key}.{name}" must be a list of {length} values (1 Hz)')
        for t, v in enumerate(vals):
            if v is None:
                if required:
                    raise ValueError(f'"{key}.{name}" has a null at index {t}; future commands must be complete')
                continue
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not np.isfinite(v):
                raise ValueError(f'"{key}.{name}"[{t}] is not a finite number: {v!r}')
            out[t, j] = v
    return out


class Predictor(BaseRunner):
    def setup(self):
        lock = json.loads((WEIGHTS / "LOCKED_BEST.json").read_text())
        expected = {
            "config.yaml": lock["config_sha256"],
            "normalizers.json": lock["normalizers_sha256"],
            "m03.onnx": ONNX_SHA256,
        }
        for name, want in expected.items():
            if _sha256(WEIGHTS / name) != want:
                raise RuntimeError(f"{name} does not match its locked SHA-256; run fetch_weights.py again")
        self.lock = lock
        cfg = yaml.safe_load((WEIGHTS / "config.yaml").read_text())
        self.sensors = cfg["schema"]["sensors"]
        self.transfer = cfg["schema"]["transfer_sensors"]
        self.commands = cfg["schema"]["actions"]
        self.T = int(cfg["protocol"]["context_len"])
        self.horizons = [int(h) for h in cfg["protocol"]["horizons"]]
        norm = json.loads((WEIGHTS / "normalizers.json").read_text())
        self.s_center = np.asarray(norm["sensor"]["center"], np.float64)
        self.s_scale = np.asarray(norm["sensor"]["scale"], np.float64) + norm["sensor"]["eps"]
        self.c_center = np.asarray(norm["action"]["center"], np.float64)
        self.c_scale = np.asarray(norm["action"]["scale"], np.float64) + norm["action"]["eps"]
        self.session = ort.InferenceSession(str(WEIGHTS / "m03.onnx"), providers=["CPUExecutionProvider"])

    def encode(self, obj):
        """Turn the parsed input into the five ONNX feeds, each with a leading batch axis of 1."""
        if not isinstance(obj, dict):
            raise ValueError("the window must be a JSON object")
        extra = sorted(set(obj) - {"sensors", "past_commands", "future_commands", "hidden"})
        if extra:
            raise ValueError(f"unknown top-level key(s): {extra}")
        hidden = obj.get("hidden") or []
        if not isinstance(hidden, list) or any(h not in self.sensors for h in hidden):
            raise ValueError(f'"hidden" must be a list of sensor names from {self.sensors}')

        x = _series(obj, "sensors", self.sensors, self.T, required=False)
        present = np.isfinite(x)
        x = np.where(present, (x - self.s_center) / self.s_scale, 0.0).astype(np.float32)
        schema = np.ones(len(self.sensors), np.float32)
        for name in hidden:
            j = self.sensors.index(name)
            x[:, j] = 0.0
            present[:, j] = False
            schema[j] = 0.0

        past = _series(obj, "past_commands", self.commands, self.T, required=False)
        past = np.where(np.isfinite(past), (past - self.c_center) / self.c_scale, 0.0).astype(np.float32)
        future = _series(obj, "future_commands", self.commands, max(self.horizons), required=True)
        future = np.stack([future[:h].mean(axis=0) for h in self.horizons])
        future = ((future - self.c_center) / self.c_scale).astype(np.float32)

        return {
            "x": x[None],
            "past_actions": past[None],
            "future_actions": future[None],
            "present": present.astype(np.float32)[None],
            "schema": schema[None],
        }

    def run(
        self,
        window: str = Input(
            description="JSON object with 32 s of sensor context and the commands for the next "
            "16 s, at 1 Hz. See the README for the format."
        ),
        coverage: float = Input(
            description="Coverage of the central prediction interval (Gaussian head).", default=0.9, ge=0.5, le=0.99
        ),
    ) -> dict:
        try:
            obj = json.loads(window)
        except json.JSONDecodeError as e:
            raise ValueError(f'"window" is not valid JSON: {e}') from e
        mu, logvar = self.session.run(None, self.encode(obj))
        mean = mu[0].astype(np.float64) * self.s_scale + self.s_center
        std = np.exp(0.5 * logvar[0].astype(np.float64)) * self.s_scale
        z = NormalDist().inv_cdf(0.5 + coverage / 2)
        forecast = {
            name: {
                "mean": mean[:, j].tolist(),
                "std": std[:, j].tolist(),
                "lower": (mean[:, j] - z * std[:, j]).tolist(),
                "upper": (mean[:, j] + z * std[:, j]).tolist(),
            }
            for j, name in enumerate(self.sensors)
        }
        return {
            "horizons_s": self.horizons,
            "coverage": coverage,
            "forecast": forecast,
            "transfer_sensors": self.transfer,
            "model": {
                "method": self.lock["method"],
                "checkpoint_sha256": self.lock["checkpoint_sha256"],
                "onnx_sha256": ONNX_SHA256,
            },
        }
