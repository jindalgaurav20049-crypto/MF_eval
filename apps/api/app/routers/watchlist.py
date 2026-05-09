from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.notifications import add_to_watchlist, list_notifications, list_watchlist

router = APIRouter(prefix="/watchlist", tags=["watchlist"])
logger = structlog.get_logger(__name__)


class WatchlistRequest(BaseModel):
    email: str
    scheme_id: str


@router.post("")
async def add_watchlist(payload: WatchlistRequest, db: Session = Depends(get_db)) -> dict:
    logger.info("watchlist_add", email=payload.email, scheme_id=payload.scheme_id)
    entry = add_to_watchlist(db, payload.email, payload.scheme_id)
    if entry is None:
        return {"status": "not_found"}
    return {"status": "ok", "watchlist_id": entry.id}


@router.get("/{user_id}")
async def get_watchlist(user_id: str, db: Session = Depends(get_db)) -> dict:
    entries = list_watchlist(db, user_id)
    return {
        "user_id": user_id,
        "watchlist": [
            {"scheme_id": entry.scheme_id, "added_at": entry.added_at.isoformat()}
            for entry in entries
        ],
    }


@router.get("/{user_id}/notifications")
async def get_notifications(user_id: str, db: Session = Depends(get_db)) -> dict:
    notifications = list_notifications(db, user_id)
    return {
        "user_id": user_id,
        "notifications": [
            {
                "title": notice.title,
                "message": notice.message,
                "type": notice.notification_type,
                "created_at": notice.created_at.isoformat(),
                "status": notice.status,
            }
            for notice in notifications
        ],
    }
