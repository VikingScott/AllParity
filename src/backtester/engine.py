"""
================================================================================
📜 DESIGN REQUIREMENTS: BACKTEST ENGINE
================================================================================
1. [Core Responsibility] Event-Driven Simulation:
   - Iterate through time (daily loop).
   - Fetch strategy signals -> Calculate PnL -> Update Portfolio -> Log Results.

2. [Data Integrity]:
   - Must handle NaN/Missing data gracefully (using .fillna(0.0) before operations).
   - Ensure alignment between Strategy signals and Market returns.

3. [Realism & Friction]:
   - Implement Weight Drift: Weights change daily due to asset price movement.
   - Implement Transaction Costs: Apply cost to Turnover based on Config.
   - Support flexible Rebalancing Logic (Time-based vs. Drift-based).

4. [Benchmark]:
   - Provide a built-in 60/40 benchmark calculation for easy comparison.
================================================================================
"""

import pandas as pd
import numpy as np
from src.core.data import DataLoader
from src.backtester.config import BacktestConfig

class BacktestEngine:
    def __init__(self, start_date, end_date):
        # Engine 只负责管时间和数据，不管手续费
        self.returns = DataLoader.load_returns()
        try:
            self.returns = self.returns.loc[start_date:end_date]
        except KeyError:
            print(f"❌ Date range {start_date} to {end_date} not in data!")
            self.returns = pd.DataFrame()
            
        self.dates = self.returns.index
        
    def _is_rebalance_day(self, date_idx, freq, current_weights, target_weights):
        """
        判断今天是否是调仓日
        :param current_weights: 当前持仓 (漂移后)
        :param target_weights: 策略想要的目标持仓
        """
        # 1. 基础模式
        if freq == '1D': return True
        if freq == 'Signal': return True 
        
        # 2. 漂移模式 (Drift-based)
        if freq.startswith('Drift_'):
            try:
                threshold = float(freq.split('_')[1]) # e.g. "Drift_0.05" -> 0.05
            except:
                return True # 解析失败默认调仓
            
            # 如果当前是空仓，或者目标变了，肯定要调
            if current_weights.empty or target_weights.empty:
                return True
                
            # 计算最大偏差
            # 对齐索引
            all_assets = current_weights.index.union(target_weights.index)
            w_curr = current_weights.reindex(all_assets).fillna(0.0)
            w_tgt = target_weights.reindex(all_assets).fillna(0.0)
            
            max_deviation = np.abs(w_curr - w_tgt).max()
            
            # 只有当偏差超过阈值时才调仓
            return max_deviation > threshold

        # 3. 时间模式 (Time-based)
        current_date = self.dates[date_idx]
        
        # 检查是不是最后一天
        if date_idx + 1 >= len(self.dates):
            return True
            
        next_date = self.dates[date_idx + 1]
        
        if freq == '1W':  return current_date.week != next_date.week
        if freq == '1M':  return current_date.month != next_date.month
        if freq == '3M':  return current_date.quarter != next_date.quarter
        if freq == '6M':  return (current_date.month % 6) != (next_date.month % 6)
        if freq == '12M': return current_date.year != next_date.year
        if freq == '18M': 
            # 简单算法：每 1.5 年
            # 这里简化处理：每 18 个月大概是 540 天，或者用 month count
            # 这种非标准频率很难精确对齐日历，建议用 12M 代替
            return current_date.year != next_date.year

        return True

    def run_strategy(self, strategy_instance, name="Strategy", config=None):
        """
        运行策略
        :param config: 专属于这个策略的 BacktestConfig (手续费、频率)
        """
        # 如果没传配置，就用默认的无摩擦配置
        cfg = config if config else BacktestConfig(transaction_cost=0.0, rebalance_freq='1D')
        
        print(f"⚙️ Running: {name:<15} | Cost: {cfg.transaction_cost*10000:>3.0f} bps | Freq: {cfg.rebalance_freq}")
        
        capital = 1.0
        daily_rets = []
        
        # 记录当前的实际持仓权重 (初始为空)
        current_weights = pd.Series(dtype=float)
        
        # 记录上一次的策略目标 (用于 Signal 模式对比)
        last_strategy_weights = pd.Series(dtype=float)

        for i, date in enumerate(self.dates):
            
            # --- Step A: 询问策略今天的意图 ---
            # (这是理想目标，不代表一定要执行)
            try:
                raw_w = strategy_instance.get_weights(date)
                strategy_target = pd.Series(raw_w)
            except Exception:
                strategy_target = pd.Series(dtype=float)

            # --- Step B: 判断是否执行调仓 ---
            # 传入当前持仓(current)和策略意图(target)来判断是否触发阈值
            do_rebalance = self._is_rebalance_day(i, cfg.rebalance_freq, current_weights, strategy_target)
            
            # 特殊逻辑修正：Signal 模式
            if cfg.rebalance_freq == 'Signal':
                # 只有当策略意图发生实质变化时，才视为 "Signal Change"
                # 否则保持 current_weights (让其漂移)
                if strategy_target.equals(last_strategy_weights):
                    do_rebalance = False
                else:
                    do_rebalance = True
                    last_strategy_weights = strategy_target.copy()

            # --- Step C: 确定最终目标权重 ---
            if do_rebalance:
                final_target_weights = strategy_target
            else:
                # 不调仓 = 目标就是当前实际持仓 (Hold Drift)
                final_target_weights = current_weights

            # --- Step D: 计算交易成本 ---
            all_assets = current_weights.index.union(final_target_weights.index)
            w_curr = current_weights.reindex(all_assets).fillna(0.0).astype(float)
            w_tgt = final_target_weights.reindex(all_assets).fillna(0.0).astype(float)
            
            turnover = np.abs(w_tgt - w_curr).sum()
            cost = turnover * cfg.transaction_cost
            
            # --- Step E: 计算收益 ---
            if not w_tgt.empty:
                # [关键修复] fillna(0.0) 防止 NaN 传染
                today_rets = self.returns.loc[date].reindex(w_tgt.index).fillna(0.0)
                gross_ret = today_rets.dot(w_tgt)
            else:
                gross_ret = 0.0
                
            net_ret = gross_ret - cost
            
            capital = capital * (1 + net_ret)
            daily_rets.append(net_ret)
            
            # --- Step F: 计算次日漂移权重 ---
            if not w_tgt.empty:
                # 价格变动导致权重变化
                drifted = w_tgt * (1 + (today_rets if 'today_rets' in locals() else 0))
                sum_w = drifted.sum()
                if sum_w != 0:
                    current_weights = drifted / sum_w
                else:
                    current_weights = pd.Series(dtype=float)
            else:
                current_weights = pd.Series(dtype=float)
            
        return pd.Series(daily_rets, index=self.dates, name=name)

    def run_benchmark_6040(self):
        """
        Standard 60/40 Benchmark (Frictionless, Daily Rebalance)
        """
        print("⚖️ Constructing Benchmark...")
        stock = 'SPY'
        bond = 'AGG' if 'AGG' in self.returns.columns else 'IEF'
        
        if stock not in self.returns.columns:
            return pd.Series(dtype=float)
            
        weights = pd.Series({stock: 0.6, bond: 0.4})
        
        # [关键修复] 提取子集后先填 0，再做矩阵乘法
        subset = self.returns[weights.index].fillna(0.0)
        return subset.dot(weights).rename("Benchmark")