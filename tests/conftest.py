import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session", autouse=True)
def synthetic_dataset():
    """Generate the synthetic dataset once per test session if it is not already present."""
    csv_path = ROOT / "data" / "synthetic_ds01_ds03.csv"
    if not csv_path.exists():
        subprocess.run(
            [sys.executable, "examples/make_synthetic_ds01_ds03.py"],
            cwd=ROOT,
            check=True,
        )
