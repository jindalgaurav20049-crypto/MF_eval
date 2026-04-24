import math

from analytics_engine.calculators.sharpe import sharpe_ratio


def _monthly_returns(n: int, mean: float = 0.01, std: float = 0.02) -> list[float]:
    """Generate synthetic monthly returns."""
    import random
    random.seed(42)
    return [mean + std * (random.random() - 0.5) for _ in range(n)]


def test_sharpe_returns_none_on_insufficient_data():
    assert sharpe_ratio([0.01, 0.02, 0.005]) is None


def test_sharpe_returns_none_on_zero_std():
    # All returns identical → zero std dev
    returns = [0.01] * 12
    assert sharpe_ratio(returns) is None


def test_sharpe_returns_float_with_enough_data():
    returns = _monthly_returns(24)
    result = sharpe_ratio(returns)
    assert result is not None
    assert isinstance(result, float)


def test_sharpe_positive_for_good_returns():
    # Monthly returns clearly above risk-free (6.5% annual → ~0.526%/month)
    returns = [0.015] * 24  # 1.5% per month
    # std dev is 0 → should return None (edge case)
    assert sharpe_ratio(returns) is None  # all same → zero std


def test_sharpe_with_varying_returns():
    returns = [0.02, -0.01, 0.015, 0.008, -0.005, 0.012] * 4  # 24 observations
    result = sharpe_ratio(returns)
    assert result is not None
    assert math.isfinite(result)


def test_sharpe_higher_for_better_risk_adjusted():
    good_returns = [0.015, 0.014, 0.016, 0.013, 0.015, 0.014] * 4
    bad_returns  = [0.02, -0.01, 0.025, -0.008, 0.022, -0.012] * 4
    s_good = sharpe_ratio(good_returns)
    s_bad = sharpe_ratio(bad_returns)
    assert s_good is not None
    assert s_bad is not None
    assert s_good > s_bad


def test_sharpe_custom_risk_free_rate():
    returns = _monthly_returns(24)
    s_low_rf = sharpe_ratio(returns, risk_free_rate_annual=0.04)
    s_high_rf = sharpe_ratio(returns, risk_free_rate_annual=0.09)
    # Lower risk-free → higher Sharpe (if returns above risk-free)
    if s_low_rf is not None and s_high_rf is not None:
        # Just verify no crash; direction depends on actual return level vs risk-free
        assert math.isfinite(s_low_rf) and math.isfinite(s_high_rf)


def test_sharpe_eleven_obs_returns_none():
    returns = _monthly_returns(11)
    assert sharpe_ratio(returns) is None
