# src/config_regime.py

"""
全天候策略 - 宏观体制划分配置
"""

# ===========================
# 1. 趋势定义参数 (Trend Definitions)
# ===========================
# 用于计算 Macro 数据的 "Current vs Trend"
# 窗口期建议：90天 (约一个季度) 或 126天 (半年)
MACRO_TREND_WINDOW = 90

# ===========================
# 2. 通胀合成参数 (Inflation Blending)
# ===========================
# 逻辑：S_pi = w_core * Core + w_head * Head
INFLATION_WEIGHTS = {
    "core": 0.7,      # 核心PCE/CPI权重 (锚)
    "headline": 0.3   # 名义PCE/CPI权重 (风筝)
}

# ===========================
# 3. 市场信号否决阈值 (Market Veto Thresholds)
# ===========================
# 只有当市场信号恶化到一定程度时，才触发"降级/否决"

# VIX 恐慌阈值
# 长期均值约 19-20。超过 25 通常代表市场进入压力状态。
THRESHOLD_VIX_PANIC = 25.0

# 信用利差 (Signal_Risk) 警戒线
# 历史均值约 2.0。超过 2.5 通常代表信贷紧缩。
THRESHOLD_CREDIT_STRESS = 2.5

# 收益率曲线 (Signal_YieldCurve) 倒挂
# 小于 0 即为倒挂，预示衰退。
THRESHOLD_CURVE_INVERT = 0.0

# ===========================
# 4. 体制映射表 (Regime Mapping)
# ===========================
# 1: Goldilocks (Growth+, Inflation-)
# 2: Reflation/Overheat (Growth+, Inflation+)
# 3: Stagflation (Growth-, Inflation+)
# 4: Deflation/Recession (Growth-, Inflation-)
REGIME_CODE_MAP = {
    (1, -1): 1,  # G+, I-
    (1, 1):  2,  # G+, I+
    (-1, 1): 3,  # G-, I+
    (-1, -1): 4  # G-, I-
}
# src/config_regime.py

# ... (保留之前的 MACRO_TREND_WINDOW 等配置) ...

# ===========================
# 5. 数据列名映射 (Column Mapping)
# ===========================
# Key: 代码中使用的逻辑名称
# Value: CSV/DataFrame 中的实际列名
COLUMN_MAP = {
    "growth": "Macro_Growth",
    "inflation_core": "Macro_Inflation_Core",
    "inflation_head": "Macro_Inflation_Head",
    
    # 这里修正你的报错：
    "yield_curve": "Signal_Curve_T10Y2Y",         # 原代码用的是 'Signal_YieldCurve'
    "credit_risk": "Signal_Risk_DBAA_Minus_DGS10", # 原代码用的是 'Signal_Risk'
    "vix": "Signal_Vol_VIX"                        # 原代码用的是 'Signal_VIX'
}

# ===========================
# 6. 逻辑修正参数 (Logic Overrides)
# ===========================

# 粘性通胀阈值 (Sticky Inflation Floor)
# 如果核心通胀绝对值高于此值，即使趋势向下，也强制视为通胀环境。
# 3.0% 是美联储目标(2%)的1.5倍，是一个合理的警戒线。
THRESHOLD_INFLATION_STICKY = 3.0

# 市场熔断阈值 (Market Panic Floor)
# 如果 Market Score 低于此值，无视所有宏观信号，直接转入防守 (Regime 4)。
THRESHOLD_MARKET_PANIC = -2