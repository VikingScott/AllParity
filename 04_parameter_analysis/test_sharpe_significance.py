# 04_parameter_analysis/test_sharpe_significance.py

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy import stats
import os
import sys

# ==========================================
# 1. Path Configuration
# ==========================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, 'data', 'processed')
PLOT_DIR = os.path.join(PROJECT_ROOT, 'outputs', 'plots', '05_component_rules') # Storing in rules/validation folder

if not os.path.exists(PLOT_DIR):
    os.makedirs(PLOT_DIR)

# ==========================================
# 2. Statistical Engines
# ==========================================

def calculate_newey_west_alpha(y_series, x_series, lags=12):
    """
    Calculates Alpha and its t-statistic using Newey-West HAC standard errors
    using pure NumPy (no statsmodels dependency).
    Model: y = alpha + beta * x + epsilon
    """
    # 1. Prepare Data
    df = pd.DataFrame({'Y': y_series, 'X': x_series}).dropna()
    nobs = len(df)
    
    Y = df['Y'].values
    # Add constant (intercept) column to X
    X = np.column_stack((np.ones(nobs), df['X'].values))
    
    # 2. OLS Estimation: Beta = (X'X)^-1 X'Y
    XTX = np.dot(X.T, X)
    XTX_inv = np.linalg.inv(XTX)
    beta = np.dot(np.dot(XTX_inv, X.T), Y)
    
    alpha = beta[0] # Intercept is the first coefficient
    
    # 3. Calculate Residuals
    residuals = Y - np.dot(X, beta)
    
    # 4. Newey-West Covariance Matrix Calculation
    # The Variance-Covariance matrix of beta is given by:
    # V = (X'X)^-1 * S * (X'X)^-1
    # Where S is the HAC estimator of the outer product of gradients
    
    # S_0 (Variance part)
    # X.T * (residuals^2) @ X
    # Using broadcasting for efficiency: (X * residuals[:, None]).T @ (X * residuals[:, None])
    Z = X * residuals[:, np.newaxis]
    S = np.dot(Z.T, Z)
    
    # Add Lag terms (Covariance part)
    for l in range(1, lags + 1):
        # Bartlett Kernel Weight
        weight = 1 - l / (lags + 1)
        
        # Calculate Gamma_l = sum(Z_t * Z_{t-l}.T)
        # Z[l:] corresponds to t (from l to T-1)
        # Z[:-l] corresponds to t-l (from 0 to T-1-l)
        Z_t = Z[l:]
        Z_tm1 = Z[:-l]
        
        Gamma_l = np.dot(Z_t.T, Z_tm1)
        
        # Add to S: weight * (Gamma_l + Gamma_l.T)
        S += weight * (Gamma_l + Gamma_l.T)
        
    # Calculate Variance-Covariance Matrix of Coefficients
    V_beta = np.dot(np.dot(XTX_inv, S), XTX_inv)
    
    # 5. Extract Statistics
    se_alpha = np.sqrt(V_beta[0, 0])
    t_stat = alpha / (se_alpha + 1e-16)
    
    # P-value (two-tailed t-test)
    df_resid = nobs - X.shape[1]
    p_value = 2 * (1 - stats.t.cdf(np.abs(t_stat), df=df_resid))
    
    return alpha, t_stat, p_value, None

def block_bootstrap_stats(series_test, series_ctrl, n_sims=5000, block_size=12, ci_level=0.90):
    """
    Performs Circular Block Bootstrap to test H0: Sharpe(Test) <= Sharpe(Ctrl).
    Returns P-Value, Confidence Intervals, and the full distribution.
    """
    # 1. Align & Prep Data
    df = pd.DataFrame({'T': series_test, 'C': series_ctrl}).dropna()
    n = len(df)
    data_vals = df.values
    
    # Actual Sharpe Difference
    sharpe_t = df['T'].mean() / df['T'].std() * np.sqrt(12)
    sharpe_c = df['C'].mean() / df['C'].std() * np.sqrt(12)
    diff_actual = sharpe_t - sharpe_c
    
    # 2. Bootstrap Loop
    n_blocks = int(np.ceil(n / block_size))
    diffs_sim = []
    
    # Fixed seed for reproducibility
    np.random.seed(42)
    
    for _ in range(n_sims):
        # Random starting indices for blocks
        start_indices = np.random.randint(0, n, n_blocks)
        
        # Construct indices (Circular)
        indices = []
        for start in start_indices:
            block_idxs = np.arange(start, start + block_size) % n
            indices.extend(block_idxs)
        indices = indices[:n]
        
        # Sample
        samp = data_vals[indices]
        
        # Calculate Sharpe Diff for this sample
        # Add small epsilon to std to avoid division by zero in weird samples
        s_t = samp[:, 0].mean() / (samp[:, 0].std() + 1e-8) * np.sqrt(12)
        s_c = samp[:, 1].mean() / (samp[:, 1].std() + 1e-8) * np.sqrt(12)
        diffs_sim.append(s_t - s_c)
        
    diffs_sim = np.array(diffs_sim)
    
    # 3. Statistics
    # H0: Diff <= 0. P-value is fraction of sims where Diff <= 0.
    p_value = (diffs_sim <= 0).mean()
    
    # Confidence Interval (e.g., 90% CI is 5th to 95th percentile)
    lower_pct = (1 - ci_level) / 2 * 100
    upper_pct = (1 + ci_level) / 2 * 100
    ci_lower = np.percentile(diffs_sim, lower_pct)
    ci_upper = np.percentile(diffs_sim, upper_pct)
    
    return diff_actual, p_value, ci_lower, ci_upper, diffs_sim

# ==========================================
# 3. Main Test Runner
# ==========================================

def run_hypothesis_1_test():
    print("🚀 [H1 Test] Running Risk Parity vs 60/40 Significance Analysis...")
    
    # 1. Load Data
    res_path = os.path.join(PROJECT_ROOT, 'data', 'processed', 'strategy_results.csv')
    if not os.path.exists(res_path):
        print(f"❌ File not found: {res_path}")
        return
    df = pd.read_csv(res_path, index_col=0, parse_dates=True)
    
    # Define Target Columns for H1
    # We compare Net Retail RP vs Bench 60/40
    col_test = 'RP_Retail_XR'
    col_ctrl = 'Bench_6040_XR'
    
    if col_test not in df.columns or col_ctrl not in df.columns:
        print("❌ Required columns missing.")
        return

    # ---------------------------------------------------------
    # Part A: Primary Block Bootstrap (Block=12)
    # ---------------------------------------------------------
    print("\n🔹 Primary Test: Block Bootstrap (Block=12m, N=5000)")
    diff, p, ci_low, ci_high, dist = block_bootstrap_stats(
        df[col_test], df[col_ctrl], n_sims=5000, block_size=12
    )
    
    print(f"   Actual Sharpe Diff: {diff:.4f}")
    print(f"   P-Value (H0<=0):    {p:.4f}")
    print(f"   90% Conf. Interval: [{ci_low:.4f}, {ci_high:.4f}]")
    
    significance = "SIGNIFICANT" if p < 0.05 else ("MARGINAL" if p < 0.10 else "INSIGNIFICANT")
    print(f"   Conclusion:         {significance}")

    # ---------------------------------------------------------
    # Part B: Robustness - Block Size Sensitivity
    # ---------------------------------------------------------
    print("\n🔹 Robustness 1: Block Length Sensitivity")
    block_sizes = [6, 12, 24, 36, 48]
    sensitivity_res = []
    
    for b in block_sizes:
        _, p_val, _, _, _ = block_bootstrap_stats(
            df[col_test], df[col_ctrl], n_sims=2000, block_size=b
        )
        sensitivity_res.append({'Block Size': b, 'P-Value': p_val})
        
    df_sens = pd.DataFrame(sensitivity_res)
    print(df_sens.to_string(index=False))

    # ---------------------------------------------------------
    # Part C: Robustness - Newey-West Alpha
    # ---------------------------------------------------------
    print("\n🔹 Robustness 2: Newey-West Alpha (Regression vs 60/40)")
    alpha, t_stat, p_reg, _ = calculate_newey_west_alpha(df[col_test], df[col_ctrl])
    
    # Alpha is monthly here, usually we report annualized alpha for context
    alpha_ann = alpha * 12
    print(f"   Annualized Alpha:   {alpha_ann:.2%}")
    print(f"   NW t-statistic:     {t_stat:.4f}")
    print(f"   P-Value (2-sided):  {p_reg:.4f}")
    
    reg_sig = "SIGNIFICANT" if p_reg < 0.05 else "INSIGNIFICANT"
    print(f"   Conclusion:         {reg_sig}")

    # ---------------------------------------------------------
    # Part D: Visualization (Publication Ready)
    # ---------------------------------------------------------
    plt.figure(figsize=(10, 6))
    
    # Histogram of Bootstrap Distribution
    plt.hist(dist, bins=50, color='#1f77b4', alpha=0.6, density=True, label='Bootstrap Dist. (H0)')
    
    # Actual Difference Line
    plt.axvline(diff, color='gold', lw=3, label=f'Actual Diff (+{diff:.2f})')
    
    # Zero Line
    plt.axvline(0, color='red', ls='--', lw=1.5, label='Zero (H0 Boundary)')
    
    # CI Area
    plt.axvspan(ci_low, ci_high, color='gray', alpha=0.1, label='90% CI')
    
    plt.title(f'Hypothesis 1 Test: RP (Retail) vs 60/40\nP-Value={p:.4f} | 90% CI: [{ci_low:.2f}, {ci_high:.2f}]')
    plt.xlabel('Sharpe Ratio Difference (RP - 60/40)')
    plt.ylabel('Probability Density')
    plt.legend(loc='upper left')
    plt.grid(True, alpha=0.2)
    
    save_path = os.path.join(PLOT_DIR, 'significance_h1_bootstrap.png')
    plt.savefig(save_path)
    print(f"\n✅ Plot Saved: {save_path}")

if __name__ == "__main__":
    run_hypothesis_1_test()