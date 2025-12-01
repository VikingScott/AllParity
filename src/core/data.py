import pandas as pd
from pathlib import Path

# ==========================================
# 路径配置
# ==========================================
# 向上追溯3层: src/core/data.py -> src/core -> src -> Project_Root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
FEATURES_DIR = PROJECT_ROOT / "data" / "features"

class DataLoader:
    """
    数据加载核心类
    职责: 统一读取 CSV，并强制清洗索引格式 (DatetimeIndex)，防止回测切片为空。
    """

    @staticmethod
    def _clean_index(df):
        """
        [核心修复] 索引清洗器
        解决: "Benchmark returns 0" 的罪魁祸首通常是日期格式对不上。
        """
        if df.empty:
            return df
            
        try:
            # 1. 强制转为 Datetime 对象 (处理字符串索引)
            # utc=True 兼容各种怪异格式
            df.index = pd.to_datetime(df.index, utc=True)
            
            # 2. 暴力去除时区信息 (UTC -> Naive)
            # 这样 '2023-01-01 00:00+00:00' 就会变成 '2023-01-01'
            # 方便和回测引擎里的 date (通常无时区) 进行比较
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)
                
            # 3. 排序 (防止切片失效)
            df = df.sort_index()
            
        except Exception as e:
            print(f"⚠️ DataLoader Warning: Index cleaning failed: {e}")
            
        return df

    @staticmethod
    def load_prices():
        """读取资产价格 (Adj Close)"""
        path = PROCESSED_DIR / "asset_prices.csv"
        if not path.exists(): 
            raise FileNotFoundError(f"❌ Missing Data: {path} - Please run scripts/update_data.py first.")
        
        df = pd.read_csv(path, index_col=0)
        return DataLoader._clean_index(df)

    @staticmethod
    def load_returns():
        """读取资产收益率 (Pct Change)"""
        path = PROCESSED_DIR / "asset_returns.csv"
        if not path.exists(): 
            raise FileNotFoundError(f"❌ Missing Data: {path}")
        
        df = pd.read_csv(path, index_col=0)
        return DataLoader._clean_index(df)

    @staticmethod
    def load_macro():
        """读取宏观数据"""
        path = PROCESSED_DIR / "macro_features.csv"
        if not path.exists(): 
            # 宏观数据允许缺失，不报错，返回 None
            return None
        
        df = pd.read_csv(path, index_col=0)
        return DataLoader._clean_index(df)

    @staticmethod
    def load_feature(filename):
        """读取特征信号"""
        path = FEATURES_DIR / filename
        if not path.exists(): 
            print(f"⚠️ Feature file not found: {filename}")
            return None
        
        df = pd.read_csv(path, index_col=0)
        return DataLoader._clean_index(df)
    
    @staticmethod
    def save_feature(df, filename):
        """保存特征信号"""
        FEATURES_DIR.mkdir(parents=True, exist_ok=True)
        # 保存前也建议清洗一下，确保写入的是标准格式
        df = DataLoader._clean_index(df)
        df.to_csv(FEATURES_DIR / filename)
        print(f"✅ Feature saved: {filename}")