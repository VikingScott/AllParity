# 07_trend_following/run_trend_simulation.py

import pandas as pd
import numpy as np
import os
import sys

# ==========================================
# 1. Path Configuration
# ==========================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
TARGET_DIR_03 = os.path.join(PROJECT_ROOT, '03_1_strategy_construction')
if TARGET_DIR_03 not in sys.path: sys.path.append(TARGET_DIR_03)

from strategy_config import StrategyConfig
from strategy_logic import StrategyLogic

OUTPUT_DIR = os.path.join(PROJECT_ROOT, 'data', 'processed')

def run_trend_simulation():
    print("🚀 [Trend Simulation] Starting: Naive RP vs Trend-Filtered RP...")
    
    # 1. Load Data
    path_returns = os.path.join(OUTPUT_DIR, 'data_final_returns.csv')
    if not os.path.exists(path_returns):
        print("❌ Final returns data not found. Please run previous steps first.")
        return
        
    df_all = pd.read_csv(path_returns, index_col=0, parse_dates=True)
    
    # Extract RP Asset Excess Returns (XR)
    df_rp_xr = df_all[StrategyConfig.ASSETS_RP_XR]
    
    # Calculate Total Returns (TR) for Trend Signal (XR + RF)
    rf = df_all['Risk_Free']
    df_rp_tr = df_rp_xr.add(rf, axis=0)
    
    # Prepare Benchmark & Target Vol
    stock_tr = df_all[StrategyConfig.ASSET_6040_STOCK_TR]
    bond_tr = df_all[StrategyConfig.ASSET_6040_BOND_TR]
    bench_6040_tr = 0.60 * stock_tr + 0.40 * bond_tr
    # bench_6040_xr = bench_6040_tr - rf # Not strictly needed here if we merge later
    
    vol_target = StrategyLogic.calculate_rolling_vol(bench_6040_tr, StrategyConfig.VOL_LOOKBACK)

    # ==========================================
    # Step 1: Baseline (Naive RP) Calculation
    # ==========================================
    print("   [1/3] Calculating Baseline (Naive RP)...")
    
    vol_assets = StrategyLogic.calculate_rolling_vol(df_rp_xr, StrategyConfig.VOL_LOOKBACK)
    w_naive = StrategyLogic.calculate_inverse_vol_weights(vol_assets)
    
    # Ex-ante Vol Estimate
    vol_naive_est = StrategyLogic.calculate_portfolio_ex_ante_vol_covariance(
        w_naive, df_rp_xr, StrategyConfig.VOL_LOOKBACK
    ).clip(lower=StrategyConfig.MIN_VOL_FLOOR)
    
    # Leverage Calculation
    lev_naive = StrategyLogic.calculate_leverage_ratio_match_market(
        vol_naive_est, vol_target, max_cap=StrategyConfig.MAX_LEVERAGE_RETAIL
    )
    
    # Naive Returns (Baseline)
    # Note: We calculate this mainly to ensure alignment, though it might already exist in strategy_results.csv
    # ret_naive = StrategyLogic.calculate_strategy_performance(...) 

    # ==========================================
    # Step 2: Trend Signal Generation
    # ==========================================
    print("   [2/3] Generating Trend Signals (MA10 on Total Return)...")
    
    # Get Raw Signal (at time T), Logic handles shifting later if needed, 
    # but usually signal T is used for weights T+1. 
    # StrategyLogic.apply_trend_filter usually expects aligned weights/signals.
    trend_signal_raw = StrategyLogic.calculate_trend_signal(df_rp_tr, window=10)
    
    # Save signals for auditing
    trend_signal_raw.to_csv(os.path.join(OUTPUT_DIR, 'trend_signals_raw.csv'))

    # ==========================================
    # Step 3: Apply Trend Filter (Trend RP)
    # ==========================================
    print("   [3/3] Constructing Trend-Filtered Portfolio...")
    
    # 1. Filter Weights (Cash-Reserve Mode: Do NOT normalize, sum < 1 implies cash)
    w_trend = StrategyLogic.apply_trend_filter(w_naive, trend_signal_raw)
    
    # 2. Leverage Setting (Use Naive Leverage)
    # We maintain the same leverage target as the base strategy to isolate the trend effect.
    lev_trend = lev_naive.copy() 
    
    # 3. Calculate Performance (Unified Shift: Weights T -> Returns T+1)
    ret_trend = StrategyLogic.calculate_strategy_performance(
        df_rp_xr, w_trend.shift(1), lev_trend.shift(1), StrategyConfig.BORROW_SPREAD
    )

    # ==========================================
    # 🆕 NEW: Generate Diagnostics
    # ==========================================
    print("   [Diagnostics] Generating Leverage Analysis...")
    
    # Analysis based on actual positions held (Shifted)
    w_trend_shifted = w_trend.shift(1)
    lev_trend_shifted = lev_trend.shift(1)
    
    # Nominal Risk Weight Sum (Risk-on Proportion)
    sum_w_trend = w_trend_shifted.sum(axis=1)
    
    # Actual Gross Exposure (Leverage * Active Weights)
    actual_exposure = sum_w_trend * lev_trend_shifted
    
    # Actual Borrowing (Exposure > 1.0)
    borrow_amount = (actual_exposure - 1.0).clip(lower=0.0)
    
    # Count of Active Assets
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
    # Step 4: Merge Results into Main Strategy File
    # ==========================================
    print("   [4/4] Merging results into strategy_results.csv...")
    
    path_main_res = os.path.join(OUTPUT_DIR, 'strategy_results.csv')
    
    if os.path.exists(path_main_res):
        df_main = pd.read_csv(path_main_res, index_col=0, parse_dates=True)
        print(f"      Loaded existing results with columns: {df_main.columns.tolist()}")
    else:
        # Fallback if main file doesn't exist (shouldn't happen in flow)
        print("      ⚠️ Main results file not found. Creating new one.")
        df_main = pd.DataFrame(index=ret_trend.index)
        df_main['Risk_Free'] = rf

    # Add/Update Trend Columns
    # XR: Excess Return
    df_main['RP_Trend_XR'] = ret_trend
    
    # TR: Total Return (XR + RF)
    # Re-align RF index just in case
    rf_aligned = rf.reindex(ret_trend.index).fillna(0.0)
    df_main['RP_Trend_TR'] = ret_trend + rf_aligned

    # Save Back
    df_main.dropna(how='all').to_csv(path_main_res)
    print(f"✅ Simulation Complete. Results updated in: {path_main_res}")

    # Also save weights separately for plotting later
    path_w = os.path.join(OUTPUT_DIR, 'trend_weights.csv')
    w_trend.columns = [f"Trend_{c}" for c in w_trend.columns]
    w_trend.to_csv(path_w)

if __name__ == "__main__":
    run_trend_simulation()