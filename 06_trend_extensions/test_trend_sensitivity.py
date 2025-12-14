# 07_trend_following/test_trend_sensitivity.py

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
import sys

# 引入 Logic 以便重新计算
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
TARGET_DIR_03 = os.path.join(PROJECT_ROOT, '03_1_strategy_construction')
if TARGET_DIR_03 not in sys.path: sys.path.append(TARGET_DIR_03)

from strategy_logic import StrategyLogic
from strategy_config import StrategyConfig

OUTPUT_DIR = os.path.join(PROJECT_ROOT, 'data', 'processed')
PLOT_DIR = os.path.join(PROJECT_ROOT, 'outputs', 'plots', '07_trend_following')

def run_sensitivity_test():
    print("🚀 [Trend Test] Parameter Sensitivity (MA Window)...")
    
    # 1. 准备数据
    df_all = pd.read_csv(os.path.join(OUTPUT_DIR, 'data_final_returns.csv'), index_col=0, parse_dates=True)
    df_rp_xr = df_all[StrategyConfig.ASSETS_RP_XR]
    rf = df_all['Risk_Free']
    df_rp_tr = df_rp_xr.add(rf, axis=0) # 用于算信号
    
    # 准备 Baseline (Naive) 权重和杠杆 (只算一次)
    vol_assets = StrategyLogic.calculate_rolling_vol(df_rp_xr, StrategyConfig.VOL_LOOKBACK)
    w_naive = StrategyLogic.calculate_inverse_vol_weights(vol_assets)
    
    # 目标 Vol (用于算杠杆)
    stock_tr = df_all[StrategyConfig.ASSET_6040_STOCK_TR]
    bond_tr = df_all[StrategyConfig.ASSET_6040_BOND_TR]
    bench_6040_tr = 0.60 * stock_tr + 0.40 * bond_tr
    vol_target = StrategyLogic.calculate_rolling_vol(bench_6040_tr, StrategyConfig.VOL_LOOKBACK)
    
    vol_naive_est = StrategyLogic.calculate_portfolio_ex_ante_vol_covariance(w_naive, df_rp_xr, StrategyConfig.VOL_LOOKBACK)
    lev_naive = StrategyLogic.calculate_leverage_ratio_match_market(vol_naive_est, vol_target, max_cap=StrategyConfig.MAX_LEVERAGE_RETAIL)

    # 2. 定义测试参数 (MA 窗口)
    windows = [6, 8, 10, 12, 15, 18, 24]
    results = []
    
    print(f"   Testing windows: {windows}")
    
    for w in windows:
        # A. 计算信号 (Raw)
        sig_raw = StrategyLogic.calculate_trend_signal(df_rp_tr, window=w)
        
        # B. 过滤权重
        w_trend = StrategyLogic.apply_trend_filter(w_naive, sig_raw)
        
        # C. 计算业绩 (Shifted)
        # 沿用 Naive 杠杆
        ret_trend = StrategyLogic.calculate_strategy_performance(
            df_rp_xr, w_trend.shift(1), lev_naive.shift(1), StrategyConfig.BORROW_SPREAD
        )
        ret_trend = ret_trend.dropna()
        
        # D. 统计指标
        # Sharpe
        sharpe = ret_trend.mean() / ret_trend.std() * np.sqrt(12)
        
        # Max Drawdown (基于 Total Return)
        cum_wealth = (1 + ret_trend + rf.reindex(ret_trend.index)).cumprod()
        dd = (cum_wealth / cum_wealth.cummax() - 1).min()
        
        results.append({
            'Window': w,
            'Sharpe': sharpe,
            'Max_DD': dd
        })
        print(f"      Window={w}: Sharpe={sharpe:.2f}, MaxDD={dd:.2%}")
        
    df_res = pd.DataFrame(results).set_index('Window')
    
    # 3. 绘图 (双轴图：Sharpe vs DD)
    fig, ax1 = plt.subplots(figsize=(10, 6))
    
    # 左轴: Sharpe (柱状图)
    bars = ax1.bar(df_res.index.astype(str), df_res['Sharpe'], color='#1f77b4', alpha=0.6, label='Sharpe Ratio')
    ax1.set_xlabel('MA Window (Months)')
    ax1.set_ylabel('Sharpe Ratio', color='#1f77b4', fontweight='bold')
    ax1.tick_params(axis='y', labelcolor='#1f77b4')
    ax1.set_ylim(0, df_res['Sharpe'].max() * 1.2)
    
    # 标记当前使用的 MA(10)
    target_idx = windows.index(10)
    bars[target_idx].set_color('#2ca02c') # Green for chosen one
    bars[target_idx].set_alpha(0.8)
    
    # 右轴: Drawdown (折线图)
    ax2 = ax1.twinx()
    ax2.plot(df_res.index.astype(str), df_res['Max_DD'], color='red', marker='o', lw=2, label='Max Drawdown')
    ax2.set_ylabel('Max Drawdown', color='red', fontweight='bold')
    ax2.tick_params(axis='y', labelcolor='red')
    # 倒置 Y 轴让回撤看起来更直观 (0 在上面)
    ax2.set_ylim(df_res['Max_DD'].min() * 1.2, 0)
    
    plt.title('Trend Robustness: Performance across MA Windows')
    
    # Add simple legend manually if needed, or rely on axis colors
    
    save_path = os.path.join(PLOT_DIR, 'trend_test_sensitivity.png')
    plt.savefig(save_path)
    print(f"✅ Robustness Plot saved: {save_path}")

if __name__ == "__main__":
    run_sensitivity_test()