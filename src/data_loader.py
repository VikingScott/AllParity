"""
src/data_loader.py
DOP (Data-Oriented Programming) 风格实现
原则：
1. 代码与数据分离：函数只负责变换数据。
2. 不可变性：不修改输入数据，返回新数据。
3. 显式输入：不依赖 class self 状态。
"""

import pandas as pd
from pathlib import Path
from typing import Tuple

# 定义数据存放常数，但允许通过参数覆盖
DEFAULT_DATA_DIR = Path("data")

def load_csv_as_dataframe(file_path: Path, date_col: str = 'date') -> pd.DataFrame:
    """
    通用加载函数：读取 CSV，标准化日期索引
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    df = pd.read_csv(file_path)
    
    # 统一列名为 'date'
    cols = {c: 'date' for c in df.columns if c.lower() == 'date'}
    if cols:
        df = df.rename(columns=cols)
    
    # 设置索引
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').set_index('date')
    
    return df

def load_raw_datasets(data_dir: Path = DEFAULT_DATA_DIR) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    加载 Asset 和 Macro 数据
    :return: (asset_df, macro_df)
    """
    # 显式定义文件名，不藏在类里
    asset_path = data_dir / "asset_returns.csv"
    macro_path = data_dir / "Macro_Daily_Final.csv"
    
    asset_df = load_csv_as_dataframe(asset_path)
    macro_df = load_csv_as_dataframe(macro_path)
    
    return asset_df, macro_df

def align_datasets(asset_df: pd.DataFrame, macro_df: pd.DataFrame) -> pd.DataFrame:
    """
    核心对齐逻辑 (纯函数) - 修正版
    """
    # 1. 宏观数据 Reindex
    macro_aligned = macro_df.reindex(asset_df.index, method='ffill')
    
    # 2. 合并
    aligned_df = pd.concat([asset_df, macro_aligned], axis=1)
    
    # 3. 智能清洗 (Smart Drop)
    # A. 必须清洗掉：宏观数据缺失的日子
    # 如果没有宏观数据，我们无法判断象限，这部分必须扔掉
    macro_cols = macro_df.columns
    aligned_df = aligned_df.dropna(subset=macro_cols)
    
    # B. 必须清洗掉：所有资产都缺失的日子 (比如节假日，虽然 asset_df 索引应该保证了这点)
    asset_cols = asset_df.columns
    aligned_df = aligned_df.dropna(subset=asset_cols, how='all')
    
    # 注意：我们不再对 asset_cols 使用 dropna(how='any')
    # 此时 aligned_df 里，1990年的行，SPY有值，但 GLD 可能是 NaN。
    # 这完全没问题！我们的策略层会处理这个 NaN (即不分配权重)。
    
    return aligned_df

if __name__ == "__main__":
    # DOP 风格的调用链：像管道一样清晰
    assets, macro = load_raw_datasets()
    final_data = align_datasets(assets, macro)
    
    print(f"Asset Shape: {assets.shape}")
    print(f"Macro Shape: {macro.shape}")
    print(f"Aligned Shape: {final_data.shape}")
    print(final_data.head())