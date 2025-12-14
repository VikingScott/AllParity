# 07_trend_following/test_trend_significance.py

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
import sys

# 路径设置
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, 'data', 'processed')
PLOT_DIR = os.path.join(PROJECT_ROOT, 'outputs', 'plots', '07_trend_following')

if not os.path.exists(PLOT_DIR):
    os.makedirs(PLOT_DIR)

def block_bootstrap(series_test, series_ctrl, n_sims=5000, block_size=12):
    """
    Block Bootstrap 检验 Sharpe 差异显著性
    """
    # 对齐数据
    df = pd.DataFrame({'T': series_test, 'C': series_ctrl}).dropna()
    
    # 1. 计算实际统计量差异 (Actual Diff)
    # Sharpe
    sharpe_t = df['T'].mean() / df['T'].std() * np.sqrt(12)
    sharpe_c = df['C'].mean() / df['C'].std() * np.sqrt(12)
    diff_sharpe_actual = sharpe_t - sharpe_c
    
    # Max Drawdown (辅助指标，不一定做 P-value，但在 Trend 中很重要)
    # 简单起见，Bootstrap 主要检验 Sharpe，DD 差异直接看分布很难定义 P-value (因为路径依赖)
    
    n = len(df)
    data_vals = df.values
    diffs = []
    
    np.random.seed(42) # 复现性
    
    print(f"   Bootstrapping {n_sims} times (Block Size={block_size})...")
    
    for _ in range(n_sims):
        # 随机采样块
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
        
    # 计算 P-Value (H0: Trend <= Naive)
    # P-Value = Bootstrap 分布中 Diff <= 0 的比例
    p_value = (np.array(diffs) <= 0).mean()
    
    return diff_sharpe_actual, p_value, diffs

def run_significance_test():
    print("🚀 [Trend Test] Significance Analysis (Trend vs Naive)...")
    
    # 1. 读取回报数据
    path = os.path.join(DATA_DIR, 'trend_vs_naive_returns.csv')
    if not os.path.exists(path):
        print("❌ Data missing.")
        return
        
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    
    # 2. 运行检验
    diff, p, dist = block_bootstrap(df['Trend_XR'], df['Naive_XR'])
    
    print(f"\n📊 Test Results (1990-2024):")
    print(f"   Actual Sharpe Diff: {diff:.4f}")
    print(f"   P-Value: {p:.4f} (Probability that improvement is luck)")
    
    if p < 0.05:
        print("   ✅ Result is Statistically Significant (< 5%)")
    elif p < 0.10:
        print("   ⚠️ Result is Marginally Significant (< 10%)")
    else:
        print("   ❌ Result is NOT Significant (Trend improvement might be noise)")

    # 3. 画分布图
    plt.figure(figsize=(10, 6))
    plt.hist(dist, bins=50, alpha=0.7, color='#2ca02c', density=True, label='Bootstrap Distribution (H0)')
    plt.axvline(diff, color='gold', lw=3, label=f'Actual Diff (+{diff:.2f})')
    plt.axvline(0, color='gray', ls='--', lw=1)
    
    plt.title(f'Sharpe Ratio Improvement: Trend vs Naive\nP-Value = {p:.4f}')
    plt.xlabel('Sharpe Difference')
    plt.ylabel('Probability Density')
    plt.legend()
    plt.grid(True, alpha=0.2)
    
    save_path = os.path.join(PLOT_DIR, 'trend_test_significance.png')
    plt.savefig(save_path)
    print(f"✅ Plot saved: {save_path}")

if __name__ == "__main__":
    run_significance_test()