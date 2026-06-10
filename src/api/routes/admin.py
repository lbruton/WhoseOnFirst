"""
Admin API Routes — Data Export & Restore

GET  /api/v1/admin/export  — Download full .stvault backup (admin only)
POST /api/v1/admin/import  — Restore from .stvault upload (admin only)
"""

import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

# Use the shared API dependency (like the other route modules) so test
# fixtures that override src.api.dependencies.get_db cover these routes too
from src.api.dependencies import get_db
from src.api.routes.auth import require_admin
from src.services.export_service import ExportService
from src.services.import_service import ImportService, ImportValidationError

router = APIRouter()


@router.get("/export")
def export_backup(
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    """
    Export the full database as a .stvault file download.

    Returns a JSON file containing team_members, shifts, schedule, and settings.
    Users and notification_log are excluded.
    """
    service = ExportService(db)
    data = service.export_all()
    payload = json.dumps(data, indent=2, ensure_ascii=False)

    filename = f"whoseonfirst-{datetime.now().strftime('%Y-%m-%d')}.stvault"

    return StreamingResponse(
        iter([payload]),
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(payload.encode("utf-8"))),
        },
    )


@router.post("/import")
async def import_backup(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    """
    Restore database from a .stvault file upload.

    WARNING: This overwrites ALL existing data (team_members, shifts,
    schedule, settings). The operation is atomic — any error rolls back.

    Returns:
        Summary of imported row counts per table.
    """
    # Read and parse the uploaded file
    try:
        raw = await file.read()
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid JSON: {exc}",
        )

    # Validate then restore
    service = ImportService(db)
    try:
        counts = service.restore_all(payload)
    except ImportValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Import failed and was rolled back: {exc}",
        )

    return {
        "status": "success",
        "message": "Database restored successfully",
        "imported": counts,
    }
