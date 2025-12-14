# 01_data_engineering/download_credit.py

import pandas as pd
import yfinance as yf
import pandas_datareader.data as web
import os
import datetime

# ==========================================
# 0. 路径配置
# ==========================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
RAW_DIR = os.path.join(PROJECT_ROOT, 'data', 'raw')

if not os.path.exists(RAW_DIR):
    os.makedirs(RAW_DIR)

# ==========================================
# 1. 参数配置
# ==========================================
START_DATE = '1987-01-01'
END_DATE = datetime.datetime.now().strftime('%Y-%m-%d')

ASSETS = {
    'Credit_Index_Proxy': {'ticker': 'BAMLCC0A0CMTRIV', 'source': 'fred'}, # ICE BofA US Corp Master TR
    'Credit_ETF_Actual': {'ticker': 'LQD', 'source': 'yahoo'}              # iShares iBoxx IG Corp Bond ETF
}

def download_credit():
    print(f"🚀 [Credit] Starting download pipeline...")

    # -------------------------------------------------------
    # A. 下载 FRED 数据 (Index Proxy)
    # -------------------------------------------------------
    print("   [1/3] Fetching Proxy Index (ICE BofA) from FRED...")
    try:
        # FRED 返回的是 Index Value (TR)
        df_fred = web.DataReader(ASSETS['Credit_Index_Proxy']['ticker'], 'fred', START_DATE, END_DATE)
        
        # 重采样到月末 (FRED 数据通常是日频，但也可能是非交易日缺失)
        # ICE 数据本身是 Total Return Index Value
        proxy_series = df_fred.resample('ME').last().squeeze()
        proxy_series.name = 'Credit_Index_Proxy'
        
        print(f"     -> Fetched {len(proxy_series)} months of Proxy Data.")
        print(f"     -> Range: {proxy_series.index[0].date()} to {proxy_series.index[-1].date()}")
        
    except Exception as e:
        print(f"     ❌ FRED Download Failed: {e}")
        return

    # -------------------------------------------------------
    # B. 下载 Yahoo 数据 (Investable ETF)
    # -------------------------------------------------------
    print("   [2/3] Fetching Investable ETF (LQD) from Yahoo...")
    try:
        ticker = ASSETS['Credit_ETF_Actual']['ticker']
        # LQD 始于 2002
        df_yahoo = yf.download(ticker, start='2000-01-01', end=END_DATE, progress=False, auto_adjust=True)
        
        if isinstance(df_yahoo.columns, pd.MultiIndex):
            etf_series = df_yahoo['Close'].iloc[:, 0]
        else:
            etf_series = df_yahoo['Close']
            
        # 重采样到月末
        etf_series = etf_series.resample('ME').last()
        etf_series.name = 'Credit_ETF_Actual'
        
        print(f"     -> Fetched {len(etf_series)} months of ETF Data.")
        
    except Exception as e:
        print(f"     ❌ Yahoo Download Failed: {e}")
        return

    # -------------------------------------------------------
    # C. 合并与保存
    # -------------------------------------------------------
    print("   [3/3] Merging and Saving...")
    
    # 合并
    final_df = pd.concat([proxy_series, etf_series], axis=1)
    
    # 排序
    final_df = final_df.sort_index()
    
    # 保存
    save_path = os.path.join(RAW_DIR, 'credit_raw.csv')
    final_df.to_csv(save_path)
    
    print(f"✅ [Success] Credit data saved to: {save_path}")
    print(final_df.tail())

if __name__ == "__main__":
    download_credit()