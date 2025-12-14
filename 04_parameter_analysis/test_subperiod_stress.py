# 04_sensitivity_analysis/test_subperiod_stress.py

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from sensitivity_config import SensitivityConfig

def run_subperiod_test():
    print("🚀 [Sensitivity] Starting Sub-period Stress Test...")
    
    # 1. 读取 03_1 的最终结果 (strategy_results.csv)
    # 注意：这里直接读结果，保证和主回测完全一致
    result_path = os.path.join(SensitivityConfig.PROJECT_ROOT, 'data', 'processed', 'strategy_results.csv')
    if not os.path.exists(result_path):
        print("❌ Strategy results missing. Run 03_1 first.")
        return
    
    df = pd.read_csv(result_path, index_col=0, parse_dates=True)
    
    # 我们主要对比 RP Retail 和 Bench 60/40
    target_strategies = {
        'RP Retail': 'RP_Retail_XR',
        '60/40 Bench': 'Bench_6040_XR'
    }
    
    stats = []
    
    # 2. 循环切片
    for period_name, (start, end) in SensitivityConfig.SUB_PERIODS.items():
        # 切片数据
        df_sub = df.loc[start:end]
        
        if df_sub.empty:
            continue
            
        row = {'Period': period_name}
        
        for name, col in target_strategies.items():
            if col not in df_sub.columns: continue
            
            # 计算夏普
            s_xr = df_sub[col]
            sharpe = s_xr.mean() / s_xr.std() * np.sqrt(12)
            
            # 计算 CAGR (需要 TR)
            col_tr = col.replace('_XR', '_TR')
            s_tr = df_sub[col_tr]
            total_ret = (1 + s_tr).prod()
            months = len(s_tr)
            cagr = total_ret ** (12/months) - 1
            
            # 计算 MaxDD
            cum = (1 + s_tr).cumprod()
            dd = (cum / cum.cummax() - 1).min()
            
            # 存入
            row[f'{name} Sharpe'] = sharpe
            row[f'{name} CAGR'] = cagr
            row[f'{name} MaxDD'] = dd
            
        stats.append(row)
        
    df_stats = pd.DataFrame(stats).set_index('Period')
    
    # 3. 打印报告 (移除 .style.format 依赖，改用内置格式化)
    
    # 格式化显示 (Sharpe & Calmar 使用 .2f，其他使用 .2%)
    
    # A. 收益和回撤类 (百分比)
    pct_cols = [c for c in df_stats.columns if 'Sharpe' not in c]
    df_pct = df_stats[pct_cols].applymap(lambda x: f"{x:.2%}")
    
    # B. 比率类 (数字)
    sharpe_cols = [c for c in df_stats.columns if 'Sharpe' in c]
    df_sharpe = df_stats[sharpe_cols].applymap(lambda x: f"{x:.2f}")

    # 合并输出
    df_report = pd.concat([df_pct, df_sharpe], axis=1)

    print("\n📜 Sub-period Analysis Report:")
    print("="*80)
    print(df_report.to_string())
    print("="*80)
    
    # 4. 存CSV
    df_stats.to_csv(os.path.join(SensitivityConfig.PLOT_DIR, 'sensitivity_02_subperiods.csv'))
    
    
    # 5. 画个热力图 (Sharpe 对比)
    plt.figure(figsize=(10, 5))
    
    # 提取 Sharpe 列
    sharpe_cols = [c for c in df_stats.columns if 'Sharpe' in c]
    df_heatmap = df_stats[sharpe_cols]
    
    sns.heatmap(df_heatmap, annot=True, cmap='RdYlGn', center=0.5, fmt='.2f', linewidths=.5)
    plt.title('Sharpe Ratio across Macro Regimes: RP vs 60/40')
    plt.tight_layout()
    
    save_path = os.path.join(SensitivityConfig.PLOT_DIR, 'sensitivity_02_subperiods_heatmap.png')
    plt.savefig(save_path)
    print(f"✅ Sub-period Plot Saved: {save_path}")

if __name__ == "__main__":
    run_subperiod_test()