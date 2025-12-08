# src/strategy_allocation.py

import pandas as pd
import numpy as np
from src.config_strategy_v1 import (
    ALLOCATION_LOOKUP,
    DEFAULT_WEIGHTS,
    ALL_ASSETS
)

def get_target_weights(signal_df: pd.DataFrame) -> pd.DataFrame:
    """
    核心分配引擎：将 (Regime, Source) 映射为 (Asset Weights)。
    """
    # 1. 准备容器
    # 索引与信号表对齐，列为所有资产
    weights_df = pd.DataFrame(index=signal_df.index, columns=ALL_ASSETS)
    
    # 2. 查表逻辑
    # 这是一个矢量化操作的替代方案，使用 apply 逐行处理
    # 考虑到宏观数据行数不多 (几千行)，apply 的性能完全足够且逻辑最清晰
    
    def map_row_to_weights(row):
        # 构造查表用的 Key: (Regime Code, Source Tag)
        # 例如: (4, "MARKET_CIRCUIT") 或 (1, "MACRO_QUADRANT")
        key = (row['Regime'], row['Regime_Source'])
        
        # 查表，如果找不到（比如由数据缺失导致的异常状态），使用 DEFAULT_WEIGHTS (通常是全现金)
        weight_dict = ALLOCATION_LOOKUP.get(key, DEFAULT_WEIGHTS)
        return weight_dict

    # 3. 执行映射
    # 结果是一个 Series，每一行是一个字典
    weight_dicts = signal_df.apply(map_row_to_weights, axis=1)
    
    # 4. 展开为 DataFrame
    # 将字典列表转换为 DataFrame，并确保索引对齐
    weights_expanded = pd.DataFrame(weight_dicts.tolist(), index=signal_df.index)
    
    # 5. 合并与清洗
    # 确保列顺序一致，并填充潜在的 NaN 为 0.0 (空仓)
    weights_df.update(weights_expanded)
    weights_df = weights_df.fillna(0.0)
    
    return weights_df

def calculate_strategy_returns(weights_df: pd.DataFrame, asset_returns: pd.DataFrame) -> pd.Series:
    """
    回测计算引擎：计算每一天的组合收益率。
    
    关键逻辑：
    - T日的信号 -> T日收盘计算权重 -> T+1日持有 -> 获得 T+1 日的 Asset Returns
    - 因此，权重必须向下 shift(1) 才能与收益率对齐。
    """
    # 1. 滞后一期：今天的仓位，享受明天的收益
    lagged_weights = weights_df.shift(1)
    
    # 2. 对齐数据
    # 取交集索引，确保不做空值运算
    common_index = lagged_weights.index.intersection(asset_returns.index)
    w = lagged_weights.loc[common_index]
    r = asset_returns.loc[common_index]
    
    # 3. 确保资产列名一致 (为了安全)
    # 如果 asset_returns 里有一些这里没配的资产，也不影响，取交集即可
    valid_assets = [c for c in w.columns if c in r.columns]
    w = w[valid_assets]
    r = r[valid_assets]
    
    # 4. 计算点积 (Dot Product)
    # 每一行：sum(weight_i * return_i)
    portfolio_daily_ret = (w * r).sum(axis=1)
    
    return portfolio_daily_ret