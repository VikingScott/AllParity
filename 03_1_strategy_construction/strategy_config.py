# 03_1_strategy_construction/strategy_config.py

class StrategyConfig:
    # ----------------------------------------------------
    # 1. 通用参数
    # ----------------------------------------------------
    VOL_LOOKBACK = 36  
    
    # ----------------------------------------------------
    # 2. 资产配置
    # ----------------------------------------------------
    ASSETS_RP_XR = [
        'US_Stock_XR', 
        'US_Bond_10Y_XR', 
        'US_Credit_XR', 
        'Commodities_XR'
    ]
    
    # [决策] 统一使用 XR (Excess Return) 作为波动率对标
    # 这样 L = Vol_Mkt_XR / Vol_Port_XR，逻辑上最严谨
    ASSET_MARKET_XR = 'US_Stock_XR'
    
    # Benchmark 60/40 (逻辑不变，先TR后XR)
    ASSET_6040_STOCK_TR = 'US_Stock_TR'
    ASSET_6040_BOND_TR = 'US_Bond_10Y_TR'
    WEIGHT_6040 = [0.60, 0.40]

    # ----------------------------------------------------
    # 3. 融资与杠杆参数 (Risk Controls)
    # ----------------------------------------------------
    BORROW_SPREAD = 0.0050 / 12  
    
    # [核心修复] 给 Retail 设置 2.5x 上限
    MAX_LEVERAGE_RETAIL = 2.5
    
    # [核心修复] 给 Academic 加上 "Sanity Cap" (比如 10x)
    # 即使是学术研究，100倍杠杆也是数值错误，必须限制
    MAX_LEVERAGE_ACADEMIC = 10.0
    
    # [核心修复] 波动率地板 (防止分母为0导致杠杆爆炸)
    # 设定为年化 0.5% (0.005)。如果组合波动率低于这个，就按这个算。
    MIN_VOL_FLOOR = 0.005