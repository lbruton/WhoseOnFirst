from fastapi import APIRouter

from src.version import get_app_version

router = APIRouter(prefix="/api/v1", tags=["version"])


@router.get("/version")
def get_version():
    return {"version": get_app_version()}
