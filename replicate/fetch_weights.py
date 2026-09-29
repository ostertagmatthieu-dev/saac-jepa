"""Download the sealed M03 artefacts into weights/ and check their SHA-256 hashes.

The files come from the demo Space at a pinned revision, so every build of the Replicate image
bakes in the same bytes. The checkpoint, config and normalizer hashes are the ones recorded in
LOCKED_BEST.json by scripts/44_lock_best_method.py; m03.onnx is the export that tools/export_onnx.py
in the Space checked against PyTorch on all 2,457 target windows.

    python fetch_weights.py          # skips files that are already present and valid
"""

import hashlib
import sys
import urllib.request
from pathlib import Path

REPO = "https://huggingface.co/spaces/mostertag/saac-jepa-world-model/resolve"
REVISION = "739319edb6175d1dd83c40feed1c57abeb73a37f"
FILES = {
    "LOCKED_BEST.json": "343372559b205a8bc897a03a698c44989f0a1cf63bbea0d160d107458f1ef93a",
    "config.yaml": "d34b7e855ace5c89161965c1df809a8bec6331eed05705efde8132e2bf066e31",
    "normalizers.json": "ef69192f67768075b1c9f4ec216a2fa58da0fc65cc71ec8e8d4d4930455d8739",
    "m03.onnx": "21bb2f22b03fa77f3292183f65adeb488af919adfb749832a5675af967eb0a66",
}
OUT = Path(__file__).resolve().parent / "weights"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    OUT.mkdir(exist_ok=True)
    for name, want in FILES.items():
        dest = OUT / name
        if dest.exists() and sha256(dest) == want:
            print(f"ok      {name}")
            continue
        tmp = dest.with_suffix(dest.suffix + ".part")
        urllib.request.urlretrieve(f"{REPO}/{REVISION}/model/{name}", tmp)
        got = sha256(tmp)
        if got != want:
            tmp.unlink()
            sys.exit(f"SHA-256 mismatch for {name}: expected {want}, got {got}")
        tmp.replace(dest)
        print(f"fetched {name}")


if __name__ == "__main__":
    main()
