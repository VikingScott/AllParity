# 03_1_strategy_construction/main_runner.py

import pandas as pd
import numpy as np
import os
import sys

# 路径设置
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from strategy_config import StrategyConfig
from strategy_logic import StrategyLogic

# 数据路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(PROJECT_ROOT, 'data', 'processed', 'data_final_returns.csv')
OUTPUT_PATH = os.path.join(PROJECT_ROOT, 'data', 'processed', 'strategy_results.csv')

def main():
    print("🚀 [Strategy Runner v6.0] Dual-Track Targets: Paper (Equity Vol) vs Policy (60/40 Vol)...")

    # 1. 读取数据
    if not os.path.exists(DATA_PATH):
        print("❌ Data missing.")
        return
    df_all = pd.read_csv(DATA_PATH, index_col=0, parse_dates=True)
    
    s_rf = df_all['Risk_Free']
    df_rp_xr = df_all[StrategyConfig.ASSETS_RP_XR]
    
    print(f"   RP Assets: {StrategyConfig.ASSETS_RP_XR}")

    # ----------------------------------------------------
    # 2. 构建两个基准 & 两个目标波动率
    # ----------------------------------------------------
    print("   [1/4] Calculating Dual Targets (Equity Vol & 60/40 Vol)...")
    
    # --- Track A: Paper Standard (Equity / SP500) ---
    bench_sp500_xr = df_all[StrategyConfig.ASSET_MARKET_XR]
    bench_sp500_tr = bench_sp500_xr + s_rf
    # 目标：SP500 TR 的波动率
    vol_target_equity = StrategyLogic.calculate_rolling_vol(bench_sp500_tr, StrategyConfig.VOL_LOOKBACK)
    
    # --- Track B: Policy Standard (Balanced / 60/40) ---
    stock_tr = df_all[StrategyConfig.ASSET_6040_STOCK_TR]
    bond_tr = df_all[StrategyConfig.ASSET_6040_BOND_TR]
    bench_6040_tr = 0.60 * stock_tr + 0.40 * bond_tr
    bench_6040_xr = bench_6040_tr - s_rf
    # 目标：60/40 TR 的波动率
    vol_target_6040 = StrategyLogic.calculate_rolling_vol(bench_6040_tr, StrategyConfig.VOL_LOOKBACK)

    # ----------------------------------------------------
    # 3. 计算 RP 信号
    # ----------------------------------------------------
    print("   [2/4] Calculating RP Weights & Ex-Ante Risk...")
    
    # A. 资产波动率
    vol_assets_xr = StrategyLogic.calculate_rolling_vol(df_rp_xr, StrategyConfig.VOL_LOOKBACK)
    
    # B. 基础权重 (Inverse Vol)
    w_rp_base = StrategyLogic.calculate_inverse_vol_weights(vol_assets_xr)
    
    # C. 组合预期波动率 (Covariance) + Floor
    vol_rp_est = StrategyLogic.calculate_portfolio_ex_ante_vol_covariance(
        w_rp_base, df_rp_xr, StrategyConfig.VOL_LOOKBACK
    )
    vol_rp_est = vol_rp_est.clip(lower=StrategyConfig.MIN_VOL_FLOOR)

    # ----------------------------------------------------
    # 4. 计算双轨杠杆 (Dual Leverage Paths)
    # ----------------------------------------------------
    print("   [3/4] Calculating Dual Leverage Paths...")
    
    # Path A: Academic (Target = Equity Vol, Cap = 10x)
    # 这是为了复刻 AQR 论文："如果 RP 像股票一样波动，收益如何？"
    lev_acad_equity_vol = StrategyLogic.calculate_leverage_ratio_match_market(
        vol_rp_est, vol_target_equity, max_cap=StrategyConfig.MAX_LEVERAGE_ACADEMIC
    )
    
    # Path B: Retail (Target = 60/40 Vol, Cap = 2.5x)
    # 这是为了评估现实："如果 RP 像 60/40 一样波动，收益如何？"
    lev_retail_6040_vol = StrategyLogic.calculate_leverage_ratio_match_market(
        vol_rp_est, vol_target_6040, max_cap=StrategyConfig.MAX_LEVERAGE_RETAIL
    )

    # ----------------------------------------------------
    # 5. 构建组合
    # ----------------------------------------------------
    print("   [4/4] Constructing Portfolios & Saving...")
    
    # Lagging
    w_rp_lag = w_rp_base.shift(1)
    lev_acad_lag = lev_acad_equity_vol.shift(1)
    lev_retail_lag = lev_retail_6040_vol.shift(1)
    
    # --- Strategy 3: RP Unlevered ---
    rp_unlev_xr = StrategyLogic.calculate_strategy_performance(
        df_rp_xr, w_rp_lag, leverage_ratio_lagged=1.0, borrow_spread=0.0
    )
    
    # --- Strategy 4: RP Academic (Paper Standard) ---
    # Target: Equity Vol | Cap: 10x | Spread: 0
    rp_acad_xr = StrategyLogic.calculate_strategy_performance(
        df_rp_xr, w_rp_lag, leverage_ratio_lagged=lev_acad_lag, borrow_spread=0.0
    )
    
    # --- Strategy 5: RP Retail (Policy Standard) ---
    # Target: 60/40 Vol | Cap: 2.5x | Spread: 50bps
    rp_retail_xr = StrategyLogic.calculate_strategy_performance(
        df_rp_xr, w_rp_lag, leverage_ratio_lagged=lev_retail_lag, borrow_spread=StrategyConfig.BORROW_SPREAD
    )

    # ----------------------------------------------------
    # 6. 保存结果
    # ----------------------------------------------------
    df_results = pd.DataFrame({
        'Risk_Free': s_rf,
        
        # Benchmarks
        'Bench_SP500_XR': bench_sp500_xr,
        'Bench_SP500_TR': bench_sp500_tr,
        'Bench_6040_XR': bench_6040_xr,
        'Bench_6040_TR': bench_6040_tr,
        
        # Risk Parity
        'RP_Unlevered_XR': rp_unlev_xr,
        'RP_Academic_XR': rp_acad_xr, # Now targets Equity Vol
        'RP_Retail_XR': rp_retail_xr, # Now targets 60/40 Vol
        
        # Diagnostics
        'Vol_Target_Equity_TR': vol_target_equity,
        'Vol_Target_6040_TR': vol_target_6040,
        'Vol_RP_Est': vol_rp_est,
        'Lev_Ratio_Academic_Realized': lev_acad_lag, # High leverage path
        'Lev_Ratio_Retail_Realized': lev_retail_lag  # Moderate leverage path
    })
    
    # 补全 RP 的 TR
    for col in ['RP_Unlevered', 'RP_Academic', 'RP_Retail']:
        df_results[f'{col}_TR'] = df_results[f'{col}_XR'] + s_rf
        
    df_results = df_results.dropna()
    df_results.to_csv(OUTPUT_PATH)
    
    print(f"✅ Final Data Saved: {OUTPUT_PATH}")
    print("   [Track A] Academic RP -> Targets SP500 Vol")
    print("   [Track B] Retail RP   -> Targets 60/40 Vol")

if __name__ == "__main__":
    main()