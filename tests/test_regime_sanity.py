# tests/test_regime_sanity.py
import pytest
import pandas as pd
from src.data_loader import get_merged_market_state
from src.macro_regime_signal_generator import run_signal_pipeline

# 反向映射以便打印出人能看懂的文字 (例如 4 -> "Deflation")
REGIME_NAME_MAP = {v: k for k, v in {
    "Goldilocks (1)": 1,
    "Reflation (2)": 2,
    "Stagflation (3)": 3,
    "Deflation (4)": 4
}.items()}

@pytest.fixture(scope="module")
def signal_df():
    """
    Fixture: 加载数据并计算信号，只做一次，供后面所有case使用
    """
    # 1. 加载清洗后的数据
    df = get_merged_market_state(
        'data/Macro_Daily_Final.csv', 
        'data/asset_prices.csv'
    )
    # 2. 运行信号管道
    signals = run_signal_pipeline(df)
    return signals

def print_scenario_report(date_str, row):
    """辅助函数：打印漂亮的诊断报告"""
    regime_code = row['Regime']
    # ... name map logic ...
    
    # NOW: Directly access the column names provided by input CSV
    # Because we added the `.join` in run_signal_pipeline, these will exist!
    vix = row.get('Signal_Vol_VIX', 'N/A')
    risk = row.get('Signal_Risk_DBAA_Minus_DGS10', 'N/A')
    
    print(f"\n[{date_str}] Scenario Report:")
    print(f"  > Macro State: Growth={row['Trend_Growth']:.2f}, Inflation={row['Trend_Inflation_Blended']:.2f}")
    print(f"  > Market Veto: Score={row['Market_Stress_Score']} (VIX={vix}, Risk={risk})")
    print(f"  > Signal Logic: Adj_Growth={row['Growth_Signal_Adj']}")
    print(f"  > FINAL REGIME: {regime_code}")
    print("-" * 60)

def test_scenario_2008_gfc(signal_df):
    """
    测试场景 1: 2008年金融危机 (雷曼时刻)
    预期：即使宏观数据有滞后，市场信号(VIX, Risk)也应该强制将体制修正为 Deflation (Regime 4)。
    """
    # 选取 2008-10-10 (全球股市暴跌周)
    target_date = '2008-10-10'
    if pd.Timestamp(target_date) not in signal_df.index:
        pytest.skip(f"{target_date} not in data")
        
    row = signal_df.loc[target_date]
    
    # 1. 打印诊断
    print_scenario_report(target_date, row)
    
    # 2. 核心断言 (Assertion)
    # 市场压力分数应该极低 (VIX>25, Risk>2.5 -> Score <= -2)
    assert row['Market_Stress_Score'] <= -2, "Market failed to detect GFC panic!"
    
    # 增长信号应该被 Veto 修正为 -1 (即使 Trend_Growth 可能是正的)
    assert row['Growth_Signal_Adj'] == -1, "Veto logic failed to force defensive stance!"
    
    # 最终应该是 Regime 4 (Deflation)
    # 注：在危机最深处，通常是股债双杀或通缩。Regime 4 是最安全的避风港。
    assert row['Regime'] == 4, f"Expected Deflation(4), got {row['Regime']}"

def test_scenario_2020_covid(signal_df):
    """
    测试场景 2: 2020年3月 新冠熔断
    预期：VIX 瞬间飙升应触发 Veto，迅速切换至防御模式。
    """
    target_date = '2020-03-16' # 美股熔断日
    if pd.Timestamp(target_date) not in signal_df.index:
        pytest.skip("Data ending before 2020")
        
    row = signal_df.loc[target_date]
    print_scenario_report(target_date, row)
    
    # 断言：必须处于极度压力状态
    assert row['Market_Stress_Score'] <= -2
    assert row['Growth_Signal_Adj'] == -1
    assert row['Regime'] == 4

def test_scenario_2022_inflation(signal_df):
    """
    测试场景 3: 2022年 高通胀确认期
    预期：通胀趋势应该为正，且因为混合了 Headline，反应应该比纯 Core 更敏锐。
    体制应该是 Stagflation (3) 或 Reflation (2)。关键是 Inflation+。
    """
    target_date = '2022-06-15' # CPI 爆表，美联储激进加息
    if pd.Timestamp(target_date) not in signal_df.index:
        pytest.skip("Data ending before 2022")
        
    row = signal_df.loc[target_date]
    print_scenario_report(target_date, row)
    
    # 核心断言：必须识别出通胀向上
    assert row['Inflation_Signal'] == 1, "Failed to detect high inflation regime!"
    
    # 2022年对于 Growth 是有争议的(技术性衰退 vs 强劲就业)，
    # 但只要 Inflation 是 +1，我们就避开了最惨的“股债双多”错判。
    assert row['Regime'] in [2, 3], "Should be in an inflationary regime (2 or 3)"

def test_scenario_2017_goldilocks(signal_df):
    """
    场景 4: 2017 年“漂亮牛市”
    特征：美国增长强 + 核心通胀温和、VIX 极低，整体应是 risk-on 且非衰退体制。
    
    预期：
      - Market_Stress_Score >= 0 （没有系统性恐慌）
      - Regime 不应是 4，且大概率落在 1 或 2
    """
    target_date = "2017-10-20"  # 2017 年典型的平静牛市交易日之一
    if pd.Timestamp(target_date) not in signal_df.index:
        pytest.skip("Data ending before 2017")

    row = signal_df.loc[target_date]
    print_scenario_report(target_date, row)

    # 市场应该是“平静或乐观”，至少不该是 panic 区间
    assert row["Market_Stress_Score"] >= 0, "2017 牛市阶段不应被判定为市场恐慌"

    # 体制不能是 Deflation(4)，且更合理的是 1 或 2
    assert row["Regime"] in [1, 2], f"2017 牛市应处于 Growth+ 的体制，结果 Regime={row['Regime']}"

def test_scenario_2011_euro_crisis(signal_df):
    """
    场景 5: 2011 年美债降级 + 欧债危机高点 (2011-08-08)
    特征：VIX 暴涨、风险资产大跌，但整体信用与宏观未必达到 2008 那种“系统性崩溃”。

    预期：
      - Market_Stress_Score 至少 <= -1 (某个市场维度被触发)
      - Regime 应落在 [3,4] 的防御型体制，而不是 1/2 那种“增长友好”体制
    """
    target_date = "2011-08-08"
    if pd.Timestamp(target_date) not in signal_df.index:
        pytest.skip("Data ending before 2011")

    row = signal_df.loc[target_date]
    print_scenario_report(target_date, row)

    # 至少有一个 panic 信号（VIX>25 or 信用利差>2.5 or 曲线倒挂）
    assert row["Market_Stress_Score"] <= -1, "2011-08-08 应该体现明显的市场压力"

    # 防御型 Regime：Stagflation(3) 或 Deflation(4) 均可接受
    assert row["Regime"] in [3, 4], f"2011 危机高点不应被判为风险友好体制，结果 Regime={row['Regime']}"

def test_scenario_2009_recovery(signal_df):
    """
    场景 6: 2009 年中期复苏阶段
    特征：宏观数据仍偏弱，但金融市场压力已显著缓解，不能再一直触发“GFC 熔断”。

    预期：
      - Market_Stress_Score > THRESHOLD_MARKET_PANIC (= -2)
      - 即 Regime 若为 4，也应该是由 Growth/Inflation 判出来，而不是熔断硬锁。
    """
    target_date = "2009-06-15"
    if pd.Timestamp(target_date) not in signal_df.index:
        pytest.skip("Data ending before 2009")

    row = signal_df.loc[target_date]
    print_scenario_report(target_date, row)

    # 熔断不应再被触发
    assert row["Market_Stress_Score"] > -2, "2009 复苏阶段不应继续触发 GFC 式熔断"
    # 这里不强行约束 Regime 数值，只要不是被 panic 强行锁死就行

def test_scenario_2021_reflation(signal_df):
    """
    场景 7: 2021 年后期，高通胀 + 市场尚未恐慌的 Reflation 阶段
    特征：通胀已经明显上来，但 VIX 没有像 2020/2008 那样失控。

    预期：
      - Inflation_Signal == 1 （进入通胀型环境）
      - Market_Stress_Score > -2 （不触发危机熔断）
      - Regime 应处在 2 或 3 （通胀型体制）
    """
    target_date = "2021-11-10"
    if pd.Timestamp(target_date) not in signal_df.index:
        pytest.skip("Data ending before 2021")

    row = signal_df.loc[target_date]
    print_scenario_report(target_date, row)

    assert row["Inflation_Signal"] == 1, "2021 高通胀阶段应被识别为 Inflation+"
    assert row["Market_Stress_Score"] > -2, "2021 并非 GFC 级别危机，不应触发熔断"
    assert row["Regime"] in [2, 3], f"2021 高通胀环境应落在通胀型体制，结果 Regime={row['Regime']}"