# 03_1_strategy_construction/strategy_logic.py

import pandas as pd
import numpy as np
from scipy.optimize import minimize

class StrategyLogic:
    
    @staticmethod
    def calculate_rolling_vol(df_returns, window):
        return df_returns.rolling(window=window).std() * np.sqrt(12)

    @staticmethod
    def calculate_inverse_vol_weights(vol_df):
        inv_vol = 1.0 / (vol_df + 1e-8)
        weights = inv_vol.div(inv_vol.sum(axis=1), axis=0)
        return weights

    @staticmethod
    def calculate_erc_weights(df_returns, window, rebalance_freq='ME'):
        # ERC 逻辑保持不变...
        rolling_cov = df_returns.rolling(window=window).cov()
        try:
            rebal_dates = df_returns.resample(rebalance_freq).last().index
        except:
            rebal_dates = df_returns.resample('M').last().index

        weights_list = []
        valid_dates = []
        n_assets = df_returns.shape[1]
        x0 = np.array([1.0/n_assets] * n_assets) 
        
        def erc_objective(w, Sigma):
            w = np.maximum(w, 0.0)
            port_var = w @ Sigma @ w.T
            mrc = Sigma @ w.T
            rc = w * mrc
            target = np.mean(rc)
            return np.sum((rc - target)**2) * 10000

        constraints = ({'type': 'eq', 'fun': lambda x: np.sum(x) - 1.0})
        bounds = tuple((0.0, 1.0) for _ in range(n_assets))
        
        print(f"      [ERC] Optimizing {len(rebal_dates)} periods...")
        for d in rebal_dates:
            try:
                Sigma_df = rolling_cov.loc[d]
                if Sigma_df.shape != (n_assets, n_assets): continue
                Sigma = Sigma_df.values
                if np.isnan(Sigma).any(): continue
                
                res = minimize(erc_objective, x0, args=(Sigma,), method='SLSQP', bounds=bounds, constraints=constraints, tol=1e-9, options={'maxiter': 100})
                
                if res.success:
                    w_opt = res.x / np.sum(res.x)
                    weights_list.append(w_opt)
                    valid_dates.append(d)
                    x0 = w_opt 
                else:
                    weights_list.append(x0)
                    valid_dates.append(d)
            except Exception:
                continue
        
        if not weights_list:
            return pd.DataFrame(np.nan, index=df_returns.index, columns=df_returns.columns)

        df_w_monthly = pd.DataFrame(weights_list, index=valid_dates, columns=df_returns.columns)
        return df_w_monthly.reindex(df_returns.index).ffill()

    @staticmethod
    def calculate_ex_post_risk_contribution(weights_df, returns_df, lookback):
        # 保持不变...
        rolling_cov = returns_df.rolling(window=lookback).cov()
        rc_list = []
        dates = weights_df.index
        n_assets = len(weights_df.columns)
        nan_row = [np.nan] * n_assets
        
        for d in dates:
            try:
                Sigma_df = rolling_cov.loc[d]
                if Sigma_df.shape != (n_assets, n_assets):
                    rc_list.append(nan_row)
                    continue
                Sigma = Sigma_df.values
                w = weights_df.loc[d].values
                if np.isnan(w).any() or np.isnan(Sigma).any():
                    rc_list.append(nan_row)
                    continue
                port_var = w @ Sigma @ w.T
                if port_var == 0:
                    rc_list.append(nan_row)
                else:
                    rc = w * (Sigma @ w.T)
                    rc_list.append(rc / port_var)
            except KeyError:
                rc_list.append(nan_row)
        return pd.DataFrame(rc_list, index=dates, columns=weights_df.columns)

    @staticmethod
    def calculate_portfolio_ex_ante_vol_covariance(weights_df, returns_df, window):
        # 保持不变...
        rolling_cov = returns_df.rolling(window=window).cov()
        port_vols = []
        dates = weights_df.index
        n_assets = len(weights_df.columns)
        for d in dates:
            try:
                Sigma_df = rolling_cov.loc[d]
                if Sigma_df.shape != (n_assets, n_assets):
                    port_vols.append(np.nan)
                    continue
                cov_t = Sigma_df.values
                w = weights_df.loc[d].values
                if np.isnan(cov_t).any() or np.isnan(w).any():
                    port_vols.append(np.nan)
                else:
                    port_var = w @ cov_t @ w.T
                    port_std = np.sqrt(port_var * 12)
                    port_vols.append(port_std)
            except KeyError:
                port_vols.append(np.nan)
        return pd.Series(port_vols, index=dates, name='Port_ExAnte_Vol')

    @staticmethod
    def calculate_leverage_ratio_match_market(port_ex_ante_vol, market_vol, max_cap=None):
        leverage_ratio = market_vol / (port_ex_ante_vol + 1e-8)
        leverage_ratio = leverage_ratio.clip(lower=0.0)
        if max_cap is not None:
            leverage_ratio = leverage_ratio.clip(upper=max_cap)
        return leverage_ratio

    # ============================================================
    # 🔧 FIX: 融资成本基于实际敞口 (Risk-Off = De-leverage)
    # ============================================================
    @staticmethod
    def calculate_strategy_performance(df_xr, weights_lagged, leverage_ratio_lagged, borrow_spread=0.0):
        """
        计算策略净值，支持部分仓位（weights_sum < 1）
        
        Args:
            weights_lagged: 已经 shift(1) 过的权重 (可能因 Trend 过滤导致 sum < 1)
            leverage_ratio_lagged: 目标杠杆倍数 (Multiplier)
        """
        # 1. 计算组合的名义加权超额收益 (Nominal Portfolio XR)
        # 此时还没有乘杠杆。如果 weights_sum < 1，这里隐含了 (1-sum) 的部分是 Cash(XR=0)
        port_xr_unlevered = (weights_lagged * df_xr).sum(axis=1)

        # 2. 对齐杠杆序列
        if np.isscalar(leverage_ratio_lagged):
            lev_target = pd.Series(leverage_ratio_lagged, index=port_xr_unlevered.index)
        else:
            lev_target = leverage_ratio_lagged.reindex(port_xr_unlevered.index)

        # 3. 计算含杠杆的总收益 (Gross Return)
        # 公式: R_gross = Sum(w_i * r_i) * L
        lev_xr_gross = port_xr_unlevered * lev_target

        # 4. 计算融资成本 (关键修正点)
        # 实际风险敞口 (Actual Exposure) = Sum(Weights) * Target_Leverage
        # 例子: 
        #   Naive: Sum(w)=1.0, L=2.5 -> Exposure=2.5 -> Borrow=1.5
        #   Trend Risk-Off: Sum(w)=0.5, L=2.5 -> Exposure=1.25 -> Borrow=0.25 (自动去杠杆)
        #   Full Cash: Sum(w)=0.0, L=2.5 -> Exposure=0.0 -> Borrow=0.0 (不付息)
        
        actual_exposure = weights_lagged.sum(axis=1) * lev_target
        
        # 额外融资额 = max(0, Actual_Exposure - 1.0)
        extra_leverage = (actual_exposure - 1.0).clip(lower=0.0)
        
        financing_cost = extra_leverage * borrow_spread

        return lev_xr_gross - financing_cost

    # ============================================================
    # 🔧 FIX: 移除内部 Shift，保证严格时序对齐
    # ============================================================
    @staticmethod
    def calculate_trend_signal(df_returns, window=10):
        """
        计算趋势信号 (MA Filter)
        返回 Raw Signal (T时刻的信号)，不进行 shift。
        调用者需要在应用到 Returns 时自行 shift(1)。
        """
        # 1. 重建价格
        price_index = (1 + df_returns.fillna(0)).cumprod()
        
        # 2. 计算均线
        ma = price_index.rolling(window=window).mean()
        
        # 3. 信号生成
        signal = (price_index > ma).astype(int)
        signal[ma.isna()] = np.nan # Warm-up period
        
        # [Fix] 移除 shift(1)，由 Runner 统一处理
        return signal

    @staticmethod
    def apply_trend_filter(weights, trend_signal):
        """
        应用趋势过滤器
        Filtered_Weights = Original_Weights * Signal
        """
        signal_aligned = trend_signal.reindex(weights.index).fillna(1)
        return weights * signal_aligned