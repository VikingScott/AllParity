# 01_data_engineering/download_treasury.py

import pandas as pd
import pandas_datareader.data as web
import yfinance as yf
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
    # 核心原料：10年期收益率
    'DGS10': {'source': 'fred', 'code': 'DGS10'},
    
    # 辅助原料：7年期收益率 (用于计算 Rolldown 斜率)
    # 10年期和7年期之间插值，可以很好地估算 9年11个月的利率
    'DGS7':  {'source': 'fred', 'code': 'DGS7'},
    
    # 验证数据：7-10年期国债 ETF
    'IEF':   {'source': 'yahoo', 'code': 'IEF'}
}

def download_treasury_raw():
    print(f"🚀 [Treasury] Starting Raw Data Download (Enhanced)...")
    
    data_frames = []

    # --- A. 下载 FRED 数据 (DGS10 + DGS7) ---
    print("   [1/2] Fetching Yields (10Y & 7Y) from FRED...")
    try:
        # 一次性下载两个
        codes = [ASSETS['DGS10']['code'], ASSETS['DGS7']['code']]
        df_fred = web.DataReader(codes, 'fred', START_DATE, END_DATE)
        
        df_fred.index.name = 'Date'
        # 重命名列
        df_fred.columns = ['US_Treasury_10Y_Yield', 'US_Treasury_7Y_Yield']
        
        data_frames.append(df_fred)
        print(f"     -> Fetched {len(df_fred)} rows.")
    except Exception as e:
        print(f"     ❌ FRED Download Failed: {e}")

    # --- B. 下载 Yahoo 数据 (IEF) ---
    print("   [2/2] Fetching IEF from Yahoo...")
    try:
        df_yahoo = yf.download(ASSETS['IEF']['code'], start='2000-01-01', end=END_DATE, progress=False, auto_adjust=True)
        
        if isinstance(df_yahoo.columns, pd.MultiIndex):
            series_ief = df_yahoo['Close'].iloc[:, 0]
        else:
            series_ief = df_yahoo['Close']
            
        series_ief.name = 'Validation_IEF_Price'
        data_frames.append(series_ief)
        print(f"     -> Fetched {len(series_ief)} rows.")
    except Exception as e:
        print(f"     ❌ Yahoo Download Failed: {e}")

    # --- C. 合并与保存 ---
    if data_frames:
        print("   [3/3] Merging and Saving...")
        final_df = pd.concat(data_frames, axis=1).sort_index()
        
        save_path = os.path.join(RAW_DIR, 'treasury_raw.csv')
        final_df.to_csv(save_path)
        print(f"✅ [Success] Enhanced Treasury data saved to: {save_path}")
        print(final_df.tail())
    else:
        print("❌ All downloads failed.")

if __name__ == "__main__":
    download_treasury_raw()