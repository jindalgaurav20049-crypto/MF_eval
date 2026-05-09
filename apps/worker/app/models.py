from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import TIMESTAMP, Date, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Scheme(Base):
    __tablename__ = "scheme"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    amfi_scheme_code: Mapped[str] = mapped_column(String(20))


class NAVHistoryDaily(Base):
    __tablename__ = "nav_history_daily"

    scheme_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nav_date = mapped_column(Date, primary_key=True)
    nav: Mapped[Decimal] = mapped_column(Numeric(18, 4))


class ComputedMetricSnapshot(Base):
    __tablename__ = "computed_metric_snapshot"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scheme_id: Mapped[int] = mapped_column(Integer, ForeignKey("scheme.id", ondelete="CASCADE"))
    computed_at = mapped_column(TIMESTAMP(timezone=True), default=datetime.utcnow)
    period_label: Mapped[str] = mapped_column(String(20))
    cagr_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    std_dev_annualized: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    sharpe_ratio: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    sortino_ratio: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    max_drawdown_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    health_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))


class UserWatchlist(Base):
    __tablename__ = "user_watchlist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id = mapped_column(UUID(as_uuid=True))
    scheme_id: Mapped[int] = mapped_column(Integer)


class UserNotification(Base):
    __tablename__ = "user_notification"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id = mapped_column(UUID(as_uuid=True))
    scheme_id: Mapped[int | None] = mapped_column(Integer)
    notification_type: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(160))
    message: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String(20))
