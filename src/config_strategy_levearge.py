"""
Retail Leverage Config (V1)

目标：
为“可杠杆 Risk Parity / Target Vol”提供清晰、不会互相打架的配置边界。
本文件只定义规则，不实现优化。

核心理念：
1) 杠杆体现为“允许权重总和 > 1”，而不是在引擎里二次乘。
2) 正常体制不让现金参与 RP 优化。
3) Regime 4 熔断为 Hard Override：直接给定权重且禁止杠杆缩放。
4) 融资成本用 gross exposure 模型显式扣费，不依赖现金列收益。
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List

# ------------------------------------------------------------
# 0. 资产池（尽量复用你已有 tickers）
# ------------------------------------------------------------
# 如果你希望完全复用已有 config，可以改为：
# from src.config_strategy_v1 import ALL_ASSETS
# 这里写死一份更独立，更不易互相污染。

ASSETS_EQUITY = ["SPY", "EFA", "EEM", "IWM"]
ASSETS_BOND   = ["TLT", "IEF", "LQD", "TIP"]
ASSETS_COMM   = ["DBC", "GLD"]
ASSETS_CASH   = ["SGOV"]  # 只用于熔断/防御，不参与正常 RP

ALL_ASSETS = ASSETS_EQUITY + ASSETS_BOND + ASSETS_COMM + ASSETS_CASH

# ------------------------------------------------------------
# 1. 杠杆版 Risk Parity 的 “核心优化宇宙”
#    ✅ 排除现金
# ------------------------------------------------------------
RP_CORE_ASSETS: List[str] = (
    ASSETS_EQUITY
    + ASSETS_BOND
    + ASSETS_COMM
)

# 你可以更保守一些（只用 5 大经典）：
RP_CLASSIC_5 = [a for a in ["SPY", "TLT", "IEF", "GLD", "DBC"] if a in RP_CORE_ASSETS]


# ------------------------------------------------------------
# 2. Regime 4 熔断 Hard Override
#    ✅ 禁止杠杆缩放
# ------------------------------------------------------------
REGIME_4_WEIGHTS: Dict[str, float] = {
    "SGOV": 0.70,
    "GLD": 0.30,
}

# ------------------------------------------------------------
# 3. 再平衡与 Deadband（给引擎用）
# ------------------------------------------------------------
REBALANCE_FREQ = "ME"  # Month End (避免 pandas 的 'M' FutureWarning)
DEADBAND_THRESHOLD_ABS = 0.02  # 绝对权重偏离阈值（±2%）

# 额外可选：相对阈值（如果你以后想做更细的 deadband）
DEADBAND_THRESHOLD_REL = None  # 例如 0.10 表示 10% 相对偏离


# ------------------------------------------------------------
# 4. 杠杆/目标波动率配置
# ------------------------------------------------------------
# 这是 “杠杆版核心逻辑” 的总开关
ENABLE_LEVERAGE = True

# 目标波动率（年化）
TARGET_VOL_ANN = 0.10  # 10%

# 波动率估计窗口
VOL_WINDOW_DAYS = 252
VOL_FLOOR_ANN = 0.03   # 避免除以极小 vol 导致杠杆爆炸
VOL_CAP_ANN   = 0.30   # 上限保护（可选）

# 杠杆上限
LEVERAGE_CAP = 2.0     # 对散户更现实
LEVERAGE_FLOOR = 0.0

# ✅ 关键原则：
# allocation 层如果输出了“已杠杆权重”，引擎不要再乘 leverage
# 这条规则你之后会在 allocation 文件里显式遵守。


# ------------------------------------------------------------
# 5. 融资成本模型（引擎用）
# ------------------------------------------------------------
# 方式：borrow = max(gross_exposure - 1, 0)
# 其中 gross_exposure = sum(abs(weights))
#
# 你可以选择：
# A) 固定年化融资利率
# B) 用宏观/短端利率序列（以后再接）
#
# 这里先给 A)

USE_FIXED_FINANCING_RATE = True
FINANCING_RATE_ANN = 0.00  # 8% 年化，先保守设个常数

# 如果未来你要切换成数据序列（比如用 FRED TB3MS / DGS3MO），
# 在 allocation/engine 中读取这个开关即可：
FINANCING_RATE_SERIES_COL = None  # e.g. "RF_3M"


# ------------------------------------------------------------
# 6. 输出/调试保护
# ------------------------------------------------------------
ENABLE_GUARDRAILS = True

# 如果 gross_exposure 超过这个数字，建议直接 raise 或强制 clip
GROSS_EXPOSURE_HARD_CAP = 3.0

# 防止 1 + daily_ret <= 0 的灾难性日
# 引擎可使用：
# levered_ret = levered_ret.clip(lower=MAX_SINGLE_DAY_LOSS)
MAX_SINGLE_DAY_LOSS = -0.95


# ------------------------------------------------------------
# 7. 用于“RP 直觉对照”的基准定义（可给 dashboard/analysis 使用）
# ------------------------------------------------------------
BENCH_RP_CORE_PREF = ["SPY", "TLT", "IEF", "GLD", "DBC"]
BENCH_ALLOW_60_40 = True
BENCH_ALLOW_EW_CORE = True


# ------------------------------------------------------------
# 8. 可选：把参数封装成 dataclass（更利于后续扩展）
# ------------------------------------------------------------
@dataclass(frozen=True)
class LeveragePolicy:
    enable: bool = ENABLE_LEVERAGE
    target_vol_ann: float = TARGET_VOL_ANN
    vol_window_days: int = VOL_WINDOW_DAYS
    vol_floor_ann: float = VOL_FLOOR_ANN
    leverage_cap: float = LEVERAGE_CAP
    leverage_floor: float = LEVERAGE_FLOOR

@dataclass(frozen=True)
class FinancingPolicy:
    use_fixed_rate: bool = USE_FIXED_FINANCING_RATE
    rate_ann: float = FINANCING_RATE_ANN
    series_col: str | None = FINANCING_RATE_SERIES_COL

@dataclass(frozen=True)
class RebalancePolicy:
    freq: str = REBALANCE_FREQ
    deadband_abs: float = DEADBAND_THRESHOLD_ABS
    deadband_rel: float | None = DEADBAND_THRESHOLD_REL