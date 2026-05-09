from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import AppUser, ComputedMetricSnapshot, Scheme, UserNotification, UserWatchlist


def add_to_watchlist(db: Session, email: str, scheme_code: str) -> UserWatchlist | None:
    user = _get_or_create_user(db, email)
    scheme = db.execute(
        select(Scheme).where(Scheme.amfi_scheme_code == scheme_code)
    ).scalar_one_or_none()
    if scheme is None:
        return None
    existing = db.execute(
        select(UserWatchlist).where(
            UserWatchlist.user_id == user.id, UserWatchlist.scheme_id == scheme.id
        )
    ).scalar_one_or_none()
    if existing:
        return existing
    entry = UserWatchlist(user_id=user.id, scheme_id=scheme.id)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def list_watchlist(db: Session, user_id: str) -> list[UserWatchlist]:
    return db.execute(select(UserWatchlist).where(UserWatchlist.user_id == user_id)).scalars().all()


def list_notifications(db: Session, user_id: str) -> list[UserNotification]:
    return (
        db.execute(
            select(UserNotification)
            .where(UserNotification.user_id == user_id)
            .order_by(UserNotification.created_at.desc())
        )
        .scalars()
        .all()
    )


def generate_watchlist_alerts(db: Session) -> int:
    watchlist = db.execute(select(UserWatchlist)).scalars().all()
    alerts = 0
    for entry in watchlist:
        snapshot = (
            db.execute(
                select(ComputedMetricSnapshot)
                .where(ComputedMetricSnapshot.scheme_id == entry.scheme_id)
                .order_by(ComputedMetricSnapshot.computed_at.desc())
            )
            .scalars()
            .first()
        )
        if snapshot is None or snapshot.health_score is None:
            continue
        if float(snapshot.health_score) < settings.health_alert_threshold:
            notification = UserNotification(
                user_id=entry.user_id,
                scheme_id=entry.scheme_id,
                notification_type="health_drop",
                title="Fund health dropped",
                message="A watchlisted fund health score dipped below 50. Consider reviewing.",
                payload_json=json.dumps({"health_score": float(snapshot.health_score)}),
                status="queued",
                created_at=datetime.now(timezone.utc),
            )
            db.add(notification)
            alerts += 1
    db.commit()
    return alerts


def _get_or_create_user(db: Session, email: str) -> AppUser:
    user = db.execute(select(AppUser).where(AppUser.email == email)).scalar_one_or_none()
    if user:
        return user
    user = AppUser(email=email, display_name=email.split("@")[0])
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
