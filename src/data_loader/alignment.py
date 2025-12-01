import pandas as pd
import logging
from pathlib import Path

# ==========================================
# 配置区域
# ==========================================
PROJECT_ROOT = Path(__file__).parent.parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "daily"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
CONFIG_DIR = PROJECT_ROOT / "config"

# 确保输出目录存在
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format='%(message)s')

class DataAligner:
    def __init__(self):
        pass

    def load_tickers_from_config(self, config_name):
        """从指定的 config csv 中读取 ticker 列表"""
        config_path = CONFIG_DIR / config_name
        if not config_path.exists():
            logging.warning(f"Config not found: {config_path}")
            return []
        
        try:
            df = pd.read_csv(config_path)
            # 兼容 ticker 和 yf_ticker (因为文件名是 ticker)
            if 'ticker' in df.columns:
                return df['ticker'].dropna().unique().tolist()
            else:
                return []
        except Exception as e:
            logging.error(f"Error reading {config_name}: {e}")
            return []

    def build_matrix(self, tickers, value_col='Adj Close'):
        """读取多个 csv，合并成一个宽矩阵 (Date x Tickers)"""
        combined = {}
        
        for t in tickers:
            file_path = RAW_DIR / f"{t}.csv"
            if not file_path.exists():
                logging.warning(f"Missing raw file for: {t}")
                continue
            
            try:
                df = pd.read_csv(file_path, index_col=0, parse_dates=True)
                # 简单去重，防止 index 重复报错
                df = df[~df.index.duplicated(keep='last')]
                
                if value_col in df.columns:
                    combined[t] = df[value_col]
                else:
                    logging.warning(f"Column {value_col} not found in {t}")
            except Exception as e:
                logging.error(f"Error processing {t}: {e}")

        if not combined:
            return pd.DataFrame()

        # 合并 (Outer Join 保证不丢数据，后续再清洗)
        matrix = pd.DataFrame(combined)
        return matrix.sort_index()

    def run(self):
        logging.info("--- Starting Alignment Process ---")

        # 1. 处理主角 (Tradable Assets)
        # ------------------------------------------------
        etf_tickers = self.load_tickers_from_config("etf_universe.csv")
        # 未来如果有单只股票，可以在这里加: stock_tickers = ...
        # trade_tickers = etf_tickers + stock_tickers
        
        logging.info(f"Building Asset Matrix for {len(etf_tickers)} ETFs...")
        asset_prices = self.build_matrix(etf_tickers, value_col='Adj Close')
        
        if asset_prices.empty:
            logging.error("No asset data found! Check raw files.")
            return

        # [关键] 确定“主时间轴” (Master Timeline)
        # 通常以数据最全的宽基指数为锚，或者取并集后去除全空行
        # 这里我们简单粗暴：去除所有资产都休市的日子 (Drop rows where all are NaN)
        asset_prices.dropna(how='all', inplace=True)
        
        # 填充资产价格的空洞 (ETF 之间假期可能微小不同，用 ffill 比较安全)
        # 注意：这里 ffill 是为了计算收益率时不出现断层，但第一天之前的 NaNs 会保留
        asset_prices_filled = asset_prices.ffill()

        # 计算收益率矩阵 (Returns Matrix)
        # 这是后续计算相关性、波动率的核心数据
        asset_returns = asset_prices_filled.pct_change()

        # 保存资产数据
        asset_prices.to_csv(PROCESSED_DIR / "asset_prices.csv")
        asset_returns.to_csv(PROCESSED_DIR / "asset_returns.csv")
        logging.info(f"✅ Saved asset_prices.csv & asset_returns.csv (Shape: {asset_prices.shape})")


        # 2. 处理配角 (Macro/Auxiliary)
        # ------------------------------------------------
        macro_tickers = self.load_tickers_from_config("macro_universe.csv")
        
        if macro_tickers:
            logging.info(f"Building Macro Matrix for {len(macro_tickers)} indicators...")
            # 宏观数据我们要的是 'Close' (对于单列数据 downloader 已经把值赋给了 Close/Adj Close)
            macro_levels = self.build_matrix(macro_tickers, value_col='Close')

            if not macro_levels.empty:
                # [核心逻辑] 配角迁就主角
                # 强行重置 Index 为资产矩阵的 Index (Left Join)
                # 这样可以保证：只有交易日才有宏观数据，非交易日的宏观数据会被丢弃
                aligned_macro = macro_levels.reindex(asset_prices.index)
                
                # [关键] 宏观数据必须 Forward Fill
                # 如果周五股市有交易，但宏观数据还没出(NaN)，就沿用上一次的值
                aligned_macro = aligned_macro.ffill()
                
                # 保存
                aligned_macro.to_csv(PROCESSED_DIR / "macro_features.csv")
                logging.info(f"✅ Saved macro_features.csv (Aligned to Assets, Shape: {aligned_macro.shape})")
            else:
                logging.warning("Macro matrix is empty.")
        else:
            logging.info("No macro_universe.csv found or empty. Skipping macro alignment.")

        logging.info("--- Alignment Complete ---")

if __name__ == "__main__":
    aligner = DataAligner()
    aligner.run()