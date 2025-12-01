"""
================================================================================
🚀 MAIN RESEARCH CONTROLLER
================================================================================
此脚本负责协调 Config, Runner 和 Reporter。
1. 读取 config/scenarios.py 中的实验配置。
2. 调用 Runner 进行交互式回测。
3. 调用 Reporter 生成报表。
================================================================================
"""
import sys
from pathlib import Path
from datetime import datetime

sys.path.append(str(Path(__file__).resolve().parent.parent))

from config.scenarios import SCENARIOS, BENCHMARK_SETUP
from src.research.runner import ResearchRunner # 需新建
from src.analysis.reporter import ResearchReporter # 需新建

def main():
    timestamp = datetime.now().strftime('%Y%m%d_%H%M')
    output_dir = Path(__file__).resolve().parent.parent / "reports" / "data" / f"batch_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"🎬 SESSION START: {timestamp}")
    print(f"📂 Output Directory: {output_dir}")

    # 1. 初始化 Runner
    runner = ResearchRunner(SCENARIOS, BENCHMARK_SETUP)
    
    # 2. 运行回测 (包含交互式时间选择)
    results = runner.run(output_dir)
    
    if not results:
        print("👋 Session aborted.")
        return

    # 3. 生成报告
    reporter = ResearchReporter(output_dir)
    reporter.generate_report(results)
    
    print(f"\n✨ All Done. Check reports in {output_dir}")

if __name__ == "__main__":
    main()