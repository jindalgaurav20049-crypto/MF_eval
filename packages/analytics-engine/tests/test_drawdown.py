import pytest
from analytics_engine.calculators.drawdown import max_drawdown


def test_max_drawdown_simple():
    navs = [100, 120, 90, 110, 80, 130]
    result = max_drawdown(navs)
    # Peak is 120, trough is 80 → (80 - 120) / 120 = -0.3333
    assert abs(result - (-1 / 3)) < 1e-9


def test_max_drawdown_no_drawdown():
    navs = [100, 110, 120, 130]
    result = max_drawdown(navs)
    assert result == 0.0


def test_max_drawdown_all_falling():
    navs = [100, 90, 80, 70]
    result = max_drawdown(navs)
    # (70 - 100) / 100 = -0.3
    assert abs(result - (-0.3)) < 1e-9


def test_max_drawdown_single_element():
    result = max_drawdown([100.0])
    assert result == 0.0


def test_max_drawdown_raises_on_empty():
    with pytest.raises(ValueError, match="must not be empty"):
        max_drawdown([])


def test_max_drawdown_raises_on_zero_nav():
    with pytest.raises(ValueError, match="positive"):
        max_drawdown([100, 0, 50])


def test_max_drawdown_raises_on_negative_nav():
    with pytest.raises(ValueError, match="positive"):
        max_drawdown([100, -10, 50])


def test_max_drawdown_recovers_fully():
    # Goes down then recovers to new high
    navs = [100, 50, 150]
    result = max_drawdown(navs)
    # (50 - 100) / 100 = -0.5
    assert abs(result - (-0.5)) < 1e-9


def test_max_drawdown_multiple_troughs():
    # Two troughs; second is deeper
    navs = [100, 80, 110, 60, 120]
    result = max_drawdown(navs)
    # Peak 110, trough 60 → (60 - 110)/110 = -0.4545...
    assert abs(result - (-50 / 110)) < 1e-9
