import pandas as pd
from datetime import datetime
from pathlib import Path
from src.core.data import DataLoader
from src.backtester.engine import BacktestEngine

class ResearchRunner:
    def __init__(self, scenarios, benchmark_setup):
        self.scenarios = scenarios
        self.benchmark_setup = benchmark_setup
        self.data_loaded = False
        
    def load_data(self):
        print("📥 Loading Data into Memory...")
        self.returns = DataLoader.load_returns()
        self.ma_signals = DataLoader.load_feature("signal_ma_200.csv") # 暂时硬编码，未来可配置
        
        # 注入信号给策略
        for sc in self.scenarios:
            if hasattr(sc['strategy'], 'signals'):
                sc['strategy'].signals = self.ma_signals
        self.data_loaded = True

    def select_timeframe(self):
        """交互式时间选择"""
        if not self.data_loaded: self.load_data()
        
        print("\n🔍 Analyzing Data Availability...")
        # 收集所有 tickers
        all_tickers = set(self.benchmark_setup['strategy'].tickers)
        for sc in self.scenarios:
            all_tickers.update(sc['strategy'].tickers)
            
        # 计算公共区间
        valid_tickers = [t for t in all_tickers if t in self.returns.columns]
        subset = self.returns[valid_tickers].dropna()
        
        if subset.empty:
            print("❌ No overlapping data found!")
            return None, None
            
        min_date = subset.index[0].date()
        max_date = subset.index[-1].date()
        duration = (max_date - min_date).days / 365.25
        
        print("-" * 50)
        print(f"📊 Assets: {len(valid_tickers)} ({', '.join(valid_tickers[:5])}...)")
        print(f"🔗 Max Common Range: \033[92m{min_date}\033[0m to \033[92m{max_date}\033[0m")
        print(f"   Duration: {duration:.1f} years")
        print("-" * 50)
        
        user_in = input(f"Press [Enter] to use this range, [q] to quit, or type Start Date (YYYY-MM-DD): ").strip()
        
        if user_in.lower() == 'q':
            return None, None
        
        start_date = user_in if user_in else str(min_date)
        return start_date, str(max_date)

    def run(self, output_dir):
        """执行回测并保存原始数据"""
        start, end = self.select_timeframe()
        if not start: return None
        
        print(f"\n🚀 Running Backtest Engine ({start} -> {end})...")
        engine = BacktestEngine(self.returns, start, end)
        
        results = {}
        
        # 1. Run Benchmark
        b_name = self.benchmark_setup['name']
        b_strat = self.benchmark_setup['strategy']
        # 注意：这里我们给 Benchmark 也用 run_strategy 跑，以获得完整的 Cost/Turnover 数据
        # 虽然 config 是无摩擦，但我们要格式统一
        b_ret, b_pos = engine.run(b_strat, config=self.benchmark_setup['config'])
        results[b_name] = {'rets': b_ret, 'pos': b_pos, 'cost': 0.0, 'turnover': 0.0} # 简化，benchmark暂不记录cost细节
        
        # 2. Run Scenarios
        for sc in self.scenarios:
            name = sc['name']
            # Engine 现在返回 (Returns, Positions)
            # 我们需要修改 Engine 让它返回更多细节，或者我们在这里简单处理
            # 现在的 Engine.run 返回的是 (ret_series, pos_df)
            # 为了获取 Cost 和 Turnover，建议修改 Engine 返回 (rets, pos, metrics_df)
            # 但为了不改动太多，我们暂且只存 Returns 和 Pos
            
            rets, pos = engine.run(sc['strategy'], config=sc['config'])
            
            # 对齐
            common = rets.index.intersection(results[b_name]['rets'].index)
            if len(common) > 0:
                results[name] = {
                    'rets': rets.loc[common],
                    'pos': pos.loc[common]
                }
        
        # 对齐 Benchmark 到第一个策略
        first_strat = list(results.keys())[1] # 0 is bench
        common_idx = results[first_strat]['rets'].index
        results[b_name]['rets'] = results[b_name]['rets'].loc[common_idx]
        results[b_name]['pos'] = results[b_name]['pos'].loc[common_idx]

        self._save_raw_data(results, output_dir)
        return results

    def _save_raw_data(self, results, output_dir):
        print("💾 Saving Raw Data...")
        # 保存收益率矩阵
        df_rets = pd.DataFrame({k: v['rets'] for k, v in results.items()})
        df_rets.to_csv(output_dir / "raw_daily_returns.csv")
        
        # 保存每个策略的详细持仓
        raw_dir = output_dir / "raw_details"
        raw_dir.mkdir(exist_ok=True)
        for name, data in results.items():
            data['pos'].to_csv(raw_dir / f"{name}_positions.csv")