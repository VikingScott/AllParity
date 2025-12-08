import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
from pathlib import Path

# --- Configuration ---
INPUT_FILE = Path("outputs/backtest_results.csv")
OUTPUT_DIR = Path("outputs")

# 定义颜色映射
REGIME_COLORS = {
    1: '#d5e8d4',  # Green (Goldilocks)
    2: '#dae8fc',  # Blue (Reflation)
    3: '#ffe6cc',  # Orange (Stagflation)
    4: '#f8cecc'   # Red (Crash/Deflation)
}

# 定义资产颜色 (用于堆积图)
ASSET_COLORS = {
    'W_SPY': '#1f77b4', 'W_EFA': '#aec7e8', 'W_EEM': '#98df8a', 'W_IWM': '#2ca02c', # Equities
    'W_TLT': '#9467bd', 'W_IEF': '#c5b0d5', 'W_LQD': '#8c564b', 'W_TIP': '#e377c2', # Bonds
    'W_DBC': '#ff7f0e', 'W_GLD': '#ffbb78',                                       # Comm
    'W_SGOV': '#7f7f7f', 'W_BIL': '#c7c7c7'                                       # Cash
}

def load_results():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"❌ Cannot find {INPUT_FILE}. Run engine first.")
    
    print(f"Loading results from {INPUT_FILE}...")
    df = pd.read_csv(INPUT_FILE, index_col=0, parse_dates=True)
    df = df.sort_index()
    return df

def get_return_col(df):
    """自动适配收益率列名"""
    if 'Strategy_Return' in df.columns: return 'Strategy_Return'
    if 'Portfolio_Daily_Ret' in df.columns: return 'Portfolio_Daily_Ret'
    raise KeyError("Return column not found")

def calculate_stats(df):
    """计算核心指标"""
    ret_col = get_return_col(df)
    daily_ret = df[ret_col]
    
    start_nav = df['Equity_Curve'].iloc[0]
    end_nav = df['Equity_Curve'].iloc[-1]
    
    days = (df.index[-1] - df.index[0]).days
    years = days / 365.25
    cagr = (end_nav / start_nav) ** (1 / years) - 1 if years > 0 else 0
    max_dd = df['Drawdown'].min()
    
    if daily_ret.std() == 0:
        sharpe = 0
    else:
        sharpe = (daily_ret.mean() * 252) / (daily_ret.std() * np.sqrt(252))
        
    return {"CAGR": cagr, "MaxDD": max_dd, "Sharpe": sharpe}

def plot_dashboard_phase1(df, stats):
    """Phase 1: 生存证明 (净值 + 回撤)"""
    print("Generating Phase 1 Plot (Survival)...")
    sns.set_theme(style="whitegrid")
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 10), sharex=True, gridspec_kw={'height_ratios': [3, 1]})

    # 1. Regime Background
    if 'Regime' in df.columns:
        df['Regime'] = df['Regime'].fillna(0)
        df['Regime_Group'] = (df['Regime'] != df['Regime'].shift()).cumsum()
        for _, block in df.groupby('Regime_Group'):
            regime = block['Regime'].iloc[0]
            color = REGIME_COLORS.get(regime, 'white')
            ax1.axvspan(block.index.min(), block.index.max(), color=color, alpha=0.5, lw=0)

    # 2. Equity Curve
    ax1.plot(df.index, df['Equity_Curve'], color='#2b5797', lw=2, label='AllParity')
    if 'Benchmark_SPY' in df.columns:
        ax1.plot(df.index, df['Benchmark_SPY'], color='gray', lw=1, ls='--', alpha=0.6, label='SPY')
    
    ax1.set_yscale('log')
    ax1.set_title(f"Cumulative Return (Log) | CAGR: {stats['CAGR']:.1%} | Sharpe: {stats['Sharpe']:.2f}", fontsize=14, fontweight='bold')
    ax1.legend(loc='upper left')

    # 3. Drawdown
    ax2.fill_between(df.index, df['Drawdown'], 0, color='red', alpha=0.3)
    ax2.plot(df.index, df['Drawdown'], color='red', lw=1)
    ax2.set_ylabel("Drawdown")
    ax2.set_ylim(bottom=min(df['Drawdown'].min()*1.1, -0.05), top=0.01)

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "dashboard_1_survival.png", dpi=150)
    plt.close()

def plot_dashboard_phase2(df):
    """Phase 2: 质量自证 (持仓堆积 + 体制分析)"""
    print("Generating Phase 2 Plot (Quality)...")
    sns.set_theme(style="white") # 使用白色背景更适合堆积图
    
    fig = plt.figure(figsize=(16, 12))
    gs = fig.add_gridspec(2, 2, height_ratios=[2, 1])
    
    # --- Chart A: Asset Allocation (Stacked) ---
    ax1 = fig.add_subplot(gs[0, :])
    
    # 提取权重列
    w_cols = [c for c in df.columns if c.startswith('W_')]
    # 按预定义颜色表排序，保证颜色一致性
    sorted_cols = sorted(w_cols, key=lambda x: list(ASSET_COLORS.keys()).index(x) if x in ASSET_COLORS else 99)
    
    if sorted_cols:
        y_stack = df[sorted_cols].fillna(0).clip(0, 1) # 确保无负值
        ax1.stackplot(df.index, y_stack.T, labels=[c.replace('W_','') for c in sorted_cols], 
                      colors=[ASSET_COLORS.get(c, 'gray') for c in sorted_cols], alpha=0.9)
        
        ax1.set_title("Historical Asset Allocation (Stacked)", fontsize=14, fontweight='bold')
        ax1.set_ylabel("Weight")
        ax1.set_ylim(0, 1.0)
        ax1.legend(loc='upper left', bbox_to_anchor=(1, 1), ncol=1, fontsize=9)
        ax1.margins(x=0)

    # --- Chart B: Regime Performance (Bar) ---
    ax2 = fig.add_subplot(gs[1, 0])
    
    ret_col = get_return_col(df)
    # 计算分体制年化收益
    regime_stats = df.groupby('Regime')[ret_col].mean() * 252 * 100
    
    colors = [REGIME_COLORS.get(r, 'gray') for r in regime_stats.index]
    bars = ax2.bar(regime_stats.index.astype(str), regime_stats.values, color=colors, edgecolor='black')
    
    ax2.set_title("Annualized Return by Regime (%)", fontsize=12)
    ax2.axhline(0, color='black', lw=1)
    ax2.bar_label(bars, fmt='%.1f%%', padding=3)

    # --- Chart C: Macro Inputs (Line) ---
    ax3 = fig.add_subplot(gs[1, 1])
    ax3.plot(df.index, df['Trend_Growth'], color='green', label='Growth', lw=1.5)
    ax3.plot(df.index, df['Trend_Inflation_Blended'], color='orange', label='Inflation', lw=1.5)
    ax3.axhline(0, color='black', ls='--', alpha=0.3)
    ax3.set_title("Underlying Macro Trends", fontsize=12)
    ax3.legend(loc='lower left', fontsize=9)

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "dashboard_2_allocation.png", dpi=150)
    plt.close()
    print(f"✅ Dashboards saved to {OUTPUT_DIR}")

def run_analytics():
    try:
        df = load_results()
        stats = calculate_stats(df)
        
        # 打印简单报表
        print(f"\n📊 Performance Summary:")
        print(f"   CAGR:   {stats['CAGR']:.2%}")
        print(f"   Sharpe: {stats['Sharpe']:.2f}")
        print(f"   MaxDD:  {stats['MaxDD']:.2%}")
        
        # 生成两张图
        plot_dashboard_phase1(df, stats)
        plot_dashboard_phase2(df)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_analytics()