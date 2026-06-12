"""
Tests for the version bump script's fail-fast guard.

A missing/empty/malformed VERSION file must abort the bump, never return a
sentinel that would drive a global string replacement across the tree.
"""

import importlib.util
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "bump_version.py"
_spec = importlib.util.spec_from_file_location("bump_version", _SCRIPT)
bump_version = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bump_version)


class TestGetCurrentVersion:
    """get_current_version must validate before returning (WOF-14 review hardening)."""

    def test_reads_valid_version(self, tmp_path):
        vf = tmp_path / "VERSION"
        vf.write_text("1.8.0\n")
        assert bump_version.get_current_version(vf) == "1.8.0"

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            bump_version.get_current_version(tmp_path / "VERSION")

    def test_empty_file_raises(self, tmp_path):
        vf = tmp_path / "VERSION"
        vf.write_text("   \n")
        with pytest.raises(ValueError):
            bump_version.get_current_version(vf)

    def test_malformed_version_raises(self, tmp_path):
        vf = tmp_path / "VERSION"
        vf.write_text("not-a-version")
        with pytest.raises(ValueError):
            bump_version.get_current_version(vf)
