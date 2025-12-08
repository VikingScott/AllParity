# verify_allocation.py

import pandas as pd
from src.data_loader import get_merged_market_state
from src.macro_regime_signal_generator import run_signal_pipeline
from src.strategy_allocation import get_target_weights
from src.config_regime import COLUMN_MAP

def verify_strategy_logic():
    print("1. Loading Data...")
    df_market = get_merged_market_state('data/Macro_Daily_Final.csv', 'data/asset_prices.csv')
    
    print("2. Generating Signals...")
    signal_df = run_signal_pipeline(df_market)
    
    print("3. Calculating Target Weights...")
    weights_df = get_target_weights(signal_df)
    
    # 合并信号和权重以便查看，方便人类阅读
    debug_df = pd.concat([signal_df[['Regime', 'Regime_Source']], weights_df], axis=1)
    
    # === 关键点检查 (Spot Checks) ===
    checkpoints = [
        ("2008-10-10", "GFC Panic (Should be 100% Cash)"),
        ("2017-06-01", "Goldilocks (Should be Equity Heavy)"),
        ("2022-06-15", "Inflation Spike (Should be Comm/TIPs)"),
    ]
    
    print("\n" + "="*60)
    print("STRATEGY LOGIC VERIFICATION")
    print("="*60)
    
    for date_str, desc in checkpoints:
        if date_str not in debug_df.index:
            print(f"⚠️ Date {date_str} not found in data.")
            continue
            
        row = debug_df.loc[date_str]
        
        print(f"\n📅 Date: {date_str} | Context: {desc}")
        print(f"   [Signal] Regime: {row['Regime']} ({row['Regime_Source']})")
        
        # 打印非零仓位
        active_positions = {k: v for k, v in row.items() 
                            if k not in ['Regime', 'Regime_Source'] and v > 0.0}
        
        # 格式化输出
        pos_str = ", ".join([f"{k}:{v:.0%}" for k, v in active_positions.items()])
        print(f"   [Action] Portfolio: {pos_str}")
        
        # 简单断言逻辑 (打印给人类看)
        if "Cash" in desc and row.get('SGOV', 0) < 0.9:
            print("   ❌ FAILED: Expected 100% Cash!")
        elif "Equity" in desc and row.get('SPY', 0) < 0.3:
            print("   ❌ FAILED: Expected Equity allocation!")
        elif "Inflation" in desc and (row.get('DBC', 0) + row.get('TIP', 0) < 0.3):
             print("   ❌ FAILED: Expected Inflation hedges!")
        else:
            print("   ✅ PASSED")

    print("\n" + "="*60)
    
if __name__ == "__main__":
    verify_strategy_logic()