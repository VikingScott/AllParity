"""
================================================================================
🎛️ STRATEGY CONFIGURATION & SCENARIOS
================================================================================
这里是你的“实验设计台”。
定义基准，定义策略，定义参数。
"""

import sys
from pathlib import Path
# 确保能引用 src
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.strategy.simple_ma import SimpleMAStrategy
from src.strategy.buy_hold import BuyHoldStrategy
from src.backtester.config import BacktestConfig

# ============================================================
# 1. 基准定义 (Benchmark)
# ============================================================
BENCHMARK_SETUP = {
    "name": "Benchmark_6040",
    "strategy": BuyHoldStrategy({'SPY': 0.6, 'IEF': 0.4}),
    "config": BacktestConfig(transaction_cost=0.0, rebalance_freq='1M')
}

# ============================================================
# 2. 实验场景池 (Scenarios)
# ============================================================
SCENARIOS = [
    {
        "name": "Trend_MA200_LowCost",
        "strategy": SimpleMAStrategy(['SPY', 'TLT', 'GLD'], signals_df=None), # signals_df 会在 Runner 里动态注入
        "config": BacktestConfig(
            transaction_cost=0.0005, 
            rebalance_freq='Signal'
        )
    },
    {
        "name": "Trend_MA200_HighFriction",
        "strategy": SimpleMAStrategy(['SPY', 'TLT', 'GLD'], signals_df=None),
        "config": BacktestConfig(
            transaction_cost=0.0020, 
            rebalance_freq='1D' # 故意每天调仓看损耗
        )
    },
    {
        "name": "Tech_Smart_Drift",
        "strategy": SimpleMAStrategy(['QQQ', 'SMH'], signals_df=None),
        "config": BacktestConfig(
            transaction_cost=0.0005,
            rebalance_freq='Drift_0.05'
        )
    }
]