import pandas as pd
from src.core.data import DataLoader

def get_valid_date_range(strategies, benchmark_tickers=['SPY', 'AGG', 'IEF']):
    """
    扫描策略涉及的所有资产，找出最大公共时间窗口
    """
    print("🔍 Scanning Data Availability...")
    
    # 1. 收集所有需要的 Ticker
    all_tickers = set(benchmark_tickers)
    for s in strategies:
        # 兼容两种写法：直接是 list 或者是 Strategy 对象
        if hasattr(s, 'tickers'):
            all_tickers.update(s.tickers)
    
    # 2. 读取数据检查索引
    try:
        full_data = DataLoader.load_returns()
    except Exception as e:
        print(f"❌ Error loading data: {e}")
        return None, None

    existing_tickers = [t for t in all_tickers if t in full_data.columns]
    
    if not existing_tickers:
        print("❌ Critical: No tickers found in dataset!")
        return None, None
        
    # 3. 计算公共区间
    subset = full_data[existing_tickers].dropna()
    
    if subset.empty:
        print("❌ No overlapping data found for these assets.")
        return None, None
        
    min_date = subset.index[0].date()
    max_date = subset.index[-1].date()
    
    print(f"🔗 Max Common Range: {min_date} to {max_date}")
    return str(min_date), str(max_date)

def check_series_health(series, name):
    """检查收益率序列是否正常"""
    if series.empty:
        print(f"❌ [CRITICAL] {name} returns are EMPTY! (No data)")
        return False
    
    total_ret = (1 + series).prod() - 1
    if total_ret == 0.0 and series.std() == 0.0:
        print(f"⚠️ [WARNING] {name} curve is flat (0.0%). Check logic.")
        return False
        
    return True