# src/macro_regime_signal_generator.py (Revised for Consistency)

import pandas as pd
import numpy as np
from src.config_regime import (
    INFLATION_WEIGHTS,
    REGIME_CODE_MAP,
    THRESHOLD_INFLATION_STICKY,
    THRESHOLD_MARKET_PANIC,
    THRESHOLD_GROWTH_ROBUST,
    THRESHOLD_CURVE_INVERT,
    THRESHOLD_VIX_PANIC,
    THRESHOLD_CREDIT_STRESS
)

# ==========================================
# 专属配置参数 (隔离定义)
# ==========================================

# 1. 宏观趋势参数
WINDOW_SHORT = 90
WINDOW_LONG = 252
WEIGHT_SHORT = 0.5
WEIGHT_LONG = 0.5
# [新增] 趋势信号 Deadband (Z-Score)
TREND_DEADBAND_THRESHOLD = 0.20 # 趋势 Z-Score 必须超过 0.2 才能翻转信号

# 2. 收益率曲线 - 持续性参数
CURVE_INVERT_PERSISTENCE_DAYS = 20

# 3. 市场信号 - 分层与滞回阈值 (Enter, Exit)
VIX_TIER_1 = (25.0, 22.0)
VIX_TIER_2 = (35.0, 32.0)

RISK_TIER_1 = (2.5, 2.2)
RISK_TIER_2 = (4.0, 3.7)

# 4. 警报分层阈值 (用户已调整为 -2.5)
THRESHOLD_MARKET_ALERT = -2.5
# [新增] Veto 信号持久性要求
VETO_PERSISTENCE_DAYS = 5 # 警报必须持续 5 天才能否决增长

# ==========================================
# 辅助函数库 (无修改)
# ==========================================

def calculate_rolling_zscore(series: pd.Series, window: int) -> pd.Series:
    """计算滚动 Z-Score: (当前值 - 均值) / 标准差"""
    roll_mean = series.rolling(window=window).mean()
    roll_std = series.rolling(window=window).std()
    roll_std = roll_std.replace(0, np.nan)
    z_score = (series - roll_mean) / roll_std
    return z_score.fillna(0)

def apply_hysteresis_flag(series: pd.Series, threshold_enter: float, threshold_exit: float) -> pd.Series:
    """实现滞回逻辑 (Hysteresis)"""
    mask_on = (series > threshold_enter)
    mask_off = (series < threshold_exit)
    state = pd.Series(np.nan, index=series.index)
    state[mask_on] = 1.0
    state[mask_off] = 0.0
    return state.ffill().fillna(0)


# ==========================================
# 核心逻辑
# ==========================================

def calculate_macro_trends(df: pd.DataFrame) -> pd.DataFrame:
    """Step 1: 计算双窗口加权的宏观趋势，并保留绝对水平 (无修改)"""
    signals = pd.DataFrame(index=df.index)
    
    if 'Macro_Growth' in df.columns:
        growth_z_90 = calculate_rolling_zscore(df['Macro_Growth'], WINDOW_SHORT)
        growth_z_252 = calculate_rolling_zscore(df['Macro_Growth'], WINDOW_LONG)
        signals['Trend_Growth'] = (WEIGHT_SHORT * growth_z_90 + WEIGHT_LONG * growth_z_252)
        signals['Level_Growth'] = df['Macro_Growth']
    
    if 'Macro_Inflation_Core' in df.columns and 'Macro_Inflation_Head' in df.columns:
        core_z_90 = calculate_rolling_zscore(df['Macro_Inflation_Core'], WINDOW_SHORT)
        core_z_252 = calculate_rolling_zscore(df['Macro_Inflation_Core'], WINDOW_LONG)
        trend_core = WEIGHT_SHORT * core_z_90 + WEIGHT_LONG * core_z_252
        
        head_z_90 = calculate_rolling_zscore(df['Macro_Inflation_Head'], WINDOW_SHORT)
        head_z_252 = calculate_rolling_zscore(df['Macro_Inflation_Head'], WINDOW_LONG)
        trend_head = WEIGHT_SHORT * head_z_90 + WEIGHT_LONG * head_z_252
        
        signals['Trend_Inflation_Blended'] = (trend_core * INFLATION_WEIGHTS['core'] + trend_head * INFLATION_WEIGHTS['headline'])
        signals['Level_Inflation_Core'] = df['Macro_Inflation_Core']

    return signals

def calculate_market_veto_score(df: pd.DataFrame) -> pd.Series:
    """Step 2: 计算市场否决分数 (修复曲线倒挂逻辑)"""
    score = pd.Series(0.0, index=df.index)
    
    # A. 收益率曲线 (状态持久化修复)
    if 'Signal_Curve_T10Y2Y' in df.columns:
        is_inverted = (df['Signal_Curve_T10Y2Y'] < THRESHOLD_CURVE_INVERT)
        # 连续 N 天倒挂才算进入状态
        persistence_marker = is_inverted.rolling(window=CURVE_INVERT_PERSISTENCE_DAYS).sum() == CURVE_INVERT_PERSISTENCE_DAYS
        
        # [修复] 倒挂状态一旦进入，除非反转，否则保持扣分
        curve_penalty = pd.Series(np.nan, index=df.index)
        curve_penalty[persistence_marker] = -1.0 # 触发日扣 1 分
        curve_penalty[~is_inverted] = 0.0 # 解除倒挂状态时归 0
        curve_penalty = curve_penalty.ffill().fillna(0.0) # 保持状态直到下一个状态改变
        
        score += curve_penalty 
        
    # B. 信用利差 (分层 + 滞回)
    if 'Signal_Risk_DBAA_Minus_DGS10' in df.columns:
        risk_val = df['Signal_Risk_DBAA_Minus_DGS10']
        score -= apply_hysteresis_flag(risk_val, RISK_TIER_1[0], RISK_TIER_1[1])
        score -= apply_hysteresis_flag(risk_val, RISK_TIER_2[0], RISK_TIER_2[1])

    # C. VIX (分层 + 滞回)
    if 'Signal_Vol_VIX' in df.columns:
        vix_val = df['Signal_Vol_VIX']
        score -= apply_hysteresis_flag(vix_val, VIX_TIER_1[0], VIX_TIER_1[1])
        score -= apply_hysteresis_flag(vix_val, VIX_TIER_2[0], VIX_TIER_2[1])

    return score

def determine_final_regime(
    macro_signals: pd.DataFrame, 
    market_score: pd.Series
) -> pd.DataFrame:
    """
    Step 3: 综合决策 (引入趋势滞回和Veto持久性)
    """
    df_out = pd.DataFrame(index=macro_signals.index)
    
    # 1. 初始方向 (引入 Deadband 滞回)
    trend_growth = macro_signals.get('Trend_Growth', pd.Series(0, index=macro_signals.index))
    trend_inflation = macro_signals.get('Trend_Inflation_Blended', pd.Series(0, index=macro_signals.index))
    
    # [修复] 趋势滞回 Deadband 逻辑
    raw_growth_dir = pd.Series(0, index=macro_signals.index, dtype=float)
    raw_growth_dir[trend_growth > TREND_DEADBAND_THRESHOLD] = 1.0
    raw_growth_dir[trend_growth < -TREND_DEADBAND_THRESHOLD] = -1.0
    # 使用 ffill 保持状态，除非穿过 deadband
    raw_growth_dir = raw_growth_dir.replace(0, np.nan).ffill().fillna(1.0)
    
    raw_inflation_dir = pd.Series(0, index=macro_signals.index, dtype=float)
    raw_inflation_dir[trend_inflation > TREND_DEADBAND_THRESHOLD] = 1.0
    raw_inflation_dir[trend_inflation < -TREND_DEADBAND_THRESHOLD] = -1.0
    raw_inflation_dir = raw_inflation_dir.replace(0, np.nan).ffill().fillna(1.0)
    
    
    # 2. 业务逻辑修正
    
    # A. 粘性通胀 (Sticky Inflation) (无修改)
    level_inf = macro_signals.get('Level_Inflation_Core', pd.Series(0, index=macro_signals.index))
    sticky_mask = (raw_inflation_dir < 0) & (level_inf > THRESHOLD_INFLATION_STICKY)
    adj_inflation_dir = raw_inflation_dir.copy()
    adj_inflation_dir[sticky_mask] = 1.0
    
    # B. 增长修正 (Robust Growth + Veto)
    level_growth = macro_signals.get('Level_Growth', pd.Series(0, index=macro_signals.index))
    adj_growth_dir = raw_growth_dir.copy()
    
    # B1. Robust Growth (韧性修正): Trend < 0 但 Level > 1.5% -> Force +1 (无修改)
    robust_mask = (raw_growth_dir < 0) & (level_growth > THRESHOLD_GROWTH_ROBUST)
    adj_growth_dir[robust_mask] = 1.0
    
    # B2. Growth Veto (警报否决): Score <= -2.5 -> Force -1
    # [修复] 引入 Veto 持久性检查
    veto_trigger = (market_score <= THRESHOLD_MARKET_ALERT)
    
    # 要求 Veto 必须持续 N 天才有效
    veto_persistent_marker = veto_trigger.rolling(window=VETO_PERSISTENCE_DAYS).sum() == VETO_PERSISTENCE_DAYS
    
    veto_mask = veto_persistent_marker.ffill().fillna(False) # 只要触发过，就保持 Veto 状态 N 天
    
    adj_growth_dir[veto_mask] = -1.0
    
    # 填充 0 值
    adj_growth_dir = adj_growth_dir.replace(0, 1) # 应该已经被ffill处理了，这里是最终保险
    adj_inflation_dir = adj_inflation_dir.replace(0, 1)

    # 3. 映射 Regime (默认值已修复为 1)
    def get_regime(g, i, s):
        # 熔断机制：如果分数极低 (<= -2)，强制 Deflation (4)
        if s <= THRESHOLD_MARKET_PANIC: 
            return 4
        return REGIME_CODE_MAP.get((int(g), int(i)), 1) # 默认值修复为 1
    
    df_out['Regime'] = [
        get_regime(g, i, s) 
        for g, i, s in zip(adj_growth_dir, adj_inflation_dir, market_score)
    ]
    
    # 补充 Source 标签 (无修改)
    df_out['Regime_Source'] = ["MARKET_CIRCUIT" if s <= THRESHOLD_MARKET_PANIC else "MACRO_QUADRANT" for s in market_score]
    
    # 4. 透传变量用于 Debug (新增透传 Veto Persistence)
    df_out['Trend_Growth'] = trend_growth
    df_out['Level_Growth'] = level_growth
    df_out['Trend_Inflation_Blended'] = trend_inflation
    df_out['Level_Inflation_Core'] = level_inf
    df_out['Market_Stress_Score'] = market_score
    df_out['Growth_Signal_Adj'] = adj_growth_dir
    df_out['Inflation_Signal_Adj'] = adj_inflation_dir
    df_out['Veto_Active'] = veto_mask.astype(int) # 新增 Veto 状态追踪
    
    return df_out

def run_signal_pipeline(merged_df: pd.DataFrame) -> pd.DataFrame:
    """管道入口 (无修改)"""
    macro = calculate_macro_trends(merged_df)
    score = calculate_market_veto_score(merged_df)
    regime = determine_final_regime(macro, score)
    
    # Join Raw Signals
    raw_cols = ['Signal_Vol_VIX', 'Signal_Risk_DBAA_Minus_DGS10', 'Signal_Curve_T10Y2Y']
    existing = [c for c in raw_cols if c in merged_df.columns]
    if existing:
        regime = regime.join(merged_df[existing], how='left')
        
    return regime