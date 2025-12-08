# verify_allocation.py

import pandas as pd
from src.data_loader import get_merged_market_state

from src.macro_regime_signal_generator import run_signal_pipeline
from src.strategy_allocation import get_target_weights

def verify_strategy_logic():
    print("1. Loading Data...")
    df_market = get_merged_market_state('data/Macro_Daily_Final.csv', 'data/asset_prices.csv')
    
    print("2. Generating Signals (V2 Pipeline)...")
    signal_df = run_signal_pipeline(df_market)
    
    print("3. Calculating Target Weights...")
    weights_df = get_target_weights(signal_df)
    
    # 构造调试视图：合并 信号核心列 + 权重分配列
    # 我们不仅看 Regime，还要看 Source，这决定了是“经济衰退”还是“市场熔断”
    debug_cols = ['Regime', 'Regime_Source', 'Market_Stress_Score', 'Trend_Growth', 'Trend_Inflation_Blended']
    debug_df = pd.concat([signal_df[debug_cols], weights_df], axis=1)
    
    # === 关键历史节点检查 (The Acid Test) ===
    checkpoints = [
        ("2017-01-10", "2017 Growth check 1)"),
        ("2017-10-20", "Goldilocks Bull (Expect: Macro Source -> High Equity)"),
        ("2017-06-15", "2017 Growth check 2)"),
        ("2017-10-20", "2017 Growth check 3)"),
    ]
    
    print("\n" + "="*80)
    print("STRATEGY LOGIC VERIFICATION REPORT")
    print("="*80)
    
    for date_str, desc in checkpoints:
        if date_str not in debug_df.index:
            print(f"⚠️ Date {date_str} not found in data.")
            continue
            
        row = debug_df.loc[date_str]
        
        print(f"\n📅 [{date_str}] Context: {desc}")
        print(f"   [Inputs] Score: {row['Market_Stress_Score']} | Growth: {row['Trend_Growth']:.2f} | Infl: {row['Trend_Inflation_Blended']:.2f}")
        print(f"   [Signal] Regime: {row['Regime']} | Source: {row['Regime_Source']}")
        
        # 筛选出仓位 > 0 的资产进行打印
        active_positions = {k: v for k, v in row.items() 
                            if k not in debug_cols and isinstance(v, (int, float)) and v > 0.001}
        
        # 格式化输出
        pos_str = " | ".join([f"{k}: {v:.0%}" for k, v in active_positions.items()])
        print(f"   [Action] Portfolio: {pos_str}")
        
        # --- 自动断言逻辑 ---
        if "Cash" in desc:
            if row['Regime_Source'] != "MARKET_CIRCUIT":
                print("   ❌ FAIL: Should be MARKET_CIRCUIT triggered!")
            elif row.get('SGOV', 0) < 0.9:
                print("   ❌ FAIL: Cash (SGOV) allocation is too low!")
            else:
                print("   ✅ PASS: Correctly in Cash Protection mode.")
                
        elif "Equity" in desc:
            equity_sum = row.get('SPY', 0) + row.get('EFA', 0) + row.get('EEM', 0)
            if equity_sum < 0.4:
                print(f"   ❌ FAIL: Equity allocation ({equity_sum:.0%}) too low for Bull Market!")
            else:
                print("   ✅ PASS: Correctly in Risk-On mode.")
                
        elif "Inflation" in desc:
            hedge_sum = row.get('DBC', 0) + row.get('TIP', 0) + row.get('GLD', 0)
            if hedge_sum < 0.3:
                print(f"   ❌ FAIL: Inflation hedges ({hedge_sum:.0%}) too low!")
            else:
                print("   ✅ PASS: Correctly holding Inflation Hedges.")

    print("\n" + "="*80)
    print("Verification Complete.")

if __name__ == "__main__":
    verify_strategy_logic()