from src.strategy.base import BaseStrategy
import pandas as pd

class CompositeStrategy(BaseStrategy):
    def __init__(self, strategies):
        """
        :param strategies: dict {strategy_instance: weight}
        例如: {ma_strat: 0.5, buy_hold_strat: 0.5}
        """
        self.strategies = strategies
        
        # 归一化策略权重
        total_w = sum(strategies.values())
        self.strat_weights = {k: v / total_w for k, v in strategies.items()}

    def get_weights(self, date):
        final_weights = pd.Series(dtype=float)
        
        for strat, strat_w in self.strat_weights.items():
            # 获取子策略的权重
            w_dict = strat.get_weights(date)
            if not w_dict: continue
            
            s_weights = pd.Series(w_dict)
            
            # 加权叠加
            # Final = Strat_Weight * Asset_Weight
            weighted_s = s_weights * strat_w
            
            final_weights = final_weights.add(weighted_s, fill_value=0)
            
        return final_weights.to_dict()