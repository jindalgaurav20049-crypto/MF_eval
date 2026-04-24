"""Max Drawdown calculator."""

from __future__ import annotations


def max_drawdown(nav_series: list[float]) -> float:
    """
    Compute the maximum peak-to-trough drawdown from a NAV series.

    The result is a negative decimal (or 0.0 if no drawdown occurred),
    e.g., -0.285 for a 28.5% drawdown.

    Args:
        nav_series: Ordered list of NAV values (oldest first). Must be non-empty.

    Returns:
        Maximum drawdown as a negative decimal (0.0 if no drawdown).

    Raises:
        ValueError: If nav_series is empty or contains non-positive values.

    Examples:
        >>> max_drawdown([100, 120, 90, 110, 80, 130])
        -0.3333333333333333
    """
    if not nav_series:
        raise ValueError("nav_series must not be empty")
    if any(v <= 0 for v in nav_series):
        raise ValueError("All NAV values must be positive")

    peak = nav_series[0]
    max_dd = 0.0

    for nav in nav_series:
        if nav > peak:
            peak = nav
        drawdown = (nav - peak) / peak
        if drawdown < max_dd:
            max_dd = drawdown

    return max_dd
