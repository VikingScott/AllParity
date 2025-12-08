import pandas as pd
from pathlib import Path
from typing import Tuple, Dict

def load_and_clean_data(
    macro_path: str, 
    price_path: str
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    加载并清洗数据，但不进行合并。
    """
    # 1. 加载宏观数据
    macro = pd.read_csv(macro_path, parse_dates=['Date'], index_col='Date')
    # 宏观数据通常会有 'NA' 字符串或空值，需要处理
    macro = macro.ffill().dropna() 

    # 2. 加载资产价格
    prices = pd.read_csv(price_path, parse_dates=['date'], index_col='date')
    prices = prices.ffill() # 简单的价格修补

    return macro, prices

def align_macro_to_trading_days(
    macro: pd.DataFrame, 
    prices: pd.DataFrame
) -> pd.DataFrame:
    """
    核心对齐逻辑：将宏观数据映射到交易日历上。
    关键点：必须使用 ffill (前向填充)，严禁 bfill (后向填充，那是未来函数)。
    """
    # 以资产价格的索引（交易日）为准
    trading_days = prices.index.sort_values()
    
    # 将宏观数据重索引到交易日，并向前填充
    # reindex 会引入 NaNs (如果某交易日没有宏观数据)，ffill 会用最近的过去数据填充
    macro_aligned = macro.reindex(trading_days, method='ffill')
    
    # 如果开头有空值（因为宏观数据开始得晚），可以选择删除或保留
    # 这里我们保留，由策略层决定如何处理
    return macro_aligned

def get_merged_market_state(macro_path: str, price_path: str) -> pd.DataFrame:
    """
    对外暴露的主函数：获取对齐后的世界视图
    """
    macro_raw, prices_raw = load_and_clean_data(macro_path, price_path)
    macro_aligned = align_macro_to_trading_days(macro_raw, prices_raw)
    
    # 合并成一张宽表 (Wide Table)
    # 加上前缀以防列名冲突
    merged_df = pd.concat([prices_raw, macro_aligned], axis=1)
    
    return merged_df