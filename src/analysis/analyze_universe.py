import pandas as pd
import sys
from pathlib import Path

# 适配路径，确保能导入 src
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(PROJECT_ROOT))

from src.core.data import DataLoader
from src.analysis.metrics import PerformanceMetrics

# 配置
BENCHMARK = 'SPY'
RF_TICKER = 'DGS3MO'

class UniverseAnalyzer:
    def __init__(self):
        self.returns = DataLoader.load_returns()
        self.prices = DataLoader.load_prices()
        self.macro = DataLoader.load_macro()
        
        # 准备动态无风险利率
        self.rf_series = None
        if self.macro is not None and RF_TICKER in self.macro.columns:
            # 年化百分比 -> 日度小数
            self.rf_series = (self.macro[RF_TICKER] / 100.0) / 252
        else:
            print(f"⚠️  RF Ticker {RF_TICKER} not found. Using static 0.04.")

    def run_analysis(self, window_days=None, title="Full History"):
        """
        :param window_days: 回看天数 (None 代表全历史)
        """
        print(f"\n📊 ASSET UNIVERSE REPORT: {title}")
        print("="*60)

        # 1. 数据切片
        data_slice = self.returns
        if window_days:
            data_slice = self.returns.tail(window_days)
        
        rf_slice = 0.04
        if self.rf_series is not None:
            rf_slice = self.rf_series.reindex(data_slice.index).ffill().fillna(0.0)

        results = []
        
        # 2. 循环计算每个资产的指标 (复用 PerformanceMetrics)
        for ticker in data_slice.columns:
            # 提取单资产收益流
            series = data_slice[ticker].dropna()
            if len(series) < 10: continue # 数据太少跳过
            
            # 对齐 RF
            if isinstance(rf_slice, pd.Series):
                asset_rf = rf_slice.reindex(series.index).fillna(0.0)
            else:
                asset_rf = rf_slice

            # 调用数学核心
            metrics = PerformanceMetrics(series, risk_free_rate=asset_rf)
            
            stats = metrics.get_summary_dict()
            stats['Ticker'] = ticker
            # 补充一些非数学信息
            stats['Years'] = len(series) / 252
            
            results.append(stats)

        # 3. 生成报表
        if not results:
            print("No valid data found.")
            return

        df_res = pd.DataFrame(results).set_index('Ticker')
        # 选一些核心列展示
        cols = ['CAGR', 'Vol', 'Sharpe', 'MaxDD', 'Calmar']
        print(df_res[cols].sort_values('Sharpe', ascending=False))

        # 4. 相关性分析 (保留原有逻辑)
        self.analyze_correlations(data_slice, title)

    def analyze_correlations(self, df, title):
        corr = df.corr()
        print(f"\n⚡ Correlation Analysis ({title})")
        print("-" * 40)
        
        # 与基准的相关性
        if BENCHMARK in corr.columns:
            print(f"Top 5 correlated with {BENCHMARK}:")
            print(corr[BENCHMARK].sort_values(ascending=False).head(6).iloc[1:].to_string())
        
        # 极值对
        print("\nStrongest Pairs (>0.9):")
        c = corr.abs().unstack().sort_values(ascending=False)
        seen = set()
        for idx, val in c.items():
            if val > 0.999 or val < 0.9: continue
            a, b = idx
            pair = tuple(sorted((a, b)))
            if pair in seen: continue
            seen.add(pair)
            print(f"  {a} - {b}: {corr.loc[a,b]:.3f}")

if __name__ == "__main__":
    app = UniverseAnalyzer()
    # 1. 全历史
    app.run_analysis(title="All Time")
    # 2. 最近一年
    app.run_analysis(window_days=252, title="Trailing 1-Year")