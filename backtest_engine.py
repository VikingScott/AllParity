import pandas as pd
import numpy as np
import os
from pathlib import Path

# --- Import Internal Modules ---
from src.data_loader import get_merged_market_state
from src.macro_regime_signal_generator import run_signal_pipeline
from src.strategy_allocation import get_target_weights, calculate_strategy_returns
from src.config_strategy_v1 import ALL_ASSETS

# --- Configuration ---
DATA_DIR = Path("data")
OUTPUT_DIR = Path("outputs")
OUTPUT_FILE = OUTPUT_DIR / "backtest_results.csv"

def ensure_output_dir():
    """Ensure the output directory exists."""
    if not OUTPUT_DIR.exists():
        os.makedirs(OUTPUT_DIR)
        print(f"Created output directory: {OUTPUT_DIR}")

def run_backtest_engine():
    print("=" * 60)
    print("🚀 STARTING BACKTEST ENGINE (V2)")
    print("=" * 60)

    # -----------------------------------------------------------
    # 1. Data Loading & Cleaning
    # -----------------------------------------------------------
    print("\n[Step 1] Loading and aligning market data...")
    # 这里的 df_market 包含了 Asset Prices (如 SPY, TLT) 和 Macro Data
    df_market = get_merged_market_state(
        str(DATA_DIR / 'Macro_Daily_Final.csv'), 
        str(DATA_DIR / 'asset_prices.csv')
    )
    print(f"   > Loaded {len(df_market)} rows of aligned data.")
    print(f"   > Date Range: {df_market.index.min().date()} to {df_market.index.max().date()}")

    # -----------------------------------------------------------
    # 2. Signal Generation (The "Brain")
    # -----------------------------------------------------------
    print("\n[Step 2] Generating Macro Regimes (Signal Layer)...")
    # 调用 V2 逻辑 (含 Robust Growth, Sticky Inflation, Market Veto)
    signal_df = run_signal_pipeline(df_market)
    
    # 检查信号完整性
    if 'Regime' not in signal_df.columns:
        raise ValueError("Critical Error: 'Regime' column missing from signal output!")
    print("   > Signals generated successfully.")

    # -----------------------------------------------------------
    # 3. Strategy Allocation (The "Commander")
    # -----------------------------------------------------------
    print("\n[Step 3] Allocating Asset Weights (Strategy Layer)...")
    # 根据 Regime 查表，决定买什么
    weights_df = get_target_weights(signal_df)
    print("   > Target weights calculated.")

    # -----------------------------------------------------------
    # 4. Performance Calculation (The "Accountant")
    # -----------------------------------------------------------
    print("\n[Step 4] Calculating Portfolio Performance...")
    
    # A. 准备资产收益率
    # 我们直接从对齐后的 df_market 中提取资产价格列，并计算日收益率
    # 这样能保证收益率的 Index 与 信号的 Index 完美匹配
    # 过滤掉不在我们配置表(ALL_ASSETS)里的杂项列
    valid_assets = [col for col in ALL_ASSETS if col in df_market.columns]
    missing_assets = set(ALL_ASSETS) - set(valid_assets)
    if missing_assets:
        print(f"   ⚠️ Warning: The following config assets are missing in data: {missing_assets}")
    
    asset_prices = df_market[valid_assets]
    asset_returns = asset_prices.pct_change().fillna(0)
    
    # B. 计算组合收益 (含滞后处理)
    # 逻辑：T日的信号 -> T+1日的持仓 -> T+1日的收益
    # calculate_strategy_returns 内部已经做了 shift(1)
    portfolio_daily_ret = calculate_strategy_returns(weights_df, asset_returns)
    
    # C. 计算净值曲线 (Equity Curve)
    # 设初始净值为 1.0
    equity_curve = (1 + portfolio_daily_ret).cumprod()
    
    # D. 计算回撤 (Drawdown) - 方便后续画图
    running_max = equity_curve.cummax()
    drawdown = (equity_curve - running_max) / running_max

    # -----------------------------------------------------------
    # 5. Data Consolidation & Export
    # -----------------------------------------------------------
    print("\n[Step 5] Consolidating and Exporting Results...")
    
    # 我们要把所有重要数据拼成一张大宽表 (Big Wide Table)
    # 1. 核心表现
    export_df = pd.DataFrame({
        'Portfolio_Daily_Ret': portfolio_daily_ret,
        'Equity_Curve': equity_curve,
        'Drawdown': drawdown
    }, index=signal_df.index)
    
    # 2. 信号数据 (Regime, Trends, Scores)
    # 排除掉用来 debug 的中间列，只留核心
    signal_cols = [
        'Regime', 'Regime_Source', 
        'Trend_Growth', 'Trend_Inflation_Blended', 
        'Market_Stress_Score'
    ]
    # 如果有原始 VIX 等数据，也带上
    raw_cols = ['Signal_Vol_VIX', 'Signal_Risk_DBAA_Minus_DGS10', 'Signal_Curve_T10Y2Y']
    cols_to_merge = signal_cols + [c for c in raw_cols if c in signal_df.columns]
    
    export_df = export_df.join(signal_df[cols_to_merge], how='left')
    
    # 3. 权重数据 (带前缀 W_ 以便区分)
    weights_with_prefix = weights_df.add_prefix('W_')
    export_df = export_df.join(weights_with_prefix, how='left')
    
    # 4. 资产原始净值 (可选，用于对比基准)
    # 比如我们也把 SPY 的净值放进去，方便后续画 Relative Strength
    if 'SPY' in asset_returns.columns:
        export_df['Benchmark_SPY'] = (1 + asset_returns['SPY']).cumprod()
    if 'TLT' in asset_returns.columns:
        export_df['Benchmark_TLT'] = (1 + asset_returns['TLT']).cumprod()

    # 5. 保存
    ensure_output_dir()
    export_df.to_csv(OUTPUT_FILE)
    
    print(f"   ✅ SUCCESS! Backtest results saved to: {OUTPUT_FILE}")
    print(f"   > Columns: {len(export_df.columns)}")
    print(f"   > Rows:    {len(export_df)}")
    
    # 简单打印最终结果
    final_return = equity_curve.iloc[-1] - 1
    print(f"\n📊 Quick Stats:")
    print(f"   > Total Return: {final_return:.2%}")
    print(f"   > Max Drawdown: {drawdown.min():.2%}")

if __name__ == "__main__":
    try:
        run_backtest_engine()
    except Exception as e:
        print(f"\n❌ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()