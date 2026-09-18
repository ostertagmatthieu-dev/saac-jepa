from __future__ import annotations
import os, pickle, random, json
from pathlib import Path
import numpy as np
import torch


def set_seed(seed: int, deterministic: bool = False):
    """Seed python/numpy/torch/cuda. `deterministic` also pins cuDNN and the
    cuBLAS workspace so matmul reductions are reproducible (slower)."""
    seed = int(seed)
    os.environ['PYTHONHASHSEED'] = str(seed)
    random.seed(seed)
    np.random.seed(seed % (2**32))
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    if deterministic:
        os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG', ':4096:8')
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False
        try: torch.use_deterministic_algorithms(True, warn_only=True)
        except Exception: pass
    return seed


def seed_worker(worker_id: int):
    """DataLoader worker_init_fn: derive numpy/random seeds from torch's per-worker
    base seed so masks/augmentations are reproducible run-to-run but vary per epoch."""
    s = torch.initial_seed() % (2**32)
    np.random.seed(s)
    random.seed(s)


def make_generator(seed: int):
    g = torch.Generator(); g.manual_seed(int(seed)); return g


def device_from_arg(name='auto'):
    if name == 'auto':
        return torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    return torch.device(name)


def ensure_dir(path):
    p = Path(path); p.mkdir(parents=True, exist_ok=True); return p


def atomic_torch_save(obj, path):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    torch.save(obj, tmp); os.replace(tmp, path)


TRUST_CHECKPOINT_ENV = 'CNCJEPA_TRUST_CHECKPOINT'


def torch_load_checkpoint(path, map_location='cpu'):
    """Load a checkpoint written by `atomic_torch_save`, without executing it.

    A `.pt` file is a pickle, so `torch.load(..., weights_only=False)` runs whatever the
    file says to run: opening an untrusted checkpoint is the same as running an untrusted
    script. Everything we save is tensors plus plain Python (`model`, `cfg`, `epoch`,
    `best`, `select_on`, `val`, `history`, `method`), all of which the restricted
    `weights_only=True` unpickler accepts, so a file that needs more than that is either
    not ours or has been tampered with and is refused rather than silently trusted.

    Passing `weights_only` explicitly also fixes the behaviour across the supported torch
    range: the default flipped to True in torch 2.6, so on the `torch>=2.3` floor these
    call sites would otherwise unpickle freely.

    Set `CNCJEPA_TRUST_CHECKPOINT=1` to fall back to the unrestricted loader for a file you
    produced yourself -- for instance an old checkpoint holding a numpy scalar.
    """
    try:
        return torch.load(path, map_location=map_location, weights_only=True)
    except pickle.UnpicklingError as e:
        if os.environ.get(TRUST_CHECKPOINT_ENV, '') not in ('1', 'true', 'True'):
            raise RuntimeError(
                f"{path} could not be loaded under weights_only=True, so it holds objects "
                f"beyond tensors and plain Python. Loading it unrestricted executes arbitrary "
                f"code from the file. If you produced this checkpoint yourself, re-run with "
                f"{TRUST_CHECKPOINT_ENV}=1; otherwise do not load it."
            ) from e
        return torch.load(path, map_location=map_location, weights_only=False)


def count_parameters(model):
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


def jsonl_append(path, row):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as f:
        f.write(json.dumps(row, default=str) + '\n')
