import pandas as pd
import numpy as np

class RollingAnalyzer:
    def __init__(self, returns_series, benchmark_series=None, risk_free_rate=0.04):
        self.returns = returns_series
        self.benchmark = benchmark_series
        self.rf = risk_free_rate
        self.trading_days = 252

        # 预计算净值曲线 (Start=1.0)
        self.prices = (1 + self.returns).cumprod()
        if self.benchmark is not None:
            self.bench_prices = (1 + self.benchmark).cumprod()

    def calculate_standard_metrics(self, window=252*3):
        # ... (保持不变) ...
        df = pd.DataFrame(index=self.returns.index)
        price_ratio = self.prices / self.prices.shift(window)
        df['CAGR'] = price_ratio.pow(self.trading_days / window) - 1
        df['Vol'] = self.returns.rolling(window).std() * np.sqrt(self.trading_days)
        df['Sharpe'] = (df['CAGR'] - self.rf) / df['Vol'].replace(0, np.nan)
        
        if self.benchmark is not None:
            df['Corr_Bench'] = self.returns.rolling(window).corr(self.benchmark)
            cov = self.returns.rolling(window).cov(self.benchmark)
            var = self.benchmark.rolling(window).var()
            df['Beta'] = cov / var
        return df

    def _max_dd_func(self, x):
        """辅助：计算序列 x 的 MaxDD (NumPy 版本)"""
        # [Fix] 使用 numpy 计算，适配 raw=True
        comp = np.cumprod(1 + x)       # 累计净值
        peak = np.maximum.accumulate(comp) # 历史最高
        dd = (comp - peak) / peak      # 回撤
        return np.min(dd)

    def calculate_drawdown_term_structure(self, windows=[5, 21, 63, 126, 252]):
        df = pd.DataFrame(index=self.returns.index)
        for w in windows:
            col_name = f"MaxDD_{w}d"
            df[col_name] = self.returns.rolling(w).apply(self._max_dd_func, raw=True)
        return df