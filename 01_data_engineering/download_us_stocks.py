# 01_data_engineering/download_us_stocks.py

import pandas as pd
import yfinance as yf
import os

# ==========================================
# 0. 路径配置 (锚定项目根目录)
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
# 结束时间设为今天
import datetime
END_DATE = datetime.datetime.now().strftime('%Y-%m-%d')

# 定义资产对：Key是保存的列名，Value是Ticker
ASSETS = {
    'US_Stock_Index_Proxy': '^SP500TR',  # 历史回测用：标普500全收益指数
    'US_Stock_ETF_Actual': 'SPY'         # 实盘映射用：SPY ETF (1993年开始)
}

def download_us_stocks():
    print(f"🚀 [US Stocks] Starting download from {START_DATE} to {END_DATE}...")
    
    data_frames = []
    
    for col_name, ticker in ASSETS.items():
        print(f"   Downloading {col_name} ({ticker})...")
        try:
            # auto_adjust=True 会自动处理拆股和分红，得到复权价格
            df = yf.download(ticker, start=START_DATE, end=END_DATE, progress=False, auto_adjust=True)
            
            # 提取 Close 列 (对于 auto_adjust=True，Close 就是 Adj Close/Total Return)
            if isinstance(df.columns, pd.MultiIndex):
                series = df['Close'].iloc[:, 0] # 处理多层索引
            else:
                series = df['Close']
            
            # 重采样到月末 (Month End)
            series_monthly = series.resample('ME').last()
            series_monthly.name = col_name
            
            data_frames.append(series_monthly)
            
            # 打印数据概况
            start_date = series_monthly.index[0].date()
            end_date = series_monthly.index[-1].date()
            print(f"     -> Fetched {len(series_monthly)} months ({start_date} to {end_date})")
            
        except Exception as e:
            print(f"     ❌ Error downloading {ticker}: {e}")

    # 合并
    if data_frames:
        print("   Merging data...")
        final_df = pd.concat(data_frames, axis=1)
        
        # 排序
        final_df = final_df.sort_index()
        
        # 保存到独立文件
        save_path = os.path.join(RAW_DIR, 'us_stocks_raw.csv')
        final_df.to_csv(save_path)
        print(f"✅ [Success] US Stocks data saved to: {save_path}")
        print(final_df.tail())
    else:
        print("❌ [Failure] No data downloaded.")

if __name__ == "__main__":
    download_us_stocks()