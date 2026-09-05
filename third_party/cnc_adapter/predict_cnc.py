"""Uniform prediction harness for the three official baselines.

Run as a SUBPROCESS with ``cwd`` set to the repo directory.  A subprocess (rather than
an in-process import) is mandatory: all three repos expose top-level ``utils`` /
``layers`` / ``models`` packages whose names collide, so at most one repo can be
imported per interpreter.

Why a custom harness at all, instead of each repo's own ``test()``:

  * SimMTM's ``Exp_SimMTM.test()`` saves NOTHING -- it only appends MSE/MAE to a text
    file -- so its predictions are unrecoverable from upstream code.
  * PatchTST saves ``pred.npy`` but has ``true.npy`` commented out.
  * None of the three can evaluate a trained model against a DIFFERENT csv, which is
    exactly what the DS03 ``target_all`` zero-shot pass requires.
  * Their metric helpers score all ``pred_len`` steps; our protocol scores the
    horizons {1,2,4,8,16} only.

Emits an ``.npz`` with ``pred``/``true``/``mask`` all shaped (N, pred_len, C), aligned
window-for-window with ``Dataset_CNC``.  ``mask`` is False wherever the ground truth
was absent in the export (the 7 DS03-missing sensors), so downstream metrics never
score against an imputed value.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader

sys.path.insert(0, str(Path.cwd()))  # repo modules (models/, layers/, utils/)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # cnc_adapter package

from cnc_adapter.cnc_dataset import Dataset_CNC  # noqa: E402


def build_model(kind, cfg):
    """Instantiate the repo's own Model class from a complete args Namespace."""
    if kind == "patchtst":
        from models.PatchTST import Model
    elif kind == "itransformer":
        from model.iTransformer import Model
    elif kind == "simmtm":
        cfg.task_name = "finetune"  # selects the forecasting head, not the SSL head
        from models.SimMTM import Model
    else:
        raise ValueError(f"unknown repo kind: {kind}")
    return Model(cfg)


def forward(kind, model, x, x_mark, y, y_mark, pred_len, label_len):
    if kind == "patchtst":
        # exp_main routes any model with 'TST' in its name to model(batch_x); the
        # decoder inputs and time marks are never consulted.
        return model(x)
    if kind == "simmtm":
        return model(x, x_mark)
    # iTransformer: encoder-only, but exp_* still assembles an Informer-style dec_inp.
    dec_inp = torch.zeros_like(y[:, -pred_len:, :])
    dec_inp = torch.cat([y[:, :label_len, :], dec_inp], dim=1).float()
    out = model(x, x_mark, dec_inp, y_mark)
    return out[0] if isinstance(out, (tuple, list)) else out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", required=True, choices=["patchtst", "itransformer", "simmtm"])
    ap.add_argument("--args-json", required=True, help="complete args dict written by script 66")
    ap.add_argument("--ckpt", default=None)
    ap.add_argument("--out", default=None, help="destination .npz")
    ap.add_argument("--device", default="cuda:0")
    ap.add_argument("--batch-size", type=int, default=256)
    ap.add_argument("--smoke", action="store_true",
                    help="CPU shape check: build an untrained model, run 2 batches, "
                         "skip checkpoint loading and npz output")
    a = ap.parse_args()
    if not a.smoke and (a.ckpt is None or a.out is None):
        ap.error("--ckpt and --out are required unless --smoke is given")

    cfg = argparse.Namespace(**json.loads(Path(a.args_json).read_text()))
    # flag='test' makes Dataset_CNC read whichever split CNC_TEST_SPLIT names, so the
    # same code path serves source_test and the target_all zero-shot pass.
    ds = Dataset_CNC(
        root_path=getattr(cfg, "root_path", None), flag="test",
        size=[cfg.seq_len, cfg.label_len, cfg.pred_len], features=cfg.features,
    )
    print(json.dumps(ds.summary(), indent=2), flush=True)

    device = torch.device("cpu" if a.smoke or "cpu" in a.device or not torch.cuda.is_available()
                          else a.device)
    model = build_model(a.kind, cfg)
    if not a.smoke:
        state = torch.load(a.ckpt, map_location="cpu", weights_only=False)
        # All three repos' EarlyStopping saves a bare state_dict. SimMTM's PRETRAIN
        # checkpoint is wrapped as {'epoch', 'model_state_dict'}, but that one is loaded
        # by the repo's own transfer_weights() during fine-tuning, never here. Unwrap the
        # known wrappers anyway, and load strictly so a silent key mismatch is impossible.
        for key in ("state_dict", "model_state_dict", "model"):
            if isinstance(state, dict) and isinstance(state.get(key), dict):
                state = state[key]
                break
        model.load_state_dict(state, strict=True)
    model.to(device).eval()

    if a.smoke:
        loader = DataLoader(ds, batch_size=a.batch_size, shuffle=False, num_workers=0)
        for bi, (x, y, xm, ym) in enumerate(loader):
            if bi >= 2:
                break
            with torch.no_grad():
                out = forward(a.kind, model, x.float(), xm.float(), y.float(), ym.float(),
                              cfg.pred_len, cfg.label_len)
            out = out[:, -cfg.pred_len:, :]
            print(f"SMOKE {a.kind} batch{bi}: x={tuple(x.shape)} y={tuple(y.shape)} "
                  f"x_mark={tuple(xm.shape)} out={tuple(out.shape)} finite={bool(torch.isfinite(out).all())}",
                  flush=True)
            assert out.shape == (x.shape[0], cfg.pred_len, cfg.c_out), out.shape
            assert torch.isfinite(out).all()
        print(f"SMOKE {a.kind}: OK", flush=True)
        return

    loader = DataLoader(ds, batch_size=a.batch_size, shuffle=False, drop_last=False, num_workers=0)
    preds = []
    with torch.no_grad():
        for x, y, xm, ym in loader:
            x = x.float().to(device); y = y.float().to(device)
            xm = xm.float().to(device); ym = ym.float().to(device)
            out = forward(a.kind, model, x, xm, y, ym, cfg.pred_len, cfg.label_len)
            preds.append(out[:, -cfg.pred_len:, :].float().cpu().numpy())
    pred = np.concatenate(preds, axis=0)

    true = np.stack([ds.target_true(i) for i in range(len(ds))]).astype(np.float32)
    mask = np.stack([ds.target_mask(i) for i in range(len(ds))])
    assert pred.shape == true.shape == mask.shape, (pred.shape, true.shape, mask.shape)

    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        a.out, pred=pred, true=true, mask=mask,
        columns=np.array(ds.cols), summary=np.array(json.dumps(ds.summary())),
    )
    print(f"wrote {a.out} pred={pred.shape}", flush=True)


if __name__ == "__main__":
    main()
