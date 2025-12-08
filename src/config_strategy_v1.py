# src/config_strategy_v1.py

"""
AllParity Strategy - Asset Allocation Configuration (Static Weights V1)
定义不同宏观体制下的目标资产配置权重。
"""

# ===========================
# 1. 资产池定义 (Asset Universe)
# ===========================
# 必须与 asset_prices.csv 的列名完全一致
ASSETS_EQUITY = ['SPY', 'EFA', 'EEM', 'IWM']
ASSETS_BOND   = ['TLT', 'IEF', 'LQD', 'TIP']
ASSETS_COMM   = ['DBC', 'GLD']
ASSETS_CASH   = ['SGOV']

# 全资产列表
ALL_ASSETS = ASSETS_EQUITY + ASSETS_BOND + ASSETS_COMM + ASSETS_CASH

# ===========================
# 2. 体制配置表 (Regime Allocations)
# ===========================
# 权重之和必须为 1.0 (100%)

# Regime 1: Goldilocks (Growth Rising, Inflation Falling)
# 策略：高配股票，搭配信用债，低配商品/长债
WEIGHTS_REGIME_1 = {
    'SPY': 0.40,  # 美股核心
    'EFA': 0.15,  # 发达国家
    'EEM': 0.05,  # 新兴市场
    'IWM': 0.10,  # 小盘股 (高Beta)
    'LQD': 0.10,  # 公司债 (信用风险暴露)
    'IEF': 0.20,  # 中期国债 (底仓)
    # --- Underweight ---
    'TLT': 0.00,
    'TIP': 0.00,
    'DBC': 0.00,
    'GLD': 0.00,
    'SGOV': 0.00
}

# Regime 2: Reflation (Growth Rising, Inflation Rising)
# 策略：股票 + 大宗商品 + 抗通胀债
WEIGHTS_REGIME_2 = {
    'SPY': 0.25,
    'EEM': 0.15,  # 通胀周期新兴市场通常表现较好
    'DBC': 0.25,  # 核心进攻资产：商品
    'TIP': 0.20,  # 抗通胀债
    'IWM': 0.10,  # 周期股
    'GLD': 0.05,  # 辅助抗通胀
    # --- Underweight ---
    'TLT': 0.00,  # 通胀是长债杀手
    'IEF': 0.00,
    'LQD': 0.00,
    'EFA': 0.00,
    'SGOV': 0.00
}

# Regime 3: Stagflation (Growth Falling, Inflation Rising)
# 策略：防守型实物资产 (黄金/商品) + 现金/短债
WEIGHTS_REGIME_3 = {
    'GLD': 0.25,  # 黄金是对抗滞胀的核心
    'DBC': 0.15,  # 商品维持一定仓位
    'TIP': 0.20,  # 实际利率可能走低
    'SGOV': 0.20, # 现金防守
    'IEF': 0.10,  # 中债避险
    'LQD': 0.10,  # 少量高等级信用债
    # --- Underweight ---
    'SPY': 0.00,  # 杀估值 + 杀盈利
    'EFA': 0.00,
    'EEM': 0.00,
    'IWM': 0.00,
    'TLT': 0.00
}

# Regime 4 (Macro): Deflationary Recession (Growth Falling, Inflation Falling)
# 策略：长久期国债 (Duration) 是唯一的神
WEIGHTS_REGIME_4_MACRO = {
    'TLT': 0.50,  # 进攻型长债
    'IEF': 0.30,  # 防守型中债
    'GLD': 0.10,  # 货币对冲
    'LQD': 0.10,  # 投资级债
    # --- Underweight ---
    'SPY': 0.00,
    'EFA': 0.00,
    'EEM': 0.00,
    'IWM': 0.00,
    'DBC': 0.00,
    'TIP': 0.00,
    'SGOV': 0.00
}

# Regime 4 (Panic): Market Circuit Breaker
# 策略：流动性危机模式，只保留现金和超短债
WEIGHTS_REGIME_4_PANIC = {
    'SGOV': 1.00, # 100% 现金/短债 ETF
    # --- Everything Else Sold ---
    'SPY': 0.00, 'EFA': 0.00, 'EEM': 0.00, 'IWM': 0.00,
    'TLT': 0.00, 'IEF': 0.00, 'LQD': 0.00, 'TIP': 0.00,
    'DBC': 0.00, 'GLD': 0.00
}

# ===========================
# 3. 策略映射总表 (Master Map)
# ===========================
# Key: (Regime Code, Source Tag)
# Value: Weight Config
ALLOCATION_LOOKUP = {
    (1, "MACRO_QUADRANT"): WEIGHTS_REGIME_1,
    (2, "MACRO_QUADRANT"): WEIGHTS_REGIME_2,
    (3, "MACRO_QUADRANT"): WEIGHTS_REGIME_3,
    (4, "MACRO_QUADRANT"): WEIGHTS_REGIME_4_MACRO, # 经济衰退 -> 买债
    
    # 无论 Regime 是几，只要来源是 MARKET_CIRCUIT，就是 Panic 模式
    (4, "MARKET_CIRCUIT"): WEIGHTS_REGIME_4_PANIC, # 市场熔断 -> 现金
}

# 默认回退配置 (Fallback)
DEFAULT_WEIGHTS = {asset: 0.0 for asset in ALL_ASSETS}
DEFAULT_WEIGHTS['SGOV'] = 1.0