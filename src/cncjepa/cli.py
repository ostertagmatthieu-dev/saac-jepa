from __future__ import annotations
import argparse,sys
from pathlib import Path

def bootstrap():
    root=Path(__file__).resolve().parents[2]
    if str(root/'src') not in sys.path: sys.path.insert(0,str(root/'src'))

def parser(desc):
    p=argparse.ArgumentParser(desc); p.add_argument('--config',default='configs/base.yaml'); p.add_argument('--device',default='auto'); p.add_argument('--out',default=None); return p
