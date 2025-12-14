# 02_component_testing/test_risk_contribution.py

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os

# ==========================================
# 0. Path Configuration
# ==========================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

# Input: Final Excess Returns
DATA_PATH = os.path.join(PROJECT_ROOT, 'data', 'processed', 'data_final_returns.csv')
# Output: Plot folder
PLOT_DIR = os.path.join(PROJECT_ROOT, 'outputs', 'plots', '02_component_testing')

if not os.path.exists(PLOT_DIR):
    os.makedirs(PLOT_DIR)

def run_risk_contribution_test():
    print("🚀 [Component Test] Starting Risk Contribution Signal Test...")

    # 1. Load Data
    if not os.path.exists(DATA_PATH):
        print(f"❌ Data not found: {DATA_PATH}")
        return
    
    df_ret = pd.read_csv(DATA_PATH, index_col=0, parse_dates=True)
    
    # Filter for Excess Return columns only
    assets = [c for c in df_ret.columns if 'XR' in c]
    df_assets = df_ret[assets]
    print(f"   Assets loaded: {assets}")

    # 2. Calculate Indicators (Rolling Volatility)
    # Lookback window for signal generation (e.g., 12 months)
    lookback = 12
    rolling_vol = df_assets.rolling(window=lookback).std()

    # 3. Generate Signal: Inverse Volatility Weights
    # Formula: w_i = (1/vol_i) / Sum(1/vol_j)
    inv_vol = 1.0 / rolling_vol
    inv_vol_weights = inv_vol.div(inv_vol.sum(axis=1), axis=0)

    # 4. Calculate Risk Contributions (Ex-Post Analysis)
    # Risk Contribution_i = Weight_i * Volatility_i
    # Note: In a naive RP (no correlation), this should be equal for all assets.
    
    # Scenario A: Signal Based (Inverse Vol weighting)
    # We multiply the weight (signal) by the *realized* volatility of that month
    rc_signal = inv_vol_weights * rolling_vol
    # Normalize to % to see share of risk
    rc_signal_pct = rc_signal.div(rc_signal.sum(axis=1), axis=0)

    # Scenario B: Benchmark (Equal Weighting)
    # Weight = 0.25 for all
    ew_weights = pd.DataFrame(0.25, index=df_assets.index, columns=assets)
    rc_ew = ew_weights * rolling_vol
    rc_ew_pct = rc_ew.div(rc_ew.sum(axis=1), axis=0)

    # 5. Visualization
    print("   Generating Risk Contribution Plots...")
    
    fig, axes = plt.subplots(2, 1, figsize=(12, 10), sharex=True)

    # Plot 1: Benchmark (Equal Weight) Risk Distribution
    # This shows why RP is needed: Stocks/Commodities dominate risk here.
    axes[0].stackplot(rc_ew_pct.index, rc_ew_pct.T, labels=[c.replace('_XR', '') for c in assets], alpha=0.8)
    axes[0].set_title(f'Benchmark: Risk Contribution of Equal Weight Portfolio (The Problem)')
    axes[0].set_ylabel('Share of Total Portfolio Risk')
    axes[0].legend(loc='upper left')
    axes[0].grid(True, alpha=0.3)
    axes[0].set_ylim(0, 1)

    # Plot 2: Signal Based (Inverse Vol) Risk Distribution
    # This validates the signal: Risk shares should be roughly equal (approx 0.25 each).
    axes[1].stackplot(rc_signal_pct.index, rc_signal_pct.T, labels=[c.replace('_XR', '') for c in assets], alpha=0.8)
    axes[1].set_title(f'Signal Test: Risk Contribution of Inverse-Vol Weights (The Solution)')
    axes[1].set_ylabel('Share of Total Portfolio Risk')
    axes[1].set_xlabel('Date')
    axes[1].grid(True, alpha=0.3)
    axes[1].set_ylim(0, 1)
    
    # Add a horizontal line at 0.25 (Ideal Risk Parity)
    axes[1].axhline(0.25, color='white', linestyle='--', linewidth=1, alpha=0.5)

    plt.tight_layout()
    save_path = os.path.join(PLOT_DIR, 'test_01_risk_contribution.png')
    plt.savefig(save_path)
    print(f"✅ Risk Contribution Test plot saved to: {save_path}")

if __name__ == "__main__":
    run_risk_contribution_test()