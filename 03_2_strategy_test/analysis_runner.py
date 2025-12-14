# 03_2_strategy_test/analysis_runner.py

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os

# ==========================================
# 0. 路径配置
# ==========================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DATA_PATH = os.path.join(PROJECT_ROOT, 'data', 'processed', 'strategy_results.csv')
PLOT_DIR = os.path.join(PROJECT_ROOT, 'outputs', 'plots', '03_strategy_results')

if not os.path.exists(PLOT_DIR):
    os.makedirs(PLOT_DIR)

# ==========================================
# 1. 核心计算函数 (白名单模式，稳健)
# ==========================================
def calculate_metrics(df_all):
    """
    显式指定要分析的 5 个策略，不再依赖列名自动匹配，防止 NaN。
    """
    # 我们关心的 5 个核心策略 (不包含 Vol_Market 这种诊断列)
    target_strategies = [
        'Bench_SP500', 
        'Bench_6040', 
        'RP_Unlevered', 
        'RP_Academic', 
        'RP_Retail'
    ]
    
    results = []
    valid_indices = []

    for strat in target_strategies:
        col_xr = f"{strat}_XR"
        col_tr = f"{strat}_TR"
        
        # 检查列是否存在
        if col_xr not in df_all.columns or col_tr not in df_all.columns:
            continue
            
        s_xr = df_all[col_xr]
        s_tr = df_all[col_tr]
        
        # --- 计算指标 ---
        
        # 1. CAGR (年化收益)
        total_ret = (1 + s_tr).prod()
        n_months = len(s_tr)
        cagr = total_ret ** (12 / n_months) - 1
        
        # 2. Volatility (年化波动)
        vol = s_tr.std() * np.sqrt(12)
        
        # 3. Sharpe Ratio (超额收益 / 波动)
        sharpe = s_xr.mean() / s_xr.std() * np.sqrt(12)
        
        # 4. Max Drawdown
        cum_ret = (1 + s_tr).cumprod()
        peak = cum_ret.cummax()
        drawdown = (cum_ret - peak) / peak
        max_dd = drawdown.min()
        
        # 5. Calmar Ratio
        calmar = cagr / abs(max_dd) if max_dd != 0 else np.nan
        
        results.append({
            'CAGR': cagr,
            'Volatility': vol,
            'Sharpe_Ratio': sharpe,
            'Max_Drawdown': max_dd,
            'Calmar_Ratio': calmar
        })
        valid_indices.append(strat) # 干净的名字，没有 _XR 后缀

    return pd.DataFrame(results, index=valid_indices)

def plot_cumulative_wealth(df, filename):
    """画累计净值图 (Log Scale)"""
    plt.figure(figsize=(12, 7))
    
    # 显式指定要画的列，避免画出诊断数据
    plot_map = {
        'Bench_SP500_TR': {'color': 'gray', 'label': 'S&P 500', 'ls': '--', 'lw': 1},
        'Bench_6040_TR':  {'color': 'black', 'label': '60/40 Benchmark', 'ls': '-.', 'lw': 2},
        'RP_Retail_TR':   {'color': '#d62728', 'label': 'RP Retail (Capped)', 'ls': '-', 'lw': 2.5},
        'RP_Academic_TR': {'color': '#1f77b4', 'label': 'RP Academic (Uncapped)', 'ls': '-', 'lw': 1, 'alpha': 0.6}
    }
    
    for col, style in plot_map.items():
        if col in df.columns:
            cum_wealth = (1 + df[col]).cumprod()
            plt.plot(cum_wealth.index, cum_wealth, **style)
            
    plt.yscale('log')
    plt.title('Cumulative Wealth (Log Scale): Risk Parity vs 60/40')
    plt.ylabel('Wealth Index (Log)')
    plt.grid(True, which="both", ls="-", alpha=0.2)
    plt.legend()
    plt.savefig(os.path.join(PLOT_DIR, filename))
    plt.close()

def plot_drawdown(df, filename):
    """画回撤图"""
    cols = ['Bench_6040_TR', 'RP_Retail_TR', 'Bench_SP500_TR']
    colors = ['black', 'red', 'gray']
    
    plt.figure(figsize=(12, 6))
    
    for i, col in enumerate(cols):
        if col in df.columns:
            cum = (1 + df[col]).cumprod()
            dd = (cum - cum.cummax()) / cum.cummax()
            label = col.replace('_TR', '')
            plt.plot(dd.index, dd, label=label, color=colors[i], lw=1.5 if 'RP' in col else 1)
            plt.fill_between(dd.index, dd, 0, color=colors[i], alpha=0.1)
            
    plt.title('Drawdown Profile: RP Retail vs 60/40')
    plt.ylabel('Drawdown %')
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.savefig(os.path.join(PLOT_DIR, filename))
    plt.close()

def plot_rolling_sharpe_vs_6040(df, filename):
    """[需求更新] 滚动夏普：RP Retail vs 60/40"""
    plt.figure(figsize=(12, 5))
    
    # 计算滚动夏普 (36个月)
    window = 36
    
    # RP Retail
    rp_xr = df['RP_Retail_XR']
    rp_roll_sharpe = rp_xr.rolling(window).mean() / rp_xr.rolling(window).std() * np.sqrt(12)
    
    # Bench 60/40
    bench_xr = df['Bench_6040_XR']
    bench_roll_sharpe = bench_xr.rolling(window).mean() / bench_xr.rolling(window).std() * np.sqrt(12)
    
    plt.plot(bench_roll_sharpe.index, bench_roll_sharpe, label='Benchmark 60/40', color='black', alpha=0.6, lw=1.5)
    plt.plot(rp_roll_sharpe.index, rp_roll_sharpe, label='RP Retail', color='red', lw=2)
    
    plt.axhline(0, color='black', lw=0.5)
    plt.title(f'Rolling {window}-Month Sharpe Ratio: RP Retail vs 60/40')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.savefig(os.path.join(PLOT_DIR, filename))
    plt.close()

def plot_leverage(df, filename):
    """杠杆率"""
    cols = [c for c in df.columns if 'Lev_Ratio' in c and 'Realized' in c]
    plt.figure(figsize=(12, 5))
    for col in cols:
        label = col.replace('Lev_Ratio_', '').replace('_Realized', '')
        plt.plot(df.index, df[col], label=label)
    plt.axhline(1, color='black', ls='--', alpha=0.5)
    plt.title('Leverage Dynamics')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.savefig(os.path.join(PLOT_DIR, filename))
    plt.close()

# ==========================================
# 2. 主流程
# ==========================================
def main_analysis():
    print("🚀 [Analysis v4.0] Generating Institutional Report...")
    
    if not os.path.exists(DATA_PATH):
        print(f"❌ Data not found: {DATA_PATH}")
        return
    df = pd.read_csv(DATA_PATH, index_col=0, parse_dates=True)
    
    # 1. 计算表格 (Fix NaN Issue)
    print("   [1/3] Calculating Metrics (Robust Mode)...")
    metrics = calculate_metrics(df)
    
    print("\n" + "="*80)
    print("🏆 FINAL PERFORMANCE SUMMARY (1993 - 2025)")
    print("="*80)
    
    # 分开显示，避免百分号混淆
    # A. 收益风险类 (显示 %)
    pct_cols = ['CAGR', 'Volatility', 'Max_Drawdown']
    print(metrics[pct_cols].applymap(lambda x: f"{x:.2%}"))
    print("-" * 40)
    
    # B. 比率类 (显示 数字)
    ratio_cols = ['Sharpe_Ratio', 'Calmar_Ratio']
    print(metrics[ratio_cols].applymap(lambda x: f"{x:.2f}"))
    print("="*80 + "\n")
    
    metrics.to_csv(os.path.join(PLOT_DIR, 'performance_metrics.csv'))

    # 2. 画图
    print("   [2/3] Generating Standard Plots...")
    plot_cumulative_wealth(df, '01_cumulative_wealth_log.png')
    plot_drawdown(df, '02_drawdown_profile.png')
    plot_leverage(df, '03_leverage_dynamics.png')
    
    # 3. 滚动夏普 (RP vs 60/40)
    print("   [3/3] Generating Rolling Sharpe (RP vs 60/40)...")
    plot_rolling_sharpe_vs_6040(df, '04_rolling_sharpe_vs_6040.png')
    
    print(f"✅ Analysis Complete. Check: {PLOT_DIR}")

if __name__ == "__main__":
    main_analysis()