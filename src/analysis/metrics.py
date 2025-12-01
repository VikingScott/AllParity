import pandas as pd
import numpy as np

class PerformanceMetrics:
    def __init__(self, daily_returns, risk_free_rate=0.04):
        self.returns = daily_returns
        self.rf = risk_free_rate
        self.trading_days = 252

    def cagr(self):
        if self.returns.empty: return 0.0
        total_ret = (1 + self.returns).prod() - 1
        years = len(self.returns) / self.trading_days
        if years <= 0: return 0.0
        return (1 + total_ret) ** (1 / years) - 1

    def volatility(self):
        return self.returns.std() * np.sqrt(self.trading_days)

    def sharpe(self):
        vol = self.volatility()
        if vol == 0: return 0.0
        # 超额收益的夏普
        excess_ret = self.returns.mean() * self.trading_days - self.rf
        return excess_ret / vol

    def max_drawdown(self):
        cum_ret = (1 + self.returns).cumprod()
        peak = cum_ret.cummax()
        dd = (cum_ret - peak) / peak
        return dd.min()

    def sortino(self):
        # 只计算下行波动
        downside_returns = self.returns[self.returns < 0]
        downside_vol = downside_returns.std() * np.sqrt(self.trading_days)
        if downside_vol == 0: return 0.0
        excess_ret = self.returns.mean() * self.trading_days - self.rf
        return excess_ret / downside_vol

    def calmar(self):
        mdd = abs(self.max_drawdown())
        if mdd == 0: return 0.0
        return self.cagr() / mdd

    def final_value(self, initial_capital=1000):
        return initial_capital * (1 + self.returns).prod()

    def get_summary_dict(self):
        return {
            'CAGR': self.cagr(),
            'Vol': self.volatility(),
            'Sharpe': self.sharpe(),
            'MaxDD': self.max_drawdown(),
            'Sortino': self.sortino(),
            'Calmar': self.calmar(),
            'Final_1k': self.final_value(1000)
        }