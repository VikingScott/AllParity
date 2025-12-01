"""
================================================================================
📜 DESIGN REQUIREMENTS
================================================================================
1. [Interaction]: Auto-detect common date range.
2. [Simulation]: Inject transaction costs & rebalancing frequency via Config.
3. [Reporting]: 
   - Dynamic Folder Naming (based on strategies).
   - Terminal Summary Table (CAGR, Sharpe, Vol, MaxDD).
   - CSV Outputs: Annual, Monthly, Rolling, AND Daily Matrix.
================================================================================
"""

import warnings
# [关键] 全局静音：屏蔽 FutureWarning (fillna, downcasting)
warnings.simplefilter(action='ignore', category=FutureWarning)
warnings.simplefilter(action='ignore', category=UserWarning)

import sys
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime

# Path Hack
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.core.data import DataLoader
from src.strategy.simple_ma import SimpleMAStrategy
from src.backtester.engine import BacktestEngine
from src.backtester.config import BacktestConfig
from src.analysis.metrics import PerformanceMetrics
from src.analysis.rolling import RollingAnalyzer 
from src.analysis.reporting import ReportGenerator

# ============================================================
# 1. 🔬 RESEARCH CONFIGURATION (在此处修改配置)
# ============================================================

SCENARIOS = [
    {
        "name": "MA200_LowCost",
        "strategy": SimpleMAStrategy(['SPY', 'TLT', 'GLD']),
        "config": BacktestConfig(
            transaction_cost=0.0005, 
            rebalance_freq='Signal'
        )
    },
    {
        "name": "MA200_HighCost",
        "strategy": SimpleMAStrategy(['SPY', 'TLT', 'GLD']),
        "config": BacktestConfig(
            transaction_cost=0.0020, # 20bps
            rebalance_freq='1D'      # 每日强平
        )
    },
    {
        "name": "Tech_Drift",
        "strategy": SimpleMAStrategy(['QQQ', 'SMH']),
        "config": BacktestConfig(
            transaction_cost=0.0005,
            rebalance_freq='Drift_0.05'
        )
    }
]

CUSTOM_START_DATE = "2005-01-01" 
CUSTOM_END_DATE = None 

# ============================================================
# 2. HELPER FUNCTIONS
# ============================================================

def get_valid_date_range(strategies):
    print("🔍 Scanning Data Availability...")
    all_tickers = set(['SPY', 'AGG', 'IEF']) 
    for s in strategies:
        all_tickers.update(s.tickers)
    
    try:
        full_data = DataLoader.load_returns()
    except Exception as e:
        print(f"❌ Error loading data: {e}")
        return None, None

    existing_tickers = [t for t in all_tickers if t in full_data.columns]
    if not existing_tickers:
        print("❌ Critical: No tickers found in dataset!")
        return None, None
        
    subset = full_data[existing_tickers].dropna()
    if subset.empty:
        print("❌ No overlapping data found.")
        return None, None
        
    min_date = subset.index[0].date()
    max_date = subset.index[-1].date()
    
    print(f"🔗 Max Common Range: {min_date} to {max_date}")
    return str(min_date), str(max_date)

def print_terminal_summary(results, bench_rets):
    """
    [新增需求 1] 在终端打印漂亮的汇总表
    """
    print("\n" + "="*65)
    print("📊 FINAL PERFORMANCE SUMMARY")
    print("="*65)
    
    summary_data = []
    
    # 1. Add Benchmark
    m_b = PerformanceMetrics(bench_rets)
    summary_data.append({
        "Strategy": "Benchmark (60/40)",
        "CAGR": f"{m_b.cagr():.2%}",
        "Sharpe": f"{m_b.sharpe():.2f}",
        "Vol": f"{m_b.volatility():.2%}",
        "MaxDD": f"{m_b.max_drawdown():.2%}",
        "Final($1k)": f"${m_b.final_value(1000):,.0f}"
    })
    
    # 2. Add Strategies
    for name, rets in results.items():
        m_s = PerformanceMetrics(rets)
        summary_data.append({
            "Strategy": name,
            "CAGR": f"{m_s.cagr():.2%}",
            "Sharpe": f"{m_s.sharpe():.2f}",
            "Vol": f"{m_s.volatility():.2%}",
            "MaxDD": f"{m_s.max_drawdown():.2%}",
            "Final($1k)": f"${m_s.final_value(1000):,.0f}"
        })
        
    df = pd.DataFrame(summary_data)
    # 设置打印格式，不省略列
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 1000)
    # 左对齐 Strategy 列
    print(df.to_string(index=False, justify='left'))
    print("="*65 + "\n")

# ============================================================
# 3. MAIN EXECUTION
# ============================================================

def main():
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # [新增需求 2] 智能文件夹命名
    # 提取策略名，用下划线连接，太长就截断
    strat_names = [s['name'] for s in SCENARIOS]
    name_str = "_".join(strat_names)
    if len(name_str) > 50: name_str = name_str[:50] + "..."
    
    folder_name = f"batch_{timestamp}_{name_str}"
    report_dir = Path(__file__).resolve().parent.parent / "reports" / "data" / folder_name
    report_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"🚀 RESEARCH RUNNER")
    print(f"📂 Output Dir: {folder_name}")
    
    # 1. Timeframe
    all_strats_obj = [s['strategy'] for s in SCENARIOS]
    auto_start, auto_end = get_valid_date_range(all_strats_obj)
    if not auto_start: return

    start_date = CUSTOM_START_DATE if CUSTOM_START_DATE else auto_start
    end_date = CUSTOM_END_DATE if CUSTOM_END_DATE else auto_end
    
    print(f"📅 Range: {start_date} to {end_date}")

    # 2. Init Engine
    engine = BacktestEngine(start_date, end_date)
    
    # 3. Benchmark
    bench_rets = engine.run_benchmark_6040()
    if bench_rets.empty: return

    # 4. Run Scenarios
    results = {}
    for sc in SCENARIOS:
        name = sc['name']
        strat = sc['strategy']
        cfg = sc['config']
        
        rets = engine.run_strategy(strat, name=name, config=cfg)
        
        # 简单有效性检查
        if not rets.empty and rets.std() > 0:
            common = rets.index.intersection(bench_rets.index)
            results[name] = rets.loc[common]

    if not results:
        print("❌ No valid results.")
        return

    # Align Bench
    primary_idx = results[list(results.keys())[0]].index
    bench_rets = bench_rets.loc[primary_idx]

    # 5. Generate Reports (Delegated to ReportGenerator)
    # 这里我们只保留最复杂的 Annual/Rolling CSV 生成
    reporter = ReportGenerator(report_dir)
    reporter.save_all(results, bench_rets)
    
    # [新增需求 3] Daily Returns Matrix
    # 这是一个非常有用的原始数据文件
    print("📝 Saving Daily Returns Matrix...")
    daily_dfs = [bench_rets.rename("Benchmark")]
    for name, rets in results.items():
        daily_dfs.append(rets.rename(name))
    
    df_daily = pd.concat(daily_dfs, axis=1)
    df_daily.to_csv(report_dir / "daily_returns_matrix.csv")
    print("✅ Saved daily_returns_matrix.csv")

    # [新增需求 1] Terminal Summary
    print_terminal_summary(results, bench_rets)

    print(f"🎉 Done. Reports in: {report_dir}")

if __name__ == "__main__":
    main()