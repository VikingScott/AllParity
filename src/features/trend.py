import pandas as pd
import numpy as np

class TrendFeatures:
    """
    趋势特征计算器 (纯逻辑版)
    职责: 接收价格矩阵 -> 计算数学指标 -> 输出对齐后的信号
    """
    def __init__(self, prices_df):
        """
        :param prices_df: 全量价格矩阵 (DataFrame)
        """
        self.prices = prices_df

    def calculate_ma_signal(self, window):
        """
        计算均线突破信号
        Logic: Close > MA(window) -> 1.0 (Long)
        """
        if window <= 0:
            raise ValueError("Window must be > 0")
            
        # 1. 计算指标
        ma = self.prices.rolling(window=window).mean()
        
        # 2. 生成逻辑信号
        signal = (self.prices > ma).astype(float)
        
        # 3. [关键] 防未来函数处理
        # 今天的收盘价只能用于明天的决策
        signal = signal.shift(1)
        
        # 4. 清洗
        # 刚上市或计算初期的 NaN 填为 0 (空仓)
        return signal.fillna(0.0)

    def calculate_crossover_signal(self, fast_window, slow_window):
        """
        (示例) 计算双均线交叉信号
        Logic: MA(fast) > MA(slow) -> 1.0
        """
        ma_fast = self.prices.rolling(window=fast_window).mean()
        ma_slow = self.prices.rolling(window=slow_window).mean()
        
        signal = (ma_fast > ma_slow).astype(float).shift(1)
        return signal.fillna(0.0)