
import pandas as pd
import numpy as np

# --- Internal Imports ---
from src.config_strategy_v1 import ALL_ASSETS
# 导入原 Risk Parity 分配器
from src.strategy_allocation_risk_parity import get_target_weights_risk_parity as get_weights_rp

# --- V3 策略核心配置 ---
# 熔断器的硬编码权重 (70% 现金, 30% 黄金)
REGIME_4_WEIGHTS = {
    'SGOV': 0.70, # 现金/短债
    'GLD': 0.30,  # 黄金
    'BIL': 0.00, # 明确其他现金为 0
}
# 在非危机时，Risk Parity 模型应忽略的资产 (剔除现金 - 步骤 1)
CASH_ASSETS_FOR_EXCLUSION = ['SGOV', 'BIL'] 
# 在非危机时，Risk Parity 优化的资产列表 (排除现金)
RP_ASSETS_UNIVERSE = [a for a in ALL_ASSETS if a not in CASH_ASSETS_FOR_EXCLUSION]


def get_target_weights_retail_v3(signal_df: pd.DataFrame, asset_prices: pd.DataFrame) -> pd.DataFrame:
    """
    Retail V3 版本权重分配器：
    1. Regime 4 触发熔断 (强制 70% 现金 + 30% 黄金)。
    2. 其他 Regime，对剔除现金的资产运行 Risk Parity。
    """
    if signal_df.empty:
        return pd.DataFrame(0.0, index=[pd.NaT], columns=ALL_ASSETS)

    last_signal = signal_df['Regime'].iloc[-1]
    last_date = signal_df.index[-1]

    # --- 1. Regime 4 熔断逻辑 ---
    if last_signal == 4:
        weights_out = pd.DataFrame(0.0, index=[last_date], columns=ALL_ASSETS)
        for asset, weight in REGIME_4_WEIGHTS.items():
            if asset in weights_out.columns:
                weights_out.loc[last_date, asset] = weight
        return weights_out

    # --- 2. 正常 Risk Parity 逻辑 (剔除现金) ---
    rp_assets = [a for a in RP_ASSETS_UNIVERSE if a in asset_prices.columns]
    rp_price_df = asset_prices[rp_assets]

    weights_df = get_weights_rp(signal_df, rp_price_df)

    # ✅ 关键修复 1：只保留最后一行（保证引擎不会取错）
    weights_df = weights_df.loc[[last_date]] if last_date in weights_df.index else weights_df.tail(1)

    # 补齐缺失资产（被剔除的现金等）
    for col in ALL_ASSETS:
        if col not in weights_df.columns:
            weights_df[col] = 0.0

    weights_df = weights_df[ALL_ASSETS]

    # ✅ 关键修复 2：安全归一化 + 0 行 fallback
    row_sum = weights_df.sum(axis=1)

    weights_df = weights_df.div(row_sum.replace(0, np.nan), axis=0).fillna(0.0)

    # 如果归一化后仍然出现全 0 行，强制现金
    zero_rows = weights_df.sum(axis=1) == 0
    if zero_rows.any():
        weights_df.loc[zero_rows, :] = 0.0
        if 'SGOV' in weights_df.columns:
            weights_df.loc[zero_rows, 'SGOV'] = 1.0

    return weights_df