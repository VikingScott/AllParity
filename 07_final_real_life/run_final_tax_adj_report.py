# 07_final_real_life/run_final_report.py

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
import sys

# 路径设置
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, 'data', 'processed')
PLOT_DIR = os.path.join(PROJECT_ROOT, 'outputs', 'plots', '07_final_real_life')

from real_life_config import RealLifeConfig

def calculate_metrics_with_tax(series, tax_rate):
    """
    计算含税指标
    简化模型：Tax-Adjusted CAGR = Pre-Tax CAGR * (1 - Tax_Rate)
    这是一种保守的估计，假设利润最终都需要交税。
    """
    total_ret = (1 + series).prod()
    n_years = len(series) / 12.0
    cagr_gross = total_ret ** (1 / n_years) - 1
    
    # Tax Adjustment (Haircut on gains)
    # 如果 CAGR 是正的，扣税；如果是负的，假设没有抵扣（保守）
    if cagr_gross > 0:
        cagr_net = cagr_gross * (1 - tax_rate)
    else:
        cagr_net = cagr_gross
        
    vol = series.std() * np.sqrt(12)
    sharpe = series.mean() / series.std() * np.sqrt(12)
    
    # Calmar (Tax adjusted CAGR / Gross DD)
    cum_ret = (1 + series).cumprod()
    drawdown = (cum_ret / cum_ret.cummax()) - 1
    max_dd = drawdown.min()
    calmar = cagr_net / abs(max_dd) if max_dd != 0 else np.nan
    
    return {
        'CAGR (Pre-Tax)': cagr_gross,
        'CAGR (After-Tax)': cagr_net,
        'Tax Rate Used': tax_rate,
        'Volatility': vol,
        'Sharpe': sharpe,
        'Max_Drawdown': max_dd
    }

def run_final_report():
    print("🚀 [Grand Finale] Generating Comparison Report...")
    
    path = os.path.join(DATA_DIR, 'final_real_life_returns.csv')
    if not os.path.exists(path):
        print("❌ Run 'analysis_real_world_impact.py' first.")
        return
    
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    rf = df['Risk_Free']
    
    # 还原 Total Return (Net of Fees)
    # 我们对比：Naive(Net), ERC(Net), Trend(Net)
    df_tr = pd.DataFrame()
    df_tr['Naive RP (Net)'] = df['Naive_Net'] + rf
    df_tr['ERC RP (Net)'] = df['ERC_Net'] + rf
    df_tr['Trend RP (Net)'] = df['Trend_Net'] + rf
    df_tr['Bench 60/40'] = df['Bench_6040_XR'] + rf
    
    # ==========================================
    # 1. 生成终极表格 (含税务分析)
    # ==========================================
    metrics = []
    
    # 定义每个策略适用的税率
    tax_map = {
        'Naive RP (Net)': RealLifeConfig.TAX_RATE_LONG_TERM,
        'ERC RP (Net)': RealLifeConfig.TAX_RATE_LONG_TERM,
        'Trend RP (Net)': RealLifeConfig.TAX_RATE_SHORT_TERM, # 30% !!!
        'Bench 60/40': RealLifeConfig.TAX_RATE_LONG_TERM
    }
    
    for col in df_tr.columns:
        tax_rate = tax_map.get(col, 0.20)
        m = calculate_metrics_with_tax(df_tr[col].pct_change().fillna(0), tax_rate) # TR to Returns
        # 注意：df_tr 已经是 monthly returns 吗？
        # 上一步算出来的是 XR，加了 RF 变成了 TR monthly returns。
        # 所以直接传 df_tr[col] 即可，不需要 pct_change
        m = calculate_metrics_with_tax(df_tr[col], tax_rate)
        m['Strategy'] = col
        metrics.append(m)
        
    df_metrics = pd.DataFrame(metrics).set_index('Strategy')
    
    # 格式化
    df_fmt = df_metrics.copy()
    for c in df_fmt.columns:
        if 'CAGR' in c or 'Drawdown' in c or 'Tax Rate' in c:
            df_fmt[c] = df_fmt[c].apply(lambda x: f"{x:.2%}")
        elif 'Sharpe' in c or 'Vol' in c:
            df_fmt[c] = df_fmt[c].apply(lambda x: f"{x:.2f}")

    print("\n🏆 Final  Performance (Net of Fees & Taxes):")
    print("="*80)
    print(df_fmt[['CAGR (Pre-Tax)', 'Tax Rate Used', 'CAGR (After-Tax)', 'Max_Drawdown', 'Sharpe']].to_string())
    print("="*80)
    
    df_metrics.to_csv(os.path.join(PLOT_DIR, 'final_performance_table.csv'))
    
    # ==========================================
    # 2. 画最终净值图 (Net of Fees)
    # ==========================================
    cum_wealth = (1 + df_tr).cumprod()
    
    plt.figure(figsize=(12, 7))
    plt.plot(cum_wealth.index, cum_wealth['Naive RP (Net)'], color='gray', ls='--', alpha=0.6, label='Naive RP (Net)')
    plt.plot(cum_wealth.index, cum_wealth['ERC RP (Net)'], color='#1f77b4', ls='-.', alpha=0.6, label='ERC RP (Net)')
    plt.plot(cum_wealth.index, cum_wealth['Trend RP (Net)'], color='#2ca02c', lw=2.5, label='Trend RP (Net)')
    plt.plot(cum_wealth.index, cum_wealth['Bench 60/40'], color='black', ls=':', alpha=0.5, label='60/40')
    
    plt.yscale('log')
    plt.title('Final "Real Life" Equity Curves (Net of Fees & Transaction Costs)')
    plt.ylabel('Wealth Index (Log)')
    plt.grid(True, which='both', alpha=0.2)
    plt.legend()
    
    plt.savefig(os.path.join(PLOT_DIR, 'final_02_equity_curves_net.png'))
    print(f"✅ Final Plot Saved.")

if __name__ == "__main__":
    run_final_report()