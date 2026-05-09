from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.events import (
    import_manager_changes,
    import_scheme_events,
    list_manager_changes,
    list_scheme_events,
)
from app.services.funds_service import get_scheme_by_code

router = APIRouter(prefix="/events", tags=["events"])
logger = structlog.get_logger(__name__)


@router.post("/manager-changes/import")
async def upload_manager_changes(
    file: UploadFile = File(...), db: Session = Depends(get_db)
) -> dict:
    payload = await file.read()
    logger.info("manager_changes_import", filename=file.filename)
    count = import_manager_changes(db, payload)
    return {"rows_loaded": count}


@router.post("/scheme-events/import")
async def upload_scheme_events(file: UploadFile = File(...), db: Session = Depends(get_db)) -> dict:
    payload = await file.read()
    logger.info("scheme_events_import", filename=file.filename)
    count = import_scheme_events(db, payload)
    return {"rows_loaded": count}


@router.get("/funds/{scheme_id}/manager-changes")
async def manager_changes(scheme_id: str, db: Session = Depends(get_db)) -> dict:
    scheme = get_scheme_by_code(db, scheme_id)
    if scheme is None:
        return {"scheme_id": scheme_id, "changes": []}
    changes = list_manager_changes(db, scheme.id)
    return {
        "scheme_id": scheme_id,
        "changes": [
            {
                "manager_name": change.manager_name,
                "start_date": change.start_date.isoformat(),
                "end_date": change.end_date.isoformat() if change.end_date else None,
                "is_current": bool(change.is_current),
            }
            for change in changes
        ],
    }


@router.get("/funds/{scheme_id}/regulatory-events")
async def regulatory_events(scheme_id: str, db: Session = Depends(get_db)) -> dict:
    scheme = get_scheme_by_code(db, scheme_id)
    if scheme is None:
        return {"scheme_id": scheme_id, "events": []}
    events = list_scheme_events(db, scheme.id)
    return {
        "scheme_id": scheme_id,
        "events": [
            {
                "event_date": event.event_date.isoformat(),
                "event_type": event.event_type,
                "description": event.description,
                "metadata": event.metadata_json,
            }
            for event in events
        ],
    }
