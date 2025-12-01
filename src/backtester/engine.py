import pandas as pd
import numpy as np
from src.backtester.config import BacktestConfig

class BacktestEngine:
    def __init__(self, returns_df):
        """
        :param returns_df: 全市场收益率矩阵 (Date x Ticker)，必须已清洗对齐
        """
        self.returns = returns_df
        self.dates = returns_df.index

    def _is_rebalance_day(self, date_idx, freq, current_w, target_w):
        """判断是否需要调仓"""
        if freq == '1D' or freq == 'Signal': return True
        
        # Drift 模式
        if freq.startswith('Drift_'):
            try: threshold = float(freq.split('_')[1])
            except: return True
            if current_w.empty or target_w.empty: return True
            
            # 对齐并计算偏差
            idx = current_w.index.union(target_w.index)
            w_c = current_w.reindex(idx).fillna(0.0)
            w_t = target_w.reindex(idx).fillna(0.0)
            return np.abs(w_c - w_t).max() > threshold

        # Time 模式
        if date_idx + 1 >= len(self.dates): return True
        curr_dt = self.dates[date_idx]
        next_dt = self.dates[date_idx + 1]
        
        if freq == '1W': return curr_dt.week != next_dt.week
        if freq == '1M': return curr_dt.month != next_dt.month
        if freq == '3M': return curr_dt.quarter != next_dt.quarter
        if freq == '12M': return curr_dt.year != next_dt.year
        
        return True

    def run(self, strategy, config=None):
        """
        执行回测
        :return: (daily_returns_series, daily_positions_df)
        """
        cfg = config if config else BacktestConfig()
        
        capital = 1.0
        daily_rets = []
        positions_history = []
        
        # 初始状态
        current_weights = pd.Series(dtype=float)
        last_target_weights = pd.Series(dtype=float)

        for i, date in enumerate(self.dates):
            # 1. 询问策略目标
            try:
                raw_w = strategy.get_weights(date)
                target_w = pd.Series(raw_w)
            except:
                target_w = pd.Series(dtype=float)

            # 2. 判断调仓
            do_rebal = self._is_rebalance_day(i, cfg.rebalance_freq, current_weights, target_w)
            
            # Signal 模式优化
            if cfg.rebalance_freq == 'Signal':
                if target_w.equals(last_target_weights):
                    do_rebal = False
                else:
                    do_rebal = True
                    last_target_weights = target_w.copy()

            final_w = target_w if do_rebal else current_weights

            # 3. 计算交易成本
            # 对齐权重
            assets = current_weights.index.union(final_w.index)
            w_curr = current_weights.reindex(assets).fillna(0.0)
            w_tgt = final_w.reindex(assets).fillna(0.0)
            
            turnover = np.abs(w_tgt - w_curr).sum()
            cost = turnover * cfg.transaction_cost

            # 4. 计算收益
            gross_ret = 0.0
            if not w_tgt.empty:
                # 获取当日资产收益 (填0防止炸裂)
                day_asset_rets = self.returns.loc[date].reindex(w_tgt.index).fillna(0.0)
                gross_ret = day_asset_rets.dot(w_tgt)
            
            net_ret = gross_ret - cost
            daily_rets.append(net_ret)
            
            # 5. 记录持仓 (记录的是当日收盘后的名义权重，即漂移前的目标权重)
            # 也可以记录漂移后的，看你分析需求。通常记录 Target 更直观。
            positions_history.append(w_tgt.to_dict())

            # 6. 计算漂移 (为明天做准备)
            if not w_tgt.empty:
                drifted = w_tgt * (1 + (day_asset_rets if 'day_asset_rets' in locals() else 0))
                sum_w = drifted.sum()
                current_weights = drifted / sum_w if sum_w != 0 else pd.Series(dtype=float)
            else:
                current_weights = pd.Series(dtype=float)

        # 结果打包
        ret_series = pd.Series(daily_rets, index=self.dates)
        pos_df = pd.DataFrame(positions_history, index=self.dates).fillna(0.0)
        
        return ret_series, pos_df