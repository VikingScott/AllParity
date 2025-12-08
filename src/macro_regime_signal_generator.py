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
    # COLUMN_MAP, # 已移除：不再需要映射，直接使用原始列名
    THRESHOLD_INFLATION_STICKY,
    THRESHOLD_MARKET_PANIC
)

def calculate_macro_trends(df: pd.DataFrame) -> pd.DataFrame:
    """
    第一步：计算宏观基础趋势，并保留绝对水平
    直接使用 CSV 中的原始列名
    """
    signals = pd.DataFrame(index=df.index)
    
    # 直接使用原始数据列名 'Macro_Growth'
    # 确保你的 CSV 输入列名是准确的
    if 'Macro_Growth' in df.columns:
        growth_ma = df['Macro_Growth'].rolling(window=MACRO_TREND_WINDOW).mean()
        signals['Trend_Growth'] = df['Macro_Growth'] - growth_ma
    
    # 2. 通胀趋势
    # 直接使用 'Macro_Inflation_Core' 和 'Macro_Inflation_Head'
    if 'Macro_Inflation_Core' in df.columns and 'Macro_Inflation_Head' in df.columns:
        inf_core_ma = df['Macro_Inflation_Core'].rolling(window=MACRO_TREND_WINDOW).mean()
        inf_head_ma = df['Macro_Inflation_Head'].rolling(window=MACRO_TREND_WINDOW).mean()
        
        trend_core = df['Macro_Inflation_Core'] - inf_core_ma
        trend_head = df['Macro_Inflation_Head'] - inf_head_ma
        
        signals['Trend_Inflation_Blended'] = (
            trend_core * INFLATION_WEIGHTS['core'] + 
            trend_head * INFLATION_WEIGHTS['headline']
        )
        
        # [关键修正]：保留通胀的绝对数值，用于"粘性通胀"判断
        signals['Level_Inflation_Core'] = df['Macro_Inflation_Core']

    return signals

def calculate_market_veto_score(df: pd.DataFrame) -> pd.Series:
    """
    第二步：计算市场否决分数
    直接读取原始信号列
    """
    score = pd.Series(0, index=df.index)
    
    # 直接使用原始列名：'Signal_Curve_T10Y2Y'
    if 'Signal_Curve_T10Y2Y' in df.columns:
        # 倒挂 ( < 0 ) 扣分
        score -= (df['Signal_Curve_T10Y2Y'] < THRESHOLD_CURVE_INVERT).astype(int)
        
    # 直接使用原始列名：'Signal_Risk_DBAA_Minus_DGS10'
    if 'Signal_Risk_DBAA_Minus_DGS10' in df.columns:
        # 信用利差过大 扣分
        score -= (df['Signal_Risk_DBAA_Minus_DGS10'] > THRESHOLD_CREDIT_STRESS).astype(int)
        
    # 直接使用原始列名：'Signal_Vol_VIX'
    if 'Signal_Vol_VIX' in df.columns:
        # VIX 恐慌 扣分
        score -= (df['Signal_Vol_VIX'] > THRESHOLD_VIX_PANIC).astype(int)
    
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
    raw_growth_dir = np.sign(macro_signals.get('Trend_Growth', pd.Series(0, index=macro_signals.index))).fillna(0)
    raw_inflation_dir = np.sign(macro_signals.get('Trend_Inflation_Blended', pd.Series(0, index=macro_signals.index))).fillna(0)
    
    # --- 2. 逻辑修正层 (Business Logic Layer) ---
    
    # 修正 A: 粘性通胀 (Sticky Inflation)
    level_inf_core = macro_signals.get('Level_Inflation_Core', pd.Series(0, index=macro_signals.index))
    high_inflation_mask = (level_inf_core > THRESHOLD_INFLATION_STICKY)
    
    # 只有当原始信号判断为负(Falling)时，才强制修正为正(Rising)
    sticky_fix_mask = (raw_inflation_dir < 0) & high_inflation_mask
    
    adj_inflation_dir = raw_inflation_dir.copy()
    adj_inflation_dir[sticky_fix_mask] = 1.0
    
    # 修正 B: 增长否决 (Growth Veto)
    adj_growth_dir = raw_growth_dir.copy()
    veto_mask = (raw_growth_dir > 0) & (market_score <= THRESHOLD_MARKET_PANIC)
    adj_growth_dir[veto_mask] = -1.0
    
    # 填充 0 值
    adj_growth_dir = adj_growth_dir.replace(0, 1)
    adj_inflation_dir = adj_inflation_dir.replace(0, 1)

    # --- 3. 映射 Regime ---
    def get_regime_label(g, i, score):
        # 修正 C: 危机熔断 (Crisis Circuit Breaker)
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
    df_out['Trend_Growth'] = macro_signals.get('Trend_Growth', 0)
    df_out['Trend_Inflation_Blended'] = macro_signals.get('Trend_Inflation_Blended', 0)
    df_out['Level_Inflation_Core'] = level_inf_core
    
    df_out['Growth_Signal_Adj'] = adj_growth_dir
    df_out['Inflation_Signal'] = adj_inflation_dir
    df_out['Market_Stress_Score'] = market_score
    
    return df_out

def run_signal_pipeline(merged_df: pd.DataFrame) -> pd.DataFrame:
    """
    运行完整的信号生成管道
    """
    macro_trends = calculate_macro_trends(merged_df)
    market_score = calculate_market_veto_score(merged_df)
    regime_df = determine_final_regime(macro_trends, market_score)
    
    # [关键修复]: 将原始的市场信号列透传到输出中
    # 这样测试脚本或后续分析模块就能看到 VIX, Risk 等原始数值，而不仅仅是 Score
    raw_cols_to_keep = [
        'Signal_Vol_VIX', 
        'Signal_Risk_DBAA_Minus_DGS10', 
        'Signal_Curve_T10Y2Y'
    ]
    # 只合并存在的列，防止报错
    existing_cols = [c for c in raw_cols_to_keep if c in merged_df.columns]
    
    if existing_cols:
        regime_df = regime_df.join(merged_df[existing_cols], how='left')
    
    return regime_df