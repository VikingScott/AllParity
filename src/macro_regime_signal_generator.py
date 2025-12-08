# src/macro_regime_signal_generator.py

import pandas as pd
import numpy as np
from src.config_regime import (
    MACRO_TREND_WINDOW, 
    INFLATION_WEIGHTS, 
    THRESHOLD_VIX_PANIC, 
    THRESHOLD_CREDIT_STRESS, 
    THRESHOLD_CURVE_INVERT,
    REGIME_CODE_MAP,
    COLUMN_MAP,
    THRESHOLD_INFLATION_STICKY, # New
    THRESHOLD_MARKET_PANIC      # New
)

def calculate_macro_trends(df: pd.DataFrame) -> pd.DataFrame:
    """
    第一步：计算宏观基础趋势，并保留绝对水平
    """
    signals = pd.DataFrame(index=df.index)
    
    col_growth = COLUMN_MAP['growth']
    col_inf_core = COLUMN_MAP['inflation_core']
    col_inf_head = COLUMN_MAP['inflation_head']

    # 1. 增长趋势
    growth_ma = df[col_growth].rolling(window=MACRO_TREND_WINDOW).mean()
    signals['Trend_Growth'] = df[col_growth] - growth_ma
    
    # 2. 通胀趋势
    inf_core_ma = df[col_inf_core].rolling(window=MACRO_TREND_WINDOW).mean()
    inf_head_ma = df[col_inf_head].rolling(window=MACRO_TREND_WINDOW).mean()
    
    trend_core = df[col_inf_core] - inf_core_ma
    trend_head = df[col_inf_head] - inf_head_ma
    
    signals['Trend_Inflation_Blended'] = (
        trend_core * INFLATION_WEIGHTS['core'] + 
        trend_head * INFLATION_WEIGHTS['headline']
    )
    
    # [关键修正]：保留通胀的绝对数值，用于"粘性通胀"判断
    signals['Level_Inflation_Core'] = df[col_inf_core]

    return signals

def calculate_market_veto_score(df: pd.DataFrame) -> pd.Series:
    # ... (保持不变) ...
    score = pd.Series(0, index=df.index)
    col_curve = COLUMN_MAP['yield_curve']
    col_risk = COLUMN_MAP['credit_risk']
    col_vix = COLUMN_MAP['vix']
    
    if col_curve in df.columns:
        score -= (df[col_curve] < THRESHOLD_CURVE_INVERT).astype(int)
    if col_risk in df.columns:
        score -= (df[col_risk] > THRESHOLD_CREDIT_STRESS).astype(int)
    if col_vix in df.columns:
        score -= (df[col_vix] > THRESHOLD_VIX_PANIC).astype(int)
    
    return score

def determine_final_regime(
    macro_signals: pd.DataFrame, 
    market_score: pd.Series
) -> pd.DataFrame:
    """
    第三步：综合决策 (含熔断机制)
    """
    df_out = pd.DataFrame(index=macro_signals.index)
    
    # --- 1. 初始信号计算 ---
    # fillna(0) 处理冷启动
    raw_growth_dir = np.sign(macro_signals['Trend_Growth']).fillna(0)
    raw_inflation_dir = np.sign(macro_signals['Trend_Inflation_Blended']).fillna(0)
    
    # --- 2. 逻辑修正层 (Business Logic Layer) ---
    
    # 修正 A: 粘性通胀 (Sticky Inflation)
    # 如果核心通胀绝对值 > 3.0%，强制认为通胀是向上的 (1)，哪怕短期趋势在回调。
    # 逻辑：高通胀背景下，任何回调都是暂时的，防守通胀才是第一要务。
    high_inflation_mask = (macro_signals['Level_Inflation_Core'] > THRESHOLD_INFLATION_STICKY)
    # 只有当原始信号判断为负(Falling)时，才强制修正为正(Rising)
    # 这样避免把本来就要Rising的信号搞乱
    sticky_fix_mask = (raw_inflation_dir < 0) & high_inflation_mask
    
    adj_inflation_dir = raw_inflation_dir.copy()
    adj_inflation_dir[sticky_fix_mask] = 1.0
    
    # 修正 B: 增长否决 (Growth Veto)
    # 保持原有逻辑：市场不好，就别信增长
    adj_growth_dir = raw_growth_dir.copy()
    veto_mask = (raw_growth_dir > 0) & (market_score <= THRESHOLD_MARKET_PANIC)
    adj_growth_dir[veto_mask] = -1.0
    
    # 填充 0 值
    adj_growth_dir = adj_growth_dir.replace(0, 1)
    adj_inflation_dir = adj_inflation_dir.replace(0, 1)

    # --- 3. 映射 Regime ---
    def get_regime_label(g, i, score):
        # 修正 C: 危机熔断 (Crisis Circuit Breaker)
        # 如果市场极度恐慌 (Score <= -2)，直接进入 Regime 4 (Deflation/Cash)
        # 这是为了应对 2008年 GFC 这种股债双杀时刻
        if score <= THRESHOLD_MARKET_PANIC:
             return 4
             
        try:
            return REGIME_CODE_MAP.get((int(g), int(i)), 4)
        except ValueError:
            return 4

    regimes = [
        get_regime_label(g, i, s) 
        for g, i, s in zip(adj_growth_dir, adj_inflation_dir, market_score)
    ]
    
    df_out['Regime'] = regimes
    
    # --- 4. 透传中间变量 (Debugging) ---
    df_out['Trend_Growth'] = macro_signals['Trend_Growth']
    df_out['Trend_Inflation_Blended'] = macro_signals['Trend_Inflation_Blended']
    df_out['Level_Inflation_Core'] = macro_signals['Level_Inflation_Core'] # 方便查看是否触发Sticky
    
    df_out['Growth_Signal_Adj'] = adj_growth_dir
    df_out['Inflation_Signal'] = adj_inflation_dir
    df_out['Market_Stress_Score'] = market_score
    
    return df_out

# run_signal_pipeline 保持不变
def run_signal_pipeline(merged_df: pd.DataFrame) -> pd.DataFrame:
    macro_trends = calculate_macro_trends(merged_df)
    market_score = calculate_market_veto_score(merged_df)
    regime_df = determine_final_regime(macro_trends, market_score)
    return regime_df