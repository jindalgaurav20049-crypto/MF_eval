"""Pydantic schemas for API request/response models."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class AnalysisMode(str, Enum):
    BEGINNER = "beginner"
    ADVANCED = "advanced"


# ── Health ────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str


# ── Fund Search ───────────────────────────────────────────────────────────────

class FundSearchResult(BaseModel):
    scheme_id: str
    scheme_name: str
    amc_name: str
    category: str
    sub_category: str
    plan: str  # "Direct" | "Regular"
    option: str  # "Growth" | "IDCW"
    nav: float | None = None
    aum_cr: float | None = None  # AUM in crores


class FundSearchResponse(BaseModel):
    query: str
    total: int
    results: list[FundSearchResult]


# ── Fund Summary ──────────────────────────────────────────────────────────────

class ReturnMetrics(BaseModel):
    period: str
    absolute_return_pct: float | None = None
    cagr_pct: float | None = None
    vs_benchmark_pct: float | None = None
    vs_category_avg_pct: float | None = None
    category_percentile: int | None = None  # 1–100, lower = better


class RiskMetrics(BaseModel):
    std_dev_annualized: float | None = None
    beta: float | None = None
    max_drawdown_pct: float | None = None
    downside_capture_ratio: float | None = None
    upside_capture_ratio: float | None = None
    sharpe_ratio: float | None = None
    sortino_ratio: float | None = None


class FundHealthScore(BaseModel):
    overall: float | None = None  # 0–100
    returns_consistency: float | None = None
    risk_containment: float | None = None
    risk_adjusted_efficiency: float | None = None
    portfolio_quality: float | None = None
    stability_governance: float | None = None
    cost_efficiency: float | None = None
    confidence: str | None = None  # "high" | "medium" | "low"


class BeginnerSummary(BaseModel):
    """Simplified summary for beginner mode — plain language labels."""

    scheme_id: str
    scheme_name: str
    mode: AnalysisMode = AnalysisMode.BEGINNER
    fund_health_score: FundHealthScore
    yearly_growth_rate_3y: float | None = None  # CAGR 3Y label for beginners
    did_it_beat_index_3y: bool | None = None
    risk_level: str | None = None  # "Low" | "Moderate" | "High" | "Very High"
    expense_ratio_pct: float | None = None
    fund_age_years: float | None = None
    verdict: str | None = None  # "Strong" | "Average" | "Weak" | "Insufficient Data"
    sip_note: str | None = None


class AdvancedSummary(BaseModel):
    """Full metric suite for advanced mode."""

    scheme_id: str
    scheme_name: str
    mode: AnalysisMode = AnalysisMode.ADVANCED
    fund_health_score: FundHealthScore
    return_metrics: list[ReturnMetrics] = Field(default_factory=list)
    risk_metrics: RiskMetrics | None = None
    expense_ratio_pct: float | None = None
    aum_cr: float | None = None
    fund_age_years: float | None = None
    fund_manager: str | None = None
    manager_tenure_years: float | None = None
    benchmark: str | None = None
    sebi_category: str | None = None


FundSummaryResponse = BeginnerSummary | AdvancedSummary


# ── Compare ───────────────────────────────────────────────────────────────────

class CompareSchemeSlot(BaseModel):
    scheme_id: str
    scheme_name: str
    category: str
    expense_ratio_pct: float | None = None
    nav: float | None = None
    return_1y_pct: float | None = None
    return_3y_cagr_pct: float | None = None
    return_5y_cagr_pct: float | None = None
    std_dev_3y: float | None = None
    sharpe_3y: float | None = None
    max_drawdown_pct: float | None = None
    fund_health_score: float | None = None


class CompareResponse(BaseModel):
    mode: AnalysisMode
    schemes: list[CompareSchemeSlot]
    note: str | None = None


# ── Error ─────────────────────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    detail: str
    code: str | None = None
    extra: dict[str, Any] | None = None
