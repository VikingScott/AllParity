# 02_component_testing/test_vol_clustering.py

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import os
from scipy import stats

# ==========================================
# 0. Path Configuration
# ==========================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

DATA_PATH = os.path.join(PROJECT_ROOT, 'data', 'processed', 'data_final_returns.csv')
PLOT_DIR = os.path.join(PROJECT_ROOT, 'outputs', 'plots', '02_component_testing')

if not os.path.exists(PLOT_DIR):
    os.makedirs(PLOT_DIR)

def run_vol_clustering_test():
    print("🚀 [Component Test] Starting Volatility Clustering Test...")

    # 1. Load Data
    if not os.path.exists(DATA_PATH):
        print(f"❌ Data not found: {DATA_PATH}")
        return
    
    df_ret = pd.read_csv(DATA_PATH, index_col=0, parse_dates=True)
    
    # We use US Stocks as the primary proxy for this test (most observable volatility)
    # But we can iterate through all assets
    assets = [c for c in df_ret.columns if 'XR' in c]
    
    # 2. Setup Visualization
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    axes = axes.flatten()
    
    print("   Analyzing Volatility Persistence (Lag-1 Autocorrelation)...")

    for i, asset in enumerate(assets):
        if i >= 4: break # Limit to 4 subplots
        
        # A. Calculate Realized Volatility (Rolling 12-month)
        # This is our "Indicator" value
        vol_indicator = df_ret[asset].rolling(window=12).std() * np.sqrt(12)
        
        # B. Prepare Lagged Data for Regression
        # X: Volatility at t-1
        # Y: Volatility at t
        df_lag = pd.DataFrame({'Vol_t': vol_indicator, 'Vol_t_minus_1': vol_indicator.shift(1)}).dropna()
        
        # C. Statistical Test (Linear Regression)
        slope, intercept, r_value, p_value, std_err = stats.linregress(df_lag['Vol_t_minus_1'], df_lag['Vol_t'])
        
        # D. Plot Scatter with Regression Line
        ax = axes[i]
        # Scatter plot
        ax.scatter(df_lag['Vol_t_minus_1'], df_lag['Vol_t'], alpha=0.3, s=10, label='Monthly Observations')
        
        # Regression line
        x_vals = np.array(ax.get_xlim())
        y_vals = intercept + slope * x_vals
        ax.plot(x_vals, y_vals, 'r--', label=f'Fit (R²={r_value**2:.2f})')
        
        # Styling
        asset_name = asset.replace('_XR', '')
        ax.set_title(f'{asset_name}: Volatility Clustering\nSlope (Persistence) = {slope:.2f}')
        ax.set_xlabel('Volatility (Month t-1)')
        ax.set_ylabel('Volatility (Month t)')
        ax.legend(loc='upper left')
        ax.grid(True, alpha=0.3)
        
        print(f"     -> {asset_name}: Slope={slope:.3f}, R-Squared={r_value**2:.3f} (High R2 = Strong Clustering)")

    plt.tight_layout()
    save_path = os.path.join(PLOT_DIR, 'test_02_vol_clustering.png')
    plt.savefig(save_path)
    print(f"✅ Volatility Clustering Test plot saved to: {save_path}")

if __name__ == "__main__":
    run_vol_clustering_test()