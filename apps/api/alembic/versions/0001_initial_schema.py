"""initial schema

Revision ID: 0001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Optional TimescaleDB extension — non-breaking if not available
    op.execute(
        "DO $$ BEGIN CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE; "
        "EXCEPTION WHEN OTHERS THEN NULL; END $$;"
    )

    # ── app_user ──────────────────────────────────────────────────────────────
    op.create_table(
        "app_user",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("display_name", sa.String(120), nullable=True),
        sa.Column("analysis_mode", sa.String(20), server_default="beginner", nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_app_user_email", "app_user", ["email"])

    # ── amc ───────────────────────────────────────────────────────────────────
    op.create_table(
        "amc",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("amfi_code", sa.String(20), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("short_name", sa.String(60), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("amfi_code"),
    )
    op.create_index("ix_amc_amfi_code", "amc", ["amfi_code"])

    # ── scheme ────────────────────────────────────────────────────────────────
    op.create_table(
        "scheme",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("amfi_scheme_code", sa.String(20), nullable=False),
        sa.Column("amc_id", sa.Integer(), nullable=False),
        sa.Column("scheme_name", sa.String(400), nullable=False),
        sa.Column("sebi_category", sa.String(100), nullable=True),
        sa.Column("sebi_sub_category", sa.String(100), nullable=True),
        sa.Column("plan", sa.String(30), nullable=True),  # Direct | Regular
        sa.Column("option", sa.String(30), nullable=True),  # Growth | IDCW
        sa.Column("benchmark_name", sa.String(200), nullable=True),
        sa.Column("inception_date", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["amc_id"], ["amc.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("amfi_scheme_code"),
    )
    op.create_index("ix_scheme_amfi_code", "scheme", ["amfi_scheme_code"])
    op.create_index("ix_scheme_sebi_category", "scheme", ["sebi_category"])
    op.create_index("ix_scheme_amc_id", "scheme", ["amc_id"])

    # ── nav_history_daily ─────────────────────────────────────────────────────
    op.create_table(
        "nav_history_daily",
        sa.Column("scheme_id", sa.Integer(), nullable=False),
        sa.Column("nav_date", sa.Date(), nullable=False),
        sa.Column("nav", sa.Numeric(18, 4), nullable=False),
        sa.ForeignKeyConstraint(["scheme_id"], ["scheme.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("scheme_id", "nav_date"),
    )
    op.create_index("ix_nav_history_scheme_date", "nav_history_daily", ["scheme_id", "nav_date"])

    # ── benchmark_history_daily ───────────────────────────────────────────────
    op.create_table(
        "benchmark_history_daily",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("index_name", sa.String(200), nullable=False),
        sa.Column("index_date", sa.Date(), nullable=False),
        sa.Column("close_value", sa.Numeric(18, 4), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("index_name", "index_date"),
    )
    op.create_index(
        "ix_benchmark_index_date", "benchmark_history_daily", ["index_name", "index_date"]
    )

    # ── scheme_portfolio_snapshot ─────────────────────────────────────────────
    op.create_table(
        "scheme_portfolio_snapshot",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("scheme_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("isin", sa.String(20), nullable=True),
        sa.Column("instrument_name", sa.String(400), nullable=True),
        sa.Column("instrument_type", sa.String(40), nullable=True),
        sa.Column("sector", sa.String(100), nullable=True),
        sa.Column("weight_pct", sa.Numeric(8, 4), nullable=True),
        sa.Column("market_value_cr", sa.Numeric(18, 2), nullable=True),
        sa.Column("rating", sa.String(20), nullable=True),
        sa.ForeignKeyConstraint(["scheme_id"], ["scheme.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_scheme_portfolio_scheme_date",
        "scheme_portfolio_snapshot",
        ["scheme_id", "snapshot_date"],
    )

    # ── fund_manager_tenure ───────────────────────────────────────────────────
    op.create_table(
        "fund_manager_tenure",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("scheme_id", sa.Integer(), nullable=False),
        sa.Column("manager_name", sa.String(200), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("is_current", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.ForeignKeyConstraint(["scheme_id"], ["scheme.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_fund_manager_scheme", "fund_manager_tenure", ["scheme_id"])

    # ── scheme_event ──────────────────────────────────────────────────────────
    op.create_table(
        "scheme_event",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("scheme_id", sa.Integer(), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column(
            "event_type", sa.String(60), nullable=False
        ),  # manager_change | category_change | merger | sebi_directive
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["scheme_id"], ["scheme.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scheme_event_scheme_date", "scheme_event", ["scheme_id", "event_date"])

    # ── computed_metric_snapshot ──────────────────────────────────────────────
    op.create_table(
        "computed_metric_snapshot",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("scheme_id", sa.Integer(), nullable=False),
        sa.Column(
            "computed_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("period_label", sa.String(20), nullable=False),  # 1Y, 3Y, 5Y, etc.
        sa.Column("cagr_pct", sa.Numeric(10, 4), nullable=True),
        sa.Column("std_dev_annualized", sa.Numeric(10, 4), nullable=True),
        sa.Column("sharpe_ratio", sa.Numeric(10, 4), nullable=True),
        sa.Column("sortino_ratio", sa.Numeric(10, 4), nullable=True),
        sa.Column("max_drawdown_pct", sa.Numeric(10, 4), nullable=True),
        sa.Column("beta", sa.Numeric(10, 4), nullable=True),
        sa.Column("alpha_pct", sa.Numeric(10, 4), nullable=True),
        sa.Column("information_ratio", sa.Numeric(10, 4), nullable=True),
        sa.Column("upside_capture", sa.Numeric(10, 4), nullable=True),
        sa.Column("downside_capture", sa.Numeric(10, 4), nullable=True),
        sa.Column("health_score", sa.Numeric(6, 2), nullable=True),
        sa.ForeignKeyConstraint(["scheme_id"], ["scheme.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scheme_id", "period_label", "computed_at"),
    )
    op.create_index(
        "ix_computed_metric_scheme_period",
        "computed_metric_snapshot",
        ["scheme_id", "period_label"],
    )

    # ── user_watchlist ────────────────────────────────────────────────────────
    op.create_table(
        "user_watchlist",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("scheme_id", sa.Integer(), nullable=False),
        sa.Column(
            "added_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["scheme_id"], ["scheme.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "scheme_id"),
    )
    op.create_index("ix_user_watchlist_user", "user_watchlist", ["user_id"])

    # ── user_portfolio_txn ────────────────────────────────────────────────────
    op.create_table(
        "user_portfolio_txn",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("scheme_id", sa.Integer(), nullable=False),
        sa.Column("txn_date", sa.Date(), nullable=False),
        sa.Column(
            "txn_type", sa.String(20), nullable=False
        ),  # purchase | redemption | switch_in | switch_out
        sa.Column("amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("units", sa.Numeric(18, 4), nullable=True),
        sa.Column("nav_at_txn", sa.Numeric(18, 4), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["scheme_id"], ["scheme.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_portfolio_user_scheme", "user_portfolio_txn", ["user_id", "scheme_id"])
    op.create_index("ix_user_portfolio_txn_date", "user_portfolio_txn", ["txn_date"])


def downgrade() -> None:
    op.drop_table("user_portfolio_txn")
    op.drop_table("user_watchlist")
    op.drop_table("computed_metric_snapshot")
    op.drop_table("scheme_event")
    op.drop_table("fund_manager_tenure")
    op.drop_table("scheme_portfolio_snapshot")
    op.drop_table("benchmark_history_daily")
    op.drop_table("nav_history_daily")
    op.drop_table("scheme")
    op.drop_table("amc")
    op.drop_table("app_user")
