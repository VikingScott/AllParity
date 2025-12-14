# 01_data_engineering/download_risk_free.py

import pandas as pd
import pandas_datareader.data as web
import datetime
import os
import numpy as np

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
    'Rf_Monthly_Rate': 'TB3MS',  # 月度年化利率 (%)
    'Rf_Daily_Rate': 'DTB3'      # 日度年化利率 (%)
}

def download_risk_free():
    print(f"🚀 [Risk Free] Downloading Treasury Bill Rates from FRED...")
    
    # -------------------------------------------------------
    # A. 下载数据
    # -------------------------------------------------------
    try:
        # 一次性下载
        df = web.DataReader(list(ASSETS.values()), 'fred', START_DATE, END_DATE)
        print(f"   Fetched data range: {df.index[0].date()} to {df.index[-1].date()}")
    except Exception as e:
        print(f"❌ Error downloading: {e}")
        return

    # -------------------------------------------------------
    # B. 处理月度数据 (TB3MS)
    # -------------------------------------------------------
    print("   [1/2] Processing Monthly Data (TB3MS)...")
    # 1. 取出月度列
    monthly_series = df[ASSETS['Rf_Monthly_Rate']].dropna()
    
    # 2. 确保是对齐到月末 (FRED 默认是月初 01号)
    # TB3MS 通常代表"当月平均"，我们把它作为"当月持有国债的无风险收益"
    monthly_series = monthly_series.resample('ME').last()
    
    # 3. 计算月度几何收益率 (Geometric Return)
    # 公式: (1 + r_annual)^ (1/12) - 1
    # 注意: 数据是百分数 (e.g. 5.0)，先除以 100
    rf_monthly_ret = (1 + monthly_series / 100.0) ** (1/12) - 1
    rf_monthly_ret.name = 'Rf_Monthly_Ret'
    
    # 保存月度
    monthly_path = os.path.join(RAW_DIR, 'risk_free_monthly.csv')
    rf_monthly_ret.to_csv(monthly_path)
    print(f"     -> Saved monthly Rf to: {monthly_path}")

    # -------------------------------------------------------
    # C. 处理日度数据 (DTB3)
    # -------------------------------------------------------
    print("   [2/2] Processing Daily Data (DTB3)...")
    # 1. 取出日度列并填充空值 (周末/节假日沿用上一个交易日利率)
    daily_series = df[ASSETS['Rf_Daily_Rate']].fillna(method='ffill').dropna()
    
    # 2. 计算日度几何收益率
    # 公式: (1 + r_annual)^ (1/252) - 1
    # 业界通常用 252 (交易日) 或 360/365 (日历日)。
    # 为了与股票回测对齐，建议用 252。如果是算利息成本，通常用 360。
    # 这里我们用 252，方便算 Sharpe。
    rf_daily_ret = (1 + daily_series / 100.0) ** (1/252) - 1
    rf_daily_ret.name = 'Rf_Daily_Ret'
    
    # 保存日度
    daily_path = os.path.join(RAW_DIR, 'risk_free_daily.csv')
    rf_daily_ret.to_csv(daily_path)
    print(f"     -> Saved daily Rf to: {daily_path}")
    
    print("✅ [Success] Risk-Free Rate processing complete.")
    print("\nPreview Monthly:")
    print(rf_monthly_ret.tail(3))
    print("\nPreview Daily:")
    print(rf_daily_ret.tail(3))

if __name__ == "__main__":
    download_risk_free()