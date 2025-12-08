# src/strategy_allocation_leverage_v1.py

from __future__ import annotations

import pandas as pd
import numpy as np
from typing import Optional, Dict

# -----------------------------
# Config (Leverage V1)
# -----------------------------
from src.config_strategy_levearge import (
    ALL_ASSETS,
    RP_CORE_ASSETS,
    RP_CLASSIC_5,
    REGIME_4_WEIGHTS,
    ENABLE_LEVERAGE,
    TARGET_VOL_ANN,
    VOL_WINDOW_DAYS,
    VOL_FLOOR_ANN,
    VOL_CAP_ANN,
    LEVERAGE_CAP,
    LEVERAGE_FLOOR,
    ENABLE_GUARDRAILS,
    GROSS_EXPOSURE_HARD_CAP,
    REGIME_LEVERAGE_CAPS
)

# -----------------------------
# Optional: your existing RP optimizer
# If unavailable, we will fallback to naive inv-vol
# -----------------------------
try:
    from src.strategy_allocation_risk_parity import get_target_weights_risk_parity as get_weights_rp
    _HAS_RP_OPT = True
except Exception:
    get_weights_rp = None
    _HAS_RP_OPT = False


# =========================================================
# DOP Helpers
# =========================================================

def _as_of_to_ts(as_of, index: pd.DatetimeIndex) -> pd.Timestamp:
    if as_of is None:
        return index[-1]
    return pd.Timestamp(as_of)


def _select_core_universe(asset_prices: pd.DataFrame) -> list:
    """
    Prefer classic 5 if enough available, else use RP_CORE_ASSETS intersection.
    """
    cols = list(asset_prices.columns)
    classic = [a for a in RP_CLASSIC_5 if a in cols]
    if len(classic) >= 3:
        return classic
    core = [a for a in RP_CORE_ASSETS if a in cols]
    return core


def _tail_window(df: pd.DataFrame, as_of: pd.Timestamp, window: int) -> pd.DataFrame:
    """
    DOP principle: pull the minimal needed data slice internally.
    """
    sub = df.loc[:as_of]
    if window is not None and window > 0:
        return sub.tail(window)
    return sub


def _naive_inv_vol_weights(prices: pd.DataFrame) -> pd.Series:
    """
    Fallback RP-ish weights: inverse vol using daily returns of prices slice.
    """
    rets = prices.pct_change().dropna()
    if rets.empty:
        # cold start: equal weight
        n = prices.shape[1]
        return pd.Series(1.0 / n, index=prices.columns)

    vol = rets.std()
    inv = 1 / vol.replace(0, np.nan)
    w = inv / inv.sum()
    w = w.fillna(0.0)

    # if everything is nan (rare), fallback to equal weight
    if float(w.sum()) == 0.0:
        n = prices.shape[1]
        w = pd.Series(1.0 / n, index=prices.columns)
    return w


def _compute_base_rp_weights(
    signal_df: pd.DataFrame,
    price_df: pd.DataFrame,
    as_of: pd.Timestamp
) -> pd.Series:
    """
    Compute unlevered base weights (sum=1) using:
    - your existing optimizer if present
    - else naive inv-vol fallback
    """
    universe = _select_core_universe(price_df)
    if len(universe) < 2:
        # degenerate fallback
        return pd.Series(0.0, index=ALL_ASSETS)

    prices_core = price_df[universe].copy()

    if _HAS_RP_OPT and get_weights_rp is not None:
        # DOP-friendly usage: pass minimal slices, not whole history each day
        # Here we assume your RP function can handle "recent history" inputs.
        w_df = get_weights_rp(signal_df, prices_core)
        # We only need the last row
        w = w_df.iloc[-1].copy()
    else:
        w = _naive_inv_vol_weights(prices_core)

    # Ensure Series, sum=1 on core assets
    w = w.reindex(universe).fillna(0.0)
    s = float(w.sum())
    if s > 0:
        w = w / s

    # Expand to ALL_ASSETS with zeros
    out = pd.Series(0.0, index=ALL_ASSETS)
    for a in universe:
        out[a] = float(w.get(a, 0.0))
    return out


def _estimate_base_port_vol_ann(
    base_w: pd.Series,
    price_df: pd.DataFrame,
    as_of: pd.Timestamp,
    vol_window: int
) -> float:
    """
    Estimate annualized vol of the unlevered base portfolio using recent window.
    This is portfolio-level vol (more stable than per-asset mixing).
    """
    universe = [a for a in base_w.index if base_w[a] != 0 and a in price_df.columns]
    if len(universe) == 0:
        return VOL_FLOOR_ANN

    prices_sub = _tail_window(price_df[universe], as_of, vol_window + 5)
    rets = prices_sub.pct_change().dropna()
    if rets.empty:
        return VOL_FLOOR_ANN

    w_vec = base_w[universe].values.astype(float)
    port_ret = (rets.values * w_vec).sum(axis=1)

    vol_daily = np.std(port_ret, ddof=1) if len(port_ret) > 1 else 0.0
    vol_ann = vol_daily * np.sqrt(252)

    if np.isnan(vol_ann) or vol_ann == 0:
        vol_ann = VOL_FLOOR_ANN

    # soft cap/floor to avoid crazy leverage
    vol_ann = max(vol_ann, VOL_FLOOR_ANN)
    vol_ann = min(vol_ann, VOL_CAP_ANN)

    return float(vol_ann)


def _compute_leverage_multiplier(vol_base_ann: float) -> float:
    if not ENABLE_LEVERAGE:
        return 1.0
    lev = TARGET_VOL_ANN / max(vol_base_ann, VOL_FLOOR_ANN)
    lev = float(np.clip(lev, LEVERAGE_FLOOR, LEVERAGE_CAP))
    return lev


# =========================================================
# Public API: DOP-friendly allocation
# =========================================================

# Simple monthly cache:
# key = "YYYY-MM"
_CACHE: Dict[str, pd.Series] = {}


def get_target_weights_leverage_v1(
    signal_df: pd.DataFrame,
    asset_prices: pd.DataFrame,
    as_of: Optional[pd.Timestamp] = None,
    lookback_prices: int = 400,
    lookback_signals: int = 400,
) -> pd.DataFrame:
    """
    Leverage Allocation V1 (DOP)

    Key points:
    - DOP-friendly: engine should call this ONLY on rebalance dates.
    - Internal slicing with tail(window). Avoid passing loc[:date] externally.
    - Regime 4 hard override (no leverage).
    - Normal regimes:
        1) compute unlevered base RP weights (sum=1)
        2) estimate base portfolio vol (annualized)
        3) scale by leverage multiplier
        4) output weights that may sum > 1 (DO NOT renormalize)
    - Returns a 1-row DataFrame indexed by as_of date.
    """
    if signal_df is None or signal_df.empty:
        return pd.DataFrame(0.0, index=[pd.NaT], columns=ALL_ASSETS)

    as_of_ts = _as_of_to_ts(as_of, signal_df.index)

    # Cache by month
    cache_key = as_of_ts.strftime("%Y-%m")
    if cache_key in _CACHE:
        w_cached = _CACHE[cache_key].copy()
        return pd.DataFrame([w_cached.values], index=[as_of_ts], columns=ALL_ASSETS)

    # Minimal internal slices (DOP)
    sig = _tail_window(signal_df, as_of_ts, lookback_signals)
    px = _tail_window(asset_prices, as_of_ts, lookback_prices)

    last_regime = int(sig["Regime"].iloc[-1]) if "Regime" in sig.columns else 0

    # -----------------------------
    # 1) Regime 4 Hard Override
    # -----------------------------
    if last_regime == 4:
        w = pd.Series(0.0, index=ALL_ASSETS)
        for a, wt in REGIME_4_WEIGHTS.items():
            if a in w.index:
                w[a] = wt
        # cache and return
        _CACHE[cache_key] = w
        return pd.DataFrame([w.values], index=[as_of_ts], columns=ALL_ASSETS)

    # -----------------------------
    # 2) Normal Regimes: Base RP
    # -----------------------------
    base_w = _compute_base_rp_weights(sig, px, as_of_ts)

    # -----------------------------
    # 3) Estimate base portfolio vol
    # -----------------------------
    vol_base_ann = _estimate_base_port_vol_ann(
        base_w, px, as_of_ts, VOL_WINDOW_DAYS
    )

    # -----------------------------
    # 4) Leverage scaling (single source of truth)
    # -----------------------------
    lev = _compute_leverage_multiplier(vol_base_ann)

    # -----------------------------
    # 4) Leverage scaling (single source of truth)
    # -----------------------------
    lev = _compute_leverage_multiplier(vol_base_ann)

    # 4b) [关键修改] 应用 Regime-Conditional Cap
    # 目的：阻止在R4等低Alpha/低Vol体制下过度杠杆化
    if REGIME_LEVERAGE_CAPS is not None and last_regime in REGIME_LEVERAGE_CAPS:
        # 获取当前体制的上限，如果未设置则回退到整体 LEVERAGE_CAP
        regime_cap = REGIME_LEVERAGE_CAPS.get(last_regime, LEVERAGE_CAP)
        
        # 强制应用上限：最终杠杆乘数是原始计算值和体制上限中的最小值
        lev = min(lev, regime_cap)
    
    w = base_w * lev

    # -----------------------------
    # 5) Guardrails
    # -----------------------------
    if ENABLE_GUARDRAILS:
        gross = float(w.abs().sum())
        if gross > GROSS_EXPOSURE_HARD_CAP:
            # hard clip proportionally to avoid catastrophic backtests
            scale = GROSS_EXPOSURE_HARD_CAP / gross
            w = w * scale

    # Cache
    _CACHE[cache_key] = w

    return pd.DataFrame([w.values], index=[as_of_ts], columns=ALL_ASSETS)


# Convenience alias to match your engine import style
get_target_weights_leverage = get_target_weights_leverage_v1