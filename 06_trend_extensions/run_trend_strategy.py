# 07_trend_following/run_trend_simulation.py

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

def run_trend_simulation():
    print("🚀 [Trend Simulation] Starting: Naive RP vs Trend-Filtered RP...")
    
    # 1. 读取数据
    df_all = pd.read_csv(os.path.join(OUTPUT_DIR, 'data_final_returns.csv'), index_col=0, parse_dates=True)
    
    # 提取 RP 资产的超额收益 (XR)
    df_rp_xr = df_all[StrategyConfig.ASSETS_RP_XR]
    
    # 关键：构建总收益 (TR) 用于计算均线信号
    rf = df_all['Risk_Free']
    df_rp_tr = df_rp_xr.add(rf, axis=0)
    
    # 准备 Bench
    stock_tr = df_all[StrategyConfig.ASSET_6040_STOCK_TR]
    bond_tr = df_all[StrategyConfig.ASSET_6040_BOND_TR]
    bench_6040_tr = 0.60 * stock_tr + 0.40 * bond_tr
    bench_6040_xr = bench_6040_tr - rf
    vol_target = StrategyLogic.calculate_rolling_vol(bench_6040_tr, StrategyConfig.VOL_LOOKBACK)

    # ==========================================
    # Step 1: Baseline (Naive RP)
    # ==========================================
    print("   [1/3] Calculating Baseline (Naive RP)...")
    
    vol_assets = StrategyLogic.calculate_rolling_vol(df_rp_xr, StrategyConfig.VOL_LOOKBACK)
    w_naive = StrategyLogic.calculate_inverse_vol_weights(vol_assets)
    
    vol_naive_est = StrategyLogic.calculate_portfolio_ex_ante_vol_covariance(
        w_naive, df_rp_xr, StrategyConfig.VOL_LOOKBACK
    ).clip(lower=StrategyConfig.MIN_VOL_FLOOR)
    
    lev_naive = StrategyLogic.calculate_leverage_ratio_match_market(
        vol_naive_est, vol_target, max_cap=StrategyConfig.MAX_LEVERAGE_RETAIL
    )
    
    ret_naive = StrategyLogic.calculate_strategy_performance(
        df_rp_xr, w_naive.shift(1), lev_naive.shift(1), StrategyConfig.BORROW_SPREAD
    )

    # ==========================================
    # Step 2: Trend Signal Generation
    # ==========================================
    print("   [2/3] Generating Trend Signals (MA10 on Total Return)...")
    
    # 获取 Raw Signal (T时刻信号)，Logic 内部不再 shift
    trend_signal_raw = StrategyLogic.calculate_trend_signal(df_rp_tr, window=10)
    
    # 保存信号
    trend_signal_raw.to_csv(os.path.join(OUTPUT_DIR, 'trend_signals_raw.csv'))

    # ==========================================
    # Step 3: Apply Trend Filter (Trend RP)
    # ==========================================
    print("   [3/3] Constructing Trend-Filtered Portfolio...")
    
    # 1. 过滤权重 (Cash-Reserve Mode: 不归一化)
    w_trend = StrategyLogic.apply_trend_filter(w_naive, trend_signal_raw)
    
    # 2. 杠杆设定 (沿用 Naive 杠杆)
    lev_trend = lev_naive.copy() 
    
    # 3. 计算净值 (统一 Shift)
    ret_trend = StrategyLogic.calculate_strategy_performance(
        df_rp_xr, w_trend.shift(1), lev_trend.shift(1), StrategyConfig.BORROW_SPREAD
    )

    # ==========================================
    # 🆕 NEW: 生成诊断数据 (Diagnostics)
    # ==========================================
    print("   [Diagnostics] Generating Leverage Analysis...")
    
    # 我们看的是 T 时刻持仓 (Shifted)
    w_trend_shifted = w_trend.shift(1)
    lev_trend_shifted = lev_trend.shift(1)
    
    # 名义仓位总和 (Risk-on Proportion)
    sum_w_trend = w_trend_shifted.sum(axis=1)
    
    # 实际风险敞口 (Gross Exposure)
    actual_exposure = sum_w_trend * lev_trend_shifted
    
    # 实际融资额 (Borrowing)
    borrow_amount = (actual_exposure - 1.0).clip(lower=0.0)
    
    # 活跃资产数量
    active_assets_count = trend_signal_raw.shift(1).sum(axis=1)

    diag = pd.DataFrame({
        "Active_Assets": active_assets_count,
        "Risk_On_Weight_Sum": sum_w_trend,
        "Target_Leverage": lev_trend_shifted,
        "Actual_Gross_Exposure": actual_exposure,
        "Actual_Borrowing": borrow_amount
    }).dropna()
    
    diag_path = os.path.join(OUTPUT_DIR, 'trend_diagnostics.csv')
    diag.to_csv(diag_path)
    print(f"      Diagnostics saved: {diag_path}")

    # ==========================================
    # Save Results
    # ==========================================
    df_res = pd.DataFrame({
        'Risk_Free': rf,
        'Naive_XR': ret_naive,
        'Trend_XR': ret_trend,
        'Bench_6040_XR': bench_6040_xr
    }).dropna()
    
    w_trend.columns = [f"Trend_{c}" for c in w_trend.columns]
    w_naive.columns = [f"Naive_{c}" for c in w_naive.columns]
    df_weights = pd.concat([w_trend, w_naive], axis=1).dropna()
    
    path_res = os.path.join(OUTPUT_DIR, 'trend_vs_naive_returns.csv')
    path_w = os.path.join(OUTPUT_DIR, 'trend_vs_naive_weights.csv')
    
    df_res.to_csv(path_res)
    df_weights.to_csv(path_w)
    
    print(f"✅ Simulation Complete.")

if __name__ == "__main__":
    run_trend_simulation()