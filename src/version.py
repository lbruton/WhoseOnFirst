"""
Single source of truth for the application version.

Every version surface (FastAPI app, /health, /api, /api/v1/version, data
exports) reads from the canonical VERSION file at the repo root via
``get_app_version()`` — eliminating the hardcoded-literal drift class (WOF-14).
"""

from pathlib import Path

_VERSION_FILE = Path(__file__).resolve().parent.parent / "VERSION"


def get_app_version() -> str:
    """Return the canonical app version, or "unknown" if the VERSION file is absent."""
    try:
        return _VERSION_FILE.read_text().strip()
    except FileNotFoundError:
        return "unknown"
