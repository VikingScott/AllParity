# 07_trend_following/run_trend_performance_report.py

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import os
import sys

# 路径设置
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, 'data', 'processed')
PLOT_DIR = os.path.join(PROJECT_ROOT, 'outputs', 'plots', '07_trend_following') 

if not os.path.exists(PLOT_DIR):
    os.makedirs(PLOT_DIR)

def run_performance_report():
    print("🚀 [Trend Report] Generating Paper-Grade Charts...")
    
    # 1. 读取数据 (Returns, Weights, Signals)
    ret_path = os.path.join(DATA_DIR, 'trend_vs_naive_returns.csv')
    w_path = os.path.join(DATA_DIR, 'trend_vs_naive_weights.csv')
    sig_path = os.path.join(DATA_DIR, 'trend_signals_raw.csv')
    
    if not os.path.exists(ret_path) or not os.path.exists(w_path) or not os.path.exists(sig_path):
        print("❌ Data missing. Run 'run_trend_simulation.py' first.")
        return
        
    df_ret = pd.read_csv(ret_path, index_col=0, parse_dates=True)
    df_w = pd.read_csv(w_path, index_col=0, parse_dates=True)
    df_sig = pd.read_csv(sig_path, index_col=0, parse_dates=True)
    
    # 2. 计算累计净值 (Cumulative Wealth) - 用于 Metrics
    if 'Risk_Free' in df_ret.columns:
        rf = df_ret['Risk_Free']
        df_tr = pd.DataFrame()
        df_tr['Naive_TR'] = df_ret['Naive_XR'] + rf
        df_tr['Trend_TR'] = df_ret['Trend_XR'] + rf
        df_tr['Bench_6040_TR'] = df_ret['Bench_6040_XR'] + rf
    else:
        df_tr = df_ret[['Naive_XR', 'Trend_XR', 'Bench_6040_XR']]

    cum_wealth = (1 + df_tr).cumprod()
    drawdowns = (cum_wealth / cum_wealth.cummax()) - 1
    
    # -------------------------------------------------------
    # Task 2: 全历史图 (保持不变，略)
    # -------------------------------------------------------
    # (为了代码简洁，这里略过全历史图，专注画那张 Zoom 图)
    
    # -------------------------------------------------------
    # Task 3: 2022 Zoom Combine Plot (论文级图表)
    # -------------------------------------------------------
    print("   Drawing Combined Zoom Plot...")
    
    # 时间窗口：包含 2022 暴跌前后
    zoom_start = '2021-06-01'
    zoom_end = '2023-06-01'
    
    # 数据切片
    df_zoom_wealth = cum_wealth.loc[zoom_start:zoom_end]
    df_zoom_wealth = df_zoom_wealth / df_zoom_wealth.iloc[0] # Rebase to 1.0
    
    df_zoom_w = df_w.loc[zoom_start:zoom_end]
    df_zoom_sig = df_sig.loc[zoom_start:zoom_end]
    
    # 准备权重数据
    # A. Naive (Full Invested)
    naive_cols = [c for c in df_zoom_w.columns if c.startswith('Naive_')]
    df_naive_w = df_zoom_w[naive_cols].copy()
    df_naive_w.columns = [c.replace('Naive_', '').replace('_XR', '') for c in df_naive_w.columns]
    
    # B. Trend (With Cash)
    trend_cols = [c for c in df_zoom_w.columns if c.startswith('Trend_')]
    df_trend_w = df_zoom_w[trend_cols].copy()
    df_trend_w.columns = [c.replace('Trend_', '').replace('_XR', '') for c in df_trend_w.columns]
    df_trend_w['Cash'] = (1.0 - df_trend_w.sum(axis=1)).clip(lower=0.0)
    
    # 统一颜色映射
    # 资产: Stocks(Blue), Bonds(Orange), Credit(Green), Commodities(Red), Cash(Gray)
    # 注意：根据你的列名顺序调整
    assets = [c for c in df_naive_w.columns]
    color_map = {
        'US_Stock': '#1f77b4',       # Blue
        'US_Bond_10Y': '#ff7f0e',    # Orange
        'US_Credit': '#2ca02c',      # Green
        'Commodities': '#d62728',    # Red
        'Cash': '#d3d3d3'            # Gray
    }
    
    # 确保 Stackplot 顺序一致
    # 建议顺序: Cash (底), Bonds, Credit, Stocks, Commodities (顶)
    stack_order = ['US_Bond_10Y', 'US_Credit', 'US_Stock', 'Commodities']
    # 过滤掉不存在的列
    stack_order = [c for c in stack_order if c in df_naive_w.columns]
    
    naive_stack_data = df_naive_w[stack_order]
    trend_stack_data = df_trend_w[['Cash'] + stack_order] # Trend 多一个 Cash
    
    naive_colors = [color_map.get(c, 'gray') for c in stack_order]
    trend_colors = [color_map['Cash']] + naive_colors

    # ==========================
    # 绘图布局 (GridSpec)
    # ==========================
    fig = plt.figure(figsize=(12, 10))
    # 4 行布局: Wealth(3), Signal(0.5), Naive(1.5), Trend(1.5) -> 总和 6.5
    # height_ratios=[3, 0.4, 1.5, 1.5]
    gs = fig.add_gridspec(4, 1, height_ratios=[3, 0.3, 1.5, 1.5], hspace=0.1)
    
    ax1 = fig.add_subplot(gs[0, 0]) # Wealth
    ax2 = fig.add_subplot(gs[1, 0], sharex=ax1) # Signal Strip
    ax3 = fig.add_subplot(gs[2, 0], sharex=ax1) # Naive Alloc
    ax4 = fig.add_subplot(gs[3, 0], sharex=ax1) # Trend Alloc
    
    # --- Ax1: Wealth Curves ---
    ax1.plot(df_zoom_wealth.index, df_zoom_wealth['Naive_TR'], label='Naive RP (Baseline)', color='orange', ls='--', lw=2)
    ax1.plot(df_zoom_wealth.index, df_zoom_wealth['Trend_TR'], label='Trend RP (Cash Reserve)', color='#2ca02c', lw=3)
    ax1.plot(df_zoom_wealth.index, df_zoom_wealth['Bench_6040_TR'], label='60/40', color='black', ls=':', alpha=0.6)
    
    ax1.set_ylabel('Normalized Wealth')
    ax1.set_title('(A) Performance during Inflation Shock (2022)', loc='left', fontweight='bold')
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc='lower left')
    ax1.tick_params(labelbottom=False)
    
    # --- Ax2: Signal Strip (Heatmap style) ---
    # 我们把 Signal 画成 0/1 的热力条
    # df_zoom_sig 是 (Dates, Assets)
    # 我们只关心主要的 Risk-Off 来源 (通常是 Bonds 和 Stocks)
    # 为了简化，我们画所有资产的平均信号强度 (Risk-On Ratio)
    risk_on_ratio = df_zoom_sig.mean(axis=1)
    
    # 使用 pcolormesh 画条带
    # 扩展数据以适配 pcolormesh
    dates = mdates.date2num(df_zoom_sig.index)
    # Create a 1D array for the image
    im = ax2.imshow(risk_on_ratio.values[np.newaxis, :], aspect='auto', cmap='RdYlGn', 
                    extent=[dates[0], dates[-1], 0, 1], vmin=0, vmax=1)
    
    ax2.set_yticks([])
    ax2.set_ylabel('Signal', rotation=0, labelpad=20, va='center')
    ax2.set_title('(B) Aggregate Trend Signal (Green=Risk On, Red=Risk Off)', loc='left', fontsize=10)
    ax2.tick_params(labelbottom=False)
    
    # --- Ax3: Naive Allocation (Baseline) ---
    ax3.stackplot(naive_stack_data.index, naive_stack_data.T, labels=stack_order, colors=naive_colors, alpha=0.85)
    ax3.set_ylabel('Naive Weight')
    ax3.set_ylim(0, 1.0)
    ax3.set_title('(C) Naive Allocation (Fully Invested)', loc='left', fontsize=10)
    ax3.tick_params(labelbottom=False)
    ax3.grid(True, alpha=0.3, axis='x')
    
    # --- Ax4: Trend Allocation (With Cash) ---
    labels_trend = ['Cash'] + stack_order
    ax4.stackplot(trend_stack_data.index, trend_stack_data.T, labels=labels_trend, colors=trend_colors, alpha=0.85)
    ax4.set_ylabel('Trend Weight')
    ax4.set_ylim(0, 1.0)
    ax4.set_title('(D) Trend Allocation (Cash Reserve Active)', loc='left', fontsize=10)
    ax4.grid(True, alpha=0.3, axis='x')
    
    # Format X-Axis dates nicely
    ax4.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    ax4.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    
    # Legend for Allocations (Shared)
    # 放 Ax4 下面或者 Ax3 里面
    # 我们在 Ax4 放一个 Legend，只显示 Asset classes
    handles, labels = ax4.get_legend_handles_labels()
    # 逆序 Legend 以匹配 Stackplot 视觉顺序 (Top to Bottom)
    ax4.legend(handles[::-1], labels[::-1], loc='center left', bbox_to_anchor=(1.0, 1.0), title="Asset Class")
    
    plt.tight_layout()
    # 手动微调 hspace 以紧凑
    plt.subplots_adjust(hspace=0.2)
    
    zoom_path = os.path.join(PLOT_DIR, 'trend_2022_analysis.png')
    plt.savefig(zoom_path, bbox_inches='tight', dpi=300) # 高清保存
    print(f"✅ Combined Zoom Plot Saved: {zoom_path}")

if __name__ == "__main__":
    run_performance_report()