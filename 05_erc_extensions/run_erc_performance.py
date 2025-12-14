# 05_erc_extensions/run_erc_performance_report.py

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
import sys

# 路径设置
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, 'data', 'processed')
# 注意：这里我们沿用之前的 Plot 目录习惯，或者你可以改为 outputs/plots/05_erc_extension
PLOT_DIR = os.path.join(PROJECT_ROOT, 'outputs', 'plots', '06_erc_extension') 

if not os.path.exists(PLOT_DIR):
    os.makedirs(PLOT_DIR)

def calculate_metrics(series):
    """计算核心评价指标"""
    # 1. CAGR
    total_ret = (1 + series).prod()
    n_years = len(series) / 12.0
    cagr = total_ret ** (1 / n_years) - 1
    
    # 2. Volatility (Annualized)
    vol = series.std() * np.sqrt(12)
    
    # 3. Sharpe Ratio (假设 Rf 已包含在 XR 中或者对比的是 XR，这里简单处理)
    # 如果 series 是 XR (超额收益)，Sharpe = Mean / Std
    sharpe = series.mean() / series.std() * np.sqrt(12)
    
    # 4. Max Drawdown
    cum_ret = (1 + series).cumprod()
    peak = cum_ret.cummax()
    drawdown = (cum_ret - peak) / peak
    max_dd = drawdown.min()
    
    # 5. Calmar Ratio
    calmar = cagr / abs(max_dd) if max_dd != 0 else np.nan
    
    return {
        'CAGR': cagr,
        'Volatility': vol,
        'Sharpe': sharpe,
        'Max_Drawdown': max_dd,
        'Calmar': calmar
    }

def run_performance_report():
    print("🚀 [ERC Report] Generating Performance Charts & Metrics...")
    
    # 1. 读取收益数据
    file_path = os.path.join(DATA_DIR, 'erc_vs_naive_returns.csv')
    if not os.path.exists(file_path):
        print("❌ Data missing. Run 'run_erc_simulation.py' first.")
        return
        
    df = pd.read_csv(file_path, index_col=0, parse_dates=True)
    
    # 2. 计算累计净值 (Cumulative Wealth)
    # 假设 CSV 里存的是 XR (超额收益)，我们需要加回 Risk_Free 得到 TR (总收益) 才能画净值
    # 如果 CSV 里有 Risk_Free 列
    if 'Risk_Free' in df.columns:
        rf = df['Risk_Free']
        df_tr = pd.DataFrame()
        df_tr['Naive_TR'] = df['Naive_XR'] + rf
        df_tr['ERC_TR'] = df['ERC_XR'] + rf
        df_tr['Bench_6040_TR'] = df['Bench_6040_XR'] + rf # 假设 Bench 也是 XR
    else:
        # 如果没有 Rf，就直接画 XR (不推荐，但作为 fallback)
        print("⚠️ Warning: Risk_Free not found, plotting Excess Returns.")
        df_tr = df[['Naive_XR', 'ERC_XR', 'Bench_6040_XR']]

    cum_wealth = (1 + df_tr).cumprod()
    
    # 3. 计算回撤 (Drawdown)
    drawdowns = (cum_wealth / cum_wealth.cummax()) - 1
    
    # ==========================================
    # 输出 1: 指标统计 CSV
    # ==========================================
    metrics = []
    for col in df_tr.columns:
        # 传入原始月度收益率计算指标
        if 'Naive' in col: name = 'Naive RP'
        elif 'ERC' in col: name = 'ERC RP'
        else: name = 'Bench 60/40'
        
        # 注意：计算指标最好用原始收益率，而不是累计净值
        ret_series = df_tr[col]
        m = calculate_metrics(ret_series)
        m['Strategy'] = name
        metrics.append(m)
        
    df_metrics = pd.DataFrame(metrics).set_index('Strategy')
    # 格式化输出
    print("\n📊 Performance Metrics:")
    print(df_metrics.style.format("{:.2%}").to_string())
    
    metrics_path = os.path.join(PLOT_DIR, 'erc_performance_metrics.csv')
    df_metrics.to_csv(metrics_path)
    print(f"✅ Metrics CSV Saved: {metrics_path}")

    # ==========================================
    # 输出 2: 累计净值图 (Log Scale)
    # ==========================================
    plt.figure(figsize=(12, 7))
    plt.plot(cum_wealth['Naive_TR'], label='Naive RP (Baseline)', color='orange', linestyle='--', alpha=0.8)
    plt.plot(cum_wealth['ERC_TR'], label='ERC RP (Extension)', color='#1f77b4', linewidth=2)
    plt.plot(cum_wealth['Bench_6040_TR'], label='Benchmark 60/40', color='black', linestyle=':', linewidth=1)
    
    plt.yscale('log')
    plt.title('Cumulative Wealth: ERC vs Naive RP vs 60/40 (Log Scale)')
    plt.ylabel('Wealth Index ($)')
    plt.grid(True, which="both", ls="-", alpha=0.2)
    plt.legend()
    
    wealth_path = os.path.join(PLOT_DIR, 'erc_performance_wealth.png')
    plt.savefig(wealth_path)
    print(f"✅ Wealth Plot Saved: {wealth_path}")

    # ==========================================
    # 输出 3: 回撤图 (Drawdown)
    # ==========================================
    plt.figure(figsize=(12, 6))
    plt.plot(drawdowns['Naive_TR'], label='Naive RP', color='orange', linestyle='--', alpha=0.6)
    plt.plot(drawdowns['ERC_TR'], label='ERC RP', color='#1f77b4', linewidth=1.5)
    plt.plot(drawdowns['Bench_6040_TR'], label='60/40', color='black', linestyle=':', alpha=0.4)
    
    plt.fill_between(drawdowns.index, drawdowns['ERC_TR'], 0, color='#1f77b4', alpha=0.1)
    
    plt.title('Drawdown Profile: ERC vs Naive')
    plt.ylabel('Drawdown (%)')
    plt.grid(True, alpha=0.3)
    plt.legend()
    
    dd_path = os.path.join(PLOT_DIR, 'erc_performance_drawdown.png')
    plt.savefig(dd_path)
    print(f"✅ Drawdown Plot Saved: {dd_path}")

if __name__ == "__main__":
    run_performance_report()