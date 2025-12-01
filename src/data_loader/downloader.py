import os
import time
import random
import logging
import pandas as pd
import yfinance as yf
import pandas_datareader.data as web
from pathlib import Path
from datetime import datetime, timedelta

# ==========================================
# 配置区域 (UPDATED: 允许多个配置源)
# ==========================================
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "raw" / "daily"
LOG_DIR = PROJECT_ROOT / "logs"

# 定义所有需要加载的配置文件的路径和类型
# 注意：你需要确保这些文件存在于 config/ 目录下
CONFIG_FILES = [
    {'path': PROJECT_ROOT / "config" / "etf_universe.csv", 'config_type': 'etf'},
    {'path': PROJECT_ROOT / "config" / "macro_universe.csv", 'config_type': 'macro'},
    # 未来可在此处添加 'singlestock_universe.csv' 或其他数据源
]

DATA_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

# 设置日志 (保持与你习惯一致)
logging.basicConfig(
    filename=LOG_DIR / f"update_{datetime.now().strftime('%Y%m%d')}.log",
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
logging.getLogger('').addHandler(console)

class MarketDataUpdater:
    def __init__(self):
        pass

    def load_universe(self):
        """[NEW] 加载所有配置文件并合并"""
        full_universe = []
        
        for config_info in CONFIG_FILES:
            path = config_info['path']
            config_type = config_info['config_type']
            
            if not path.exists():
                logging.warning(f"Configuration file not found: {path}. Skipping.")
                continue

            try:
                df = pd.read_csv(path)
                
                # 确保关键列存在，并进行清洗
                df = df.dropna(subset=['ticker', 'yf_ticker'])
                
                if 'source' not in df.columns:
                    df['source'] = 'yahoo' # 默认使用 Yahoo

                # 增加 Config Type 字段，用于下游模块（如数据对齐或风控）的分类
                df['config_type'] = config_type
                
                full_universe.append(df)
            except Exception as e:
                logging.error(f"Error reading and processing {path}: {e}")
                
        if not full_universe:
            logging.error("No valid configuration files were loaded.")
            return pd.DataFrame()

        return pd.concat(full_universe, ignore_index=True)


    def get_existing_data(self, filepath):
        if not filepath.exists():
            return None, None
        try:
            df = pd.read_csv(filepath, index_col=0, parse_dates=True)
            if df.empty: return None, None
            df.index = pd.to_datetime(df.index)
            return df, df.index[-1]
        except Exception as e:
            logging.error(f"Error reading {filepath}: {e}")
            return None, None

    def clean_data(self, df, source='yahoo'):
        """标准化数据格式"""
        # 1. 去除时区
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)

        # 2. FRED 数据特殊处理 (单列 -> OHLCV)
        if source == 'fred':
            df = df.ffill()
            col_name = df.columns[0]
            # 构造标准格式，Open/High/Low/Close 都用同一个值填充
            df['Close'] = df[col_name]
            df['Adj Close'] = df[col_name]
            df['Open'] = df[col_name]
            df['High'] = df[col_name]
            df['Low'] = df[col_name]
            df['Volume'] = 0
            df = df[['Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume']]

        # 3. Yahoo 数据处理
        elif source == 'yahoo':
            if isinstance(df.columns, pd.MultiIndex):
                try:
                    df.columns = df.columns.get_level_values(0)
                except:
                    pass
            if 'Volume' not in df.columns:
                df['Volume'] = 0
        
        # 4. 统一筛选列
        expected_cols = ['Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume']
        valid_cols = [c for c in expected_cols if c in df.columns]
        df = df[valid_cols]
        
        return df.astype(float)

    def download_yahoo(self, ticker, yf_ticker, start_date=None, mode="Full"):
        """Yahoo Finance 下载逻辑"""
        max_retries = 3
        base_wait = 5 
        
        for attempt in range(max_retries):
            try:
                logging.info(f"[Yahoo] Downloading {ticker} ({mode})...")
                if mode == "Incremental" and start_date:
                    data = yf.download(yf_ticker, start=start_date, progress=False, auto_adjust=False)
                else:
                    data = yf.download(yf_ticker, period="max", progress=False, auto_adjust=False)

                if not data.empty:
                    return data
                logging.warning(f"[Yahoo] Empty data for {ticker}. Retrying...")
            except Exception as e:
                logging.warning(f"[Yahoo] Error {ticker}: {e}")
            
            time.sleep(base_wait * (attempt + 1))
        return None

    def download_fred(self, ticker, fred_id, start_date=None):
        """FRED 下载逻辑"""
        try:
            logging.info(f"[FRED] Downloading {ticker} ({fred_id})...")
            
            start = datetime(1970, 1, 1)
            if start_date:
                # 确保 FRED 请求日期不早于本地最后日期
                start = datetime.strptime(start_date, '%Y-%m-%d')
            
            df = web.DataReader(fred_id, 'fred', start, datetime.now())
            
            if not df.empty:
                return df
            else:
                logging.warning(f"[FRED] Empty data for {ticker}")
                return None
                
        except Exception as e:
            logging.error(f"[FRED] Failed to download {ticker}: {e}")
            return None

    def update_ticker(self, ticker, lookup_symbol, source):
        file_path = DATA_DIR / f"{ticker}.csv"
        existing_df, last_date = self.get_existing_data(file_path)
        
        new_data = None
        start_date_str = None
        
        if last_date:
            start_date_str = last_date.strftime('%Y-%m-%d')
            mode = "Incremental"
        else:
            mode = "Full"

        # === 分发逻辑 ===
        if source == 'fred':
            new_data = self.download_fred(ticker, lookup_symbol, start_date=start_date_str)
        else:
            new_data = self.download_yahoo(ticker, lookup_symbol, start_date=start_date_str, mode=mode)

        if new_data is None or new_data.empty:
            return

        clean_new_df = self.clean_data(new_data, source=source)
        if clean_new_df is None or clean_new_df.empty:
            return

        # 合并与去重
        if existing_df is not None:
            combined_df = pd.concat([existing_df, clean_new_df])
            combined_df = combined_df[~combined_df.index.duplicated(keep='last')]
            combined_df = combined_df.sort_index()
        else:
            combined_df = clean_new_df

        combined_df.to_csv(file_path)
        logging.info(f"Saved {ticker} [{source}]. Rows: {len(combined_df)}")

    def run(self):
        """主运行方法，加载所有配置并开始更新"""
        universe = self.load_universe()
        
        if universe.empty:
            return

        logging.info(f"Starting update for {len(universe)} combined tickers...")

        for index, row in universe.iterrows():
            ticker = row['ticker']
            lookup_symbol = row['yf_ticker']
            # 确保 source 字段存在且是小写，以便匹配 'fred' 或 'yahoo'
            source = row['source'].strip().lower() 
            
            self.update_ticker(ticker, lookup_symbol, source)
            
            time.sleep(random.uniform(1.0, 2.0))

        logging.info("All updates completed.")

if __name__ == "__main__":
    updater = MarketDataUpdater()
    updater.run()