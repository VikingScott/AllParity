# 01_data_engineering/download_commodities.py

import pandas as pd
import yfinance as yf
import os
import numpy as np

# ==========================================
# 0. 路径配置
# ==========================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
RAW_DIR = os.path.join(PROJECT_ROOT, 'data', 'raw')

# 本地 CSV 文件路径 (请确保文件在这个位置)
LOCAL_GSCI_PATH = os.path.join(RAW_DIR, 'GSCI_Month_start_TR.csv')

# ==========================================
# 1. 函数：处理本地 GSCI CSV
# ==========================================
def process_local_gsci():
    print(f"   [1/2] Processing Local GSCI CSV from: {LOCAL_GSCI_PATH}...")
    
    if not os.path.exists(LOCAL_GSCI_PATH):
        print(f"❌ Error: File not found at {LOCAL_GSCI_PATH}")
        print("   Please upload 'GSCI_Month_start_TR.csv' to the data/raw/ folder.")
        return None

    try:
        # 读取 CSV
        df = pd.read_csv(LOCAL_GSCI_PATH)
        
        # 1. 解析日期 (格式是 MM/DD/YYYY)
        df['Date'] = pd.to_datetime(df['Date'], format='%m/%d/%Y')
        
        # 2. 【关键】将日期推到月末 (Month End)
        # 现在的 01/01/1991 代表 1991年1月，应该对齐到 1991-01-31
        df['Date'] = df['Date'] + pd.offsets.MonthEnd(0)
        
        # 设置索引
        df = df.set_index('Date').sort_index()
        
        # 3. 清洗 Price 列 (去除逗号，转 float)
        # 注意：CSV 里的 Price 就是 Total Return Index
        clean_price = df['Price'].astype(str).str.replace(',', '').astype(float)
        
        # 4. 归一化 (让 1990年起点为 1.0，方便对比)
        # 或者保留原始值也可以，这里我们重命名一下
        clean_price.name = 'Commodity_Index_Proxy'
        
        print(f"     -> Loaded {len(clean_price)} months of GSCI TR Data.")
        print(f"     -> Range: {clean_price.index[0].date()} to {clean_price.index[-1].date()}")
        return clean_price

    except Exception as e:
        print(f"❌ Error processing GSCI CSV: {e}")
        return None

# ==========================================
# 2. 函数：下载 Yahoo ETF
# ==========================================
def download_etf_gsg():
    print("   [2/2] Fetching Investable ETF (GSG) from Yahoo...")
    try:
        # GSG 始于 2006
        etf_df = yf.download('GSG', start='2000-01-01', progress=False, auto_adjust=True)
        
        if isinstance(etf_df.columns, pd.MultiIndex):
            etf_series = etf_df['Close'].iloc[:, 0]
        else:
            etf_series = etf_df['Close']
            
        # 重采样到月末
        etf_monthly = etf_series.resample('ME').last()
        etf_monthly.name = 'Commodity_ETF_Actual'
        
        print(f"     -> Fetched {len(etf_monthly)} months of ETF Data.")
        return etf_monthly
        
    except Exception as e:
        print(f"❌ Yahoo Download Failed: {e}")
        return None

# ==========================================
# 3. 主流程
# ==========================================
def main():
    print(f"🚀 [Commodities] Starting Pipeline...")

    # 1. 处理本地 GSCI (Proxy)
    gsci_proxy = process_local_gsci()
    
    # 2. 下载 ETF (Actual)
    etf_actual = download_etf_gsg()
    
    if gsci_proxy is not None:
        # 合并
        print("   [3/3] Merging and Saving...")
        final_df = pd.concat([gsci_proxy, etf_actual], axis=1)
        
        # 排序
        final_df = final_df.sort_index()
        
        # 保存
        save_path = os.path.join(RAW_DIR, 'commodities_raw.csv')
        final_df.to_csv(save_path)
        
        print(f"✅ [Success] Commodity data saved to: {save_path}")
        print(final_df.tail())
    else:
        print("❌ Pipeline failed due to missing GSCI data.")

if __name__ == "__main__":
    main()