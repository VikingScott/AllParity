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
DATA_DIR = CURRENT_DIR.parent / "data"
OUTPUTS_DIR = CURRENT_DIR.parent / "outputs"
SAVE_DIR = CURRENT_DIR / "report_images"

# 目标回测结果文件
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
        df_assets = pd.read_csv(ASSET_RET_FILE, index_col=0, parse_dates=True)
        return df, df_assets
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        print("请确保你在项目根目录下运行了 backtest_engine.py，并且文件夹结构正确。")
        exit()

# ==========================================
# 2.1 构建更符合 Risk Parity 直觉的 Benchmark
# ==========================================
def build_rp_like_benchmarks(df_assets):
    """
    构建 RP-friendly benchmarks (只用已有 asset_returns.csv)：
    1) Benchmark_RP_InvVol: 朴素 Risk Parity (Inv-Vol, Monthly)
    2) Benchmark_60_40: 传统 60/40 (SPY + IEF/TLT)
    3) Benchmark_EW_Core: 核心资产等权
    """
    # 核心候选池（按你已有数据自动适配）
    core_candidates = ['SPY', 'TLT', 'IEF', 'GLD', 'DBC', 'LQD', 'TIP', 'EFA', 'EEM', 'IWM']
    core = [c for c in core_candidates if c in df_assets.columns]

    # RP-InvVol 优先用更“经典的多风险源核心”
    rp_core_pref = [c for c in ['SPY', 'TLT', 'IEF', 'GLD', 'DBC'] if c in df_assets.columns]
    rp_core = rp_core_pref if len(rp_core_pref) >= 3 else core[:5]

    if len(rp_core) < 3:
        print("⚠️ Not enough assets to build RP-like benchmarks. Skip benchmarks.")
        return pd.DataFrame(index=df_assets.index)

    rets_core = df_assets[rp_core].copy().fillna(0.0)
    out = pd.DataFrame(index=rets_core.index)

    # -------------------------
    # A) 60/40 Benchmark
    # -------------------------
    if 'SPY' in df_assets.columns and ('IEF' in df_assets.columns or 'TLT' in df_assets.columns):
        bond = 'IEF' if 'IEF' in df_assets.columns else 'TLT'
        rets_6040 = df_assets[['SPY', bond]].copy().fillna(0.0)
        w_6040 = pd.Series({'SPY': 0.60, bond: 0.40})
        r_6040 = (rets_6040 * w_6040.values).sum(axis=1)
        out['Benchmark_60_40'] = (1 + r_6040).cumprod()

    # -------------------------
    # B) Equal Weight (EW) on rp_core
    # -------------------------
    ew_w = np.repeat(1 / len(rp_core), len(rp_core))
    r_ew = (rets_core * ew_w).sum(axis=1)
    out['Benchmark_EW_Core'] = (1 + r_ew).cumprod()

    # -------------------------
    # C) Naive Risk Parity (Inv-Vol, Monthly)
    # -------------------------
    # 252 日滚动波动率
    vol = rets_core.rolling(252).std()
    inv_vol = 1 / vol.replace(0, np.nan)

    # ✅ 关键修复：取“每个月真实存在的第一个交易日”
    month_starts = (
        rets_core.index.to_series()
        .groupby(rets_core.index.to_period('M'))
        .first()
    )
    month_starts = pd.DatetimeIndex(month_starts.values)

    # 用 reindex 避免严格索引报错
    w_m = inv_vol.reindex(month_starts).copy()
    w_m = w_m.div(w_m.sum(axis=1), axis=0).fillna(0.0)

    # 扩展到日频
    w_daily = w_m.reindex(rets_core.index).ffill().fillna(0.0)

    # 朴素 RP 日收益
    r_rp = (w_daily * rets_core).sum(axis=1)
    out['Benchmark_RP_InvVol'] = (1 + r_rp).cumprod()

    return out

# ==========================================
# 3. 核心统计指标 (Level 1 & 2)
# ==========================================
def calc_advanced_stats(daily_ret):
    daily_ret = daily_ret.dropna()
    if len(daily_ret) == 0:
        return {
            "CAGR": 0.0, "Vol": 0.0, "Sharpe": 0.0, "Sortino": 0.0,
            "Skew": 0.0, "Kurtosis": 0.0, "VaR (95%)": 0.0, "Win Rate": 0.0
        }

    ann_ret = daily_ret.mean() * 252
    ann_vol = daily_ret.std() * np.sqrt(252)
    sharpe = ann_ret / ann_vol if ann_vol != 0 else 0

    downside = daily_ret[daily_ret < 0]
    downside_std = downside.std() * np.sqrt(252) if len(downside) > 0 else 0
    sortino = ann_ret / downside_std if downside_std != 0 else 0

    var_95 = np.percentile(daily_ret, 5)
    win_rate = len(daily_ret[daily_ret > 0]) / len(daily_ret)

    cagr = (1 + daily_ret).prod() ** (252 / len(daily_ret)) - 1

    return {
        "CAGR": cagr,
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
    """图1: 净值曲线 + 核心指标文本卡片(居中) + RP-friendly Benchmarks(不同颜色)"""
    fig, ax = plt.subplots(figsize=(12, 6))

    # --- 颜色映射（用你已有 COLORS）---
    # 如果你喜欢固定语义色，也可以改成你自己偏好的顺序
    color_map = {
        'Strategy': COLORS[0],
        'Benchmark_RP_InvVol': COLORS[1],
        'Benchmark_60_40': COLORS[2],
        'Benchmark_EW_Core': COLORS[3],
        'Benchmark_SPY': COLORS[4] if len(COLORS) > 4 else 'black'
    }

    # --- 策略净值 ---
    ax.plot(
        df.index, df['Equity_Curve'],
        label='Strategy',
        color=color_map['Strategy'],
        lw=2.2
    )

    # --- RP-friendly benchmarks（不同颜色）---
    bench_order = [
        ('Benchmark_RP_InvVol', 'Naive RP (Inv-Vol)'),
        ('Benchmark_60_40', '60/40'),
        ('Benchmark_EW_Core', 'Equal Weight Core'),
    ]
    for col, label in bench_order:
        if col in df.columns:
            ax.plot(
                df.index, df[col],
                label=label,
                color=color_map.get(col, 'gray'),
                alpha=0.85,
                ls='--',
                lw=1.6
            )

    # --- 可选：保留 SPY legacy 对照（也用独立颜色）---
    if 'Benchmark_SPY' in df.columns:
        ax.plot(
            df.index, df['Benchmark_SPY'],
            label='SPY (Legacy Bench)',
            color=color_map.get('Benchmark_SPY', 'black'),
            alpha=0.6,
            ls=':',
            lw=1.3
        )

    # --- 轴与标题 ---
    ax.set_yscale('log')
    ax.set_title("Cumulative Return (Log Scale)", fontweight='bold')
    ax.legend()

    # --- 指标文本卡片（居中）---
    text_str = '\n'.join([
        f"{k}: {v:.2%}" if k not in ['Sharpe', 'Sortino', 'Skew', 'Kurtosis']
        else f"{k}: {v:.2f}"
        for k, v in stats.items()
    ])

    props = dict(boxstyle='round', facecolor='white', alpha=0.75, edgecolor='gray')

    # ✅ 居中放置
    ax.text(
        0.5, 0.8, text_str,
        transform=ax.transAxes,
        fontsize=11,
        ha='center', va='center',
        bbox=props
    )

    plt.tight_layout()
    plt.savefig(SAVE_DIR / "01_summary_performance.png")
    plt.close()

def plot_1b_benchmark_stats(df):
    """
    图1b: 策略 + 各 Benchmark 的核心指标总览（单独一张图）
    依赖 df 中已存在的 Equity_Curve 与 Benchmark_* 曲线
    """
    curves_map = {
        "Strategy": "Equity_Curve",
        "Naive RP (Inv-Vol)": "Benchmark_RP_InvVol",
        "60/40": "Benchmark_60_40",
        "Equal Weight Core": "Benchmark_EW_Core",
        "SPY (Legacy)": "Benchmark_SPY"
    }

    stats_rows = {}

    for name, col in curves_map.items():
        if col in df.columns:
            curve = df[col].dropna()
            if len(curve) < 5:
                continue

            # ✅ 从净值曲线推 daily return
            daily_ret = curve.pct_change().dropna()

            # 用你已有的函数
            s = calc_advanced_stats(daily_ret)

            # 只挑“最核心、最能横向对比的”
            stats_rows[name] = {
                "CAGR": s["CAGR"],
                "Vol": s["Vol"],
                "Sharpe": s["Sharpe"],
                "Sortino": s["Sortino"],
                "MaxDD": df["Drawdown"].min() if name == "Strategy" else np.nan,
                "Win Rate": s["Win Rate"],
                "VaR (95%)": s["VaR (95%)"],
            }

    if not stats_rows:
        return

    stats_df = pd.DataFrame(stats_rows).T

    # ✅ 对于非 Strategy 的 MaxDD：用各自曲线计算一个
    # 这样更公平
    for name, col in curves_map.items():
        if name != "Strategy" and col in df.columns:
            curve = df[col].dropna()
            if len(curve) > 5:
                running_max = curve.cummax()
                dd = (curve - running_max) / running_max
                stats_df.loc[name, "MaxDD"] = dd.min()

    # 排序让视觉更舒服
    preferred_order = ["Strategy", "Naive RP (Inv-Vol)", "60/40", "Equal Weight Core", "SPY (Legacy)"]
    stats_df = stats_df.reindex([x for x in preferred_order if x in stats_df.index])

    # ---- 画图：Heatmap ----
    fig, ax = plt.subplots(figsize=(10, 3.5 + 0.5 * len(stats_df)))

    # 百分比列
    pct_cols = ["CAGR", "Vol", "MaxDD", "Win Rate", "VaR (95%)"]

    # 格式化显示用的副本
    display_df = stats_df.copy()
    for c in pct_cols:
        if c in display_df.columns:
            display_df[c] = display_df[c] * 100

    # Sharpe/Sortino 保留数值
    # 用 annot=True 直接显示
    sns.heatmap(
        display_df,
        annot=True,
        fmt=".2f",
        cmap="RdYlGn",
        center=0,
        cbar=False,
        ax=ax
    )

    # 轴标题美化
    ax.set_title("Strategy & Benchmark Statistics Overview", fontweight="bold")
    ax.set_xlabel("")
    ax.set_ylabel("")

    # 手动把百分比列标题补上 %
    new_xticks = []
    for col in display_df.columns:
        if col in pct_cols:
            new_xticks.append(f"{col} (%)")
        else:
            new_xticks.append(col)
    ax.set_xticklabels(new_xticks, rotation=0)

    plt.tight_layout()
    plt.savefig(SAVE_DIR / "01b_benchmark_stats.png")
    plt.close()

def plot_2_drawdown_analysis(df):
    """图2: 回撤深度 + 滚动波动率"""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

    dd = df['Drawdown']
    ax1.fill_between(dd.index, dd, 0, color='red', alpha=0.3)
    ax1.plot(dd.index, dd, color='red', lw=1)
    ax1.set_title("Underwater Plot (Drawdown)", fontweight='bold')
    ax1.set_ylabel("Drawdown %")

    roll_vol = df['Portfolio_Daily_Ret'].rolling(63).std() * np.sqrt(252)
    ax2.plot(roll_vol.index, roll_vol, color='orange', lw=1.5)
    ax2.set_title("3-Month Rolling Volatility (Annualized)", fontweight='bold')
    ax2.set_ylabel("Vol %")

    plt.tight_layout()
    plt.savefig(SAVE_DIR / "02_risk_structure.png")
    plt.close()

def plot_3_rolling_metrics(df):
    """图3: 滚动 Sharpe (稳定性检查)"""
    window = 252
    r = df['Portfolio_Daily_Ret']

    roll_ret = r.rolling(window).mean() * 252
    roll_std = r.rolling(window).std() * np.sqrt(252)

    # 防止分母为 0 导致爆炸
    roll_sharpe = roll_ret / roll_std.replace(0, np.nan)

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(roll_sharpe.index, roll_sharpe, color='green', lw=1.5)
    ax.axhline(np.nanmean(roll_sharpe), color='green', ls='--', alpha=0.5, label='Avg')
    ax.axhline(0, color='black', lw=1)

    ax.set_title(f"Rolling {window}-Day Sharpe Ratio", fontweight='bold')
    ax.legend()

    plt.tight_layout()
    plt.savefig(SAVE_DIR / "03_stability_rolling_sharpe.png")
    plt.close()

def plot_4_regime_analysis(df):
    """图4: 分体制表现"""
    if 'Regime' not in df.columns:
        return

    g = df.groupby('Regime')['Portfolio_Daily_Ret']
    regime_stats = pd.DataFrame({
        'Ann Return': g.mean() * 252,
        'Ann Vol': g.std() * np.sqrt(252),
        'Count': g.count()
    })
    regime_stats['Sharpe'] = regime_stats['Ann Return'] / regime_stats['Ann Vol'].replace(0, np.nan)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    sns.barplot(x=regime_stats.index, y=regime_stats['Ann Return'], ax=ax1, palette='viridis')
    ax1.set_title("Annualized Return by Regime", fontweight='bold')
    ax1.axhline(0, color='black')

    sns.scatterplot(
        data=regime_stats, x='Ann Vol', y='Ann Return', hue=regime_stats.index,
        s=200, ax=ax2, palette='viridis', legend=True
    )
    for idx, row in regime_stats.iterrows():
        ax2.text(row['Ann Vol'], row['Ann Return'], f" R{idx}", fontsize=12)

    ax2.set_title("Risk/Return Profile by Regime", fontweight='bold')
    ax2.set_xlabel("Volatility")
    ax2.set_ylabel("Return")

    plt.tight_layout()
    plt.savefig(SAVE_DIR / "04_regime_consistency.png")
    plt.close()

def plot_5_turnover_cost(df):
    """图5: 换手率与成本敏感性"""
    w_cols = [c for c in df.columns if c.startswith('W_')]
    if not w_cols:
        return

    weights = df[w_cols].copy()

    daily_turnover = weights.diff().abs().sum(axis=1)
    ann_turnover = daily_turnover.mean() * 252 * 0.5  # 单边年化

    costs_bps = [0, 5, 10, 20]
    fig, ax = plt.subplots(figsize=(12, 6))

    original_ret = df['Portfolio_Daily_Ret'].fillna(0.0)

    for cost in costs_bps:
        cost_impact = daily_turnover.fillna(0.0) * (cost / 10000)
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
    """图6: 收益归因"""
    w_cols = [c for c in df.columns if c.startswith('W_')]
    valid_assets = [c.replace('W_', '') for c in w_cols]
    valid_assets = [a for a in valid_assets if a in df_assets.columns]

    if not valid_assets:
        return

    common_idx = df.index.intersection(df_assets.index)
    w_aligned = df.loc[common_idx, [f"W_{a}" for a in valid_assets]].fillna(0.0)
    r_aligned = df_assets.loc[common_idx, valid_assets].fillna(0.0)

    contrib = w_aligned.values * r_aligned.values
    contrib_df = pd.DataFrame(contrib, index=common_idx, columns=valid_assets)

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
    daily = df['Portfolio_Daily_Ret'].fillna(0.0)
    monthly = daily.resample('M').apply(lambda x: (1 + x).prod() - 1)

    monthly_df = pd.DataFrame({
        'Year': monthly.index.year,
        'Month': monthly.index.month,
        'Return': monthly.values
    })

    pivot = monthly_df.pivot(index='Year', columns='Month', values='Return')

    fig, ax = plt.subplots(figsize=(10, len(pivot) * 0.5 + 2))
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

    # 2. 构建 RP-friendly benchmarks 并合并
    bench_df = build_rp_like_benchmarks(df_assets)
    if not bench_df.empty:
        common_idx = df.index.intersection(bench_df.index)
        df = df.loc[common_idx].copy()
        bench_df = bench_df.loc[common_idx].copy()
        df = df.join(bench_df, how='left')

    # 3. 计算策略统计
    stats = calc_advanced_stats(df['Portfolio_Daily_Ret'])

    print("\n[Key Statistics]")
    for k, v in stats.items():
        print(f"  {k:<12} : {v:.4f}")

    # 4. 生成图表
    print("\n>>> 🎨 Generating Plots in 'analysis_pro/report_images/'...")

    plot_1_summary_stats(df, stats)
    print("  ✅ 01 Summary & Stats (with RP-friendly Benchmarks)")

    # ✅ 新增：单独输出 benchmark stats 总览图
    plot_1b_benchmark_stats(df)
    print("  ✅ 01b Benchmark Stats Overview")

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