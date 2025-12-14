# 05_erc_extension/test_erc_significance.py

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, 'data', 'processed')
PLOT_DIR = os.path.join(PROJECT_ROOT, 'outputs', 'plots', '06_erc_extension')

# ==========================================
# 修复点：自动创建输出文件夹
# ==========================================
if not os.path.exists(PLOT_DIR):
    os.makedirs(PLOT_DIR)

def block_bootstrap(series_test, series_ctrl, n_sims=5000, block_size=12):
    # 对齐数据
    df = pd.DataFrame({'T': series_test, 'C': series_ctrl}).dropna()
    
    # 计算实际 Sharpe 差
    sharpe_t = df['T'].mean() / df['T'].std() * np.sqrt(12)
    sharpe_c = df['C'].mean() / df['C'].std() * np.sqrt(12)
    diff_actual = sharpe_t - sharpe_c
    
    n = len(df)
    data_vals = df.values
    diffs = []
    
    np.random.seed(42)
    
    # Bootstrap
    for _ in range(n_sims):
        # 随机选择块的起始点
        starts = np.random.randint(0, n, int(np.ceil(n/block_size)))
        indices = []
        for s in starts:
            indices.extend((np.arange(s, s+block_size) % n))
        indices = indices[:n]
        
        samp = data_vals[indices]
        
        # 计算样本 Sharpe
        s_t = samp[:,0].mean() / (samp[:,0].std() + 1e-8) * np.sqrt(12)
        s_c = samp[:,1].mean() / (samp[:,1].std() + 1e-8) * np.sqrt(12)
        diffs.append(s_t - s_c)
        
    # 计算 P-Value (单侧检验: ERC 是否显著 > Naive)
    # H0: ERC <= Naive (Diff <= 0)
    # P-Value = Bootstrap 分布中 Diff <= 0 的比例
    # 如果实际 Diff 是负的，P-Value 会很大（接近 1），这是正常的
    p_value = (np.array(diffs) <= 0).mean()
    
    return diff_actual, p_value, diffs

def run_significance():
    print("🚀 [ERC Test] Bootstrap Significance (ERC vs Naive)...")
    
    path = os.path.join(DATA_DIR, 'erc_vs_naive_returns.csv')
    if not os.path.exists(path):
        print("❌ Data missing. Run simulation first.")
        return

    df = pd.read_csv(path, index_col=0, parse_dates=True)
    
    # 1. Overall Test
    diff, p, dist = block_bootstrap(df['ERC_XR'], df['Naive_XR'])
    
    print(f"   Overall Period (1990-2025):")
    print(f"   Sharpe Diff: {diff:.4f} | P-Value: {p:.4f}")
    
    # 2. Plot
    plt.figure(figsize=(10, 6))
    plt.hist(dist, bins=50, alpha=0.7, color='purple', density=True, label='Bootstrap Dist')
    plt.axvline(diff, color='gold', lw=3, label=f'Actual Diff ({diff:.2f})')
    plt.axvline(0, color='red', ls='--')
    plt.title(f'Sharpe Difference: ERC vs Naive\nP-Value={p:.4f}')
    plt.legend()
    
    save_path = os.path.join(PLOT_DIR, 'erc_03_sensitivity.png')
    plt.savefig(save_path)
    print(f"✅ Significance Plot Saved: {save_path}")

if __name__ == "__main__":
    run_significance()