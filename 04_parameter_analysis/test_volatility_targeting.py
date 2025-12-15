# 04_parameter_analysis/validate_vol_targeting.py

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
import sys

# 路径设置
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, 'data', 'processed')
PLOT_DIR = os.path.join(PROJECT_ROOT, 'outputs', 'plots', '04_sensitivity')

if not os.path.exists(PLOT_DIR):
    os.makedirs(PLOT_DIR)

def run_vol_validation():
    print("🚀 [Validation] Generating Realized vs Target Volatility Plot...")
    
    # 1. 读取 Strategy Results
    df = pd.read_csv(os.path.join(DATA_DIR, 'strategy_results.csv'), index_col=0, parse_dates=True)
    
    # 2. 计算 Realized Volatility (Rolling 36M, Annualized)
    # 我们用 36个月滚动窗口来检验“长期波动率控制”的效果
    window = 36
    
    # Target (Benchmark 60/40) 的实际波动率
    vol_target_realized = df['Bench_6040_TR'].rolling(window).std() * np.sqrt(12)
    
    # RP Strategy (Academic/Levered) 的实际波动率
    vol_rp_realized = df['RP_Academic_TR'].rolling(window).std() * np.sqrt(12)
    
    # RP Unlevered (原始) 的实际波动率 (用于对比，展示如果不加杠杆波动率多低)
    vol_rp_raw_realized = df['RP_Unlevered_TR'].rolling(window).std() * np.sqrt(12)
    
    # 3. 绘图
    plt.figure(figsize=(12, 6))
    
    # Target (Benchmark)
    plt.plot(vol_target_realized.index, vol_target_realized, 
             color='black', linestyle='--', linewidth=2, label='Target Volatility (Benchmark 60/40)')
    
    # RP Levered (Result)
    plt.plot(vol_rp_realized.index, vol_rp_realized, 
             color='#1f77b4', linewidth=2, alpha=0.9, label='Realized Volatility (Levered RP)')
    
    # RP Unlevered (Raw) - 可选，画出来对比更强烈
    plt.plot(vol_rp_raw_realized.index, vol_rp_raw_realized, 
             color='orange', linestyle='-', linewidth=1, alpha=0.6, label='Unlevered Volatility (Raw RP)')

    plt.title('Validation of Volatility Targeting Engine (1990-2024)')
    plt.ylabel('Annualized Volatility (36m Rolling)')
    plt.legend(loc='upper right')
    plt.grid(True, alpha=0.3)
    

    save_path = os.path.join(PLOT_DIR, 'valid_05_realized_vs_target_vol.png')
    plt.savefig(save_path)
    print(f"✅ Plot Saved: {save_path}")

if __name__ == "__main__":
    run_vol_validation()