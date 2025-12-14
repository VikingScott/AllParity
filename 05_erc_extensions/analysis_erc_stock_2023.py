# 05_erc_extensions/analysis_erc_2023_deep_dive.py

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
import sys

# 路径设置
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, 'data', 'processed')
PLOT_DIR = os.path.join(PROJECT_ROOT, 'outputs', 'plots', '06_erc_extension')

def analyze_2023_failure():
    print("🚀 [Deep Dive] Analyzing the 2023 Divergence...")
    
    # 1. 读取数据
    path_w = os.path.join(DATA_DIR, 'erc_vs_naive_weights.csv')
    path_r = os.path.join(DATA_DIR, 'erc_vs_naive_returns.csv')
    
    if not os.path.exists(path_w):
        print("❌ Data missing.")
        return
        
    df_w = pd.read_csv(path_w, index_col=0, parse_dates=True)
    df_r = pd.read_csv(path_r, index_col=0, parse_dates=True)
    
    # 聚焦 2022-2024
    start = '2022-01-01'
    end = '2024-12-31'
    df_w = df_w.loc[start:end]
    df_r = df_r.loc[start:end]
    
    # 2. 找到股票列名
    stock_col = [c for c in df_w.columns if 'Stock' in c and 'ERC' in c][0].replace('ERC_', '')
    
    # 3. 核心图表：股票权重对比
    # 我们不仅看权重，还要看 "权重 x 杠杆" (实际股票敞口)
    # 但这里简化看权重差异就已经很说明问题了
    
    w_erc_stock = df_w[f'ERC_{stock_col}']
    w_naive_stock = df_w[f'Naive_{stock_col}']
    diff_stock = w_erc_stock - w_naive_stock
    
    # 4. 累计收益对比 (2023 Only)
    df_2023 = df_r.loc['2023-01-01':'2023-12-31']
    cum_2023 = (1 + df_2023).cumprod()
    
    # ==========================
    # 画图
    # ==========================
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))
    
    # 子图 1: 2023 年谁赚了钱？
    ax1.plot(cum_2023.index, cum_2023['Naive_XR'], label='Naive RP (+AI Rally)', color='gray', ls='--')
    ax1.plot(cum_2023.index, cum_2023['ERC_XR'], label='ERC RP (Missed Rally)', color='red')
    ax1.set_title('2023 Performance Gap: Naive vs ERC')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # 子图 2: 谁拿了更多股票？
    ax2.plot(diff_stock.index, diff_stock, color='blue', lw=1.5)
    ax2.axhline(0, color='black', ls='--')
    ax2.fill_between(diff_stock.index, diff_stock, 0, where=(diff_stock<0), color='red', alpha=0.1, label='ERC Underweight Stocks')
    ax2.set_title(f'Stock Weight Difference (ERC - Naive): Did ERC sell stocks?')
    ax2.set_ylabel('Weight Diff')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    save_path = os.path.join(PLOT_DIR, 'analysis_04_stock_underweight.png')
    plt.savefig(save_path)
    print(f"✅ Deep Dive Plot Saved: {save_path}")

if __name__ == "__main__":
    analyze_2023_failure()