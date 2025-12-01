"""
================================================================================
📜 DESIGN REQUIREMENTS: BACKTEST CONFIGURATION
================================================================================
1. [Cost Model] Transaction Cost:
   - Covers commission + slippage + bid/ask spread.
   - Defined as a flat rate (e.g., 0.0005 = 5bps) applied to turnover value.

2. [Execution] Rebalancing Frequency:
   - Time-based: '1D', '1W', '1M', '3M', '6M', '12M'.
   - Event-based: 'Signal' (Strategy dictates).
   - Drift-based: 'Drift_5%' (Rebalance only if weight deviates > 5%).
================================================================================
"""
from dataclasses import dataclass

@dataclass
class BacktestConfig:
    """
    回测环境配置类
    """
    
    # 交易成本 (Transaction Cost)
    # 例如: 0.0005 = 5bps (万分之五)
    transaction_cost: float = 0.0005
    
    # 调仓频率 (Rebalancing Frequency)
    # ------------------------------------------------------------
    # A. 基于时间 (Time-based):
    #    '1D'  : Daily
    #    '1W'  : Weekly (End of week)
    #    '1M'  : Monthly (End of month)
    #    '3M'  : Quarterly
    #    '6M'  : Semi-Annually
    #    '12M' : Annually
    #
    # B. 基于信号 (Event-based):
    #    'Signal': 仅当策略返回的目标权重发生实质变化时调仓 (适合趋势策略)
    #
    # C. 基于漂移 (Drift-based):
    #    'Drift_0.05': 当任意资产的实际权重与目标权重偏差超过 5% 时调仓
    # ------------------------------------------------------------
    rebalance_freq: str = 'Signal'