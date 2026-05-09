from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import math
import statistics

from analytics_engine.calculators.cagr import cagr_from_nav_series
from analytics_engine.calculators.drawdown import max_drawdown
from analytics_engine.calculators.sharpe import sharpe_ratio


@dataclass(frozen=True)
class TrailingMetric:
    period_label: str
    cagr_pct: float | None
    std_dev_annualized: float | None
    sharpe_ratio: float | None
    sortino_ratio: float | None
    max_drawdown_pct: float | None


@dataclass(frozen=True)
class RiskSnapshot:
    std_dev_annualized: float | None
    sharpe_ratio: float | None
    sortino_ratio: float | None
    max_drawdown_pct: float | None


def compute_trailing_metrics(nav_series: list[tuple[date, float]]) -> list[TrailingMetric]:
    if len(nav_series) < 2:
        return []
    nav_series = sorted(nav_series, key=lambda row: row[0])
    latest_date = nav_series[-1][0]
    periods = {
        "1Y": 365,
        "3Y": 365 * 3,
        "5Y": 365 * 5,
    }
    metrics: list[TrailingMetric] = []
    for label, days in periods.items():
        sliced = [row for row in nav_series if (latest_date - row[0]).days <= days]
        if len(sliced) < 2:
            metrics.append(TrailingMetric(label, None, None, None, None, None))
            continue
        navs = [row[1] for row in sliced]
        years = max((sliced[-1][0] - sliced[0][0]).days / 365.25, 0.01)
        try:
            cagr_value = cagr_from_nav_series(navs, years=years) * 100
        except ValueError:
            cagr_value = None
        returns = _returns_from_navs(navs)
        std_dev = _annualized_std_dev(returns, periods_per_year=252)
        monthly_returns = _monthly_returns(sliced)
        sharpe_value = sharpe_ratio(monthly_returns) if monthly_returns else None
        sortino_value = _sortino_ratio(monthly_returns) if monthly_returns else None
        try:
            drawdown_value = max_drawdown(navs) * 100
        except ValueError:
            drawdown_value = None
        metrics.append(
            TrailingMetric(
                period_label=label,
                cagr_pct=_round(cagr_value) if cagr_value is not None else None,
                std_dev_annualized=_round(std_dev),
                sharpe_ratio=_round(sharpe_value),
                sortino_ratio=_round(sortino_value),
                max_drawdown_pct=_round(drawdown_value) if drawdown_value is not None else None,
            )
        )
    return metrics


def compute_risk_snapshot(nav_series: list[tuple[date, float]]) -> RiskSnapshot:
    if len(nav_series) < 2:
        return RiskSnapshot(None, None, None, None)
    nav_series = sorted(nav_series, key=lambda row: row[0])
    navs = [row[1] for row in nav_series]
    returns = _returns_from_navs(navs)
    std_dev = _annualized_std_dev(returns, periods_per_year=252)
    monthly_returns = _monthly_returns(nav_series)
    try:
        drawdown_pct = max_drawdown(navs) * 100
    except ValueError:
        drawdown_pct = None
    return RiskSnapshot(
        std_dev_annualized=_round(std_dev),
        sharpe_ratio=_round(sharpe_ratio(monthly_returns) if monthly_returns else None),
        sortino_ratio=_round(_sortino_ratio(monthly_returns) if monthly_returns else None),
        max_drawdown_pct=_round(drawdown_pct) if drawdown_pct is not None else None,
    )


def compute_fund_health(metrics: list[TrailingMetric]) -> float | None:
    available = [m for m in metrics if m.cagr_pct is not None]
    if not available:
        return None
    score = 0.0
    weights = 0.0
    for metric in available:
        weight = {"1Y": 0.25, "3Y": 0.35, "5Y": 0.4}.get(metric.period_label, 0.2)
        return_score = min(max(metric.cagr_pct or 0, -10), 30)
        drawdown_score = 0.0
        if metric.max_drawdown_pct is not None:
            drawdown_score = max(0.0, 30 - abs(metric.max_drawdown_pct))
        sharpe_score = 0.0
        if metric.sharpe_ratio is not None:
            sharpe_score = min(max(metric.sharpe_ratio * 20, 0), 20)
        metric_score = return_score + drawdown_score + sharpe_score
        score += metric_score * weight
        weights += weight
    return _round(score / weights) if weights else None


def rolling_returns(nav_series: list[tuple[date, float]], window_years: int) -> list[tuple[date, float]]:
    if len(nav_series) < 2:
        return []
    nav_series = sorted(nav_series, key=lambda row: row[0])
    window_days = window_years * 365
    results: list[tuple[date, float]] = []
    for idx, (current_date, current_nav) in enumerate(nav_series):
        start_candidates = [
            nav for nav in nav_series[: idx + 1] if (current_date - nav[0]).days >= window_days
        ]
        if not start_candidates:
            continue
        start_date, start_nav = start_candidates[-1]
        years = max((current_date - start_date).days / 365.25, 0.01)
        cagr_value = cagr_from_nav_series([start_nav, current_nav], years=years) * 100
        results.append((current_date, _round(cagr_value)))
    return results


def _returns_from_navs(navs: list[float]) -> list[float]:
    returns: list[float] = []
    for previous, current in zip(navs, navs[1:]):
        if previous <= 0:
            continue
        returns.append((current / previous) - 1)
    return returns


def _annualized_std_dev(returns: list[float], periods_per_year: int) -> float | None:
    if len(returns) < 2:
        return None
    try:
        return statistics.stdev(returns) * math.sqrt(periods_per_year) * 100
    except statistics.StatisticsError:
        return None


def _monthly_returns(nav_series: list[tuple[date, float]]) -> list[float]:
    monthly: dict[tuple[int, int], float] = {}
    for nav_date, nav in nav_series:
        monthly[(nav_date.year, nav_date.month)] = nav
    ordered = [monthly[key] for key in sorted(monthly)]
    return _returns_from_navs(ordered)


def _sortino_ratio(returns: list[float], target_return: float = 0.0) -> float | None:
    if len(returns) < 6:
        return None
    downside = [r - target_return for r in returns if r < target_return]
    if not downside:
        return None
    downside_std = statistics.pstdev(downside)
    if downside_std == 0:
        return None
    mean_return = statistics.mean(returns)
    return (mean_return - target_return) / downside_std


def _round(value: float | None, digits: int = 2) -> float | None:
    if value is None:
        return None
    return round(value, digits)
