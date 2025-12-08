import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from scipy.stats import skew, kurtosis

# ==========================================
# 1. 配置与路径 (自动适配相对路径)
# ==========================================
CURRENT_DIR = Path(__file__).parent
# 假设脚本在 analysis_pro/ 下，数据在 ../outputs/ 和 ../data/
DATA_DIR = CURRENT_DIR.parent / "data"
OUTPUTS_DIR = CURRENT_DIR.parent / "outputs"
SAVE_DIR = CURRENT_DIR / "report_images"

# 目标回测结果文件 (这里默认读 Risk Parity V2)
TARGET_RESULT_FILE = OUTPUTS_DIR / "backtest_results_retail_v3.csv"
ASSET_RET_FILE = DATA_DIR / "asset_returns.csv"

# 确保保存目录存在
if not SAVE_DIR.exists():
    SAVE_DIR.mkdir()

# 绘图风格
sns.set_theme(style="whitegrid", font_scale=1.1)
plt.rcParams['figure.dpi'] = 150
COLORS = sns.color_palette("deep")

# ==========================================
# 2. 数据加载与预处理
# ==========================================
def load_data():
    print(f"🚀 Loading backtest results from: {TARGET_RESULT_FILE.name}...")
    try:
        df = pd.read_csv(TARGET_RESULT_FILE, index_col=0, parse_dates=True)
        # 加载资产原始收益率 (用于归因)
        df_assets = pd.read_csv(ASSET_RET_FILE, index_col=0, parse_dates=True)
        return df, df_assets
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        print("请确保你在项目根目录下运行了 backtest_engine.py，并且文件夹结构正确。")
        exit()

# ==========================================
# 3. 核心统计指标 (Level 1 & 2)
# ==========================================
def calc_advanced_stats(daily_ret):
    ann_ret = daily_ret.mean() * 252
    ann_vol = daily_ret.std() * np.sqrt(252)
    sharpe = ann_ret / ann_vol if ann_vol != 0 else 0
    
    # 下行偏差 (用于 Sortino)
    downside_std = daily_ret[daily_ret < 0].std() * np.sqrt(252)
    sortino = ann_ret / downside_std if downside_std != 0 else 0
    
    # 历史 VaR (95%)
    var_95 = np.percentile(daily_ret, 5)
    
    # 胜率
    win_rate = len(daily_ret[daily_ret > 0]) / len(daily_ret)
    
    return {
        "CAGR": (1 + daily_ret).prod() ** (252 / len(daily_ret)) - 1,
        "Vol": ann_vol,
        "Sharpe": sharpe,
        "Sortino": sortino,
        "Skew": skew(daily_ret),
        "Kurtosis": kurtosis(daily_ret),
        "VaR (95%)": var_95,
        "Win Rate": win_rate
    }

# ==========================================
# 4. 图表生成模块
# ==========================================

def plot_1_summary_stats(df, stats):
    """图1: 净值曲线 + 核心指标文本卡片"""
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # 净值
    ax.plot(df.index, df['Equity_Curve'], label='Strategy', color='#2b5797', lw=2)
    if 'Benchmark_SPY' in df.columns:
        ax.plot(df.index, df['Benchmark_SPY'], label='SPY (Bench)', color='gray', alpha=0.5, ls='--')
    
    ax.set_yscale('log')
    ax.set_title("Cumulative Return (Log Scale)", fontweight='bold')
    ax.legend()
    
    # 在图上打印指标
    text_str = '\n'.join([f"{k}: {v:.2%}" if k not in ['Sharpe', 'Sortino', 'Skew', 'Kurtosis'] else f"{k}: {v:.2f}" 
                          for k, v in stats.items()])
    props = dict(boxstyle='round', facecolor='wheat', alpha=0.3)
    ax.text(0.02, 0.95, text_str, transform=ax.transAxes, fontsize=10,
            verticalalignment='top', bbox=props)
    
    plt.tight_layout()
    plt.savefig(SAVE_DIR / "01_summary_performance.png")
    plt.close()

def plot_2_drawdown_analysis(df):
    """图2: 回撤深度 + 回撤持续时间"""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    
    # 绘制回撤
    dd = df['Drawdown']
    ax1.fill_between(dd.index, dd, 0, color='red', alpha=0.3)
    ax1.plot(dd.index, dd, color='red', lw=1)
    ax1.set_title("Underwater Plot (Drawdown)", fontweight='bold')
    ax1.set_ylabel("Drawdown %")
    
    # 滚动波动率 (观察风险聚集)
    roll_vol = df['Portfolio_Daily_Ret'].rolling(63).std() * np.sqrt(252)
    ax2.plot(roll_vol.index, roll_vol, color='orange', lw=1.5)
    ax2.set_title("3-Month Rolling Volatility (Annualized)", fontweight='bold')
    ax2.set_ylabel("Vol %")
    
    plt.tight_layout()
    plt.savefig(SAVE_DIR / "02_risk_structure.png")
    plt.close()

def plot_3_rolling_metrics(df):
    """图3: 滚动 Sharpe (稳定性检查)"""
    window = 252 # 1 Year
    roll_ret = df['Portfolio_Daily_Ret'].rolling(window).mean() * 252
    roll_std = df['Portfolio_Daily_Ret'].rolling(window).std() * np.sqrt(252)
    roll_sharpe = roll_ret / roll_std
    
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(roll_sharpe.index, roll_sharpe, color='green', lw=1.5)
    ax.axhline(roll_sharpe.mean(), color='green', ls='--', alpha=0.5, label='Avg')
    ax.axhline(0, color='black', lw=1)
    
    ax.set_title(f"Rolling {window}-Day Sharpe Ratio", fontweight='bold')
    ax.legend()
    
    plt.tight_layout()
    plt.savefig(SAVE_DIR / "03_stability_rolling_sharpe.png")
    plt.close()

def plot_4_regime_analysis(df):
    """图4: 分体制表现 (Level 7)"""
    if 'Regime' not in df.columns: return
    
    # 计算各 Regime 统计
    g = df.groupby('Regime')['Portfolio_Daily_Ret']
    regime_stats = pd.DataFrame({
        'Ann Return': g.mean() * 252,
        'Ann Vol': g.std() * np.sqrt(252),
        'Count': g.count()
    })
    regime_stats['Sharpe'] = regime_stats['Ann Return'] / regime_stats['Ann Vol']
    
    # 绘图
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    
    # Bar Chart: Return
    sns.barplot(x=regime_stats.index, y=regime_stats['Ann Return'], ax=ax1, palette='viridis')
    ax1.set_title("Annualized Return by Regime", fontweight='bold')
    ax1.axhline(0, color='black')
    
    # Scatter: Risk vs Return
    sns.scatterplot(data=regime_stats, x='Ann Vol', y='Ann Return', hue=regime_stats.index, s=200, ax=ax2, palette='viridis')
    for idx, row in regime_stats.iterrows():
        ax2.text(row['Ann Vol'], row['Ann Return'], f" R{idx}", fontsize=12)
    
    ax2.set_title("Risk/Return Profile by Regime", fontweight='bold')
    ax2.set_xlabel("Volatility")
    ax2.set_ylabel("Return")
    
    plt.tight_layout()
    plt.savefig(SAVE_DIR / "04_regime_consistency.png")
    plt.close()

def plot_5_turnover_cost(df):
    """图5: 换手率与成本敏感性 (Level 5)"""
    # 提取权重列
    w_cols = [c for c in df.columns if c.startswith('W_')]
    if not w_cols: return
    
    weights = df[w_cols]
    # 计算双边换手 -> 每日换手 = sum(|Wt - Wt-1|)
    # 实际交易成本通常按单边算，这里我们算"每日总交易额比例"
    daily_turnover = weights.diff().abs().sum(axis=1)
    ann_turnover = daily_turnover.mean() * 252 * 0.5 # 单边年化
    
    # 成本模拟
    costs_bps = [0, 5, 10, 20]
    fig, ax = plt.subplots(figsize=(12, 6))
    
    original_ret = df['Portfolio_Daily_Ret']
    
    for cost in costs_bps:
        # 扣费逻辑: 收益 - (换手金额 * 费率)
        # 注意: 这里是简化的每日扣费
        cost_impact = daily_turnover * (cost / 10000) 
        net_ret = original_ret - cost_impact
        net_curve = (1 + net_ret).cumprod()
        
        ax.plot(net_curve.index, net_curve, label=f"Cost {cost}bps (Ann TO: {ann_turnover:.1f}x)")
        
    ax.set_yscale('log')
    ax.set_title("Cost Sensitivity Analysis (Net Equity Curve)", fontweight='bold')
    ax.legend()
    
    plt.tight_layout()
    plt.savefig(SAVE_DIR / "05_execution_cost_sensitivity.png")
    plt.close()

def plot_6_attribution(df, df_assets):
    """图6: 收益归因 (Level 6)"""
    w_cols = [c for c in df.columns if c.startswith('W_')]
    valid_assets = [c.replace('W_', '') for c in w_cols]
    valid_assets = [a for a in valid_assets if a in df_assets.columns]
    
    if not valid_assets: return
    
    # 对齐数据
    common_idx = df.index.intersection(df_assets.index)
    w_aligned = df.loc[common_idx, [f"W_{a}" for a in valid_assets]]
    r_aligned = df_assets.loc[common_idx, valid_assets]
    
    # 贡献度 = 权重 * 收益 (近似)
    contrib = w_aligned.values * r_aligned.values
    contrib_df = pd.DataFrame(contrib, index=common_idx, columns=valid_assets)
    
    # 按年累计贡献
    cum_contrib = contrib_df.sum().sort_values(ascending=False)
    
    fig, ax = plt.subplots(figsize=(12, 6))
    sns.barplot(x=cum_contrib.index, y=cum_contrib.values, ax=ax, palette="Spectral")
    ax.set_title("Total Return Contribution by Asset (Cumulative)", fontweight='bold')
    ax.set_ylabel("Total Return contribution")
    plt.xticks(rotation=45)
    
    plt.tight_layout()
    plt.savefig(SAVE_DIR / "06_return_attribution.png")
    plt.close()

def plot_7_yearly_heatmap(df):
    """图7: 年度月度热力图"""
    daily = df['Portfolio_Daily_Ret']
    # 转为月度
    monthly = daily.resample('M').apply(lambda x: (1+x).prod() - 1)
    
    monthly_df = pd.DataFrame({
        'Year': monthly.index.year,
        'Month': monthly.index.month,
        'Return': monthly.values
    })
    
    pivot = monthly_df.pivot(index='Year', columns='Month', values='Return')
    
    fig, ax = plt.subplots(figsize=(10, len(pivot)*0.5 + 2))
    sns.heatmap(pivot, annot=True, fmt='.1%', cmap="RdYlGn", center=0, ax=ax, cbar=False)
    ax.set_title("Monthly Performance Heatmap", fontweight='bold')
    
    plt.tight_layout()
    plt.savefig(SAVE_DIR / "07_monthly_heatmap.png")
    plt.close()

# ==========================================
# 5. 主程序
# ==========================================
def main():
    print(">>> 📊 Starting Advanced Analytics Suite...")
    
    # 1. 加载数据
    df, df_assets = load_data()
    
    # 2. 计算统计
    stats = calc_advanced_stats(df['Portfolio_Daily_Ret'])
    print("\n[Key Statistics]")
    for k, v in stats.items():
        print(f"  {k:<12} : {v:.4f}")
        
    # 3. 生成图表
    print("\n>>> 🎨 Generating Plots in 'analysis_pro/report_images/'...")
    
    plot_1_summary_stats(df, stats)
    print("  ✅ 01 Summary & Stats")
    
    plot_2_drawdown_analysis(df)
    print("  ✅ 02 Drawdown & Vol Structure")
    
    plot_3_rolling_metrics(df)
    print("  ✅ 03 Rolling Stability")
    
    plot_4_regime_analysis(df)
    print("  ✅ 04 Regime Consistency")
    
    plot_5_turnover_cost(df)
    print("  ✅ 05 Cost & Turnover")
    
    plot_6_attribution(df, df_assets)
    print("  ✅ 06 Return Attribution")
    
    plot_7_yearly_heatmap(df)
    print("  ✅ 07 Monthly Heatmap")
    
    print("\n🏁 All analysis completed successfully!")

if __name__ == "__main__":
    main()