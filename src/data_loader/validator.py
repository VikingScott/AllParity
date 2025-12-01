import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import logging

# ==========================================
# 配置区域
# ==========================================
PROJECT_ROOT = Path(__file__).parent.parent.parent
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw" / "daily"
OUTPUT_DIR = PROJECT_ROOT / "data" / "processed"

# 确保输出目录存在
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 设置简易日志
logging.basicConfig(level=logging.INFO, format='%(message)s')

class DataValidator:
    def __init__(self):
        self.report_data = []
        self.today = datetime.now()

    def check_file(self, filepath):
        """检查单个 CSV 文件的健康状况"""
        ticker = filepath.stem # 文件名即 ticker
        
        try:
            df = pd.read_csv(filepath, index_col=0, parse_dates=True)
            
            if df.empty:
                return {
                    'ticker': ticker,
                    'status': 'CRITICAL',
                    'note': 'File is empty'
                }

            # 1. 基础信息
            start_date = df.index[0]
            last_date = df.index[-1]
            total_rows = len(df)
            
            # 2. 时效性检查 (Staleness)
            # 如果最后一天距离今天超过 5 天（考虑周末），标记为过期
            days_since_update = (self.today - last_date).days
            is_stale = days_since_update > 5
            
            # 3. 完整性检查 (NaNs)
            # 重点检查 Adj Close
            nan_count = df['Adj Close'].isna().sum()
            
            # 4. 逻辑一致性检查 (Integrity)
            # High 必须 >= Low
            # 为了容错 FRED 数据（可能 High=Low），我们只抓 High < Low
            logic_errors = df[df['High'] < df['Low']].shape[0]
            
            # 5. 零值检查 (Zeros)
            # 价格为 0 通常是数据错误
            zeros_count = df[df['Adj Close'] <= 0].shape[0]

            # 6. 综合评级
            status = 'OK'
            notes = []
            
            if total_rows < 10:
                status = 'WARNING'
                notes.append('Too few rows')
            
            if is_stale:
                status = 'WARNING'
                notes.append(f'Stale ({days_since_update} days old)')
                
            if logic_errors > 0:
                status = 'CRITICAL'
                notes.append(f'{logic_errors} OHLC errors')
                
            if nan_count > 0:
                status = 'CRITICAL'
                notes.append(f'{nan_count} NaNs in Price')
                
            if zeros_count > 0:
                status = 'CRITICAL'
                notes.append(f'{zeros_count} Zeros in Price')

            return {
                'ticker': ticker,
                'status': status,
                'start_date': start_date.strftime('%Y-%m-%d'),
                'last_date': last_date.strftime('%Y-%m-%d'),
                'total_rows': total_rows,
                'days_lag': days_since_update,
                'logic_errors': logic_errors,
                'zeros': zeros_count,
                'nans': nan_count,
                'note': "; ".join(notes)
            }

        except Exception as e:
            return {
                'ticker': ticker,
                'status': 'ERROR',
                'note': str(e)
            }

    def run(self):
        # 获取目录下所有 csv
        csv_files = list(RAW_DATA_DIR.glob("*.csv"))
        
        if not csv_files:
            logging.error(f"No CSV files found in {RAW_DATA_DIR}")
            return

        logging.info(f"Starting validation for {len(csv_files)} files...")
        
        for file in csv_files:
            result = self.check_file(file)
            self.report_data.append(result)
            
            # 简单的控制台反馈
            if result.get('status') != 'OK':
                logging.warning(f"[{result['status']}] {result['ticker']}: {result.get('note')}")

        # 生成报告
        report_df = pd.DataFrame(self.report_data)
        
        # 按照状态排序：Critical -> Warning -> OK
        report_df['status_rank'] = report_df['status'].map({'ERROR': 0, 'CRITICAL': 1, 'WARNING': 2, 'OK': 3})
        report_df = report_df.sort_values('status_rank').drop(columns=['status_rank'])
        
        output_path = OUTPUT_DIR / "quality_report.csv"
        report_df.to_csv(output_path, index=False)
        
        logging.info("-" * 30)
        logging.info(f"Validation complete. Report saved to: {output_path}")
        logging.info("-" * 30)
        
        # 打印摘要
        summary = report_df['status'].value_counts()
        print("\nSummary:")
        print(summary)

if __name__ == "__main__":
    validator = DataValidator()
    validator.run()