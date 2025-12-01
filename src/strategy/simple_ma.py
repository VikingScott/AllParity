from src.strategy.base import BaseStrategy
import pandas as pd

class SimpleMAStrategy(BaseStrategy):
    def __init__(self, tickers, signals_df):
        """
        :param tickers: 交易资产列表
        :param signals_df: 预先加载好的信号 DataFrame
        """
        self.tickers = tickers
        self.signals = signals_df 
        
        # 简单检查
        missing = [t for t in tickers if t not in signals_df.columns]
        if missing:
            print(f"⚠️ Strategy Warning: {missing} not in signal data!")

    def get_weights(self, date):
        if date not in self.signals.index:
            return {}

        daily_sigs = self.signals.loc[date]
        
        # 筛选出信号为 1 的资产
        candidates = [t for t in self.tickers if t in daily_sigs.index and daily_sigs[t] > 0]
        
        if not candidates: return {}
        
        # 等权分配
        w = 1.0 / len(candidates)
        return {t: w for t in candidates}