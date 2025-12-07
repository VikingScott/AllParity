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
    核心对齐逻辑 (纯函数)
    输入：两个 DataFrame
    输出：一个合并后的 DataFrame
    逻辑：以 asset_df 为主键，对 macro_df 进行前值填充 (Forward Fill)
    """
    # 1. 宏观数据 Reindex (防 Look-ahead bias 的核心)
    # 任何非交易日的宏观发布，都会被 'ffill' 到下一个交易日
    macro_aligned = macro_df.reindex(asset_df.index, method='ffill')
    
    # 2. 合并
    aligned_df = pd.concat([asset_df, macro_aligned], axis=1)
    
    # 3. 清洗早期缺失值 (不可变性：不修改原 df，返回新的)
    clean_df = aligned_df.dropna()
    
    return clean_df

if __name__ == "__main__":
    # DOP 风格的调用链：像管道一样清晰
    assets, macro = load_raw_datasets()
    final_data = align_datasets(assets, macro)
    
    print(f"Asset Shape: {assets.shape}")
    print(f"Macro Shape: {macro.shape}")
    print(f"Aligned Shape: {final_data.shape}")
    print(final_data.head())