from pathlib import Path
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1", tags=["version"])

_VERSION_FILE = Path(__file__).resolve().parents[3] / "VERSION"


@router.get("/version")
def get_version():
    try:
        version = _VERSION_FILE.read_text().strip()
    except FileNotFoundError:
        version = "unknown"
    return {"version": version}
