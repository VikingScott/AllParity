"""
ETF 组合预设文件
用于批量下载、分析或回测特定的资产群组。
"""

# ==========================================
# 1. SPDR US Sectors (美股行业板块)
# ==========================================
# 经典的 "XL" 系列，用于分析美国经济的板块轮动
US_SECTORS = [
    "XLK",  # Technology (科技 - Apple, Microsoft, Nvidia)
    "XLV",  # Health Care (医疗 - UnitedHealth, J&J)
    "XLF",  # Financials (金融 - Berkshire, JPM)
    "XLC",  # Communication (通讯 - Meta, Google, Netflix)
    "XLY",  # Consumer Discretionary (可选消费 - Amazon, Tesla)
    "XLP",  # Consumer Staples (必选消费 - P&G, Costco)
    "XLE",  # Energy (能源 - Exxon, Chevron)
    "XLI",  # Industrials (工业 - Caterpillar, Boeing)
    "XLB",  # Materials (原材料 - Linde)
    "XLU",  # Utilities (公用事业 - NextEra)
    "XLRE", # Real Estate (房地产 - PLD, AMT)
]

# ==========================================
# 2. MSCI Single Country (全球单一国家)
# ==========================================
# 用于观察地缘政治风险和全球资金流向

# 发达国家 (Developed Markets)
COUNTRIES_DM = [
    "EWJ",  # Japan (日本)
    "EWG",  # Germany (德国)
    "EWU",  # United Kingdom (英国)
    "EWQ",  # France (法国)
    "EWC",  # Canada (加拿大)
    "EWA",  # Australia (澳洲)
    "EWI",  # Italy (意大利)
    "EWP",  # Spain (西班牙)
    "EWL",  # Switzerland (瑞士)
    "EWH",  # Hong Kong (香港 - 发达市场定义)
    "EWS",  # Singapore (新加坡)
    "EDEN", # Denmark (丹麦 - 诺和诺德权重极高)
]

# 新兴市场 (Emerging Markets)
COUNTRIES_EM = [
    "MCHI", # China (中国 - 腾讯阿里等)
    "INDA", # India (印度)
    "EWT",  # Taiwan (台湾 - 台积电权重高)
    "EWZ",  # Brazil (巴西 - 资源国)
    "EWW",  # Mexico (墨西哥)
    "EZA",  # South Africa (南非)
    "KSA",  # Saudi Arabia (沙特)
    "TUR",  # Turkey (土耳其 - 波动极大)
    "THD",  # Thailand (泰国)
    "EIDO", # Indonesia (印尼)
    "VNM",  # Vietnam (越南 - 前沿市场)
    "ARGT", # Argentina (阿根廷 - 政治风险高)
]

# ==========================================
# 3. Factor & Styles (因子与风格)
# ==========================================
# 用于分析当前市场偏好什么风格
FACTORS_US = [
    "MTUM", # Momentum (动量)
    "VLUE", # Value (价值)
    "QUAL", # Quality (质量)
    "USMV", # Min Volatility (低波)
    "SIZE", # Size (小盘)
    "IWM",  # Russell 2000 (小盘基准)
    "QQQ",  # Nasdaq 100 (成长基准)
    "SPY",  # S&P 500 (大盘基准)
]

# ==========================================
# 4. Bond Ladder (债券阶梯)
# ==========================================
# 用于观察利率曲线变化
BOND_CURVE = [
    "SGOV", # 0-3 Month (超短/现金)
    "SHY",  # 1-3 Year (短债)
    "IEI",  # 3-7 Year (中短)
    "IEF",  # 7-10 Year (中长/基准)
    "TLT",  # 20+ Year (长债/久期风险)
    "EDV",  # Extended Duration (超长债/极高波动)
]

# ==========================================
# 5. Alternatives (另类资产)
# ==========================================
# 用于抗通胀或分散风险
ALTERNATIVES = [
    "GLD",  # Gold (黄金)
    "SLV",  # Silver (白银)
    "DBC",  # Broad Commodities (大宗商品)
    "USO",  # Oil (原油)
    "VNQ",  # US REITs (地产)
    "IBIT", # Bitcoin (比特币)
    "ETHA", # Ethereum (以太坊)
]

# ==========================================
# Master Dictionary (总索引)
# ==========================================
# 方便代码遍历所有组合
ALL_BUNDLES = {
    "US_Sectors": US_SECTORS,
    "Global_DM": COUNTRIES_DM,
    "Global_EM": COUNTRIES_EM,
    "Factors": FACTORS_US,
    "Bond_Curve": BOND_CURVE,
    "Alternatives": ALTERNATIVES
}