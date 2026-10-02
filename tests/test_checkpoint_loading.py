"""Checkpoints must load without executing what is inside them.

`torch.load` unpickles, so an unrestricted load runs arbitrary code from the file. These
tests pin the two halves of the guarantee in `cncjepa.utils.torch_load_checkpoint`:

 (a) every payload the trainers write stays inside what `weights_only=True` accepts, so
     tightening the loader does not cost us the ability to read our own checkpoints. This
     is the test that fails if someone later stores a numpy scalar in a metrics row.
 (b) a payload that needs the unrestricted unpickler is refused, and only the explicit
     `CNCJEPA_TRUST_CHECKPOINT` opt-in gets it loaded.
"""

import pickle

import numpy as np
import pytest
import torch

from cncjepa.utils import TRUST_CHECKPOINT_ENV, atomic_torch_save, torch_load_checkpoint

# The keys the trainers and _ssl_common actually write, with representative values.
TRAINER_PAYLOADS = {
    "jepa_best": {
        "model": {"context_encoder.w": torch.randn(2, 2), "predictor.b": torch.zeros(2)},
        "cfg": {"train": {"lr": 1e-3, "epochs": 2}, "schema": {"actions": ["a", "b"]}, "seed": 0},
        "epoch": 3,
        "best": 0.42,
        "select_on": "val_rmse",
        "val": {"epoch": 3, "ema": 0.996, "sec": 12.5, "score": 0.42, "val_rmse": 0.42,
                "val_r2": None, "collapse": 0, "zpred_eff_rank": 7.5},
    },
    "jepa_last": {
        "model": {"context_encoder.w": torch.randn(2, 2)},
        "cfg": {"train": {"lr": 1e-3}},
        "history": [{"epoch": 0, "score": 1.0, "val_rmse": 1.0, "collapse": 0},
                    {"epoch": 1, "score": 0.5, "val_rmse": 0.5, "collapse": 0}],
    },
    "forecaster_best": {
        "model": {"head.weight": torch.ones(3)},
        "cfg": {"train": {"lr": 1e-3}},
        "best": 0.7,
    },
    "ssl_best": {
        "model": {"context_encoder.w": torch.randn(2, 2)},
        "cfg": {"train": {"lr": 1e-3}},
        "method": "simmtm",
        "best": 0.3,
    },
}


@pytest.mark.parametrize("name", sorted(TRAINER_PAYLOADS))
def test_trainer_payloads_load_without_unpickling(tmp_path, name):
    """Everything we save must survive the restricted loader."""
    path = tmp_path / f"{name}.pt"
    atomic_torch_save(TRAINER_PAYLOADS[name], path)
    obj = torch_load_checkpoint(path)
    assert set(obj) == set(TRAINER_PAYLOADS[name])
    assert torch.equal(next(iter(obj["model"].values())),
                       next(iter(TRAINER_PAYLOADS[name]["model"].values())))


def test_numpy_scalar_in_a_metrics_row_is_caught_here_not_by_a_user(tmp_path):
    """A numpy scalar is the realistic way a payload stops being plain Python.

    The metric helpers cast through `float()`/`int()` precisely so this does not happen;
    if one ever slips, it must fail in CI rather than at somebody's `--ckpt` argument.
    """
    path = tmp_path / "numpy.pt"
    atomic_torch_save({"model": {"w": torch.zeros(1)}, "cfg": {}, "best": np.float64(0.5)}, path)
    with pytest.raises(RuntimeError, match="weights_only=True"):
        torch_load_checkpoint(path)


def test_unrestricted_payload_is_refused_by_default(tmp_path):
    path = tmp_path / "rich.pt"
    atomic_torch_save({"model": {"w": torch.zeros(1)}, "obj": np.float64(1.0)}, path)
    with pytest.raises(RuntimeError) as excinfo:
        torch_load_checkpoint(path)
    assert TRUST_CHECKPOINT_ENV in str(excinfo.value)
    assert isinstance(excinfo.value.__cause__, pickle.UnpicklingError)


def test_trust_env_var_is_the_only_way_through(tmp_path, monkeypatch):
    path = tmp_path / "rich.pt"
    atomic_torch_save({"model": {"w": torch.zeros(1)}, "obj": np.float64(1.0)}, path)
    monkeypatch.setenv(TRUST_CHECKPOINT_ENV, "1")
    assert float(torch_load_checkpoint(path)["obj"]) == 1.0
    monkeypatch.setenv(TRUST_CHECKPOINT_ENV, "0")
    with pytest.raises(RuntimeError):
        torch_load_checkpoint(path)


def test_a_missing_file_still_raises_its_own_error(tmp_path):
    """The refusal path must not swallow ordinary IO failures."""
    with pytest.raises(FileNotFoundError):
        torch_load_checkpoint(tmp_path / "does_not_exist.pt")
