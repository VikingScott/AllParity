from src.strategy.base import BaseStrategy
import pandas as pd

class SimpleMAStrategy(BaseStrategy):
    """
    均线趋势策略 (Trend Following)
    
    逻辑：
    1. 接收外部传入的 0/1 信号 DataFrame。
    2. 如果某资产信号为 1 (Bullish)，则买入。
    3. 资金在所有 Bullish 资产中等权分配。
    """
    def __init__(self, tickers, signal_df):
        """
        :param tickers: 要交易的资产列表
        :param signal_df: 已经加载好的信号 DataFrame (Index=Date, Col=Ticker)
                          建议在传入前确保它是 shift(1) 过的防未来函数数据。
        """
        super().__init__(tickers)
        self.signals = signal_df
        
        # 简单检查
        missing = [t for t in tickers if t not in self.signals.columns]
        if missing:
            print(f"⚠️ [Strategy] Warning: Tickers {missing} not in signal data!")

    def get_weights(self, date):
        # 1. 查表
        if date not in self.signals.index:
            return {}

        daily_sigs = self.signals.loc[date]
        
        # 2. 筛选
        # 只看我们关注的 tickers
        valid_sigs = daily_sigs.reindex(self.tickers).dropna()
        
        # 3. 决策
        # 找出信号 > 0 的资产
        active_assets = valid_sigs[valid_sigs > 0].index.tolist()
        
        if not active_assets:
            return {} # 全空仓
            
        # 4. 等权分配
        w = 1.0 / len(active_assets)
        return {t: w for t in active_assets}