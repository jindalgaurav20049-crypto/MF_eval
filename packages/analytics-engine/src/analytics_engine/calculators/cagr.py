"""CAGR (Compounded Annual Growth Rate) calculator."""

from __future__ import annotations


def cagr(beginning_value: float, ending_value: float, years: float) -> float:
    """
    Compute CAGR as a decimal (not percentage).

    Formula: (ending_value / beginning_value) ^ (1 / years) - 1

    Args:
        beginning_value: Starting NAV or value. Must be > 0.
        ending_value: Ending NAV or value. Must be > 0.
        years: Number of years. Must be > 0.

    Returns:
        CAGR as a decimal, e.g., 0.12 for 12%.

    Raises:
        ValueError: If any argument is non-positive.

    Examples:
        >>> round(cagr(100, 200, 5), 4)
        0.1487
    """
    if beginning_value <= 0:
        raise ValueError(f"beginning_value must be > 0, got {beginning_value}")
    if ending_value <= 0:
        raise ValueError(f"ending_value must be > 0, got {ending_value}")
    if years <= 0:
        raise ValueError(f"years must be > 0, got {years}")

    return (ending_value / beginning_value) ** (1.0 / years) - 1.0


def cagr_from_nav_series(navs: list[float], years: float | None = None) -> float:
    """
    Convenience wrapper: compute CAGR from a list of NAV values.

    Args:
        navs: Ordered list of NAV values (oldest first). Must have >= 2 values.
        years: Duration in years. If None, inferred from len(navs) assuming daily data
               (252 trading days per year).

    Returns:
        CAGR as a decimal.

    Raises:
        ValueError: If navs has fewer than 2 elements.
    """
    if len(navs) < 2:
        raise ValueError("navs must have at least 2 values")

    if years is None:
        years = (len(navs) - 1) / 252.0

    if years <= 0:
        raise ValueError("Computed years must be > 0")

    return cagr(navs[0], navs[-1], years)
