"""FundLens Analytics Engine — metric computation for Indian mutual funds."""

__version__ = "0.1.0"

from analytics_engine.calculators.cagr import cagr
from analytics_engine.calculators.drawdown import max_drawdown
from analytics_engine.calculators.sharpe import sharpe_ratio

__all__ = ["cagr", "max_drawdown", "sharpe_ratio"]
