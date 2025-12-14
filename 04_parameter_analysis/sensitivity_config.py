# 04_sensitivity_analysis/sensitivity_config.py

import os

class SensitivityConfig:
    # ------------------------------------------------
    # 1. 参数敏感性测试 (Parameter Sensitivity)
    # ------------------------------------------------
    # 我们要测试的 Lookback Windows (月)
    # 12m (激进), 36m (基准), 60m (迟钝), 120m (超长)
    TEST_WINDOWS = [12, 24, 36, 48, 60, 120]
    
    # ------------------------------------------------
    # 2. 子区间划分 (Sub-period Analysis)
    # ------------------------------------------------
    # 用来回答：策略在不同宏观环境下表现如何？
    SUB_PERIODS = {
        '1. Great Moderation (1993-1999)': ('1993-01-01', '1999-12-31'),
        '2. DotCom & GFC Crisis (2000-2009)': ('2000-01-01', '2009-12-31'),
        '3. Low Vol/Rate Era (2010-2019)': ('2010-01-01', '2019-12-31'),
        '4. Inflation Shock (2020-2025)':  ('2020-01-01', '2025-12-31')
    }
    
    # ------------------------------------------------
    # 3. 路径配置 (引用 03_1 的逻辑，但不修改它)
    # ------------------------------------------------
    # 输出图片路径 (新文件夹，不污染 03)
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
    
    DATA_PATH = os.path.join(PROJECT_ROOT, 'data', 'processed', 'data_final_returns.csv')
    PLOT_DIR = os.path.join(PROJECT_ROOT, 'outputs', 'plots', '04_sensitivity')
    
    if not os.path.exists(PLOT_DIR):
        os.makedirs(PLOT_DIR)