"""
Unit tests for financial calculations.
"""

import pytest
import pandas as pd
import numpy as np
from utils.calculations import calculate_cagr, calculate_sharpe_ratio, calculate_diversification_score

def test_calculate_cagr():
    # Double value in 3 years = (2)^(1/3) - 1 approx 0.2599
    assert abs(calculate_cagr(100.0, 200.0, 3.0) - 0.2599) < 0.01
    
    # Zero years check
    assert calculate_cagr(100.0, 200.0, 0.0) == 0.0

def test_calculate_sharpe_ratio():
    returns = pd.Series([0.10, 0.12, 0.08, 0.15, 0.05])
    # Returns some numeric sharpe ratio
    sharpe = calculate_sharpe_ratio(returns, risk_free_rate=0.06)
    assert isinstance(sharpe, float)

def test_calculate_diversification_score():
    # Equal allocation (perfect)
    allocations = [25.0, 25.0, 25.0, 25.0]
    score = calculate_diversification_score(allocations)
    assert abs(score - 100.0) < 0.1

