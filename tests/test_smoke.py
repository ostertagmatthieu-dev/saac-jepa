"""End-to-end smoke tests that run the repository's own scripts as subprocesses.

Each test invokes a script the same way a user would from the repository root, and
checks both the process exit code and the sentinel string the script prints on success.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _run(*args, timeout):
    return subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        env={**os.environ, "PYTHONUNBUFFERED": "1", "OMP_NUM_THREADS": "2", "MKL_NUM_THREADS": "2"},
        text=True,
        capture_output=True,
        timeout=timeout,
    )


def test_p3fix_invariants():
    result = _run("tests/test_p3fix.py", timeout=900)
    print(result.stdout[-6000:])
    print(result.stderr[-6000:])
    assert result.returncode == 0
    assert "P3FIX_TESTS_OK" in result.stdout


@pytest.mark.slow
def test_smoke_core_pipeline():
    result = _run("scripts/54_smoke_test_core.py", timeout=1800)
    print(result.stdout[-6000:])
    print(result.stderr[-6000:])
    assert result.returncode == 0
    assert "SMOKE_CORE_OK" in result.stdout


def test_triple_review():
    result = _run("scripts/55_triple_review.py", timeout=600)
    print(result.stdout[-6000:])
    print(result.stderr[-6000:])
    assert result.returncode == 0
    assert "TRIPLE_REVIEW_OK" in result.stdout
