# 03_1_strategy_construction/strategy_logic.py

import pandas as pd
import numpy as np
from scipy.optimize import minimize

class StrategyLogic:
    
    @staticmethod
    def calculate_rolling_vol(df_returns, window):
        """计算滚动年化波动率 (Signal)"""
        return df_returns.rolling(window=window).std() * np.sqrt(12)

    @staticmethod
    def calculate_inverse_vol_weights(vol_df):
        """
        计算逆波动率权重 (Naïve Risk Parity)
        注意：此方法假设资产间相关性为0或相等。
        """
        # 1. 倒数 (增加 1e-8 避免除零)
        inv_vol = 1.0 / (vol_df + 1e-8)
        # 2. 归一化 (Sum = 1.0)
        weights = inv_vol.div(inv_vol.sum(axis=1), axis=0)
        return weights

    @staticmethod
    def calculate_erc_weights(df_returns, window, rebalance_freq='ME'):
        """
        [Fix] 计算 ERC (Equal Risk Contribution) 权重
        修复了 MultiIndex 索引判断失效导致跳过优化的问题。
        增加详细的 Debug 统计。
        """
        # 1. 计算滚动协方差矩阵 (Full Covariance) -> MultiIndex (Date, Asset)
        rolling_cov = df_returns.rolling(window=window).cov()
        
        # 2. 确定调仓日期
        try:
            rebal_dates = df_returns.resample(rebalance_freq).last().index
        except:
            rebal_dates = df_returns.resample('M').last().index # Fallback
        
        weights_list = []
        valid_dates = []
        
        n_assets = df_returns.shape[1]
        # 初始猜测 (均分)
        x0 = np.array([1.0/n_assets] * n_assets) 
        
        # 目标函数: 最小化 sum( (RC_i - RC_avg)^2 )
        def erc_objective(w, Sigma):
            # 防止 w 出现极小负数导致 sqrt 报错
            w = np.maximum(w, 0.0)
            
            # Portfolio Variance = w'Zw
            port_var = w @ Sigma @ w.T
            # Marginal Risk Contribution = Sigma * w
            mrc = Sigma @ w.T
            # Risk Contribution = w * mrc
            rc = w * mrc
            
            # Target = Mean RC
            target = np.mean(rc)
            # 乘以 10000 放大误差，帮助优化器收敛
            return np.sum((rc - target)**2) * 10000

        # 约束条件: sum(w)=1
        constraints = ({'type': 'eq', 'fun': lambda x: np.sum(x) - 1.0})
        bounds = tuple((0.0, 1.0) for _ in range(n_assets))
        
        # Debug 计数器
        stats = {'total': len(rebal_dates), 'processed': 0, 'success': 0, 'failed': 0, 'skipped_nan': 0, 'skipped_key': 0}
        
        print(f"      [ERC Debug] Starting optimization for {stats['total']} periods...")
        
        for d in rebal_dates:
            try:
                # 核心修复：直接通过 .loc[d] 尝试获取切片，而不是用 if d in index
                # rolling_cov 是 MultiIndex，.loc[d] 会返回 (N, N) 的 DataFrame
                Sigma_df = rolling_cov.loc[d]
                
                # 检查形状 (防止取到非方阵)
                if Sigma_df.shape != (n_assets, n_assets):
                    stats['skipped_nan'] += 1
                    continue
                
                Sigma = Sigma_df.values
                
                # 检查 NaN (协方差矩阵不能有空值)
                if np.isnan(Sigma).any():
                    stats['skipped_nan'] += 1
                    # 如果数据不够（比如早期窗口期），直接跳过，不填充（之后 reindex 会处理为 NaN）
                    # 或者这里可以用上一期的权重填充（Hold）
                    # 这里我们选择跳过，最后 forward fill
                    continue
                
                stats['processed'] += 1
                
                # 优化
                res = minimize(
                    erc_objective, 
                    x0, 
                    args=(Sigma,), 
                    method='SLSQP', 
                    bounds=bounds, 
                    constraints=constraints,
                    tol=1e-9,      # 提高精度要求
                    options={'maxiter': 100}
                )
                
                if res.success:
                    w_opt = res.x
                    # 归一化 (防止优化器返回 0.99999)
                    w_opt = w_opt / np.sum(w_opt)
                    
                    weights_list.append(w_opt)
                    valid_dates.append(d)
                    x0 = w_opt # Warm start
                    stats['success'] += 1
                else:
                    # 优化失败，回退到 x0 (上一期权重) 或 均分
                    weights_list.append(x0)
                    valid_dates.append(d)
                    stats['failed'] += 1
                    
            except KeyError:
                # 日期不在 rolling_cov 里
                stats['skipped_key'] += 1
                continue
            except Exception as e:
                print(f"Error at {d}: {e}")
                continue
        
        print(f"      [ERC Debug] Finished. Success: {stats['success']} | Failed (Opt): {stats['failed']} | Skipped (NaN/Key): {stats['skipped_nan'] + stats['skipped_key']}")
        
        # 3. 扩展回日频 (Forward Fill)
        if not weights_list:
            print("      [Warning] No ERC weights calculated! Check data/window.")
            return pd.DataFrame(np.nan, index=df_returns.index, columns=df_returns.columns)

        df_w_monthly = pd.DataFrame(weights_list, index=valid_dates, columns=df_returns.columns)
        df_w_daily = df_w_monthly.reindex(df_returns.index).ffill()
        
        return df_w_daily

    @staticmethod
    def calculate_ex_post_risk_contribution(weights_df, returns_df, lookback):
        """
        计算事后风险贡献 (Ex-Post RC)
        """
        rolling_cov = returns_df.rolling(window=lookback).cov()
        rc_list = []
        dates = weights_df.index
        n_assets = len(weights_df.columns)
        nan_row = [np.nan] * n_assets
        
        for d in dates:
            # 同样使用 try-except 修复这里的潜在索引问题
            try:
                Sigma_df = rolling_cov.loc[d]
                if Sigma_df.shape != (n_assets, n_assets):
                    rc_list.append(nan_row)
                    continue
                
                Sigma = Sigma_df.values
                # weights 已经是 shift 过的，所以直接取 d
                w = weights_df.loc[d].values
                
                if np.isnan(w).any() or np.isnan(Sigma).any():
                    rc_list.append(nan_row)
                    continue
                
                port_var = w @ Sigma @ w.T
                if port_var == 0:
                    rc_list.append(nan_row)
                else:
                    rc = w * (Sigma @ w.T)
                    rc_list.append(rc / port_var) # Percent
            except KeyError:
                rc_list.append(nan_row)
                
        return pd.DataFrame(rc_list, index=dates, columns=weights_df.columns)

    @staticmethod
    def calculate_portfolio_ex_ante_vol_covariance(weights_df, returns_df, window):
        """利用 Rolling Covariance 计算组合预期波动率"""
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

    @staticmethod
    def calculate_strategy_performance(df_xr, weights_lagged, leverage_ratio_lagged, borrow_spread=0.0):
        port_xr = (weights_lagged * df_xr).sum(axis=1)
        if np.isscalar(leverage_ratio_lagged):
            lev = pd.Series(leverage_ratio_lagged, index=port_xr.index)
        else:
            lev = leverage_ratio_lagged.reindex(port_xr.index)
        lev_xr_gross = port_xr * lev
        extra_leverage = (lev - 1.0).clip(lower=0.0)
        financing_cost = extra_leverage * borrow_spread
        return lev_xr_gross - financing_cost