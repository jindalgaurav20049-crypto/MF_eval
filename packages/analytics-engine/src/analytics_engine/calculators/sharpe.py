"""Sharpe Ratio calculator."""

from __future__ import annotations

import math
import statistics

_MIN_OBSERVATIONS = 12  # Require at least 12 monthly returns for a meaningful Sharpe


def sharpe_ratio(
    returns: list[float],
    risk_free_rate_annual: float = 0.065,
    periods_per_year: int = 12,
) -> float | None:
    """
    Compute the annualized Sharpe Ratio from a series of periodic returns.

    Returns None instead of raising when the result would be meaningless
    (insufficient data or zero standard deviation), so callers can safely
    display "N/A" in the UI rather than crashing.

    Formula:
        Sharpe = (mean_excess_return / std_dev_returns) * sqrt(periods_per_year)

    Args:
        returns: Periodic returns as decimals (e.g., monthly: [0.01, -0.02, ...]).
        risk_free_rate_annual: Annual risk-free rate as a decimal (default 6.5%, ~India T-bill).
        periods_per_year: Number of periods in a year (12 for monthly, 252 for daily).

    Returns:
        Annualized Sharpe Ratio, or None if computation is not meaningful.

    Examples:
        >>> result = sharpe_ratio([0.01, 0.02, -0.005, 0.015, 0.008] * 3)
        >>> result is not None
        True
    """
    if len(returns) < _MIN_OBSERVATIONS:
        return None

    risk_free_per_period = (1 + risk_free_rate_annual) ** (1.0 / periods_per_year) - 1
    excess_returns = [r - risk_free_per_period for r in returns]

    mean_excess = statistics.mean(excess_returns)

    try:
        std_dev = statistics.stdev(excess_returns)
    except statistics.StatisticsError:
        return None

    if std_dev == 0.0:
        return None

    return (mean_excess / std_dev) * math.sqrt(periods_per_year)
