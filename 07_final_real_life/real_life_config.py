# 07_final_real_life/real_life_config.py

class RealLifeConfig:
    # ==========================================
    # 1. 交易摩擦 (Transaction Costs)
    # ==========================================
    # 双边费用 (买入+卖出)
    # 包含: 佣金 ($0.005/股) + 滑点 (Bid-Ask Spread)
    # 机构标准: 5-10 bps; 零售标准: 可能更高
    TRANSACTION_COST_BPS = 0.0010  # 10 bps (0.10%)
    
    # ==========================================
    # 2. 持仓成本 (Holding Costs / ETF MER)
    # ==========================================
    # 让之前的 ETF 数据发挥作用：使用它们的费率作为基准
    ETF_EXPENSE_RATIOS = {
        'US_Stock': 0.0003,    # 0.03% (VOO/SPY) - 极低
        'US_Bond_10Y': 0.0015, # 0.15% (IEF) - 较低
        'US_Credit': 0.0015,   # 0.15% (LQD) - 较低
        'Commodities': 0.0085  # 0.85% (GSG) - 很高！商品ETF通常很贵
    }
    
    # ==========================================
    # 3. 融资成本 (Financing Costs)
    # ==========================================
    # 基于 Fed Rate (Risk_Free) 之上的加点
    # IBKR Pro 约为 BM + 0.5% ~ 1.5%
    BORROW_SPREAD = 0.0080 # 0.8% (80 bps)
    
    # ==========================================
    # 4. 税务假设 (Tax Assumptions) - 用于期末评估
    # ==========================================
    TAX_RATE_LONG_TERM = 0.20   # Naive/ERC (假设多为长期持有)
    TAX_RATE_SHORT_TERM = 0.30  # Trend (假设多为短期交易)