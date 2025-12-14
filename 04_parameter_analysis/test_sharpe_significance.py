# 05_component_rules/test_sharpe_significance.py
# (或者你的 04_parameter_analysis/test_sharpe_significance.py)

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
import sys

# 路径魔法
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
TARGET_DIR_03 = os.path.join(PROJECT_ROOT, '03_1_strategy_construction')
if TARGET_DIR_03 not in sys.path:
    sys.path.append(TARGET_DIR_03)

PLOT_DIR = os.path.join(PROJECT_ROOT, 'outputs', 'plots', '05_component_rules')
if not os.path.exists(PLOT_DIR): os.makedirs(PLOT_DIR)

def block_bootstrap_p_value(series_a, series_b, n_sims=5000, block_size=12):
    """
    使用 Circular Block Bootstrap 计算 Sharpe 差异的 P-Value
    保留时间序列的自相关性。
    H0: Sharpe(A) <= Sharpe(B)
    """
    # 1. 对齐数据
    df = pd.DataFrame({'A': series_a, 'B': series_b}).dropna()
    n = len(df)
    
    # 计算实际 Sharpe 差
    # 加上 1e-8 防止分母为0
    sharpe_a = df['A'].mean() / df['A'].std() * np.sqrt(12)
    sharpe_b = df['B'].mean() / df['B'].std() * np.sqrt(12)
    diff_actual = sharpe_a - sharpe_b
    
    # 2. Block Bootstrap
    # 我们将数据视为环形 (Circular)，以便处理边界
    # 将 DataFrame 转为 numpy 数组加速
    data_vals = df.values # (n, 2)
    
    # 预先生成随机起始点
    # 我们需要构建 n_sims 个长度为 n 的序列
    # 每次抽 n/block_size 个块
    n_blocks = int(np.ceil(n / block_size))
    
    diffs_sim = []
    
    np.random.seed(42)
    
    print(f"      Running {n_sims} simulations (Block Size={block_size})...")
    
    for _ in range(n_sims):
        # 随机选择块的起始索引
        start_indices = np.random.randint(0, n, n_blocks)
        
        # 构建重采样索引
        indices = []
        for start in start_indices:
            # 生成一个块的索引 [start, start+1, ..., start+block-1]
            # 使用取模运算实现环形数据
            block_idxs = np.arange(start, start + block_size) % n
            indices.extend(block_idxs)
            
        # 截取前 n 个 (因为 n_blocks * block_size 可能 > n)
        indices = indices[:n]
        
        # 抽取样本
        samp = data_vals[indices] # (n, 2)
        samp_a = samp[:, 0]
        samp_b = samp[:, 1]
        
        # 计算该样本的 Sharpe 差
        s_a = samp_a.mean() / (samp_a.std() + 1e-8) * np.sqrt(12)
        s_b = samp_b.mean() / (samp_b.std() + 1e-8) * np.sqrt(12)
        
        diffs_sim.append(s_a - s_b)
        
    diffs_sim = np.array(diffs_sim)
    
    # 3. 计算单侧 P-Value
    # P(diff <= 0)
    p_value = (diffs_sim <= 0).mean()
    
    return diff_actual, p_value, diffs_sim

def run_significance_test():
    print("🚀 [Significance] Starting Institutional-Grade Bootstrap Test...")
    
    # 读取数据
    res_path = os.path.join(PROJECT_ROOT, 'data', 'processed', 'strategy_results.csv')
    if not os.path.exists(res_path):
        print("❌ Strategy results missing.")
        return
    df = pd.read_csv(res_path, index_col=0, parse_dates=True)
    
    # ---------------------------------------------------------
    # Test 1: Academic RP vs SP500 (Paper Core)
    # ---------------------------------------------------------
    print("\n   [Test 1] Academic RP (Target Equity Vol) vs SP500")
    # 注意：这里要用 Academic 版本（无 Cap，对标 Equity Vol）
    # 如果你之前的 main_runner 是 "Dual-Track" 版本，你应该有 RP_Academic_XR
    # 且它对标的是 SP500 Vol。
    
    col_acad = 'RP_Academic_XR'
    col_mkt = 'Bench_SP500_XR'
    
    if col_acad in df.columns and col_mkt in df.columns:
        diff_1, p_1, dist_1 = block_bootstrap_p_value(df[col_acad], df[col_mkt])
        print(f"      Actual Diff: {diff_1:.4f} | P-Value: {p_1:.4f}")
        res_1 = "SIGNIFICANT" if p_1 < 0.05 else "NOT SIGNIFICANT"
        print(f"      Result: {res_1}")
    else:
        print("      ⚠️ Columns missing for Test 1.")
        diff_1, p_1, dist_1 = 0, 1, []

    # ---------------------------------------------------------
    # Test 2: Retail RP vs 60/40 (Extension / Policy)
    # ---------------------------------------------------------
    print("\n   [Test 2] Retail RP (Target 60/40 Vol) vs 60/40")
    
    col_retail = 'RP_Retail_XR'
    col_6040 = 'Bench_6040_XR'
    
    if col_retail in df.columns and col_6040 in df.columns:
        diff_2, p_2, dist_2 = block_bootstrap_p_value(df[col_retail], df[col_6040])
        print(f"      Actual Diff: {diff_2:.4f} | P-Value: {p_2:.4f}")
        res_2 = "SIGNIFICANT" if p_2 < 0.05 else "NOT SIGNIFICANT"
        print(f"      Result: {res_2}")
    else:
        print("      ⚠️ Columns missing for Test 2.")
        diff_2, p_2, dist_2 = 0, 1, []

    # ---------------------------------------------------------
    # 画图 (双子图)
    # ---------------------------------------------------------
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    
    # Plot 1
    if len(dist_1) > 0:
        axes[0].hist(dist_1, bins=50, color='#1f77b4', alpha=0.7, density=True)
        axes[0].axvline(0, color='red', ls='--', lw=2, label='Zero')
        axes[0].axvline(diff_1, color='gold', lw=3, label=f'Actual ({diff_1:.2f})')
        axes[0].set_title(f'Paper Core: RP Academic vs SP500\nP-Value = {p_1:.4f} ({res_1})')
        axes[0].legend()
    
    # Plot 2
    if len(dist_2) > 0:
        axes[1].hist(dist_2, bins=50, color='#2ca02c', alpha=0.7, density=True)
        axes[1].axvline(0, color='red', ls='--', lw=2, label='Zero')
        axes[1].axvline(diff_2, color='gold', lw=3, label=f'Actual ({diff_2:.2f})')
        axes[1].set_title(f'Extension: RP Retail vs 60/40\nP-Value = {p_2:.4f} ({res_2})')
        axes[1].legend()
        
    plt.tight_layout()
    save_path = os.path.join(PLOT_DIR, 'significance_block_bootstrap.png')
    plt.savefig(save_path)
    print(f"\n✅ Dual Significance Plot Saved: {save_path}")


    # ---------------------------------------------------------
    # Test 3: The "Golden Era" Analysis (1993 - 2020)
    # ---------------------------------------------------------
    print("\n   [Test 3] Regime Check: Retail RP vs 60/40 (Pre-2021)")
    print("      Hypothesis: RP worked perfectly before the Inflation Shock.")
    
    # 切片数据：截止到 2020 年底
    df_pre_2021 = df.loc[:'2020-12-31']
    
    if col_retail in df_pre_2021.columns:
        diff_3, p_3, dist_3 = block_bootstrap_p_value(
            df_pre_2021[col_retail], 
            df_pre_2021[col_6040]
        )
        print(f"      Time Range: {df_pre_2021.index[0].date()} -> {df_pre_2021.index[-1].date()}")
        print(f"      Actual Diff: {diff_3:.4f} | P-Value: {p_3:.4f}")
        res_3 = "SIGNIFICANT" if p_3 < 0.05 else "NOT SIGNIFICANT"
        print(f"      Result: {res_3}")
        
        # 补画一张图
        plt.figure(figsize=(8, 5))
        plt.hist(dist_3, bins=50, color='gold', alpha=0.7, density=True, label='Bootstrap Dist.')
        plt.axvline(0, color='red', ls='--', lw=2, label='Zero')
        plt.axvline(diff_3, color='purple', lw=3, label=f'Actual ({diff_3:.2f})')
        plt.title(f'Golden Era (1993-2020): RP Retail vs 60/40\nP-Value = {p_3:.4f} ({res_3})')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.savefig(os.path.join(PLOT_DIR, 'significance_golden_era.png'))
        print(f"✅ Golden Era Plot Saved.")


    # ---------------------------------------------------------
    # Test 4: The "Theoretical Alpha" Check (Academic vs 60/40, Pre-2021)
    # ---------------------------------------------------------
    print("\n   [Test 4] Theoretical Check: Academic RP vs 60/40 (Pre-2021)")
    print("      Hypothesis: Without frictions, RP should win significantly.")
    
    # 使用 Academic 版本 (无 Spread, 10x Cap, Target Equity Vol)
    # 注意：Academic 对标的是 Equity Vol (15%)，60/40 是 (9%)
    # 直接比 Sharpe 是公平的，因为 Sharpe 已经除以了波动率
    col_acad = 'RP_Academic_XR' 
    
    if col_acad in df_pre_2021.columns:
        diff_4, p_4, dist_4 = block_bootstrap_p_value(
            df_pre_2021[col_acad], 
            df_pre_2021[col_6040]
        )
        print(f"      Actual Diff: {diff_4:.4f} | P-Value: {p_4:.4f}")
        res_4 = "SIGNIFICANT" if p_4 < 0.05 else "NOT SIGNIFICANT"
        print(f"      Result: {res_4}")

if __name__ == "__main__":
    run_significance_test()