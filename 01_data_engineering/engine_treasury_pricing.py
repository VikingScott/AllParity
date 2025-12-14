# 01_data_engineering/engine_treasury.py

import pandas as pd
import numpy as np
import os

# ==========================================
# 0. 路径配置
# ==========================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

RAW_PATH = os.path.join(PROJECT_ROOT, 'data', 'raw', 'treasury_raw.csv')
PROCESSED_DIR = os.path.join(PROJECT_ROOT, 'data', 'processed')

if not os.path.exists(PROCESSED_DIR):
    os.makedirs(PROCESSED_DIR)

# ==========================================
# 1. 核心数学函数: Semiannual + Fractional
# ==========================================
def calculate_treasury_return_semiannual(y_old, y_new, maturity_years=10, hold_months=1):
    """
    Semiannual coupon + fractional discounting.
    IMPORTANT: price_sell computed this way is a DIRTY price (accrued already embedded),
               so DO NOT add accrued again.
    """
    F = 100.0
    m = 2
    t = hold_months / 12.0

    # Par bond at purchase => coupon rate equals y_old (bond-equivalent convention)
    c = y_old
    coupon_cash = (c / m) * F

    # remaining cashflow times from settlement (shifted by t)
    pay_times = np.arange(1/m, maturity_years + 1e-12, 1/m) - t
    pay_times = pay_times[pay_times > 0]

    df = (1.0 + y_new / m) ** (-m * pay_times)

    # Dirty price at settlement (includes accrual implicitly)
    price_sell = coupon_cash * df.sum() + F * df[-1]

    # One-month holding total return (no separate coupon paid in a month)
    total_return = (price_sell - F) / F
    return total_return


# ==========================================
# 2. 批处理引擎 (含 Rolldown 逻辑)
# ==========================================
def process_treasury_data():
    print("🚀 [Treasury Engine] Starting Advanced Pricing Model (Semiannual + Rolldown)...")
    
    # 1. 读取原始数据
    if not os.path.exists(RAW_PATH):
        print(f"❌ Raw data not found: {RAW_PATH}")
        return
        
    df_raw = pd.read_csv(RAW_PATH, index_col=0, parse_dates=True)
    
    # 检查必要列
    if 'US_Treasury_10Y_Yield' not in df_raw.columns:
        print("❌ Column 'US_Treasury_10Y_Yield' missing.")
        return
        
    # 检查是否有辅助列 (7Y) 用于 Rolldown
    has_7y = 'US_Treasury_7Y_Yield' in df_raw.columns
    if has_7y:
        print("   [Info] 7Y Yield found. Rolldown adjustment enabled. ✅")
    else:
        print("   [Info] 7Y Yield missing. Skipping Rolldown (Flat curve assumption).")

    # 2. 预处理：强制转为月末数据 (Month End)
    print("   [1/3] Resampling to Month-End...")
    df_monthly = df_raw.resample('ME').last()
    
    # 转小数 (Yields in FRED are %, e.g., 4.50 -> 0.045)
    y10_series = df_monthly['US_Treasury_10Y_Yield'] / 100.0
    if has_7y:
        y7_series = df_monthly['US_Treasury_7Y_Yield'] / 100.0
    
    # 3. 逐月计算回报
    print("   [2/3] Running Pricing Loop...")
    dates = df_monthly.index
    returns = []
    valid_dates = []
    
    # 从第2个月开始
    for i in range(1, len(dates)):
        # T-1 时刻 (买入)
        # ----------------
        y_old = y10_series.iloc[i-1]
        
        # T 时刻 (卖出)
        # ----------------
        y_new_10y = y10_series.iloc[i]
        
        # --- Rolldown 调整 (核心升级点) ---
        # 我们卖出时，债券剩余期限是 9年11个月 (9.916年)
        # 应该用 9.916年的利率折现，而不是 10年的利率。
        # 如果曲线向上倾斜 (10Y > 7Y)，9.916年的利率应该比 10Y 低一点点。
        
        y_sell_disc = y_new_10y # 默认用 10Y (无 Rolldown)
        
        if has_7y:
            y_new_7y = y7_series.iloc[i]
            # 只有当两个数据都有效时才做调整
            if pd.notnull(y_new_10y) and pd.notnull(y_new_7y):
                # 简单线性插值计算斜率 (Slope per year)
                slope = (y_new_10y - y_new_7y) / (10 - 7)
                
                # 我们顺着曲线滚下来的时间是 1个月 (1/12 年)
                # Rolldown Benefit = Slope * time
                rolldown_yield_drop = slope * (1/12.0)
                
                # 修正后的折现率
                y_sell_disc = y_new_10y - rolldown_yield_drop
        
        # 如果数据缺失 (NaN)，跳过
        if pd.isna(y_old) or pd.isna(y_sell_disc):
            returns.append(np.nan)
            valid_dates.append(dates[i])
            continue
            
        # --- 调用高级定价函数 ---
        ret = calculate_treasury_return_semiannual(
            y_old=y_old, 
            y_new=y_sell_disc, # 使用包含 Rolldown 的利率
            maturity_years=10, 
            hold_months=1
        )
        
        returns.append(ret)
        valid_dates.append(dates[i])
        
    # 4. 构建结果
    s_ret = pd.Series(returns, index=valid_dates, name='US_Treasury_10Y_TR_Monthly').dropna()
    
    # 算净值
    s_index = (1 + s_ret).cumprod()
    s_index.name = 'US_Treasury_10Y_Index'
    
    # 5. 保存
    print("   [3/3] Saving Processed Data...")
    df_out = pd.DataFrame({
        'Monthly_Return': s_ret,
        'Index_Value': s_index
    })
    
    save_path = os.path.join(PROCESSED_DIR, 'treasury_processed.csv')
    df_out.to_csv(save_path)
    
    print(f"✅ [Success] Advanced Treasury data saved to: {save_path}")
    print(f"     Time Range: {df_out.index[0].date()} to {df_out.index[-1].date()}")
    print(df_out.tail())

if __name__ == "__main__":
    process_treasury_data()