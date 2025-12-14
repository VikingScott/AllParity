# 05_erc_extension/run_erc_simulation.py

import pandas as pd
import numpy as np
import os
import sys

# 路径设置
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
TARGET_DIR_03 = os.path.join(PROJECT_ROOT, '03_1_strategy_construction')
if TARGET_DIR_03 not in sys.path: sys.path.append(TARGET_DIR_03)

from strategy_config import StrategyConfig
from strategy_logic import StrategyLogic

OUTPUT_DIR = os.path.join(PROJECT_ROOT, 'data', 'processed')

def run_simulation():
    print("🚀 [ERC Extension] Starting Simulation: Naive vs ERC...")
    
    # 1. 读取数据
    df_all = pd.read_csv(os.path.join(OUTPUT_DIR, 'data_final_returns.csv'), index_col=0, parse_dates=True)
    df_rp_xr = df_all[StrategyConfig.ASSETS_RP_XR]
    
    # Target Vol (60/40)
    stock_tr = df_all[StrategyConfig.ASSET_6040_STOCK_TR]
    bond_tr = df_all[StrategyConfig.ASSET_6040_BOND_TR]
    bench_6040_tr = 0.60 * stock_tr + 0.40 * bond_tr
    bench_6040_xr = bench_6040_tr - df_all['Risk_Free']
    vol_target = StrategyLogic.calculate_rolling_vol(bench_6040_tr, StrategyConfig.VOL_LOOKBACK)

    # ==========================================
    # Track A: Naive RP (Control Group)
    # ==========================================
    print("   [1/2] Calculating Naive RP...")
    # 为了公平对比，我们尽量保持参数一致，但Naive通常每天算
    vol_assets = StrategyLogic.calculate_rolling_vol(df_rp_xr, StrategyConfig.VOL_LOOKBACK)
    w_naive = StrategyLogic.calculate_inverse_vol_weights(vol_assets)
    
    # 风险估计 (Covariance)
    vol_naive_est = StrategyLogic.calculate_portfolio_ex_ante_vol_covariance(
        w_naive, df_rp_xr, StrategyConfig.VOL_LOOKBACK
    ).clip(lower=StrategyConfig.MIN_VOL_FLOOR)
    
    # 杠杆 (Retail Cap)
    lev_naive = StrategyLogic.calculate_leverage_ratio_match_market(
        vol_naive_est, vol_target, max_cap=StrategyConfig.MAX_LEVERAGE_RETAIL
    )
    
    # 净值
    ret_naive = StrategyLogic.calculate_strategy_performance(
        df_rp_xr, w_naive.shift(1), lev_naive.shift(1), StrategyConfig.BORROW_SPREAD
    )

    # ==========================================
    # Track B: ERC RP (Test Group)
    # ==========================================
    print("   [2/2] Calculating ERC RP (Optimization)...")
    # 核心差异：权重计算方法
    w_erc = StrategyLogic.calculate_erc_weights(df_rp_xr, window=36, rebalance_freq='ME')
    
    # 风险估计 (ERC 也是基于 Covariance 的，所以用同样的函数估风险)
    vol_erc_est = StrategyLogic.calculate_portfolio_ex_ante_vol_covariance(
        w_erc, df_rp_xr, StrategyConfig.VOL_LOOKBACK
    ).clip(lower=StrategyConfig.MIN_VOL_FLOOR)
    
    # 杠杆 (同样的规则)
    lev_erc = StrategyLogic.calculate_leverage_ratio_match_market(
        vol_erc_est, vol_target, max_cap=StrategyConfig.MAX_LEVERAGE_RETAIL
    )
    
    # 净值
    ret_erc = StrategyLogic.calculate_strategy_performance(
        df_rp_xr, w_erc.shift(1), lev_erc.shift(1), StrategyConfig.BORROW_SPREAD
    )

    # ==========================================
    # Save Results
    # ==========================================
    # 保存所有中间变量以便 Analysis 脚本使用
    # 我们不仅要存 Return，还要存 Weights，因为 Signal Test 需要 Weights
    
    # 1. Returns CSV
    df_res = pd.DataFrame({
        'Risk_Free': df_all['Risk_Free'],
        'Naive_XR': ret_naive,
        'ERC_XR': ret_erc,
        'Bench_6040_XR': bench_6040_xr
    }).dropna()
    
    path_res = os.path.join(OUTPUT_DIR, 'erc_vs_naive_returns.csv')
    df_res.to_csv(path_res)
    print(f"✅ Returns Saved: {path_res}")
    
    # 2. Weights CSV (Pickle 可能更好，但 CSV 通用)
    # 我们把 ERC 和 Naive 的权重都存下来
    w_erc.columns = [f"ERC_{c}" for c in w_erc.columns]
    w_naive.columns = [f"Naive_{c}" for c in w_naive.columns]
    
    df_weights = pd.concat([w_erc, w_naive], axis=1).dropna()
    path_w = os.path.join(OUTPUT_DIR, 'erc_vs_naive_weights.csv')
    df_weights.to_csv(path_w)
    print(f"✅ Weights Saved: {path_w}")

if __name__ == "__main__":
    run_simulation()