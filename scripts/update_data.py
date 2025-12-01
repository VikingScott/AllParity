import logging
import sys
from pathlib import Path
from datetime import datetime

# ==========================================
# 配置日志输出格式
# ==========================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [MAIN] - %(message)s',
    datefmt='%H:%M:%S'
)

def main():
    print("="*60)
    print(f"🚀 GLOBAL ASSET ALLOCATION SYSTEM - UPDATE PIPELINE")
    print(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    try:
        # ---------------------------------------------------------
        # Step 1: Data Downloader (下载与增量更新)
        # ---------------------------------------------------------
        print("\n" + "-"*30)
        print(">>> STEP 1: DOWNLOADING DATA")
        print("-"*30)
        
        # 动态导入，确保路径正确
        from src.data_loader.downloader import MarketDataUpdater
        
        updater = MarketDataUpdater()
        updater.run()
        
        print("✅ Data Download Complete.")

        # ---------------------------------------------------------
        # Step 2: Data Alignment (对齐与矩阵化)
        # ---------------------------------------------------------
        print("\n" + "-"*30)
        print(">>> STEP 2: ALIGNING DATA")
        print("-"*30)
        
        from src.data_loader.alignment import DataAligner
        
        aligner = DataAligner()
        aligner.run()
        
        print("✅ Data Alignment Complete.")

        # ---------------------------------------------------------
        # 结束摘要
        # ---------------------------------------------------------
        print("\n" + "="*60)
        print("🎉 PIPELINE FINISHED SUCCESSFULLY")
        print("="*60)
        print("Next Steps:")
        print("  1. Run 'python playground.py' to simulate portfolios.")
        print("  2. Run 'python src/visualization/charting.py' to see charts.")
        print("  3. Check 'data/processed/' for updated CSVs.")
        print("="*60)

    except ImportError as e:
        logging.error(f"Module Import Error: {e}")
        print("\n❌ CRITICAL ERROR: Could not import modules.")
        print("Please ensure your folder structure is correct:")
        print("  - src/data_loader/downloader.py")
        print("  - src/data_processor/alignment.py")
        
    except Exception as e:
        logging.error(f"Pipeline Failed: {e}")
        print(f"\n❌ UNEXPECTED ERROR: {e}")

if __name__ == "__main__":
    main()