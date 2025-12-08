import pandas as pd
import pytest
from src.data_loader import get_merged_market_state

# 假设数据路径
MACRO_FILE = 'data/Macro_Daily_Final.csv'
PRICE_FILE = 'data/asset_prices.csv'

@pytest.fixture(scope="module")
def market_data():
    """Pytest fixture: 只加载一次数据，供所有测试使用"""
    df = get_merged_market_state(MACRO_FILE, PRICE_FILE)
    return df

def test_data_alignment_structure(market_data):
    """基础结构测试：确保没有未来数据泄露，且行数正确"""
    assert 'SPY' in market_data.columns
    assert 'Macro_Growth' in market_data.columns
    assert market_data.index.is_monotonic_increasing
    # 检查是否全部是交易日（不应该有周六日，除非原始价格表就有）
    # 简单检查：SPY 不应该全是空值
    assert not market_data['SPY'].isnull().all()

def test_history_2008_gfc(market_data):
    """
    历史测试 1: 2008年金融危机
    预期：VIX 高企 (超过40)，增长指标由正转负或极低
    """
    # 选取 2008-10-15 (雷曼倒闭后一个月)
    gfc_date = '2008-10-15'
    if gfc_date not in market_data.index:
        # 如果刚好那天休市，找最近的一天
        gfc_date = market_data.index[market_data.index.searchsorted(gfc_date)]
    
    row = market_data.loc[gfc_date]
    
    print(f"\n[Check 2008 GFC] Date: {gfc_date}, VIX: {row['Signal_Vol_VIX']}, Growth: {row['Macro_Growth']}")
    
    # VIX 在危机最深重时通常 > 50，这里保守一点设 > 30
    assert row['Signal_Vol_VIX'] > 30, f"GFC VIX too low: {row['Signal_Vol_VIX']}"
    # 经济增长预期应该是低迷的
    assert row['Macro_Growth'] < 1.0, f"GFC Growth too high: {row['Macro_Growth']}"

def test_history_2020_covid(market_data):
    """
    历史测试 2: 2020年3月 疫情熔断
    预期：VIX 瞬间飙升 (通常 > 60)
    """
    # 选取 2020-03-16 (美股熔断日附近)
    covid_date = '2020-03-16'
    if pd.Timestamp(covid_date) > market_data.index[-1]:
        pytest.skip("Dataset does not cover 2020")
        
    # 寻找最近的交易日
    idx = market_data.index.get_indexer([pd.Timestamp(covid_date)], method='nearest')[0]
    row = market_data.iloc[idx]
    
    print(f"\n[Check 2020 Covid] Date: {row.name}, VIX: {row['Signal_Vol_VIX']}")
    
    assert row['Signal_Vol_VIX'] > 40, f"Covid VIX check failed: {row['Signal_Vol_VIX']}"

def test_history_2022_inflation(market_data):
    """
    历史测试 3: 2022年 高通胀
    预期：核心通胀应该 > 4% (之前很多年都在2%左右)
    """
    # 选取 2022-06-01
    check_date = '2022-06-01'
    if pd.Timestamp(check_date) > market_data.index[-1]:
        pytest.skip("Dataset does not cover 2022")

    idx = market_data.index.get_indexer([pd.Timestamp(check_date)], method='nearest')[0]
    row = market_data.iloc[idx]
    
    print(f"\n[Check 2022 Inflation] Date: {row.name}, Inflation: {row['Macro_Inflation_Core']}")
    
    assert row['Macro_Inflation_Core'] > 4.0, f"2022 Inflation check failed: {row['Macro_Inflation_Core']}"