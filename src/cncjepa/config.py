from __future__ import annotations
import copy, json, yaml
from pathlib import Path


def load_config(path):
    path = Path(path)
    with path.open('r', encoding='utf-8') as f:
        cfg = yaml.safe_load(f)
    cfg['_config_path'] = str(path)
    return cfg


def save_config(cfg, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    clean = {k:v for k,v in cfg.items() if not str(k).startswith('_')}
    with path.open('w', encoding='utf-8') as f:
        yaml.safe_dump(clean, f, sort_keys=False)


def deep_update(base, patch):
    out = copy.deepcopy(base)
    for k,v in patch.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_update(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def dump_json(obj, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as f:
        json.dump(obj, f, indent=2, default=str)
