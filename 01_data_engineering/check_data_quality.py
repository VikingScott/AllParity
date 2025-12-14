# 01_data_engineering/check_data_quality.py

import pandas as pd
import matplotlib.pyplot as plt
import os
import numpy as np

# ==========================================
# 0. 路径配置
# ==========================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

RAW_DIR = os.path.join(PROJECT_ROOT, 'data', 'raw')
PROCESSED_DIR = os.path.join(PROJECT_ROOT, 'data', 'processed')
PLOT_DIR = os.path.join(PROJECT_ROOT, 'outputs', 'plots', '01_data_quality')

if not os.path.exists(PLOT_DIR):
    os.makedirs(PLOT_DIR)

def plot_proxy_vs_etf(name, proxy_series, etf_series, filename):
    """
    通用绘图函数：对比 Proxy Index 和 ETF
    """
    # 1. 提取 ETF 有数据的区间 (ETF Start Date)
    valid_etf = etf_series.dropna()
    if valid_etf.empty:
        print(f"   ⚠️ Skipping {name}: No ETF data found.")
        return
        
    start_date = valid_etf.index[0]
    
    # 2. 截取两者的重叠区间
    df_compare = pd.concat([proxy_series, etf_series], axis=1).dropna()
    
    if df_compare.empty:
        print(f"   ⚠️ Skipping {name}: No overlap.")
        return
        
    col_proxy = df_compare.columns[0]
    col_etf = df_compare.columns[1]
    
    # 3. 归一化 (Rebase to 1.0)
    # 如果是 Price/Index，直接除以第一天
    # 如果是 Return，先 cumprod
    
    # 判断是否为收益率 (简单判断：均值是否很小)
    is_return = df_compare.abs().mean().mean() < 0.1
    
    if is_return:
        nav = (1 + df_compare).cumprod()
    else:
        nav = df_compare
        
    nav = nav / nav.iloc[0]
    
    # 4. 计算指标
    corr = df_compare[col_proxy].corr(df_compare[col_etf])
    
    # 5. 画图
    plt.figure(figsize=(10, 6))
    plt.plot(nav.index, nav[col_proxy], label=f'Proxy Index (Hist)', linewidth=2, alpha=0.8)
    plt.plot(nav.index, nav[col_etf], label=f'Actual ETF (Investable)', linestyle='--', linewidth=1.5, alpha=0.9)
    
    plt.title(f'{name}: Proxy vs ETF Validation\nCorrelation: {corr:.4f} (Since {start_date.date()})')
    plt.ylabel('Normalized Growth')
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    save_path = os.path.join(PLOT_DIR, filename)
    plt.savefig(save_path)
    plt.close()
    print(f"     -> Plot saved: {filename} (Corr: {corr:.4f})")

def run_quality_check():
    print("🔍 [Quality Check] Starting Data Validation...")

    # 1. 加载 Raw 数据 (包含 ETF)
    print("   [1/2] Loading Raw Data (with ETF columns)...")
    df_stock = pd.read_csv(os.path.join(RAW_DIR, 'us_stocks_raw.csv'), index_col=0, parse_dates=True)
    df_credit = pd.read_csv(os.path.join(RAW_DIR, 'credit_raw.csv'), index_col=0, parse_dates=True)
    df_comm = pd.read_csv(os.path.join(RAW_DIR, 'commodities_raw.csv'), index_col=0, parse_dates=True)
    
    # 加载 Treasury Raw (包含 IEF) 和 Processed (包含 Synthetic)
    df_treasury_raw = pd.read_csv(os.path.join(RAW_DIR, 'treasury_raw.csv'), index_col=0, parse_dates=True)
    df_treasury_proc = pd.read_csv(os.path.join(PROCESSED_DIR, 'treasury_processed.csv'), index_col=0, parse_dates=True)

    # 2. 逐个画图
    print("   [2/2] Generating Plots...")
    
    # A. Stocks (Proxy Index vs SPY)
    plot_proxy_vs_etf('US Stocks', 
                      df_stock['US_Stock_Index_Proxy'], 
                      df_stock['US_Stock_ETF_Actual'], 
                      'valid_01_stocks_spy.png')
                      
    # B. Credit (Proxy Index vs LQD)
    plot_proxy_vs_etf('US Credit', 
                      df_credit['Credit_Index_Proxy'], 
                      df_credit['Credit_ETF_Actual'], 
                      'valid_02_credit_lqd.png')
                      
    # C. Commodities (Proxy Index vs GSG)
    plot_proxy_vs_etf('Commodities', 
                      df_comm['Commodity_Index_Proxy'], 
                      df_comm['Commodity_ETF_Actual'], 
                      'valid_03_comm_gsg.png')
                      
    # D. Treasury (Synthetic TR vs IEF)
    # 注意：Synthetic 是 Return，IEF Raw 是 Price
    # 我们把 IEF Price 转成 Return 再对比，或者把 Synthetic 转成 Index
    syn_index = df_treasury_proc['Index_Value'] # 这是我们算出来的净值
    ief_price = df_treasury_raw['Validation_IEF_Price'] # 这是 Yahoo 下载的价格
    
    plot_proxy_vs_etf('US 10Y Treasury', 
                      syn_index, 
                      ief_price, 
                      'valid_04_bond_ief.png')

    print(f"✅ Validation Complete. Plots are in {PLOT_DIR}")

if __name__ == "__main__":
    run_quality_check()