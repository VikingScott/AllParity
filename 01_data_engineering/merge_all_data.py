# 01_data_engineering/merge_all_data.py

import pandas as pd
import os

# ==========================================
# 0. 路径配置
# ==========================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

RAW_DIR = os.path.join(PROJECT_ROOT, 'data', 'raw')
PROCESSED_DIR = os.path.join(PROJECT_ROOT, 'data', 'processed')

if not os.path.exists(PROCESSED_DIR):
    os.makedirs(PROCESSED_DIR)

def merge_all_data():
    print("🚀 [Merge] Starting Grand Data Merge (TR + XR version)...")

    # -------------------------------------------------------
    # 1. 读取各路数据
    # -------------------------------------------------------
    print("   [1/4] Loading Raw & Processed Data...")
    
    # A. Stock (Raw Index Value)
    df_stock = pd.read_csv(os.path.join(RAW_DIR, 'us_stocks_raw.csv'), index_col=0, parse_dates=True)
    # B. Credit (Raw Index Value)
    df_credit = pd.read_csv(os.path.join(RAW_DIR, 'credit_raw.csv'), index_col=0, parse_dates=True)
    # C. Commodity (Raw Index Value)
    df_comm = pd.read_csv(os.path.join(RAW_DIR, 'commodities_raw.csv'), index_col=0, parse_dates=True)
    # D. Risk Free (Monthly Return)
    df_rf = pd.read_csv(os.path.join(RAW_DIR, 'risk_free_monthly.csv'), index_col=0, parse_dates=True)
    # E. Treasury (Processed Return) -> 已经是 Return 了
    df_treasury = pd.read_csv(os.path.join(PROCESSED_DIR, 'treasury_processed.csv'), index_col=0, parse_dates=True)

    # -------------------------------------------------------
    # 2. 计算 Total Returns (TR)
    # -------------------------------------------------------
    print("   [2/4] Calculating Total Returns (TR)...")
    
    # 构建一个大的 DataFrame 存放 TR
    df_returns = pd.DataFrame(index=df_stock.index)
    
    # Stock: Index -> TR
    df_returns['US_Stock_TR'] = df_stock['US_Stock_Index_Proxy'].pct_change()
    
    # Credit: Index -> TR
    df_returns['US_Credit_TR'] = df_credit['Credit_Index_Proxy'].pct_change()
    
    # Commodity: Index -> TR
    df_returns['Commodities_TR'] = df_comm['Commodity_Index_Proxy'].pct_change()
    
    # Treasury: 已经是 TR，直接重命名并加入
    # 注意：treasury_processed.csv 里可能有 'Monthly_Return' 列
    df_returns = df_returns.join(df_treasury['Monthly_Return'].rename('US_Bond_10Y_TR'), how='outer')
    
    # Risk Free: 加入 Rf
    df_returns = df_returns.join(df_rf['Rf_Monthly_Ret'].rename('Risk_Free'), how='left')

    # -------------------------------------------------------
    # 3. 计算 Excess Returns (XR)
    # -------------------------------------------------------
    print("   [3/4] Calculating Excess Returns (TR - Rf)...")
    
    # 去除没有 Rf 的早期数据
    df_returns = df_returns.dropna(subset=['Risk_Free'])
    
    assets = ['US_Stock', 'US_Credit', 'Commodities', 'US_Bond_10Y']
    
    for asset in assets:
        tr_col = f'{asset}_TR'
        xr_col = f'{asset}_XR'
        
        if tr_col in df_returns.columns:
            df_returns[xr_col] = df_returns[tr_col] - df_returns['Risk_Free']

    # -------------------------------------------------------
    # 4. 清洗与保存
    # -------------------------------------------------------
    print("   [4/4] Saving Final Datasets...")
    
    # 去除所有包含 NaN 的行 (取交集，确保所有资产同一天开始)
    df_final = df_returns.dropna()
    
    save_path = os.path.join(PROCESSED_DIR, 'data_final_returns.csv')
    df_final.to_csv(save_path)
    
    print(f"✅ [Success] Final matrix saved to: {save_path}")
    print(f"     Time Range: {df_final.index[0].date()} to {df_final.index[-1].date()}")
    print(f"     Columns: {df_final.columns.tolist()}")
    print("\nPreview:")
    print(df_final.tail())

if __name__ == "__main__":
    merge_all_data()