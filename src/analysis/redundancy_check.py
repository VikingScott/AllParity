import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime

# ==========================================
# 配置区域
# ==========================================
PROJECT_ROOT = Path(__file__).parent.parent.parent
RETURNS_PATH = PROJECT_ROOT / "data" / "processed" / "asset_returns.csv"
PRICES_PATH = PROJECT_ROOT / "data" / "processed" / "asset_prices.csv"
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "daily" # 用来查 Volume

# 判定为“一模一样”的相关性阈值
CORR_THRESHOLD = 0.99

class RedundancyAnalyzer:
    def __init__(self):
        self.returns = self.load_data(RETURNS_PATH)
        self.prices = self.load_data(PRICES_PATH)
        self.meta_cache = {} # 缓存 Start Date 和 Volume

    def load_data(self, path):
        if not path.exists():
            print(f"❌ File not found: {path}")
            return pd.DataFrame()
        return pd.read_csv(path, index_col=0, parse_dates=True)

    def get_asset_stats(self, ticker):
        """获取资产的元数据：开始时间，平均成交量"""
        if ticker in self.meta_cache:
            return self.meta_cache[ticker]

        # 1. Start Date (从 Prices 矩阵直接获取)
        valid_idx = self.prices[ticker].first_valid_index()
        start_date = valid_idx if valid_idx else datetime.now()
        
        # 2. Avg Volume (需要去读原始 Raw CSV，因为 Processed 里没存 Volume)
        # 这里做一个简单的近似：读取 raw 文件最后 30 行
        avg_vol = 0
        raw_path = RAW_DIR / f"{ticker}.csv"
        if raw_path.exists():
            try:
                df = pd.read_csv(raw_path)
                if 'Volume' in df.columns and not df.empty:
                    avg_vol = df['Volume'].tail(30).mean()
            except:
                pass
        
        stats = {
            'start_date': start_date,
            'volume': avg_vol
        }
        self.meta_cache[ticker] = stats
        return stats

    def calculate_beta(self, series_target, series_benchmark):
        """计算相对 Beta"""
        # 对齐数据
        common = pd.concat([series_target, series_benchmark], axis=1).dropna()
        if common.empty: return 0
        
        cov = common.cov().iloc[0, 1]
        var = common.iloc[:, 1].var()
        if var == 0: return 0
        return cov / var

    def run(self):
        if self.returns.empty: return
        
        print("="*60)
        print(f"🔍 ASSET REDUNDANCY CHECKER (Threshold: {CORR_THRESHOLD})")
        print("="*60)
        
        # 计算相关性矩阵
        # 这里使用最近 3 年的数据来计算相关性，更能反映当下的替代关系
        # 如果历史太长，早期的数据可能会稀释现在的相关性
        recent_returns = self.returns.tail(252 * 3) 
        corr_matrix = recent_returns.corr()
        
        columns = corr_matrix.columns
        duplicates = []
        dropped_set = set() # 防止 A-B 和 B-A 重复报告
        
        print(f"Analyzing {len(columns)} assets for identical pairs...\n")

        for i in range(len(columns)):
            for j in range(i + 1, len(columns)):
                ticker_a = columns[i]
                ticker_b = columns[j]
                
                corr_val = corr_matrix.iloc[i, j]
                
                if corr_val >= CORR_THRESHOLD:
                    # 发现高度相关对！
                    stats_a = self.get_asset_stats(ticker_a)
                    stats_b = self.get_asset_stats(ticker_b)
                    
                    # 计算 Beta (以 B 为基准看 A)
                    beta = self.calculate_beta(recent_returns[ticker_a], recent_returns[ticker_b])
                    
                    # 决策逻辑：谁老谁留下
                    date_a = stats_a['start_date']
                    date_b = stats_b['start_date']
                    
                    keep = None
                    drop = None
                    reason = ""
                    
                    if date_a < date_b:
                        keep, drop = ticker_a, ticker_b
                        reason = f"Older history ({date_a.date()} vs {date_b.date()})"
                    elif date_b < date_a:
                        keep, drop = ticker_b, ticker_a
                        reason = f"Older history ({date_b.date()} vs {date_a.date()})"
                    else:
                        # 历史一样长，比流动性
                        if stats_a['volume'] > stats_b['volume']:
                            keep, drop = ticker_a, ticker_b
                            reason = "Higher liquidity"
                        else:
                            keep, drop = ticker_b, ticker_a
                            reason = "Higher liquidity"
                    
                    duplicates.append({
                        'Keep': keep,
                        'Drop': drop,
                        'Corr': corr_val,
                        'Beta': beta,
                        'Reason': reason
                    })

        # 输出报告
        if not duplicates:
            print("✅ No redundant assets found. Your universe is clean!")
        else:
            print(f"⚠️ Found {len(duplicates)} pairs of highly identical assets:\n")
            print(f"{'KEEP':<10} | {'DROP':<10} | {'CORR':<6} | {'BETA':<6} | {'REASON'}")
            print("-" * 65)
            
            # 简单的去重展示：如果一个资产被建议删除多次，只显示一次
            # 这里的逻辑比较简单，只是展示建议
            for item in duplicates:
                print(f"{item['Keep']:<10} | {item['Drop']:<10} | {item['Corr']:.4f} | {item['Beta']:.2f}   | {item['Reason']}")

            print("\n" + "="*60)
            print("💡 ACTION PLAN:")
            unique_drops = set(d['Drop'] for d in duplicates)
            print(f"You can safely remove these {len(unique_drops)} tickers from your config:")
            print(", ".join(sorted(list(unique_drops))))
            print("="*60)

if __name__ == "__main__":
    analyzer = RedundancyAnalyzer()
    analyzer.run()