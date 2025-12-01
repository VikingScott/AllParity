import sys
from pathlib import Path

# Path Hack
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.core.data import DataLoader
from src.features.trend import TrendFeatures

def main():
    print("="*60)
    print("🏭 FEATURE ENGINEERING FACTORY")
    print("="*60)
    
    # 1. 准备数据 (Injection)
    print("Loading Prices...")
    try:
        prices = DataLoader.load_prices()
    except Exception as e:
        print(f"❌ Critical Error: {e}")
        return

    # 2. 初始化计算器
    tf = TrendFeatures(prices)
    
    # 3. 定义要生成的参数列表
    # (以后想加 MA120，就在这里加一个数字即可)
    ma_windows = [20, 60, 120, 200]
    
    print(f"\n>>> Task 1: Building Moving Average Signals {ma_windows}...")
    
    for w in ma_windows:
        filename = f"signal_ma_{w}.csv"
        print(f"   - Computing MA({w})...", end=" ")
        
        try:
            # 计算
            sig = tf.calculate_ma_signal(window=w)
            
            # 保存
            DataLoader.save_feature(sig, filename)
            
            # 简单质检
            if sig.sum().sum() == 0:
                print("⚠️  (Warning: Signal is all zeros)")
            
        except Exception as e:
            print(f"❌ Failed: {e}")

    # (预留位置给其他特征，比如动量、波动率)
    # print("\n>>> Task 2: Building Momentum Signals...")

    print("\n" + "="*60)
    print("🎉 Feature Engineering Complete.")
    print("="*60)

if __name__ == "__main__":
    main()