from src.strategy.base import BaseStrategy

class BuyHoldStrategy(BaseStrategy):
    """
    买入并持有策略 (Buy & Hold)
    固定权重，永不择时。
    """
    def __init__(self, weights_dict):
        """
        :param weights_dict: {ticker: weight}
        e.g. {'SPY': 0.6, 'TLT': 0.4}
        """
        self.target_weights = weights_dict
        # 从字典中提取 ticker 列表
        super().__init__(list(weights_dict.keys()))

    def get_weights(self, date):
        # 无论市场发生什么，我都想要这个配置
        return self.target_weights