"""
策略基类 (Strategy Interface)
所有策略必须继承此类，并实现 get_weights 方法。
"""
from abc import ABC, abstractmethod

class BaseStrategy(ABC):
    def __init__(self, tickers, **kwargs):
        """
        :param tickers: 策略涉及的资产列表
        :param kwargs: 其他策略参数 (如 signal_df, threshold 等)
        """
        self.tickers = tickers

    @abstractmethod
    def get_weights(self, date):
        """
        核心逻辑：输入日期，返回目标仓位。
        
        :param date: pd.Timestamp
        :return: dict {ticker: weight}
                 e.g. {'SPY': 0.6, 'TLT': 0.4}
                 注意：权重之和不一定非要是 1.0 (允许空仓或杠杆，取决于 Engine 设置)
        """
        pass