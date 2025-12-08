# src/config_regime.py

"""
AllParity Strategy - Macro Regime Configuration
"""

# 1. Trend Definitions
MACRO_TREND_WINDOW = 90

# 2. Inflation Blending (Anchor vs Kite)
INFLATION_WEIGHTS = {
    "core": 0.7,
    "headline": 0.3
}

# 3. Market Veto Thresholds
THRESHOLD_VIX_PANIC = 25.0       # VIX > 25 = Stress
THRESHOLD_CREDIT_STRESS = 2.5    # Spread > 2.5 = Tight Credit
THRESHOLD_CURVE_INVERT = 0.0     # 10Y-2Y < 0 = Inverted

# 4. Logic Overrides
THRESHOLD_INFLATION_STICKY = 3.0 # Core CPI > 3% = Force Inflation Regime
THRESHOLD_MARKET_PANIC = -2      # Score <= -2 = Force Crash Regime

# 5. Regime Map
# (Growth_Dir, Inflation_Dir) -> Regime Code
REGIME_CODE_MAP = {
    (1, -1): 1,  # Goldilocks
    (1, 1):  2,  # Reflation
    (-1, 1): 3,  # Stagflation
    (-1, -1): 4  # Deflation/Crash
}