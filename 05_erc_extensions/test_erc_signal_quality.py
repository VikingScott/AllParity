# 05_erc_extension/test_erc_signal_quality.py

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
import sys

# 路径
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, 'data', 'processed')
PLOT_DIR = os.path.join(PROJECT_ROOT, 'outputs', 'plots', '06_erc_extension')
if not os.path.exists(PLOT_DIR): os.makedirs(PLOT_DIR)

# 引入 Logic
sys.path.append(os.path.join(PROJECT_ROOT, '03_1_strategy_construction'))
from strategy_logic import StrategyLogic
from strategy_config import StrategyConfig

def run_signal_quality_test():
    print("🚀 [ERC Test] Signal Quality & RP Error Analysis...")
    
    # 1. 读取数据
    # 需要 Returns (计算 Cov) 和 Weights (计算 RC)
    df_all = pd.read_csv(os.path.join(DATA_DIR, 'data_final_returns.csv'), index_col=0, parse_dates=True)
    df_rp_xr = df_all[StrategyConfig.ASSETS_RP_XR]
    
    df_w = pd.read_csv(os.path.join(DATA_DIR, 'erc_vs_naive_weights.csv'), index_col=0, parse_dates=True)
    
    # 拆分权重
    cols_erc = [c for c in df_w.columns if c.startswith('ERC_')]
    cols_naive = [c for c in df_w.columns if c.startswith('Naive_')]
    
    w_erc = df_w[cols_erc]
    w_erc.columns = [c.replace('ERC_', '') for c in cols_erc]
    
    w_naive = df_w[cols_naive]
    w_naive.columns = [c.replace('Naive_', '') for c in cols_naive]
    
    # 2. 计算 Ex-Post Risk Contribution
    # 这里的 w 已经是 Shift 过的吗？不，Saved Weights 应该是当期的信号。
    # 计算 RC 时，我们通常假设 w 是 t 时刻决定的，用来持有 t+1。
    # 所以 Ex-Post RC (t+1) = w(t) * Cov(t+1)
    # 我们使用 calculate_ex_post_risk_contribution 内部逻辑（它不做 shift，假设传入的是配对好的）
    # 但我们的工具函数逻辑是: for d in dates... w.loc[d] ... cov.loc[d]
    # 如果我们要看 Ex-Post，我们应该把 weights 向后 shift(1) 再传进去，或者在函数外对齐。
    # 为了简单，我们将 weights shift(1) 后传入，这样 d 时刻拿到的是 w(t-1) 和 cov(t)
    
    print("   Calculating Ex-Post Risk Contribution (ERC)...")
    rc_erc = StrategyLogic.calculate_ex_post_risk_contribution(
        w_erc.shift(1), df_rp_xr, StrategyConfig.VOL_LOOKBACK
    ).dropna()
    
    print("   Calculating Ex-Post Risk Contribution (Naive)...")
    rc_naive = StrategyLogic.calculate_ex_post_risk_contribution(
        w_naive.shift(1), df_rp_xr, StrategyConfig.VOL_LOOKBACK
    ).dropna()
    
    # 3. 计算 RP Error (Sum |RC - 0.25|)
    target = 0.25
    err_erc = (rc_erc - target).abs().sum(axis=1)
    err_naive = (rc_naive - target).abs().sum(axis=1)
    
    # 4. 画图 A: ERC Stackplot (验证是否平滑)
    plt.figure(figsize=(12, 6))
    labels = [c.replace('_XR','') for c in rc_erc.columns]
    plt.stackplot(rc_erc.index, rc_erc.T, labels=labels, alpha=0.85)
    plt.axhline(0.25, c='w', ls=':', lw=0.5); plt.axhline(0.50, c='w', ls=':', lw=0.5); plt.axhline(0.75, c='w', ls=':', lw=0.5)
    plt.title('ERC Strategy: Ex-Post Risk Contribution (Ideally Equal)')
    plt.ylabel('Risk Share')
    plt.margins(0,0)
    plt.legend(loc='upper left', bbox_to_anchor=(1, 1))
    plt.tight_layout()
    plt.savefig(os.path.join(PLOT_DIR, 'erc_01_stackplot.png'))
    print(f"✅ Stackplot Saved.")
    
    # 5. 画图 B: Error Comparison (验证是否改进)
    plt.figure(figsize=(12, 6))
    plt.plot(err_naive.index, err_naive, color='gray', alpha=0.6, label='Naive RP (Inverse-Vol)', lw=1)
    plt.plot(err_erc.index, err_erc, color='#1f77b4', alpha=0.9, label='ERC RP (Optimized)', lw=1.5)
    
    plt.title('Risk Parity Error: Naive vs ERC')
    plt.ylabel('Total Absolute Error from 25%')
    plt.axvspan(pd.Timestamp('2022-01-01'), pd.Timestamp('2023-01-01'), color='red', alpha=0.1, label='2022 Inflation Shock')
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    plt.savefig(os.path.join(PLOT_DIR, 'erc_02_error_comparison.png'))
    print(f"✅ Error Comparison Saved.")

if __name__ == "__main__":
    run_signal_quality_test()