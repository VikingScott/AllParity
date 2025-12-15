# 05_erc_extensions/test_erc_conditional_bootstrap.py

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
PLOT_DIR = os.path.join(PROJECT_ROOT, 'outputs', 'plots', '06_erc_extension')

if not os.path.exists(PLOT_DIR):
    os.makedirs(PLOT_DIR)

# ==========================================
# 2. Statistical Engine: Conditional Bootstrap
# ==========================================
def conditional_block_bootstrap(series_diff, mask_regime, n_sims=5000, block_size=12):
    """
    Performs Paired Block Bootstrap on the Conditional Set S.
    
    H1: Mean(Diff) < 0 (ERC underperforms in regime S)
    H0: Mean(Diff) >= 0
    
    Returns:
        mu_actual: Realized annualized mean difference in regime S
        p_value:   Proportion of bootstrap samples where mean >= 0
        mus_sim:   Distribution of bootstrapped means
    """
    # 1. Isolate the Conditional Set S
    # We filter the difference series to include only months in the regime
    data_S = series_diff[mask_regime].values
    n = len(data_S)
    
    if n < block_size:
        print(f"⚠️ Warning: Regime sample size ({n}) too small for block bootstrap.")
        return 0.0, 1.0, np.array([])
    
    # 2. Calculate Actual Statistic (Delta mu_S)
    # Annualized mean difference
    mu_actual = np.mean(data_S) * 12 
    
    # 3. Bootstrap Loop
    mus_sim = []
    # We treat the regime-filtered data as a time series for blocking
    # (Preserving local clustering of the regime itself if contiguous)
    n_blocks = int(np.ceil(n / block_size))
    
    np.random.seed(42) # Reproducibility
    
    for _ in range(n_sims):
        # Generate random start indices for blocks
        start_indices = np.random.randint(0, n, n_blocks)
        
        # Construct indices (Circular Block Bootstrap)
        indices = []
        for start in start_indices:
            # Block indices: [start, start+1, ..., start+block-1]
            # Modulo n ensures circularity
            block_idxs = np.arange(start, start + block_size) % n
            indices.extend(block_idxs)
        
        # Truncate to original length
        indices = indices[:n]
        
        # Resample the data
        samp = data_S[indices]
        
        # Calculate statistic for this simulation
        mus_sim.append(np.mean(samp) * 12)
        
    mus_sim = np.array(mus_sim)
    
    # 4. Calculate One-Sided P-Value
    # Formula: p = (1/B) * Sum( I(mu_sim >= 0) )
    # This tests H0: mu >= 0. If p is small, we reject H0 in favor of H1 (mu < 0).
    p_value = (mus_sim >= 0).mean()
    
    return mu_actual, p_value, mus_sim

# ==========================================
# 3. Main Runner
# ==========================================
def run_conditional_test():
    print("🚀 [H2 Test] Running Conditional Block Bootstrap (Set S)...")
    
    # 1. Load Data
    path_assets = os.path.join(DATA_DIR, 'data_final_returns.csv')
    path_strat = os.path.join(DATA_DIR, 'erc_vs_naive_returns.csv')
    
    if not os.path.exists(path_assets) or not os.path.exists(path_strat):
        print("❌ Data files missing.")
        return

    df_assets = pd.read_csv(path_assets, index_col=0, parse_dates=True)
    df_strat = pd.read_csv(path_strat, index_col=0, parse_dates=True)
    
    # 2. Define Regime S (High Correlation)
    # Target Assets for Correlation Proxy
    target_assets = ['US_Stock_XR', 'US_Bond_10Y_XR', 'US_Credit_XR', 'Commodities_XR']
    target_assets = [c for c in target_assets if c in df_assets.columns]
    
    print("   Calculating Rolling 12m Correlation...")
    # Calculate Rolling Correlation Matrix
    rolling_corr = df_assets[target_assets].rolling(12).corr()
    
    # Extract Average Off-Diagonal Correlation per date
    dates = df_strat.index
    avg_corrs = []
    
    for d in dates:
        try:
            corr_mat = rolling_corr.loc[d]
            n_assets = corr_mat.shape[0]
            if n_assets > 1:
                # Average of off-diagonal elements
                # (Sum of all elements - Sum of diagonal (N)) / (N^2 - N)
                avg_rho = (corr_mat.values.sum() - n_assets) / (n_assets*n_assets - n_assets)
            else:
                avg_rho = np.nan
            avg_corrs.append(avg_rho)
        except KeyError:
            avg_corrs.append(np.nan)
            
    df_strat['Avg_Corr'] = avg_corrs
    df_strat = df_strat.dropna()
    
    # Define Threshold for "Stress Set S"
    # We use Top 20% of correlation months
    threshold = df_strat['Avg_Corr'].quantile(0.80)
    mask_S = df_strat['Avg_Corr'] >= threshold
    
    print(f"   Regime S Defined: Correlation >= {threshold:.2f} (N={sum(mask_S)} months)")
    
    # 3. Perform Bootstrap Test
    # Variable: Excess Return Difference (ERC - Naive)
    diff_series = df_strat['ERC_XR'] - df_strat['Naive_XR']
    
    mu_S, p_val, dist = conditional_block_bootstrap(
        diff_series, mask_S, n_sims=5000, block_size=12
    )
    
    print(f"\n📊 Hypothesis H2 Results (Regime S):")
    print(f"   Actual Diff (Delta mu_S): {mu_S:.2%}")
    print(f"   P-Value (One-sided):      {p_val:.4f}")
    
    if p_val < 0.05:
        print("   ✅ Result: REJECT H0. ERC significantly underperforms in high correlation.")
    else:
        print("   ❌ Result: FAIL TO REJECT H0. Underperformance is not statistically significant.")

    # 4. Visualization: Histogram of Delta mu_S
    plt.figure(figsize=(10, 6))
    
    # Histogram
    plt.hist(dist, bins=50, color='#9467bd', alpha=0.6, density=True, label='Bootstrap Dist. ($\Delta \mu_S$)')
    
    # H0 Boundary (Zero)
    plt.axvline(0, color='red', ls='--', lw=2, label='Null Hypothesis ($\Delta \mu_S \geq 0$)')
    
    # Actual Statistic
    plt.axvline(mu_S, color='gold', lw=3, label=f'Actual ({mu_S:.2%})')
    
    # Styling
    plt.title(f'Hypothesis 2: Cost of Complexity in Regime S\n$\Delta \mu_S$ (ERC - Naive) | $P$-Value = {p_val:.4f}')
    plt.xlabel('Annualized Excess Return Difference')
    plt.ylabel('Probability Density')
    plt.legend(loc='upper left')
    plt.grid(True, alpha=0.2)
    
    # Save
    save_path = os.path.join(PLOT_DIR, 'significance_h2_bootstrap_conditional.png')
    plt.savefig(save_path)
    print(f"\n✅ Plot Saved: {save_path}")

if __name__ == "__main__":
    run_conditional_test()