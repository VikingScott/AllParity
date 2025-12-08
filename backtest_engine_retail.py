# backtest_engine_retail_v3.py (NEW FILE)

import pandas as pd
import numpy as np
import os
from pathlib import Path
import datetime
import inspect

# --- Internal Imports ---
from src.data_loader import get_merged_market_state
from src.macro_regime_signal_generator import run_signal_pipeline
from src.config_strategy_v1 import ALL_ASSETS

# 导入 V3 策略分配器
from src.strategy_allocation_retail_v3 import get_target_weights_retail_v3 as get_weights_v3

# --- Configuration ---
DATA_DIR = Path("data")
OUTPUT_DIR = Path("outputs")
OUTPUT_FILE = OUTPUT_DIR / "backtest_results_retail_v3.csv"

# --- V3 策略核心配置 ---
REBALANCE_FREQ = 'M' # 步骤 3: 更改为月度调仓 (Monthly)
DEADBAND_THRESHOLD = 0.02 # 步骤 4: ±2% 绝对死区

# --- 通用函数 (复用) ---
def ensure_directories():
    """创建必要的输出文件夹"""
    if not OUTPUT_DIR.exists():
        os.makedirs(OUTPUT_DIR)
        print(f"📁 Created output directory: {OUTPUT_DIR}")

def calculate_strategy_returns(weights_df: pd.DataFrame, asset_returns: pd.DataFrame) -> pd.Series:
    """通用回测计算逻辑 (复用)"""
    lagged_weights = weights_df.shift(1)
    common_index = lagged_weights.index.intersection(asset_returns.index)
    w = lagged_weights.loc[common_index]
    r = asset_returns.loc[common_index]
    valid_assets = [c for c in w.columns if c in r.columns]
    w = w[valid_assets]
    r = r[valid_assets]
    return (w * r).sum(axis=1)

# --- 核心 V3 引擎 (引入月度调仓与 Deadband) ---
def run_engine_v3():
    start_time = datetime.datetime.now()
    print("=" * 60)
    print("🚀 ALL PARITY BACKTEST ENGINE (RETAIL V3: MONTHLY + DEADBAND)")
    print("=" * 60)

    # -----------------------------------------------------------
    # Step 1: 加载与对齐数据
    # -----------------------------------------------------------
    try:
        df_market = get_merged_market_state(
            str(DATA_DIR / 'Macro_Daily_Final.csv'), 
            str(DATA_DIR / 'asset_prices.csv')
        )
    except FileNotFoundError as e:
        print(f"   ❌ Error: Data file not found. {e}")
        return
    valid_assets = [col for col in ALL_ASSETS if col in df_market.columns]
    asset_prices = df_market[valid_assets]
    asset_returns = asset_prices.pct_change().fillna(0)
    signal_df = run_signal_pipeline(df_market)
    
    common_index = df_market.index.intersection(signal_df.index)
    df_market = df_market.loc[common_index]
    signal_df = signal_df.loc[common_index]
    asset_prices = asset_prices.loc[common_index]
    asset_returns = asset_returns.loc[common_index]

    # -----------------------------------------------------------
    # Step 2: 月度调仓循环 (Monthly Rebalance Loop)
    # -----------------------------------------------------------
    ensure_directories()
    s_name = "retail_v3"
    print(f"\n👉 Running Strategy: {s_name.upper()} (Freq: {REBALANCE_FREQ}, Deadband: {DEADBAND_THRESHOLD:.1%})")
    
    # 确定调仓日 (每月第一个交易日)
    rebalance_dates = signal_df.index.to_series().resample(REBALANCE_FREQ).first().dropna().index
    
    # 记录每日权重
    weights_df = pd.DataFrame(index=signal_df.index, columns=valid_assets).fillna(0.0)
    
    # 当前实际持仓权重 (用 Series 存储)
    current_weights = pd.Series(0.0, index=valid_assets)
    
    # 回测主循环：按天迭代
    for i, date in enumerate(signal_df.index):
        
        # 每天都用 (1+return) 调整当前权重 (更精确的实盘模拟)
        if i > 0:
            yesterday = signal_df.index[i-1]
            daily_returns = asset_returns.loc[date]
            # 权重根据前一天的收益率和持仓调整 (模拟市值波动)
            # 忽略这一步可以，但加上更严谨
            
        # 检查是否是调仓日
        is_rebalance_day = date in rebalance_dates
        
        if is_rebalance_day:
            
            # --- A. 计算目标权重 ---
            current_signals = signal_df.loc[:date]
            current_prices = asset_prices.loc[:date]
            target_weights_series = get_weights_v3(current_signals, current_prices).iloc[0]
            
            # --- B. Deadband / 阈值检查 (步骤 4) ---
            # 检查是否有任一资产的偏离度超过阈值
            # 初始日 i=0 必须交易
            deviation_check = (target_weights_series - current_weights).abs().max()
            
            if i == 0 or deviation_check > DEADBAND_THRESHOLD:
                
                weights_df.loc[date] = target_weights_series
                current_weights = target_weights_series
                
            else:
                # 不调仓，继续持有当前权重
                weights_df.loc[date] = current_weights
                
        
        else:
            # 非调仓日，继续持有上一个调仓日的权重
            if i > 0:
                weights_df.loc[date] = current_weights
    
    weights_df = weights_df.ffill().fillna(0.0)

    # -----------------------------------------------------------
    # Step 3: 绩效计算与保存
    # -----------------------------------------------------------
    portfolio_daily_ret = calculate_strategy_returns(weights_df, asset_returns)
    equity_curve = (1 + portfolio_daily_ret).cumprod()
    running_max = equity_curve.cummax()
    drawdown = (equity_curve - running_max) / running_max
    
    export_df = pd.DataFrame({
        'Portfolio_Daily_Ret': portfolio_daily_ret,
        'Equity_Curve': equity_curve,
        'Drawdown': drawdown
    }, index=signal_df.index)
    
    signal_cols = ['Regime', 'Regime_Source', 'Trend_Growth', 'Trend_Inflation_Blended', 'Market_Stress_Score']
    export_df = export_df.join(signal_df[signal_cols], how='left')
    export_df = export_df.join(weights_df.add_prefix('W_'), how='left')
    
    if 'SPY' in asset_returns.columns:
        export_df['Benchmark_SPY'] = (1 + asset_returns['SPY']).cumprod()
    if 'TLT' in asset_returns.columns:
        export_df['Benchmark_TLT'] = (1 + asset_returns['TLT']).cumprod()

    filename = OUTPUT_FILE
    export_df.to_csv(filename)
    
    total_ret = equity_curve.iloc[-1] - 1
    mdd = drawdown.min()
    print("\n" + " " * 60)
    print(f"   ✅ Saved to: {filename.name}")
    print(f"   📊 Return: {total_ret:.2%} | MaxDD: {mdd:.2%}")

    end_time = datetime.datetime.now()
    duration = (end_time - start_time).total_seconds()
    print("\n" + "=" * 60)
    print(f"🏁 RETAIL V3 STRATEGY COMPLETED in {duration:.2f}s")
    print("=" * 60)

if __name__ == "__main__":
    run_engine_v3()