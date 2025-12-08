# src/macro_regime_signal_generator_v2.py
# (建议后续直接重命名为 src/macro_regime_signal_generator.py 以覆盖旧版)

import pandas as pd
import numpy as np
from src.config_regime import (
    INFLATION_WEIGHTS,
    REGIME_CODE_MAP,
    THRESHOLD_INFLATION_STICKY, # 建议在 Config 里设为 3.0
    THRESHOLD_MARKET_PANIC      # 建议在 Config 里设为 -2.0
)

# ==========================================
# V2 专属配置参数 (隔离定义)
# ==========================================

# 1. 宏观趋势参数
WINDOW_SHORT = 90
WINDOW_LONG = 252
WEIGHT_SHORT = 0.4
WEIGHT_LONG = 0.6

# 2. 收益率曲线 - 持续性参数
CURVE_INVERT_PERSISTENCE_DAYS = 20

# 3. 市场信号 - 分层与滞回阈值
VIX_TIER_1 = (25.0, 22.0)
VIX_TIER_2 = (35.0, 32.0)
RISK_TIER_1 = (2.5, 2.2)
RISK_TIER_2 = (4.0, 3.7)

# 4. 警报分层阈值 (新增)
# Score <= -1.0 : 警报级 (Alert)，触发 Growth Veto，但不熔断
# Score <= -2.0 : 熔断级 (Panic)，直接锁定 Regime 4 (引用 import 的 THRESHOLD_MARKET_PANIC)
THRESHOLD_MARKET_ALERT = -1.0


# ==========================================
# 辅助函数库
# ==========================================

def calculate_rolling_zscore(series: pd.Series, window: int) -> pd.Series:
    """计算滚动 Z-Score"""
    roll_mean = series.rolling(window=window).mean()
    roll_std = roll_std.replace(0, np.nan)
    z = (series - roll_mean) / roll_std
    return z.replace([np.inf, -np.inf], np.nan).fillna(0)

def apply_hysteresis_flag(series: pd.Series, threshold_enter: float, threshold_exit: float) -> pd.Series:
    """实现滞回逻辑 (Hysteresis)"""
    mask_on = (series > threshold_enter)
    mask_off = (series < threshold_exit)
    state = pd.Series(np.nan, index=series.index)
    state[mask_on] = 1.0
    state[mask_off] = 0.0
    state = state.ffill().fillna(0)
    return state


# ==========================================
# 核心逻辑 (函数名已还原，可直接被外部调用)
# ==========================================

def calculate_macro_trends(df: pd.DataFrame) -> pd.DataFrame:
    """Step 1: 计算双窗口加权的宏观趋势"""
    signals = pd.DataFrame(index=df.index)
    
    # 1. 增长趋势
    if 'Macro_Growth' in df.columns:
        growth_z_90 = calculate_rolling_zscore(df['Macro_Growth'], WINDOW_SHORT)
        growth_z_252 = calculate_rolling_zscore(df['Macro_Growth'], WINDOW_LONG)
        signals['Trend_Growth'] = WEIGHT_SHORT * growth_z_90 + WEIGHT_LONG * growth_z_252
    
    # 2. 通胀趋势
    if 'Macro_Inflation_Core' in df.columns and 'Macro_Inflation_Head' in df.columns:
        # Core
        core_z_90 = calculate_rolling_zscore(df['Macro_Inflation_Core'], WINDOW_SHORT)
        core_z_252 = calculate_rolling_zscore(df['Macro_Inflation_Core'], WINDOW_LONG)
        trend_core = WEIGHT_SHORT * core_z_90 + WEIGHT_LONG * core_z_252
        
        # Headline
        head_z_90 = calculate_rolling_zscore(df['Macro_Inflation_Head'], WINDOW_SHORT)
        head_z_252 = calculate_rolling_zscore(df['Macro_Inflation_Head'], WINDOW_LONG)
        trend_head = WEIGHT_SHORT * head_z_90 + WEIGHT_LONG * head_z_252
        
        # Blended
        signals['Trend_Inflation_Blended'] = (
            trend_core * INFLATION_WEIGHTS['core'] + 
            trend_head * INFLATION_WEIGHTS['headline']
        )
        # 显式保留 Core Level 用于 Sticky Logic
        signals['Level_Inflation_Core'] = df['Macro_Inflation_Core']

    return signals

def calculate_market_veto_score(df: pd.DataFrame) -> pd.Series:
    """Step 2: 计算市场否决分数 (分层 + 滞回)"""
    score = pd.Series(0.0, index=df.index)
    
    # A. 收益率曲线 (慢变量)
    if 'Signal_Curve_T10Y2Y' in df.columns:
        is_inverted = (df['Signal_Curve_T10Y2Y'] < 0).astype(int)
        persistence = is_inverted.rolling(window=CURVE_INVERT_PERSISTENCE_DAYS).sum()
        mask_persistent = (persistence == CURVE_INVERT_PERSISTENCE_DAYS)
        score[mask_persistent] -= 1.0

    # B. 信用利差 (分层)
    if 'Signal_Risk_DBAA_Minus_DGS10' in df.columns:
        risk_val = df['Signal_Risk_DBAA_Minus_DGS10']
        score -= apply_hysteresis_flag(risk_val, RISK_TIER_1[0], RISK_TIER_1[1]) # -1
        score -= apply_hysteresis_flag(risk_val, RISK_TIER_2[0], RISK_TIER_2[1]) # -1 (Total -2)

    # C. VIX (分层)
    if 'Signal_Vol_VIX' in df.columns:
        vix_val = df['Signal_Vol_VIX']
        score -= apply_hysteresis_flag(vix_val, VIX_TIER_1[0], VIX_TIER_1[1]) # -1
        score -= apply_hysteresis_flag(vix_val, VIX_TIER_2[0], VIX_TIER_2[1]) # -1 (Total -2)

    return score

def determine_final_regime(
    macro_signals: pd.DataFrame, 
    market_score: pd.Series
) -> pd.DataFrame:
    """
    Step 3: 综合决策 (分层防御 + 信号源标签)
    """
    df_out = pd.DataFrame(index=macro_signals.index)
    
    # --- 1. 初始方向 (Raw Direction) ---
    raw_growth_dir = np.sign(macro_signals.get('Trend_Growth', pd.Series(0, index=macro_signals.index))).fillna(0)
    raw_inflation_dir = np.sign(macro_signals.get('Trend_Inflation_Blended', pd.Series(0, index=macro_signals.index))).fillna(0)
    
    # --- 2. 业务逻辑层 (Business Logic) ---
    
    # Logic A: Sticky Inflation (锚定 Core Level)
    # 只有当 Trend 向下(-1) 但 Level 依然很高时，才强制修正为 +1
    level_inf_core = macro_signals.get('Level_Inflation_Core', pd.Series(0, index=macro_signals.index))
    sticky_mask = (raw_inflation_dir < 0) & (level_inf_core > THRESHOLD_INFLATION_STICKY)
    
    adj_inflation_dir = raw_inflation_dir.copy()
    adj_inflation_dir[sticky_mask] = 1.0
    
    # Logic B: Growth Veto (Alert Level)
    # 只要 Score <= -1 (进入警报区)，就强制看空增长
    adj_growth_dir = raw_growth_dir.copy()
    
    # [关键修改]: 阈值改为 THRESHOLD_MARKET_ALERT (-1.0)
    veto_mask = (market_score <= THRESHOLD_MARKET_ALERT)
    adj_growth_dir[veto_mask] = -1.0
    
    # 填充 0 值 (默认为 1)
    adj_growth_dir = adj_growth_dir.replace(0, 1)
    adj_inflation_dir = adj_inflation_dir.replace(0, 1)

    # --- 3. 最终映射 (Final Mapping) ---
    
    regimes = []
    sources = []
    
    for g, i, score in zip(adj_growth_dir, adj_inflation_dir, market_score):
        # Logic C: Circuit Breaker (Panic Level)
        # 只有 Score <= -2 (进入熔断区)，才无视宏观，直接锁死
        if score <= THRESHOLD_MARKET_PANIC:
            regimes.append(4)
            sources.append("MARKET_CIRCUIT") # 来源：市场熔断
        else:
            # 正常宏观象限映射
            # 注意：此时 g 已经被 Growth Veto 修正过了(如果 Score 是 -1)
            r = REGIME_CODE_MAP.get((int(g), int(i)), 4)
            regimes.append(r)
            sources.append("MACRO_QUADRANT") # 来源：宏观象限

    df_out['Regime'] = regimes
    df_out['Regime_Source'] = sources  # 新增列：用于后续归因分析
    
    # --- 4. Debug 信息 ---
    df_out['Trend_Growth'] = macro_signals.get('Trend_Growth')
    df_out['Trend_Inflation_Blended'] = macro_signals.get('Trend_Inflation_Blended')
    df_out['Level_Inflation_Core'] = level_inf_core
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