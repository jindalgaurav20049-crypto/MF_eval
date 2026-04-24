import pytest
from analytics_engine.calculators.cagr import cagr, cagr_from_nav_series


def test_cagr_doubles_in_5_years():
    result = cagr(100.0, 200.0, 5.0)
    assert abs(result - 0.14869835499704) < 1e-6


def test_cagr_flat_returns_zero():
    result = cagr(100.0, 100.0, 3.0)
    assert result == 0.0


def test_cagr_one_year():
    result = cagr(100.0, 115.0, 1.0)
    assert abs(result - 0.15) < 1e-9


def test_cagr_fractional_years():
    result = cagr(100.0, 110.0, 0.5)
    assert abs(result - 0.21) < 0.001


def test_cagr_raises_on_zero_beginning():
    with pytest.raises(ValueError, match="beginning_value"):
        cagr(0.0, 100.0, 1.0)


def test_cagr_raises_on_negative_ending():
    with pytest.raises(ValueError, match="ending_value"):
        cagr(100.0, -50.0, 1.0)


def test_cagr_raises_on_zero_years():
    with pytest.raises(ValueError, match="years"):
        cagr(100.0, 110.0, 0.0)


def test_cagr_from_nav_series_basic():
    navs = [100.0, 200.0]
    result = cagr_from_nav_series(navs, years=1.0)
    assert abs(result - 1.0) < 1e-9  # 100% return in 1 year


def test_cagr_from_nav_series_too_short():
    with pytest.raises(ValueError, match="at least 2"):
        cagr_from_nav_series([100.0])


def test_cagr_from_nav_series_infers_years():
    # 252 entries → 1 year inferred
    navs = [100.0] * 252 + [121.0]  # 253 entries, ~1 year, ~21% growth
    result = cagr_from_nav_series(navs)
    # Should be approximately 21%
    assert 0.18 < result < 0.24
