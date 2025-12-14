# 07_final_real_life/analysis_real_world_impact.py

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
import sys

# 路径设置
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, 'data', 'processed')
OUTPUT_DIR = os.path.join(PROJECT_ROOT, 'data', 'processed') # 保存计算后的 Net returns
PLOT_DIR = os.path.join(PROJECT_ROOT, 'outputs', 'plots', '07_final_real_life')

if not os.path.exists(PLOT_DIR):
    os.makedirs(PLOT_DIR)

from real_life_config import RealLifeConfig

def calculate_turnover(weights_df):
    """
    计算双边换手率 (Two-way Turnover)
    Turnover_t = Sum(|w_t - w_{t-1}|)
    注意：这是名义权重的变化，包含了 '被动变化'(价格波动) 和 '主动调仓'。
    精确算法应该剔除价格波动带来的权重漂移，但在月度再平衡假设下，
    我们可以近似认为 |w_t - w_{t-1}| 就是需要交易的量。
    """
    # 填充 NaN (比如第一天)
    w_clean = weights_df.fillna(0)
    # 每日/每月变化绝对值之和
    turnover = w_clean.diff().abs().sum(axis=1)
    return turnover

def apply_frictions(returns_df, weights_df, strategy_name):
    """
    应用真实世界的摩擦力：ETF管理费 + 交易成本
    (融资成本已经在 Returns 里扣过了，这里只需调整 Spread 差异，
     但为了简单，我们假设之前的模拟已经用了正确的 Spread，这里只扣除额外费用)
    """
    # 1. 换手率 (Turnover)
    turnover_series = calculate_turnover(weights_df)
    
    # 2. 交易成本 (Transaction Cost)
    # Cost = Turnover * BPS
    # 注意：Turnover 是总资产的比例。比如 Turnover=0.2 (20%)，Cost = 0.2 * 0.0010
    trans_cost = turnover_series * RealLifeConfig.TRANSACTION_COST_BPS
    
    # 3. 持仓成本 (Holding Cost / MER)
    # Cost = Sum(Weight_i * MER_i) / 12 (月度)
    # 我们先构建一个 MER 向量
    mer_map = RealLifeConfig.ETF_EXPENSE_RATIOS
    # 匹配列名 (去掉前缀 Naive_, Trend_ 等)
    base_cols = [c.replace('Naive_', '').replace('Trend_', '').replace('ERC_', '') for c in weights_df.columns]
    
    # 构建 MER Series
    mers = pd.Series([mer_map.get(c, 0.0) for c in base_cols], index=weights_df.columns)
    
    # 计算每日/每月 MER (假设数据是月度的)
    # MER 是年化的，所以除以 12
    monthly_mer = (weights_df * mers).sum(axis=1) / 12.0
    
    # 4. 计算净收益 (Net Return)
    # Net = Gross - Trans_Cost - Holding_Cost
    net_returns = returns_df - trans_cost - monthly_mer
    
    return net_returns, turnover_series, trans_cost, monthly_mer

def run_impact_analysis():
    print("🚀 [Real Life] Calculating Friction (Turnover, Fees, Taxes)...")
    
    # 1. 读取之前的 Gross Returns 和 Weights
    # 我们需要合并 ERC, Naive, Trend 的数据
    # 这里我们读取各自的文件
    
    # Naive & Trend
    df_ret_trend = pd.read_csv(os.path.join(DATA_DIR, 'trend_vs_naive_returns.csv'), index_col=0, parse_dates=True)
    df_w_trend = pd.read_csv(os.path.join(DATA_DIR, 'trend_vs_naive_weights.csv'), index_col=0, parse_dates=True)
    
    # ERC (如果需要对比 ERC)
    df_ret_erc = pd.read_csv(os.path.join(DATA_DIR, 'erc_vs_naive_returns.csv'), index_col=0, parse_dates=True)
    df_w_erc = pd.read_csv(os.path.join(DATA_DIR, 'erc_vs_naive_weights.csv'), index_col=0, parse_dates=True)
    
    # 提取需要的列
    # Returns
    r_naive = df_ret_trend['Naive_XR']
    r_trend = df_ret_trend['Trend_XR']
    r_erc = df_ret_erc['ERC_XR']
    rf = df_ret_trend['Risk_Free']
    
    # Weights
    w_naive = df_w_trend[[c for c in df_w_trend.columns if 'Naive_' in c]]
    w_trend = df_w_trend[[c for c in df_w_trend.columns if 'Trend_' in c]]
    w_erc = df_w_erc[[c for c in df_w_erc.columns if 'ERC_' in c]]
    
    # 2. 计算 Net Returns
    strategies = {
        'Naive': (r_naive, w_naive),
        'ERC': (r_erc, w_erc),
        'Trend': (r_trend, w_trend)
    }
    
    results = {}
    turnover_stats = {}
    
    for name, (r_gross, w) in strategies.items():
        print(f"   Processing {name}...")
        r_net, turnover, cost_trans, cost_hold = apply_frictions(r_gross, w, name)
        
        # 保存结果
        results[f'{name}_Gross'] = r_gross
        results[f'{name}_Net'] = r_net
        
        # 统计年化换手率
        # 月度 Turnover 求和 / 年数
        total_years = len(r_gross) / 12.0
        annual_turnover = turnover.sum() / total_years
        turnover_stats[name] = annual_turnover
        
        print(f"      -> Annual Turnover: {annual_turnover:.2%} | Avg Cost Drag: {(cost_trans+cost_hold).mean()*12:.2%}/yr")

    # 3. 整合并保存
    df_final = pd.DataFrame(results)
    df_final['Risk_Free'] = rf
    df_final['Bench_6040_XR'] = df_ret_trend['Bench_6040_XR']
    
    out_path = os.path.join(OUTPUT_DIR, 'final_real_life_returns.csv')
    df_final.to_csv(out_path)
    print(f"✅ Final Net Returns Saved: {out_path}")
    
    # 4. 画图：换手率对比 (Bar Chart)
    plt.figure(figsize=(8, 5))
    names = list(turnover_stats.keys())
    values = list(turnover_stats.values())
    colors = ['gray', '#1f77b4', '#2ca02c'] # Naive, ERC, Trend
    
    plt.bar(names, values, color=colors, alpha=0.7)
    plt.ylabel('Annual Two-way Turnover')
    plt.title(f'Strategy Turnover Analysis\n(Impacts Transaction Costs & Taxes)')
    
    # 标数值
    for i, v in enumerate(values):
        plt.text(i, v + 0.05, f"{v:.1%}", ha='center')
        
    plt.ylim(0, max(values) * 1.2)
    plt.grid(axis='y', alpha=0.3)
    
    plt.savefig(os.path.join(PLOT_DIR, 'final_01_turnover.png'))
    print(f"✅ Turnover Plot Saved.")
    
    return df_final, turnover_stats

if __name__ == "__main__":
    run_impact_analysis()