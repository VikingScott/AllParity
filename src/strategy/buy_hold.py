from src.strategy.base import BaseStrategy

class BuyHoldStrategy(BaseStrategy):
    """固定比例持有策略 (用于基准或定投)"""
    def __init__(self, weights):
        self.weights = weights
        self.tickers = list(weights.keys())

    def get_weights(self, date):
        return self.weights