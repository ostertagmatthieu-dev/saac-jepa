from __future__ import annotations
import os, random, json
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


def count_parameters(model):
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


def jsonl_append(path, row):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as f:
        f.write(json.dumps(row, default=str) + '\n')
