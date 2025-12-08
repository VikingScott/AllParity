# workflow_backtest_engine.py

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

# 导入两个策略分配器
# V1: 静态查表
from src.strategy_allocation import get_target_weights as get_weights_static
# V2: 风险平价 + 趋势过滤
from src.strategy_allocation_risk_parity import get_target_weights_risk_parity as get_weights_rp

# --- Configuration ---
DATA_DIR = Path("data")
OUTPUT_DIR = Path("outputs")

# 定义要运行的策略清单
STRATEGIES = [
    {
        "name": "static_v1",
        "func": get_weights_static,
        "desc": "Baseline: Static Weights per Regime"
    },
    {
        "name": "risk_parity_v2",
        "func": get_weights_rp,
        "desc": "Advanced: Risk Parity + Trend Filter"
    }
]

def ensure_directories():
    """创建必要的输出文件夹"""
    if not OUTPUT_DIR.exists():
        os.makedirs(OUTPUT_DIR)
        print(f"📁 Created output directory: {OUTPUT_DIR}")

def calculate_strategy_returns(weights_df: pd.DataFrame, asset_returns: pd.DataFrame) -> pd.Series:
    """
    通用回测计算逻辑 (复用)
    """
    # 1. 滞后一期：T日的信号，T+1日的持仓
    lagged_weights = weights_df.shift(1)
    
    # 2. 对齐数据
    common_index = lagged_weights.index.intersection(asset_returns.index)
    w = lagged_weights.loc[common_index]
    r = asset_returns.loc[common_index]
    
    # 3. 确保列名一致
    valid_assets = [c for c in w.columns if c in r.columns]
    w = w[valid_assets]
    r = r[valid_assets]
    
    # 4. 计算组合收益
    return (w * r).sum(axis=1)

def run_engine():
    start_time = datetime.datetime.now()
    print("=" * 60)
    print("🚀 ALL PARITY BACKTEST ENGINE (MULTI-STRATEGY)")
    print("=" * 60)

    # -----------------------------------------------------------
    # Step 1: 加载与对齐数据 (Shared)
    # -----------------------------------------------------------
    print("\n[Step 1] Loading Market Data...")
    try:
        df_market = get_merged_market_state(
            str(DATA_DIR / 'Macro_Daily_Final.csv'), 
            str(DATA_DIR / 'asset_prices.csv')
        )
        print(f"   > Loaded {len(df_market)} rows.")
    except FileNotFoundError as e:
        print(f"   ❌ Error: Data file not found. {e}")
        return

    # 准备资产价格和收益率 (所有策略共用)
    valid_assets = [col for col in ALL_ASSETS if col in df_market.columns]
    asset_prices = df_market[valid_assets]
    asset_returns = asset_prices.pct_change().fillna(0)

    # -----------------------------------------------------------
    # Step 2: 生成宏观信号 (Shared)
    # -----------------------------------------------------------
    print("\n[Step 2] Generating Macro Signals...")
    signal_df = run_signal_pipeline(df_market)
    print("   > Signals generated successfully.")

    # -----------------------------------------------------------
    # Step 3: 多策略循环 (Strategy Loop)
    # -----------------------------------------------------------
    ensure_directories()
    
    for strat in STRATEGIES:
        s_name = strat['name']
        s_func = strat['func']
        print(f"\n👉 Running Strategy: {s_name.upper()}")
        print(f"   ({strat['desc']})")
        
        # --- A. 权重分配 (Allocation) ---
        # 智能参数适配：检查函数是否需要 price_df
        # V1 只需要 signal_df，V2 需要 signal_df + price_df
        sig = inspect.signature(s_func)
        if 'price_df' in sig.parameters:
            print(f"   > Calculating weights (Dynamic Mode)...")
            weights_df = s_func(signal_df, asset_prices)
        else:
            print(f"   > Calculating weights (Static Mode)...")
            weights_df = s_func(signal_df)
            
        weights_df = weights_df.fillna(0.0)
        
        # --- B. 绩效计算 (Performance) ---
        portfolio_daily_ret = calculate_strategy_returns(weights_df, asset_returns)
        equity_curve = (1 + portfolio_daily_ret).cumprod()
        
        # 计算回撤
        running_max = equity_curve.cummax()
        drawdown = (equity_curve - running_max) / running_max
        
        # --- C. 结果打包 (Pack Results) ---
        export_df = pd.DataFrame({
            'Portfolio_Daily_Ret': portfolio_daily_ret,
            'Equity_Curve': equity_curve,
            'Drawdown': drawdown
        }, index=signal_df.index)
        
        # 合并信号
        signal_cols = ['Regime', 'Regime_Source', 'Trend_Growth', 'Trend_Inflation_Blended', 'Market_Stress_Score']
        export_df = export_df.join(signal_df[signal_cols], how='left')
        
        # 合并权重
        export_df = export_df.join(weights_df.add_prefix('W_'), how='left')
        
        # 合并基准 (SPY/TLT)
        if 'SPY' in asset_returns.columns:
            export_df['Benchmark_SPY'] = (1 + asset_returns['SPY']).cumprod()
        if 'TLT' in asset_returns.columns:
            export_df['Benchmark_TLT'] = (1 + asset_returns['TLT']).cumprod()

        # --- D. 保存 (Save) ---
        filename = OUTPUT_DIR / f"backtest_results_{s_name}.csv"
        export_df.to_csv(filename)
        
        # 打印简报
        total_ret = equity_curve.iloc[-1] - 1
        mdd = drawdown.min()
        print(f"   ✅ Saved to: {filename.name}")
        print(f"   📊 Return: {total_ret:.2%} | MaxDD: {mdd:.2%}")

    # -----------------------------------------------------------
    # Done
    # -----------------------------------------------------------
    end_time = datetime.datetime.now()
    duration = (end_time - start_time).total_seconds()
    print("\n" + "=" * 60)
    print(f"🏁 ALL STRATEGIES COMPLETED in {duration:.2f}s")
    print("=" * 60)

if __name__ == "__main__":
    run_engine()