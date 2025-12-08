import pandas as pd
import pytest
from src.data_loader import align_datasets

def test_alignment_logic_pure():
    """
    DOP 的优势：不需要读取磁盘文件，直接构造内存数据测试逻辑。
    """
    # 1. 构造假的资产数据 (交易日: 周一, 周二, 周三)
    assets = pd.DataFrame(
        {'SPY': [100, 101, 102]}, 
        index=pd.to_datetime(['2023-01-02', '2023-01-03', '2023-01-04'])
    )

    # 2. 构造假的宏观数据 (发布日: 周日, 周二)
    # 注意：周日(01-01)发布的数据，资产端应该在周一(01-02)看到
    macro = pd.DataFrame(
        {'GDP': [2.5, 3.0]}, 
        index=pd.to_datetime(['2023-01-01', '2023-01-03'])
    )

    # 3. 执行纯函数
    result = align_datasets(assets, macro)

    # 4. 断言
    # 周一(02) 应该拿到 周日(01) 的 GDP=2.5
    assert result.loc['2023-01-02', 'GDP'] == 2.5
    # 周二(03) 应该拿到 周二(03) 的 GDP=3.0
    assert result.loc['2023-01-03', 'GDP'] == 3.0
    # 周三(04) 应该沿用 周二(03) 的 GDP=3.0 (Forward Fill)
    assert result.loc['2023-01-04', 'GDP'] == 3.0