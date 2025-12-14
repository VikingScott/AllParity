# 03_1_strategy_construction/strategy_logic.py

import pandas as pd
import numpy as np

class StrategyLogic:
    
    @staticmethod
    def calculate_rolling_vol(df_returns, window):
        """计算滚动年化波动率 (Signal)"""
        return df_returns.rolling(window=window).std() * np.sqrt(12)

    @staticmethod
    def calculate_inverse_vol_weights(vol_df):
        """计算逆波动率权重 (Unlevered Weights)"""
        # 1. 倒数 (增加 1e-8 避免除零)
        inv_vol = 1.0 / (vol_df + 1e-8)
        # 2. 归一化 (Sum = 1.0)
        weights = inv_vol.div(inv_vol.sum(axis=1), axis=0)
        return weights

    @staticmethod
    def calculate_portfolio_ex_ante_vol_covariance(weights_df, returns_df, window):
        """
        [核心升级] 利用 Rolling Covariance Matrix 计算组合预期波动率。
        公式: Sigma_p = sqrt( w.T * Cov_Matrix * w )
        """
        # 计算滚动协方差矩阵 (N_days * N_assets, N_assets)
        rolling_cov = returns_df.rolling(window=window).cov()
        
        port_vols = []
        dates = weights_df.index
        
        for d in dates:
            if d not in rolling_cov.index:
                port_vols.append(np.nan)
                continue
                
            try:
                # 提取当天的权重 (1 x N)
                w = weights_df.loc[d].values
                # 提取当天的协方差 (N x N)
                cov_t = rolling_cov.loc[d].values
                
                if np.isnan(cov_t).any() or np.isnan(w).any():
                    port_vols.append(np.nan)
                else:
                    # w * Cov * w.T
                    port_var = w @ cov_t @ w.T
                    port_std = np.sqrt(port_var * 12) # 年化
                    port_vols.append(port_std)
                    
            except KeyError:
                port_vols.append(np.nan)
        
        return pd.Series(port_vols, index=dates, name='Port_ExAnte_Vol')

    @staticmethod
    def calculate_leverage_ratio_match_market(port_ex_ante_vol, market_vol, max_cap=None):
        """
        计算杠杆率: L = Vol_Market / Vol_Portfolio
        """
        leverage_ratio = market_vol / (port_ex_ante_vol + 1e-8)
        
        # 基础风控：不允许负杠杆
        leverage_ratio = leverage_ratio.clip(lower=0.0)
        
        if max_cap is not None:
            leverage_ratio = leverage_ratio.clip(upper=max_cap)
            
        return leverage_ratio

    @staticmethod
    def calculate_strategy_performance(df_xr, weights_lagged, leverage_ratio_lagged, borrow_spread=0.0):
        port_xr = (weights_lagged * df_xr).sum(axis=1)

        # --- make leverage a Series aligned with port_xr ---
        if np.isscalar(leverage_ratio_lagged):
            lev = pd.Series(leverage_ratio_lagged, index=port_xr.index)
        else:
            lev = leverage_ratio_lagged.reindex(port_xr.index)

        lev_xr_gross = port_xr * lev

        extra_leverage = (lev - 1.0).clip(lower=0.0)
        financing_cost = extra_leverage * borrow_spread

        return lev_xr_gross - financing_cost
