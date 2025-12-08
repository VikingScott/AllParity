# src/config_strategy_risk_parity.py

"""
AllParity Strategy - Risk Parity & Trend Filter Configuration
语义变更：这里的数值代表 'Risk Budget' (风险预算)，而非直接的金额权重。
"""

# ===========================
# 1. 策略超参数 (Hyperparameters)
# ===========================
VOL_WINDOW = 120       # 计算波动率的窗口 (日)
TREND_WINDOW = 200    # 趋势过滤的均线窗口 (日)

# ===========================
# 2. 资产分类 (Asset Classes)
# ===========================
# 现金资产不参与风险平价计算，而是作为"剩余填充"(Plug)
# 风险资产参与 (Budget / Volatility) 的计算
ASSETS_CASH = ['SGOV'] 
ASSETS_RISKY = ['SPY', 'EFA', 'EEM', 'IWM',  # Equities
                'TLT', 'IEF', 'LQD', 'TIP',  # Bonds
                'DBC', 'GLD']                # Commodities

ALL_ASSETS = ASSETS_RISKY + ASSETS_CASH

# ===========================
# 3. 风险预算表 (Risk Budgets)
# ===========================
# 逻辑：
# 1. 'SGOV' 的数值代表固定权重 (Fixed Weight)。
#    例如 Regime 3 中 SGOV=0.2，意味着先预留 20% 仓位给现金。
# 2. 其他资产的数值代表相对风险预算 (Relative Risk Budget)。
#    例如 SPY=4, IEF=1，意味着 SPY 对组合波动的贡献要是 IEF 的 4 倍。
#    由于 SPY 波动率本来就大，这可能意味着金额上 SPY 会比 IEF 多一点点，或者差不多。

# Regime 1: Goldilocks (Growth+, Inflation-)
# 风险偏好：进攻。主配股票风险。
BUDGETS_REGIME_1 = {
    'SGOV': 0.0, # 满仓进攻
    # --- Risk Budgets (Relative) ---
    'SPY': 4.0, 
    'EFA': 1.5, 
    'EEM': 1.0, 
    'IWM': 1.0,
    'LQD': 2.0, # 信用债也算进攻
    'IEF': 1.0, # 少量底仓风险
    # --- Zero Budget ---
    'TLT': 0.0, 'TIP': 0.0, 'DBC': 0.0, 'GLD': 0.0
}

# Regime 2: Reflation (Growth+, Inflation+)
# 风险偏好：抗通胀进攻。股票和商品平分秋色。
BUDGETS_REGIME_2 = {
    'SGOV': 0.0,
    # --- Risk Budgets ---
    'SPY': 2.0,
    'EEM': 1.0,
    'DBC': 3.0, # 给商品高风险预算
    'TIP': 2.0, # 给抗通胀债高风险预算
    'GLD': 0.5,
    'IWM': 1.0,
    # --- Zero Budget ---
    'TLT': 0.0, 'IEF': 0.0, 'LQD': 0.0, 'EFA': 0.5
}

# Regime 3: Stagflation (Growth-, Inflation+)
# 风险偏好：防守型实物。
BUDGETS_REGIME_3 = {
    'SGOV': 0.20, # 强制保留 20% 现金应对波动
    # --- Risk Budgets (剩余 80% 仓位内部的分配) ---
    'GLD': 6.0, # 黄金是主力
    'DBC': 4.0,
    'TIP': 3.0,
    'IEF': 0.5,
    'LQD': 0.0,
    # --- Zero Budget ---
    'SPY': 0.0, 'EFA': 0.0, 'EEM': 0.0, 'IWM': 0.0, 'TLT': 0.0
}

# Regime 4 (Macro): Deflation (Growth-, Inflation-)
# 风险偏好：利率债进攻。
BUDGETS_REGIME_4_MACRO = {
    'SGOV': 0.0,
    # --- Risk Budgets ---
    'TLT': 8.0, # 风险全给长债
    'IEF': 2.0,
    'GLD': 1.5, # 少量对冲货币贬值
    'LQD':0.0,
    # --- Zero Budget ---
    'SPY': 0.0, 'EFA': 0.0, 'EEM': 0.0, 'IWM': 0.0, 'DBC': 0.0, 'TIP': 0.0
}

# Regime 4 (Panic): Circuit Breaker
# 风险偏好：极度厌恶风险。
BUDGETS_REGIME_4_PANIC = {
    'SGOV': 1.0, # 100% 现金
    # --- All Zero ---
    'SPY': 0.0, 'TLT': 0.0, 'GLD': 0.0 # ... (others implicit 0)
}

# ===========================
# 4. 映射表
# ===========================
ALLOCATION_LOOKUP_RP = {
    (1, "MACRO_QUADRANT"): BUDGETS_REGIME_1,
    (2, "MACRO_QUADRANT"): BUDGETS_REGIME_2,
    (3, "MACRO_QUADRANT"): BUDGETS_REGIME_3,
    (4, "MACRO_QUADRANT"): BUDGETS_REGIME_4_MACRO,
    (4, "MARKET_CIRCUIT"): BUDGETS_REGIME_4_PANIC,
}

# 默认回退
DEFAULT_BUDGETS = {asset: 0.0 for asset in ALL_ASSETS}
DEFAULT_BUDGETS['SGOV'] = 1.0