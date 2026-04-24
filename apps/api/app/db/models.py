"""SQLAlchemy ORM models matching the Alembic migration schema."""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import (
    TIMESTAMP,
    Boolean,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base


class AppUser(Base):
    __tablename__ = "app_user"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(120))
    analysis_mode: Mapped[str] = mapped_column(String(20), server_default="beginner")
    created_at = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())


class AMC(Base):
    __tablename__ = "amc"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    amfi_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    short_name: Mapped[str | None] = mapped_column(String(60))
    created_at = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    schemes: Mapped[list[Scheme]] = relationship("Scheme", back_populates="amc")


class Scheme(Base):
    __tablename__ = "scheme"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    amfi_scheme_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    amc_id: Mapped[int] = mapped_column(Integer, ForeignKey("amc.id", ondelete="RESTRICT"), nullable=False)
    scheme_name: Mapped[str] = mapped_column(String(400), nullable=False)
    sebi_category: Mapped[str | None] = mapped_column(String(100))
    sebi_sub_category: Mapped[str | None] = mapped_column(String(100))
    plan: Mapped[str | None] = mapped_column(String(30))
    option: Mapped[str | None] = mapped_column(String(30))
    benchmark_name: Mapped[str | None] = mapped_column(String(200))
    inception_date = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    created_at = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    amc: Mapped[AMC] = relationship("AMC", back_populates="schemes")


class NAVHistoryDaily(Base):
    __tablename__ = "nav_history_daily"

    scheme_id: Mapped[int] = mapped_column(Integer, ForeignKey("scheme.id", ondelete="CASCADE"), primary_key=True)
    nav_date = mapped_column(Date, primary_key=True)
    nav: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)


class BenchmarkHistoryDaily(Base):
    __tablename__ = "benchmark_history_daily"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    index_name: Mapped[str] = mapped_column(String(200), nullable=False)
    index_date = mapped_column(Date, nullable=False)
    close_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)

    __table_args__ = (UniqueConstraint("index_name", "index_date"),)


class ComputedMetricSnapshot(Base):
    __tablename__ = "computed_metric_snapshot"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scheme_id: Mapped[int] = mapped_column(Integer, ForeignKey("scheme.id", ondelete="CASCADE"), nullable=False)
    computed_at = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    period_label: Mapped[str] = mapped_column(String(20), nullable=False)
    cagr_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    std_dev_annualized: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    sharpe_ratio: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    sortino_ratio: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    max_drawdown_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    beta: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    alpha_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    information_ratio: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    upside_capture: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    downside_capture: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    health_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))


class UserWatchlist(Base):
    __tablename__ = "user_watchlist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id = mapped_column(UUID(as_uuid=True), ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False)
    scheme_id: Mapped[int] = mapped_column(Integer, ForeignKey("scheme.id", ondelete="CASCADE"), nullable=False)
    added_at = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    notes: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (UniqueConstraint("user_id", "scheme_id"),)


class UserPortfolioTxn(Base):
    __tablename__ = "user_portfolio_txn"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id = mapped_column(UUID(as_uuid=True), ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False)
    scheme_id: Mapped[int] = mapped_column(Integer, ForeignKey("scheme.id", ondelete="CASCADE"), nullable=False)
    txn_date = mapped_column(Date, nullable=False)
    txn_type: Mapped[str] = mapped_column(String(20), nullable=False)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    units: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    nav_at_txn: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    created_at = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
