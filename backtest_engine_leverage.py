from __future__ import annotations

import pandas as pd
import numpy as np
import os
from pathlib import Path
import datetime

# --- Internal Imports ---
from src.data_loader import get_merged_market_state
from src.macro_regime_signal_generator import run_signal_pipeline

# --- Leverage Config ---
from src.config_strategy_levearge import (
    ALL_ASSETS,
    REBALANCE_FREQ,
    DEADBAND_THRESHOLD_ABS,
    USE_FIXED_FINANCING_RATE,
    FINANCING_RATE_ANN,
    FINANCING_RATE_SERIES_COL,
    ENABLE_GUARDRAILS,
    MAX_SINGLE_DAY_LOSS,
)

# --- Leverage Allocation (DOP version) ---
from src.strategy_allocation_leverage import get_target_weights_leverage_v1


# ==========================
# Paths
# ==========================
DATA_DIR = Path("data")
OUTPUT_DIR = Path("outputs")
OUTPUT_FILE = OUTPUT_DIR / "backtest_results_leverage_v1.csv"


# ==========================
# Utilities
# ==========================
def ensure_directories():
    if not OUTPUT_DIR.exists():
        os.makedirs(OUTPUT_DIR)
        print(f"📁 Created output directory: {OUTPUT_DIR}")


def calculate_strategy_returns(weights_df: pd.DataFrame, asset_returns: pd.DataFrame) -> pd.Series:
    """
    Core return calc:
    Use lagged weights to avoid look-ahead.
    """
    lagged = weights_df.shift(1)

    idx = lagged.index.intersection(asset_returns.index)
    w = lagged.loc[idx]
    r = asset_returns.loc[idx]

    valid_assets = [c for c in w.columns if c in r.columns]
    if len(valid_assets) == 0:
        return pd.Series(0.0, index=idx)

    w = w[valid_assets].fillna(0.0)
    r = r[valid_assets].fillna(0.0)

    # Vectorized
    ret = (w.values * r.values).sum(axis=1)
    return pd.Series(ret, index=idx, name="Portfolio_Daily_Ret")


def compute_financing_daily_rate(signal_df: pd.DataFrame) -> pd.Series:
    """
    Financing rate series (daily).
    Priority:
    1) Fixed rate if enabled
    2) Optional series column in signal_df (if you later add it)
    """
    idx = signal_df.index

    if USE_FIXED_FINANCING_RATE:
        rf_daily = FINANCING_RATE_ANN / 252.0
        return pd.Series(rf_daily, index=idx, name="Borrow_Rate_Daily")

    # If you later add a series column
    if FINANCING_RATE_SERIES_COL and FINANCING_RATE_SERIES_COL in signal_df.columns:
        # Assume the series is annualized rate in decimal
        rf_ann = signal_df[FINANCING_RATE_SERIES_COL].fillna(method="ffill").fillna(0.0)
        rf_daily = rf_ann / 252.0
        return rf_daily.rename("Borrow_Rate_Daily")

    # Fallback
    return pd.Series(0.0, index=idx, name="Borrow_Rate_Daily")


def apply_monthly_deadband(weights_m: pd.DataFrame, threshold_abs: float) -> pd.DataFrame:
    """
    Apply deadband on monthly weights only.
    If max abs deviation <= threshold, keep previous month's weights.
    """
    if weights_m.empty:
        return weights_m

    out = []
    current = None

    for dt, row in weights_m.iterrows():
        w = row.copy()

        if current is None:
            current = w
        else:
            deviation = (w - current).abs().max()
            if deviation > threshold_abs:
                current = w  # update
            # else keep current

        out.append(current)

    return pd.DataFrame(out, index=weights_m.index, columns=weights_m.columns)


# ==========================
# Engine (DOP)
# ==========================
def run_engine_leverage_v1():
    start_time = datetime.datetime.now()

    print("=" * 68)
    print("🚀 ALL PARITY BACKTEST ENGINE (LEVERAGE V1 - DOP FAST)")
    print("    Monthly Weights + Monthly Deadband + Daily Expansion")
    print("=" * 68)

    # -----------------------------------------------------------
    # Step 1: Load & Align Data
    # -----------------------------------------------------------
    try:
        df_market = get_merged_market_state(
            str(DATA_DIR / "Macro_Daily_Final.csv"),
            str(DATA_DIR / "asset_prices.csv")
        )
    except FileNotFoundError as e:
        print(f"❌ Error: Data file not found. {e}")
        return

    # Asset universe intersection
    valid_assets = [a for a in ALL_ASSETS if a in df_market.columns]

    if len(valid_assets) == 0:
        print("❌ No valid assets found in market data.")
        return

    asset_prices = df_market[valid_assets].copy()
    asset_returns = asset_prices.pct_change().fillna(0.0)

    # Regime/Signal pipeline
    signal_df = run_signal_pipeline(df_market)

    # Align indices
    common_index = df_market.index.intersection(signal_df.index)
    df_market = df_market.loc[common_index]
    signal_df = signal_df.loc[common_index]
    asset_prices = asset_prices.loc[common_index]
    asset_returns = asset_returns.loc[common_index]

    ensure_directories()

    # -----------------------------------------------------------
    # Step 2: Build Monthly Rebalance Dates (DOP)
    # -----------------------------------------------------------
    # Use month-end alias from config (REBALANCE_FREQ='ME')
    # We pick the first trading day in each period for stable behavior
    rebalance_dates = (
        signal_df.index.to_series()
        .groupby(signal_df.index.to_period("M"))
        .first()
    )
    rebalance_dates = pd.DatetimeIndex(rebalance_dates.values)

    print(f"\n👉 Rebalance freq: {REBALANCE_FREQ} | "
          f"Monthly rebalance points: {len(rebalance_dates)} | "
          f"Deadband(abs): {DEADBAND_THRESHOLD_ABS:.1%}")

    # -----------------------------------------------------------
    # Step 3: Compute Weights ONLY on Rebalance Dates
    # -----------------------------------------------------------
    weights_list = []

    for dt in rebalance_dates:
        w_df = get_target_weights_leverage_v1(
            signal_df=signal_df,
            asset_prices=asset_prices,
            as_of=dt
        )
        w = w_df.iloc[0].reindex(valid_assets).fillna(0.0)
        weights_list.append(w)

    weights_m = pd.DataFrame(weights_list, index=rebalance_dates, columns=valid_assets).fillna(0.0)

    # -----------------------------------------------------------
    # Step 4: Monthly Deadband (apply once)
    # -----------------------------------------------------------
    weights_m = apply_monthly_deadband(weights_m, DEADBAND_THRESHOLD_ABS)

    # -----------------------------------------------------------
    # Step 5: Expand to Daily Weights
    # -----------------------------------------------------------
    weights_df = weights_m.reindex(signal_df.index).ffill().fillna(0.0)

    # -----------------------------------------------------------
    # Step 6: Compute Gross Exposure & Financing Cost
    # -----------------------------------------------------------
    gross_exposure = weights_df.abs().sum(axis=1).rename("Gross_Exposure")
    borrow_ratio = (gross_exposure - 1.0).clip(lower=0.0).rename("Borrow_Ratio")

    borrow_rate_daily = compute_financing_daily_rate(signal_df)
    borrow_cost = (borrow_ratio * borrow_rate_daily).rename("Borrow_Cost_Daily")

    # -----------------------------------------------------------
    # Step 7: Portfolio Returns (No double leverage!)
    # -----------------------------------------------------------
    port_gross_ret = calculate_strategy_returns(weights_df, asset_returns).rename("Portfolio_Gross_Ret")
    port_net_ret = (port_gross_ret - borrow_cost).rename("Portfolio_Daily_Ret")

    # Optional guardrail against catastrophic negative compounding
    if ENABLE_GUARDRAILS and MAX_SINGLE_DAY_LOSS is not None:
        port_net_ret = port_net_ret.clip(lower=MAX_SINGLE_DAY_LOSS)

    # -----------------------------------------------------------
    # Step 8: Equity Curve & Drawdown
    # -----------------------------------------------------------
    equity_curve = (1.0 + port_net_ret).cumprod().rename("Equity_Curve")
    running_max = equity_curve.cummax()
    drawdown = ((equity_curve - running_max) / running_max).rename("Drawdown")

    # -----------------------------------------------------------
    # Step 9: Export
    # -----------------------------------------------------------
    export_df = pd.DataFrame(index=signal_df.index)
    export_df["Portfolio_Daily_Ret"] = port_net_ret
    export_df["Portfolio_Gross_Ret"] = port_gross_ret
    export_df["Borrow_Cost_Daily"] = borrow_cost
    export_df["Gross_Exposure"] = gross_exposure
    export_df["Borrow_Ratio"] = borrow_ratio
    export_df["Equity_Curve"] = equity_curve
    export_df["Drawdown"] = drawdown

    # Attach signals (if exist)
    signal_cols = [
        "Regime", "Regime_Source",
        "Trend_Growth", "Trend_Inflation_Blended",
        "Market_Stress_Score"
    ]
    available_signal_cols = [c for c in signal_cols if c in signal_df.columns]
    if available_signal_cols:
        export_df = export_df.join(signal_df[available_signal_cols], how="left")

    # Attach weights
    export_df = export_df.join(weights_df.add_prefix("W_"), how="left")

    # Optional simple benchmarks from your existing assets
    if "SPY" in asset_returns.columns:
        export_df["Benchmark_SPY"] = (1 + asset_returns["SPY"]).cumprod()
    if "TLT" in asset_returns.columns:
        export_df["Benchmark_TLT"] = (1 + asset_returns["TLT"]).cumprod()
    if "IEF" in asset_returns.columns:
        export_df["Benchmark_IEF"] = (1 + asset_returns["IEF"]).cumprod()
    if "GLD" in asset_returns.columns:
        export_df["Benchmark_GLD"] = (1 + asset_returns["GLD"]).cumprod()

    export_df.to_csv(OUTPUT_FILE)

    # -----------------------------------------------------------
    # Step 10: Quick Summary
    # -----------------------------------------------------------
    total_ret = float(equity_curve.iloc[-1] - 1.0) if len(equity_curve) else 0.0
    mdd = float(drawdown.min()) if len(drawdown) else 0.0
    avg_gross = float(gross_exposure.mean()) if len(gross_exposure) else 0.0

    print("\n" + " " * 60)
    print(f"✅ Saved to: {OUTPUT_FILE.name}")
    print(f"📊 Return: {total_ret:.2%} | MaxDD: {mdd:.2%} | Avg Gross Exp: {avg_gross:.2f}x")

    end_time = datetime.datetime.now()
    duration = (end_time - start_time).total_seconds()
    print("\n" + "=" * 68)
    print(f"🏁 LEVERAGE V1 BACKTEST COMPLETED in {duration:.2f}s")
    print("=" * 68)


if __name__ == "__main__":
    run_engine_leverage_v1()