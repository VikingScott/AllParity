# src/macro_regime_signal_generator.py

import pandas as pd
import numpy as np
from src.config_regime import (
    INFLATION_WEIGHTS,
    REGIME_CODE_MAP,
    THRESHOLD_INFLATION_STICKY,
    THRESHOLD_MARKET_PANIC,
    THRESHOLD_GROWTH_ROBUST,     # 确保在 config_regime.py 中已定义 (建议 1.5)
    THRESHOLD_CURVE_INVERT,      # 确保 config 中有 (建议 0.0)
    THRESHOLD_VIX_PANIC,         # 确保 config 中有 (建议 25.0) 
    THRESHOLD_CREDIT_STRESS      # 确保 config 中有 (建议 2.5)
)

# ==========================================
# 专属配置参数 (隔离定义)
# ==========================================

# 1. 宏观趋势参数
WINDOW_SHORT = 90
WINDOW_LONG = 252
WEIGHT_SHORT = 0.5
WEIGHT_LONG = 0.5

# 2. 收益率曲线 - 持续性参数
CURVE_INVERT_PERSISTENCE_DAYS = 20

# 3. 市场信号 - 分层与滞回阈值 (Enter, Exit)
VIX_TIER_1 = (25.0, 22.0)  # 紧张 -> 扣 1 分
VIX_TIER_2 = (35.0, 32.0)  # 恐慌 -> 额外扣 1 分

RISK_TIER_1 = (2.5, 2.2)   # 压力 -> 扣 1 分
RISK_TIER_2 = (4.0, 3.7)   # 危机 -> 额外扣 1 分

# 4. 警报分层阈值
THRESHOLD_MARKET_ALERT = -1.0


# ==========================================
# 辅助函数库
# ==========================================

def calculate_rolling_zscore(series: pd.Series, window: int) -> pd.Series:
    """计算滚动 Z-Score: (当前值 - 均值) / 标准差"""
    roll_mean = series.rolling(window=window).mean()
    roll_std = series.rolling(window=window).std()
    
    # 安全处理：防止除以 0
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
    """Step 1: 计算双窗口加权的宏观趋势，并保留绝对水平"""
    signals = pd.DataFrame(index=df.index)
    
    # 1. 增长趋势 (Growth Trend)
    if 'Macro_Growth' in df.columns:
        growth_z_90 = calculate_rolling_zscore(df['Macro_Growth'], WINDOW_SHORT)
        growth_z_252 = calculate_rolling_zscore(df['Macro_Growth'], WINDOW_LONG)
        
        signals['Trend_Growth'] = (
            WEIGHT_SHORT * growth_z_90 + 
            WEIGHT_LONG * growth_z_252
        )
        # [新增] 透传绝对水平，用于 Robust Growth 判断
        signals['Level_Growth'] = df['Macro_Growth']
    
    # 2. 通胀趋势 (Inflation Trend)
    if 'Macro_Inflation_Core' in df.columns and 'Macro_Inflation_Head' in df.columns:
        # Core Z-Scores
        core_z_90 = calculate_rolling_zscore(df['Macro_Inflation_Core'], WINDOW_SHORT)
        core_z_252 = calculate_rolling_zscore(df['Macro_Inflation_Core'], WINDOW_LONG)
        trend_core = WEIGHT_SHORT * core_z_90 + WEIGHT_LONG * core_z_252
        
        # Headline Z-Scores
        head_z_90 = calculate_rolling_zscore(df['Macro_Inflation_Head'], WINDOW_SHORT)
        head_z_252 = calculate_rolling_zscore(df['Macro_Inflation_Head'], WINDOW_LONG)
        trend_head = WEIGHT_SHORT * head_z_90 + WEIGHT_LONG * head_z_252
        
        # 混合 Core 和 Headline
        signals['Trend_Inflation_Blended'] = (
            trend_core * INFLATION_WEIGHTS['core'] + 
            trend_head * INFLATION_WEIGHTS['headline']
        )
        
        # 保留绝对值用于 Sticky Logic
        signals['Level_Inflation_Core'] = df['Macro_Inflation_Core']

    return signals

def calculate_market_veto_score(df: pd.DataFrame) -> pd.Series:
    """Step 2: 计算市场否决分数 (分层 + 滞回 + 慢变量)"""
    score = pd.Series(0.0, index=df.index)
    
    # A. 收益率曲线 (慢变量)
    if 'Signal_Curve_T10Y2Y' in df.columns:
        is_inverted = (df['Signal_Curve_T10Y2Y'] < THRESHOLD_CURVE_INVERT).astype(int)
        # 连续 N 天倒挂才扣分
        persistence_check = is_inverted.rolling(window=CURVE_INVERT_PERSISTENCE_DAYS).sum()
        mask_persistent = (persistence_check == CURVE_INVERT_PERSISTENCE_DAYS)
        score[mask_persistent] -= 1.0

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
    Step 3: 综合决策 (含 Robust Growth 修正)
    """
    df_out = pd.DataFrame(index=macro_signals.index)
    
    # 1. 初始方向
    # 填 0 处理冷启动
    raw_growth_dir = np.sign(macro_signals.get('Trend_Growth', pd.Series(0, index=macro_signals.index))).fillna(0)
    raw_inflation_dir = np.sign(macro_signals.get('Trend_Inflation_Blended', pd.Series(0, index=macro_signals.index))).fillna(0)
    
    # 2. 业务逻辑修正
    
    # A. 粘性通胀 (Sticky Inflation)
    level_inf = macro_signals.get('Level_Inflation_Core', pd.Series(0, index=macro_signals.index))
    sticky_mask = (raw_inflation_dir < 0) & (level_inf > THRESHOLD_INFLATION_STICKY)
    
    adj_inflation_dir = raw_inflation_dir.copy()
    adj_inflation_dir[sticky_mask] = 1.0
    
    # B. 增长修正 (Robust Growth + Veto)
    level_growth = macro_signals.get('Level_Growth', pd.Series(0, index=macro_signals.index))
    adj_growth_dir = raw_growth_dir.copy()
    
    # B1. Robust Growth (韧性修正): Trend < 0 但 Level > 1.5% -> Force +1
    robust_mask = (raw_growth_dir < 0) & (level_growth > THRESHOLD_GROWTH_ROBUST)
    adj_growth_dir[robust_mask] = 1.0
    
    # B2. Growth Veto (警报否决): Score <= -1 -> Force -1
    # [重要] Veto 的优先级高于 Robust Growth，所以放在后面执行
    veto_mask = (market_score <= THRESHOLD_MARKET_ALERT)
    adj_growth_dir[veto_mask] = -1.0
    
    # 填充 0 值
    adj_growth_dir = adj_growth_dir.replace(0, 1)
    adj_inflation_dir = adj_inflation_dir.replace(0, 1)

    # 3. 映射 Regime
    def get_regime(g, i, s):
        # 熔断机制：如果分数极低 (<= -2)，强制 Deflation (4)
        if s <= THRESHOLD_MARKET_PANIC: 
            return 4
        return REGIME_CODE_MAP.get((int(g), int(i)), 4)

    df_out['Regime'] = [
        get_regime(g, i, s) 
        for g, i, s in zip(adj_growth_dir, adj_inflation_dir, market_score)
    ]
    
    # 补充 Source 标签
    df_out['Regime_Source'] = ["MARKET_CIRCUIT" if s <= THRESHOLD_MARKET_PANIC else "MACRO_QUADRANT" for s in market_score]
    
    # 4. 透传变量用于 Debug
    df_out['Trend_Growth'] = macro_signals.get('Trend_Growth')
    df_out['Level_Growth'] = level_growth
    df_out['Trend_Inflation_Blended'] = macro_signals.get('Trend_Inflation_Blended')
    df_out['Level_Inflation_Core'] = level_inf
    df_out['Market_Stress_Score'] = market_score
    df_out['Growth_Signal_Adj'] = adj_growth_dir
    df_out['Inflation_Signal_Adj'] = adj_inflation_dir
    
    return df_out

def run_signal_pipeline(merged_df: pd.DataFrame) -> pd.DataFrame:
    """管道入口"""
    macro = calculate_macro_trends(merged_df)
    score = calculate_market_veto_score(merged_df)
    regime = determine_final_regime(macro, score)
    
    # Join Raw Signals
    raw_cols = ['Signal_Vol_VIX', 'Signal_Risk_DBAA_Minus_DGS10', 'Signal_Curve_T10Y2Y']
    existing = [c for c in raw_cols if c in merged_df.columns]
    if existing:
        regime = regime.join(merged_df[existing], how='left')
        
    return regime