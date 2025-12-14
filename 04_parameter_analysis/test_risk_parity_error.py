# 04_parameter_analysis/test_risk_parity_error.py
# (或者 05_component_rules/test_risk_parity_error.py，取决于你放哪了)

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
import sys

# ==========================================
# 1. 路径魔法 (防止 ModuleNotFoundError)
# ==========================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
TARGET_DIR_03 = os.path.join(PROJECT_ROOT, '03_1_strategy_construction')

if TARGET_DIR_03 not in sys.path:
    sys.path.append(TARGET_DIR_03)

from strategy_config import StrategyConfig
from strategy_logic import StrategyLogic

# 输出路径
PLOT_DIR = os.path.join(PROJECT_ROOT, 'outputs', 'plots', '05_component_rules')
if not os.path.exists(PLOT_DIR):
    os.makedirs(PLOT_DIR)

# ==========================================
# 2. 核心计算逻辑 (Bug 修复版)
# ==========================================
def calculate_marginal_risk_contribution(weights_df, returns_df, lookback, lag_cov=True):
    """
    计算基于协方差矩阵的严格风险贡献 (MRC)
    RC_i = w_i * (Sigma * w)_i / (w' * Sigma * w)
    """
    # 计算滚动协方差矩阵
    rolling_cov = returns_df.rolling(window=lookback).cov()
    
    rc_list = []
    dates = weights_df.index
    n_assets = len(weights_df.columns) # 获取资产数量 (4)
    
    # 准备一个全空的行 [NaN, NaN, NaN, NaN] 用于填补缺失数据
    nan_row = [np.nan] * n_assets
    
    for d in dates:
        # 确定使用哪天的协方差矩阵
        cov_date = d
        if lag_cov:
            # Ex-Ante: 尝试找前一个交易日
            loc = returns_df.index.get_loc(d)
            if loc > 0:
                cov_date = returns_df.index[loc-1]
            else:
                rc_list.append(nan_row) # <--- 修复点 1：填补一行 NaN
                continue
                
        if cov_date not in rolling_cov.index:
            rc_list.append(nan_row) # <--- 修复点 2：填补一行 NaN
            continue
            
        try:
            w = weights_df.loc[d].values # w_{t-1}
            Sigma = rolling_cov.loc[cov_date].values # Sigma
            
            # 检查空值
            if np.isnan(w).any() or np.isnan(Sigma).any():
                rc_list.append(nan_row) # <--- 修复点 3：填补一行 NaN
                continue
            
            # 核心公式
            # Portfolio Variance = w'Zw (Scalar)
            port_var = w @ Sigma @ w.T
            
            # Marginal Contribution = Sigma * w (Vector)
            mrc = Sigma @ w.T
            
            # Component Contribution = w * mrc (Vector, Element-wise)
            rc = w * mrc
            
            # Percentage RC
            # 防止除以0
            if port_var == 0:
                rc_list.append(nan_row)
            else:
                rc_pct = rc / port_var
                rc_list.append(rc_pct)
            
        except KeyError:
            rc_list.append(nan_row) # <--- 修复点 4：填补一行 NaN
            
    return pd.DataFrame(rc_list, index=dates, columns=weights_df.columns)

def run_strict_signal_test():
    print("🚀 [Signal Test] Calculating Strict Covariance-based Risk Contribution...")
    
    # 1. 读取数据
    data_path = os.path.join(PROJECT_ROOT, 'data', 'processed', 'data_final_returns.csv')
    if not os.path.exists(data_path):
        print("❌ Data not found.")
        return
        
    df_all = pd.read_csv(data_path, index_col=0, parse_dates=True)
    df_rp_xr = df_all[StrategyConfig.ASSETS_RP_XR]
    
    # 2. 复现权重 (Base Weights, Unlevered)
    vol_assets = StrategyLogic.calculate_rolling_vol(df_rp_xr, StrategyConfig.VOL_LOOKBACK)
    w_base = StrategyLogic.calculate_inverse_vol_weights(vol_assets)
    
    # w_{t-1}
    w_lag = w_base.shift(1)
    
    # 3. 计算 Ex-Ante RC (事前视角)
    print("   Calculating Ex-Ante RC (Theoretical)...")
    # 注意：这里可能会有些 NaN，这是正常的
    rc_ex_ante = calculate_marginal_risk_contribution(
        w_lag, df_rp_xr, StrategyConfig.VOL_LOOKBACK, lag_cov=True
    )
    
    # 4. 计算 Ex-Post RC (事后视角)
    print("   Calculating Ex-Post RC (Realized)...")
    rc_ex_post = calculate_marginal_risk_contribution(
        w_lag, df_rp_xr, StrategyConfig.VOL_LOOKBACK, lag_cov=False
    )
    
    # 去除空值以便画图
    rc_ex_post = rc_ex_post.dropna()
    
    # 5. 计算 RP Error (Ex-Post)
    # Error = Sum |RC_i - 0.25|
    target = 0.25
    rp_error = (rc_ex_post - target).abs().sum(axis=1)
    
    # 6. 画图
    print("   Generating Plots...")
    
    # 图 A: Ex-Post RC Stackplot
    plt.figure(figsize=(12, 6))
    labels = [c.replace('_XR','') for c in rc_ex_post.columns]
    
    plt.stackplot(rc_ex_post.index, rc_ex_post.T, labels=labels, alpha=0.85)
    plt.axhline(0.25, c='w', ls=':', lw=0.5)
    plt.axhline(0.50, c='w', ls=':', lw=0.5)
    plt.axhline(0.75, c='w', ls=':', lw=0.5)
    
    plt.title('Ex-Post Risk Contribution (Realized Covariance)')
    plt.ylabel('Risk Share')
    plt.margins(0,0)
    plt.legend(loc='upper left', bbox_to_anchor=(1, 1))
    plt.tight_layout()
    
    save_path_rc = os.path.join(PLOT_DIR, 'signal_03_strict_rc_expost.png')
    plt.savefig(save_path_rc)
    print(f"✅ Ex-Post RC Plot Saved: {save_path_rc}")
    
    # 图 B: RP Error
    plt.figure(figsize=(12, 5))
    plt.plot(rp_error.index, rp_error, color='darkred', lw=1.5, label='Risk Parity Deviation')
    
    # 标注危机
    plt.title('Risk Parity Error: When did the signal fail?')
    plt.ylabel('Total Absolute Error (Sum |RC - 0.25|)')
    
    # 标注 2022
    plt.axvspan(pd.Timestamp('2022-01-01'), pd.Timestamp('2022-12-31'), color='gray', alpha=0.3, label='2022 Inflation Shock')
    # 标注 2008
    plt.axvspan(pd.Timestamp('2008-01-01'), pd.Timestamp('2009-01-01'), color='orange', alpha=0.2, label='2008 GFC')
    
    plt.grid(True, alpha=0.3)
    plt.legend()
    
    save_path_err = os.path.join(PLOT_DIR, 'signal_04_rp_error_metric.png')
    plt.savefig(save_path_err)
    print(f"✅ RP Error Metric Plot Saved: {save_path_err}")

if __name__ == "__main__":
    run_strict_signal_test()