# 05_erc_extensions/analysis_why_erc_failed.py

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import os
import sys

# 路径设置
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, 'data', 'processed')
PLOT_DIR = os.path.join(PROJECT_ROOT, 'outputs', 'plots', '06_erc_extension')

def analyze_erc_failure():
    print("🚀 [Forensics] Analyzing why ERC underperformed Naive...")
    
    # 1. 读取权重和收益数据
    # 我们需要之前生成的中间文件
    path_w = os.path.join(DATA_DIR, 'erc_vs_naive_weights.csv')
    path_r = os.path.join(DATA_DIR, 'erc_vs_naive_returns.csv')
    path_raw = os.path.join(DATA_DIR, 'data_final_returns.csv')
    
    if not os.path.exists(path_w):
        print("❌ Data missing. Run simulation first.")
        return
        
    df_w = pd.read_csv(path_w, index_col=0, parse_dates=True)
    df_r = pd.read_csv(path_r, index_col=0, parse_dates=True)
    df_raw = pd.read_csv(path_raw, index_col=0, parse_dates=True) # 为了算相关性
    
    # ========================================================
    # Analysis 1: 权重差异 (The Allocation Gap)
    # ========================================================
    # 提取股票和债券的权重
    # 假设列名是 ERC_US_Stock_XR, Naive_US_Stock_XR 等 (根据之前的脚本)
    # 我们需要找到对应的列名
    
    stock_col = [c for c in df_w.columns if 'Stock' in c and 'ERC' in c][0].replace('ERC_', '')
    bond_col = [c for c in df_w.columns if 'Bond' in c and 'ERC' in c][0].replace('ERC_', '')
    
    # 计算差异 (ERC - Naive)
    diff_stock = df_w[f'ERC_{stock_col}'] - df_w[f'Naive_{stock_col}']
    diff_bond = df_w[f'ERC_{bond_col}'] - df_w[f'Naive_{bond_col}']
    
    plt.figure(figsize=(12, 8))
    
    ax1 = plt.subplot(2, 1, 1)
    ax1.plot(diff_stock.index, diff_stock, color='blue', label='ERC - Naive (Stock Weight)')
    ax1.axhline(0, color='black', ls='--')
    ax1.fill_between(diff_stock.index, diff_stock, 0, where=(diff_stock<0), color='red', alpha=0.1, label='ERC Underweight Stocks')
    ax1.set_title('Did ERC hold less Equity? (Weight Difference)')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    ax2 = plt.subplot(2, 1, 2)
    ax2.plot(diff_bond.index, diff_bond, color='orange', label='ERC - Naive (Bond Weight)')
    ax2.axhline(0, color='black', ls='--')
    ax2.fill_between(diff_bond.index, diff_bond, 0, where=(diff_bond>0), color='orange', alpha=0.1, label='ERC Overweight Bonds')
    ax2.set_title('Did ERC hold more Bonds? (Weight Difference)')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(os.path.join(PLOT_DIR, 'analysis_01_weight_diff.png'))
    print("✅ Analysis 1 Saved: Weight Difference")
    
    # ========================================================
    # Analysis 2: 相关性惩罚 (The Correlation Penalty)
    # ========================================================
    # 计算股债滚动相关性 (36个月)
    stock_ret = df_raw[stock_col]
    bond_ret = df_raw[bond_col]
    rolling_corr = stock_ret.rolling(36).corr(bond_ret)
    
    # 计算 ERC 相对 Naive 的超额收益 (Rolling 12m)
    # 我们看 ERC 什么时候跑输
    rel_ret = df_r['ERC_XR'] - df_r['Naive_XR']
    rolling_rel_perf = rel_ret.rolling(12).sum()
    
    # 对齐数据
    df_analysis = pd.DataFrame({
        'Correlation': rolling_corr,
        'ERC_Outperformance': rolling_rel_perf
    }).dropna()
    
    plt.figure(figsize=(10, 6))
    # 散点图
    sns.scatterplot(data=df_analysis, x='Correlation', y='ERC_Outperformance', alpha=0.6)
    
    # 加趋势线
    sns.regplot(data=df_analysis, x='Correlation', y='ERC_Outperformance', scatter=False, color='red')
    
    plt.axhline(0, color='black', ls='--')
    plt.axvline(0, color='black', ls='--')
    plt.title('The Correlation Penalty: Does ERC lose when Correlation rises?')
    plt.xlabel('Stock-Bond Correlation (36m)')
    plt.ylabel('ERC Relative Performance (12m)')
    
    plt.savefig(os.path.join(PLOT_DIR, 'analysis_02_corr_penalty.png'))
    print("✅ Analysis 2 Saved: Correlation Scatter")

    # ========================================================
    # Analysis 3: 2022 年死因特写 (The 2022 Autopsy)
    # ========================================================
    # 聚焦 2021-2023
    start_date = '2021-01-01'
    end_date = '2023-12-31'
    
    subset_w = df_w.loc[start_date:end_date]
    subset_r = df_r.loc[start_date:end_date]
    
    if len(subset_w) > 0:
        fig, ax1 = plt.subplots(figsize=(12, 6))
        
        # 画累计收益
        cum_naive = (1 + subset_r['Naive_XR']).cumprod()
        cum_erc = (1 + subset_r['ERC_XR']).cumprod()
        
        ax1.plot(cum_naive.index, cum_naive, color='gray', ls='--', label='Naive Wealth')
        ax1.plot(cum_erc.index, cum_erc, color='blue', label='ERC Wealth')
        ax1.set_ylabel('Wealth')
        ax1.legend(loc='upper left')
        
        # 画债券权重差异 (右轴)
        ax2 = ax1.twinx()
        bond_diff = subset_w[f'ERC_{bond_col}'] - subset_w[f'Naive_{bond_col}']
        ax2.fill_between(bond_diff.index, bond_diff, 0, color='orange', alpha=0.2, label='ERC Bond Overweight')
        ax2.set_ylabel('ERC Excess Bond Weight')
        ax2.legend(loc='upper right')
        
        plt.title('2022 Autopsy: Did ERC die from Bond Overweighting?')
        plt.savefig(os.path.join(PLOT_DIR, 'analysis_03_2022_autopsy.png'))
        print("✅ Analysis 3 Saved: 2022 Autopsy")

if __name__ == "__main__":
    analyze_erc_failure()