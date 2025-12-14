# 07_trend_following/run_trend_performance_report.py

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

def calculate_metrics(series):
    """计算核心评价指标"""
    total_ret = (1 + series).prod()
    n_years = len(series) / 12.0
    cagr = total_ret ** (1 / n_years) - 1
    vol = series.std() * np.sqrt(12)
    sharpe = series.mean() / series.std() * np.sqrt(12)
    
    cum_ret = (1 + series).cumprod()
    peak = cum_ret.cummax()
    drawdown = (cum_ret - peak) / peak
    max_dd = drawdown.min()
    
    calmar = cagr / abs(max_dd) if max_dd != 0 else np.nan
    
    return {
        'CAGR': cagr,
        'Volatility': vol,
        'Sharpe': sharpe,
        'Max_Drawdown': max_dd,
        'Calmar': calmar
    }

def run_performance_report():
    print("🚀 [Trend Report] Generating Performance Charts & Metrics...")
    
    # 1. 读取收益数据
    ret_path = os.path.join(DATA_DIR, 'trend_vs_naive_returns.csv')
    w_path = os.path.join(DATA_DIR, 'trend_vs_naive_weights.csv')
    
    if not os.path.exists(ret_path) or not os.path.exists(w_path):
        print("❌ Data missing. Run 'run_trend_simulation.py' first.")
        return
        
    df_ret = pd.read_csv(ret_path, index_col=0, parse_dates=True)
    df_w = pd.read_csv(w_path, index_col=0, parse_dates=True)
    
    # 2. 计算累计净值 (Cumulative Wealth)
    if 'Risk_Free' in df_ret.columns:
        rf = df_ret['Risk_Free']
        df_tr = pd.DataFrame()
        df_tr['Naive_TR'] = df_ret['Naive_XR'] + rf
        df_tr['Trend_TR'] = df_ret['Trend_XR'] + rf
        df_tr['Bench_6040_TR'] = df_ret['Bench_6040_XR'] + rf
    else:
        print("⚠️ Warning: Risk_Free not found, plotting Excess Returns.")
        df_tr = df_ret[['Naive_XR', 'Trend_XR', 'Bench_6040_XR']]

    cum_wealth = (1 + df_tr).cumprod()
    drawdowns = (cum_wealth / cum_wealth.cummax()) - 1
    
    # ==========================================
    # 输出 1: 指标统计 CSV
    # ==========================================
    metrics = []
    for col in df_tr.columns:
        if 'Naive' in col: name = 'Naive RP'
        elif 'Trend' in col: name = 'Trend RP'
        else: name = 'Bench 60/40'
        
        m = calculate_metrics(df_tr[col])
        m['Strategy'] = name
        metrics.append(m)
        
    df_metrics = pd.DataFrame(metrics).set_index('Strategy')
    df_fmt = df_metrics.applymap(lambda x: f"{x:.2%}" if isinstance(x, (int, float)) else x)
    for col in ['Sharpe', 'Calmar']:
        if col in df_metrics.columns:
            df_metrics[col] = df_metrics[col].apply(lambda x: f"{x:.2f}")
            df_fmt[col] = df_metrics[col]

    print("\n📊 Trend Strategy Performance:")
    print("="*70)
    print(df_fmt.to_string())
    print("="*70)
    df_metrics.to_csv(os.path.join(PLOT_DIR, 'trend_performance_metrics.csv'))

    # ==========================================
    # 输出 2: 累计净值图 (Full History)
    # ==========================================
    plt.figure(figsize=(12, 7))
    plt.plot(cum_wealth.index, cum_wealth['Naive_TR'], label='Naive RP (Baseline)', color='orange', linestyle='--', alpha=0.6)
    plt.plot(cum_wealth.index, cum_wealth['Trend_TR'], label='Trend RP (Cash Reserve)', color='#2ca02c', linewidth=2)
    plt.plot(cum_wealth.index, cum_wealth['Bench_6040_TR'], label='Benchmark 60/40', color='black', linestyle=':', linewidth=1)
    
    plt.yscale('log')
    plt.title('Cumulative Wealth: Trend RP vs Naive RP (Log Scale)')
    plt.ylabel('Wealth Index ($)')
    plt.grid(True, which="both", ls="-", alpha=0.2)
    plt.legend()
    plt.savefig(os.path.join(PLOT_DIR, 'trend_performance_wealth.png'))

    # ==========================================
    # 输出 3: 回撤图 (Full History)
    # ==========================================
    plt.figure(figsize=(12, 6))
    plt.plot(drawdowns.index, drawdowns['Naive_TR'], label='Naive RP', color='gray', linestyle='--', alpha=0.6)
    plt.plot(drawdowns.index, drawdowns['Trend_TR'], label='Trend RP', color='#2ca02c', linewidth=1.5)
    plt.axvspan(pd.Timestamp('2022-01-01'), pd.Timestamp('2022-12-31'), color='red', alpha=0.1, label='2022 Crisis')
    plt.fill_between(drawdowns.index, drawdowns['Trend_TR'], 0, color='#2ca02c', alpha=0.1)
    
    plt.title('Drawdown Profile: Did Trend save us in 2022?')
    plt.ylabel('Drawdown (%)')
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.savefig(os.path.join(PLOT_DIR, 'trend_performance_drawdown.png'))

if __name__ == "__main__":
    run_performance_report()