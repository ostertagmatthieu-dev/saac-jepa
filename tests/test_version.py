import importlib.metadata
import re
from pathlib import Path

import pytest
import yaml

import cncjepa

ROOT = Path(__file__).resolve().parents[1]


def test_version_is_semver():
    assert re.match(r"^\d+\.\d+\.\d+$", cncjepa.__version__)


def test_version_matches_distribution():
    try:
        distribution_version = importlib.metadata.version("saac-jepa")
    except importlib.metadata.PackageNotFoundError:
        pytest.skip("saac-jepa is not installed as a distribution")
    assert distribution_version == cncjepa.__version__


def test_version_matches_citation_cff():
    data = yaml.safe_load((ROOT / "CITATION.cff").read_text())
    if "version" not in data:
        pytest.skip("CITATION.cff has no version key")
    assert str(data["version"]) == cncjepa.__version__
