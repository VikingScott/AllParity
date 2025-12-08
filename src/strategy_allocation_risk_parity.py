# src/strategy_allocation_risk_parity.py

import pandas as pd
import numpy as np
from src.config_strategy_risk_parity import (
    ALLOCATION_LOOKUP_RP,
    DEFAULT_BUDGETS,
    ALL_ASSETS,
    ASSETS_RISKY,
    VOL_WINDOW,
    TREND_WINDOW
)

def calculate_analytics(price_df: pd.DataFrame):
    """
    预计算波动率和趋势信号
    """
    # 1. Returns
    returns_df = price_df.pct_change().fillna(0)
    
    # 2. Rolling Volatility (Annualized)
    # 最小观测值设为窗口的一半，防止初期全是 NaN
    vol_df = returns_df.rolling(window=VOL_WINDOW, min_periods=VOL_WINDOW//2).std() * np.sqrt(252)
    # 防御性处理：波动率不能为 0 (防止除以零)
    vol_df = vol_df.replace(0, np.nan).fillna(method='bfill').fillna(0.01) 

    # 3. Trend Mask (Price > MA)
    ma_df = price_df.rolling(window=TREND_WINDOW, min_periods=TREND_WINDOW//2).mean()
    # Mask = 1 if Price >= MA, else 0
    # 现金资产 (SGOV/BIL) 默认不受趋势限制，Mask 恒为 1
    trend_mask = (price_df >= ma_df).astype(float)
    for cash_asset in ['SGOV', 'BIL']:
        if cash_asset in trend_mask.columns:
            trend_mask[cash_asset] = 1.0
            
    return vol_df, trend_mask

def get_target_weights_risk_parity(signal_df: pd.DataFrame, price_df: pd.DataFrame) -> pd.DataFrame:
    """
    动态分配引擎 V2: Risk Parity + Trend Filter
    """
    # 1. 预计算指标
    # 对齐索引，确保 price_df 覆盖 signal_df 的时间段
    price_subset = price_df.reindex(signal_df.index, method='ffill')
    vol_df, trend_mask = calculate_analytics(price_subset)
    
    # 2. 准备容器
    weights_df = pd.DataFrame(0.0, index=signal_df.index, columns=ALL_ASSETS)
    
    # 3. 逐行计算 (Iterative Allocation)
    # 虽然慢一点，但逻辑最清晰，不易出错
    for date, row in signal_df.iterrows():
        # A. 获取当前配置表
        key = (row['Regime'], row['Regime_Source'])
        budgets = ALLOCATION_LOOKUP_RP.get(key, DEFAULT_BUDGETS)
        
        # B. 提取固定仓位 (Cash)
        # 假设只有一个主要的 Cash Asset (SGOV)
        fixed_weight = budgets.get('SGOV', 0.0)
        remaining_cap = 1.0 - fixed_weight
        
        # C. 风险平价计算 (针对 Risky Assets)
        # W_i = (Budget_i / Vol_i)
        raw_weights = {}
        total_risk_score = 0.0
        
        current_vols = vol_df.loc[date]
        
        for asset in ASSETS_RISKY:
            if asset in budgets and budgets[asset] > 0:
                asset_vol = current_vols.get(asset, 0.15) # 默认 15% 波动率防崩
                if asset_vol < 0.001: asset_vol = 0.001   # 极小值保护
                
                score = budgets[asset] / asset_vol
                raw_weights[asset] = score
                total_risk_score += score
        
        # D. 归一化 (Normalize) 并应用到剩余仓位
        # Initial Allocation (Before Trend Filter)
        final_row_weights = {asset: 0.0 for asset in ALL_ASSETS}
        final_row_weights['SGOV'] = fixed_weight
        
        if total_risk_score > 0:
            for asset, score in raw_weights.items():
                # 分配权重 = (分数占比) * (剩余仓位空间)
                w = (score / total_risk_score) * remaining_cap
                final_row_weights[asset] = w
        
        # E. 趋势过滤 (Trend Filter) & 现金回收 (Cash Recycling)
        # 检查每个持有资产的趋势
        current_trends = trend_mask.loc[date]
        recycled_cash = 0.0
        
        for asset in ASSETS_RISKY:
            w = final_row_weights[asset]
            if w > 0:
                # 如果趋势向下 (Mask == 0)
                if current_trends.get(asset, 1.0) == 0.0:
                    recycled_cash += w
                    final_row_weights[asset] = 0.0 # 砍仓
        
        # F. 将砍掉的仓位加回 SGOV
        final_row_weights['SGOV'] += recycled_cash
        
        # 填入 DataFrame
        weights_df.loc[date] = pd.Series(final_row_weights)
        
    return weights_df