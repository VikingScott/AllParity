import pandas as pd
import numpy as np
from pathlib import Path
from src.analysis.metrics import PerformanceMetrics
from src.analysis.rolling import RollingAnalyzer

class ReportGenerator:
    def __init__(self, output_dir):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def save_all(self, results, bench_rets):
        """
        一键生成所有报表
        :param results: dict {strategy_name: daily_returns_series}
        :param bench_rets: daily_returns_series
        """
        print(f"\n📝 Generating Reports in: {self.output_dir}")
        
        self._save_annual_comparison(results, bench_rets)
        self._save_monthly_matrix(results, bench_rets)
        self._save_rolling_analysis(results, bench_rets)
        
        print("🎉 Reports Generated Successfully.")

    def _save_annual_comparison(self, results, bench_rets):
        years = sorted(list(set(bench_rets.index.year)))
        rows = []
        for y in years:
            row = {'Year': y}
            # Bench
            b_y = bench_rets[bench_rets.index.year == y]
            if not b_y.empty:
                m_b = PerformanceMetrics(b_y)
                row['Bench_Ret'] = m_b.cagr()
                row['Bench_MaxDD'] = m_b.max_drawdown()
            
            # Strategies
            for name, s_rets in results.items():
                s_y = s_rets[s_rets.index.year == y]
                if not s_y.empty:
                    m_s = PerformanceMetrics(s_y)
                    row[f'{name}_Ret'] = m_s.cagr()
                    row[f'{name}_MaxDD'] = m_s.max_drawdown()
                    if 'Bench_Ret' in row:
                        row[f'{name}_Alpha'] = m_s.cagr() - row['Bench_Ret']
            rows.append(row)
        pd.DataFrame(rows).to_csv(self.output_dir / "annual_comparison.csv", index=False)

    def _save_monthly_matrix(self, results, bench_rets):
        dfs = []
        for name, s_rets in results.items():
            m = s_rets.resample('ME').apply(lambda x: (1+x).prod() - 1)
            m.name = name
            dfs.append(m)
        
        bench_m = bench_rets.resample('ME').apply(lambda x: (1+x).prod() - 1).rename("Benchmark")
        dfs.append(bench_m)
        
        pd.concat(dfs, axis=1).to_csv(self.output_dir / "monthly_matrix.csv")

    def _save_rolling_analysis(self, results, bench_rets):
        stats = []
        risks = []
        
        # Bench
        an_b = RollingAnalyzer(bench_rets, None)
        stats.append(an_b.calculate_standard_metrics().add_prefix("Bench_"))
        risks.append(an_b.calculate_drawdown_term_structure().add_prefix("Bench_"))
        
        # Strategies
        for name, s_rets in results.items():
            an = RollingAnalyzer(s_rets, bench_rets)
            stats.append(an.calculate_standard_metrics().add_prefix(f"{name}_"))
            risks.append(an.calculate_drawdown_term_structure().add_prefix(f"{name}_"))
            
        if stats: pd.concat(stats, axis=1).dropna(how='all').to_csv(self.output_dir / "rolling_stats.csv")
        if risks: pd.concat(risks, axis=1).dropna(how='all').to_csv(self.output_dir / "rolling_risk.csv")