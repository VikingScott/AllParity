# 06_trend_extensions/test_trend_mdd.py

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
import sys

# ==========================================
# 1. Path Configuration
# ==========================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, 'data', 'processed')
PLOT_DIR = os.path.join(PROJECT_ROOT, 'outputs', 'plots', '07_trend_extension')

if not os.path.exists(PLOT_DIR):
    os.makedirs(PLOT_DIR)

# ==========================================
# 2. Helper Functions
# ==========================================

def calculate_mdd(return_series):
    """
    Calculates Maximum Drawdown from a return series.
    Returns a negative float (e.g., -0.20).
    """
    # 1. Construct Wealth Index
    wealth_index = (1 + return_series).cumprod()
    
    # 2. Calculate Peaks
    previous_peaks = wealth_index.cummax()
    
    # 3. Calculate Drawdown
    drawdown = (wealth_index - previous_peaks) / previous_peaks
    
    return drawdown.min()

def paired_block_bootstrap_mdd(series_trend, series_naive, n_sims=5000, block_size=12):
    """
    Performs Paired Block Bootstrap to test H1: MDD_Trend > MDD_Naive (Less negative).
    
    Logic:
    1. Resample indices in blocks.
    2. Reconstruct synthetic return paths for both strategies using SAME indices.
    3. Calculate MDD for both paths.
    4. Diff = MDD_Trend - MDD_Naive.
    
    Returns:
        diff_actual: Realized difference
        p_value: Fraction of sims where diff <= 0 (Failure to improve)
        dist: Distribution of differences
    """
    # Align Data
    df = pd.DataFrame({'T': series_trend, 'N': series_naive}).dropna()
    n = len(df)
    data_vals = df.values # [Returns_Trend, Returns_Naive]
    
    # Actual Diff
    mdd_t = calculate_mdd(df['T'])
    mdd_n = calculate_mdd(df['N'])
    diff_actual = mdd_t - mdd_n # e.g., -0.15 - (-0.25) = +0.10 (Improvement)
    
    # Bootstrap
    diffs_sim = []
    n_blocks = int(np.ceil(n / block_size))
    
    np.random.seed(42)
    
    for _ in range(n_sims):
        # Generate random start indices
        start_indices = np.random.randint(0, n, n_blocks)
        
        # Construct circular block indices
        indices = []
        for start in start_indices:
            block_idxs = np.arange(start, start + block_size) % n
            indices.extend(block_idxs)
        indices = indices[:n]
        
        # Sample paired returns
        samp = data_vals[indices]
        
        # Reconstruct Wealth Path & MDD for this sample
        # Note: We treat the scrambled returns as a valid alternative path process
        # (Standard in drawdown statistical inference)
        samp_t = samp[:, 0]
        samp_n = samp[:, 1]
        
        # Quick MDD calc
        # Cumprod can be slow in loop, use log returns for speed if needed, 
        # but simple cumprod is fine for 5000 sims of length ~400
        w_t = np.cumprod(1 + samp_t)
        dd_t = (w_t - np.maximum.accumulate(w_t)) / np.maximum.accumulate(w_t)
        min_dd_t = dd_t.min()
        
        w_n = np.cumprod(1 + samp_n)
        dd_n = (w_n - np.maximum.accumulate(w_n)) / np.maximum.accumulate(w_n)
        min_dd_n = dd_n.min()
        
        diffs_sim.append(min_dd_t - min_dd_n)
        
    diffs_sim = np.array(diffs_sim)
    
    # One-sided P-Value: Fraction where Trend did NOT improve (Diff <= 0)
    p_value = (diffs_sim <= 0).mean()
    
    return diff_actual, p_value, diffs_sim

# ==========================================
# 3. Sensitivity Engine
# ==========================================
def run_window_sensitivity(df_assets, naive_weights_proxy=None):
    """
    Recalculates MDD improvement across different MA windows.
    Since we don't have the full Strategy Object here, we simulate a 
    Simplified Trend Overlay:
    1. Calculate MA Signal for each asset.
    2. Apply to Asset Returns.
    3. Re-weight (Equal Risk approximation if weights missing).
    """
    print("\n🔹 Running Parameter Sensitivity Scan (MA Windows)...")
    
    # Target Assets
    assets = ['US_Stock_XR', 'US_Bond_10Y_XR', 'US_Credit_XR', 'Commodities_XR']
    assets = [c for c in assets if c in df_assets.columns]
    
    if not assets:
        print("⚠️ Asset data missing for sensitivity check.")
        return None

    # Windows to test
    windows = [6, 8, 10, 12, 15, 18, 24]
    results = []
    
    # Calculate Asset Prices for MA
    prices = (1 + df_assets[assets]).cumprod()
    
    # Baseline Naive (Static) Return Construction
    # (Approximation: Equal Weight 1/N for sensitivity pattern, 
    #  or use 1/Vol if we implemented it. Let's use 1/N for robustness check speed
    #  assuming the *relative* improvement pattern holds.)
    #  BETTER: Use Volatility weighting on the fly.
    
    # Rolling Vol (36m)
    vol = df_assets[assets].rolling(36).std() * np.sqrt(12)
    inv_vol = 1 / vol
    w_naive = inv_vol.div(inv_vol.sum(axis=1), axis=0).shift(1).fillna(0)
    
    # Naive Strategy Return
    r_naive = (w_naive * df_assets[assets]).sum(axis=1)
    mdd_naive = calculate_mdd(r_naive)
    
    for w in windows:
        # Calculate MA Signal
        ma = prices.rolling(window=w).mean()
        signal = (prices > ma).astype(int).shift(1).fillna(0)
        
        # Trend Weights: Naive Weight * Signal
        # (Cash assumption: Weights sum < 1 implies Cash. 
        #  Return is just Sum(W * R), remainder is 0 return (XR))
        w_trend = w_naive * signal
        
        # Trend Strategy Return
        r_trend = (w_trend * df_assets[assets]).sum(axis=1)
        
        # MDD
        mdd_trend = calculate_mdd(r_trend)
        
        diff = mdd_trend - mdd_naive
        results.append({'Window': w, 'MDD_Trend': mdd_trend, 'MDD_Naive': mdd_naive, 'Diff': diff})
        
    return pd.DataFrame(results)

# ==========================================
# 4. Main Runner
# ==========================================
def run_h3_test():
    print("🚀 [H3 Test] Running Trend Efficiency & Tail Risk Analysis...")
    
    # 1. Load Strategy Results (Primary)
    path_strat = os.path.join(DATA_DIR, 'strategy_results.csv')
    path_assets = os.path.join(DATA_DIR, 'data_final_returns.csv')
    
    if not os.path.exists(path_strat):
        print("❌ Strategy results missing.")
        return

    df_res = pd.read_csv(path_strat, index_col=0, parse_dates=True)
    
    # Check Columns (Adjust based on your actual column names)
    col_naive = 'RP_Retail_XR'
    col_trend = 'RP_Trend_XR' # Assuming this exists from previous step
    
    if col_trend not in df_res.columns:
        print(f"⚠️ '{col_trend}' not found. Looking for alternative Trend column...")
        # Fallback check
        possibles = [c for c in df_res.columns if 'Trend' in c]
        if possibles:
            col_trend = possibles[0]
            print(f"   Using '{col_trend}' as Trend Strategy.")
        else:
            print("❌ No Trend Strategy column found. Cannot run Bootstrap.")
            return

    # ---------------------------------------------------------
    # Part A: Primary Bootstrap Test (MDD)
    # ---------------------------------------------------------
    print(f"\n🔹 Primary Test: Paired Block Bootstrap (MDD Diff)")
    
    diff, p_val, dist = paired_block_bootstrap_mdd(
        df_res[col_trend], df_res[col_naive], n_sims=5000, block_size=12
    )
    
    print(f"   Actual MDD Diff (Trend - Naive): {diff:.4f}")
    print(f"   (Positive = Trend Improvement)")
    print(f"   One-sided P-Value (H0: Diff <= 0): {p_val:.4f}")
    
    sig = "SIGNIFICANT" if p_val < 0.05 else "INSIGNIFICANT"
    print(f"   Conclusion: {sig} evidence that Trend reduces Drawdowns.")
    
    # Plot Bootstrap
    plt.figure(figsize=(10, 6))
    plt.hist(dist, bins=50, color='#2ca02c', alpha=0.6, density=True, label='Bootstrap Dist. ($\Delta MDD$)')
    plt.axvline(0, color='red', ls='--', lw=2, label='Null Hypothesis')
    plt.axvline(diff, color='gold', lw=3, label=f'Actual ({diff:.2f})')
    plt.title(f'Hypothesis 3: Tail Risk Mitigation\n$\Delta MDD$ (Trend - Naive) | $P$-Value = {p_val:.4f}')
    plt.xlabel('Maximum Drawdown Improvement')
    plt.ylabel('Probability Density')
    plt.legend()
    plt.grid(True, alpha=0.2)
    plt.savefig(os.path.join(PLOT_DIR, 'significance_h3_mdd_bootstrap.png'))
    print(f"✅ Bootstrap Plot Saved.")

    # ---------------------------------------------------------
    # Part B: Sensitivity Analysis (Window Scan)
    # ---------------------------------------------------------
    if os.path.exists(path_assets):
        df_assets = pd.read_csv(path_assets, index_col=0, parse_dates=True)
        df_sens = run_window_sensitivity(df_assets)
        
        if df_sens is not None:
            print("\n🔹 Robustness: Parameter Sensitivity (MA Window)")
            print(df_sens.to_string(index=False))
            
            # Plot Sensitivity
            plt.figure(figsize=(8, 5))
            plt.plot(df_sens['Window'], df_sens['Diff'], marker='o', lw=2, color='#2ca02c')
            plt.axhline(0, color='red', ls='--', label='No Improvement')
            plt.title('Robustness Check: Drawdown Improvement vs. MA Window')
            plt.xlabel('Moving Average Window (Months)')
            plt.ylabel('$\Delta$ Max Drawdown (Trend - Naive)')
            plt.grid(True, alpha=0.3)
            plt.legend()
            
            save_path = os.path.join(PLOT_DIR, 'analysis_h3_sensitivity.png')
            plt.savefig(save_path)
            print(f"✅ Sensitivity Plot Saved: {save_path}")
            
            # Save CSV for paper
            df_sens.to_csv(os.path.join(PLOT_DIR, 'table_h3_sensitivity.csv'))

if __name__ == "__main__":
    run_h3_test()