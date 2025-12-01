没问题，我已经完全理解并记住了你当前的架构和数据流。

为了确保未来的 AI 模型（或你自己）能快速接手并理解这个系统，我将其整理为一份标准的**技术架构文档 (Technical Architecture Document)**。这份文档采用了结构化的文本格式，清晰定义了目录结构、数据流转逻辑和核心数据模式。

你可以将以下内容保存为 `ARCHITECTURE.md` 或直接作为提示词喂给未来的 LLM。

-----

# 🏗️ Global Asset Allocation System - Architecture & Pipeline

## 1\. 项目目录结构 (Directory Structure)

```text
Global_Asset_System/
├── config/                         # [配置层] 系统的控制中心
│   ├── etf_bundles.py              # 预设的资产组合列表 (Python List)
│   ├── etf_universe.csv            # 核心资产池配置 (自动生成/手动管理)
│   └── macro_universe.csv          # 宏观指标配置 (FRED/Yahoo)
│
├── data/                           # [数据层] 
│   ├── raw/                        
│   │   └── daily/                  # [Raw] 原始日线数据 (每个资产一个 CSV)
│   │       ├── SPY.csv
│   │       ├── GLD.csv
│   │       └── ...
│   └── processed/                  # [Processed] 清洗、对齐后的矩阵数据
│       ├── asset_prices.csv        # 价格矩阵 (Date x Ticker)
│       ├── asset_returns.csv       # 收益率矩阵 (Date x Ticker)
│       ├── macro_features.csv      # 宏观因子矩阵 (对齐到交易日)
│       └── quality_report.csv      # 数据质量检查报告
│
├── src/                            # [逻辑层]
│   ├── data_loader/                
│   │   ├── universe_manager.py     # 资产录入工具 (Bundles -> CSV)
│   │   ├── downloader.py           # 数据下载器 (Yahoo/FRED -> Raw)
│   │   └── alignment.py            # 数据对齐器 (Raw -> Processed)
│   ├── data_processor/
│   │   └── validator.py            # 数据质检员 (Raw -> Report)
│   ├── analysis/                   # 静态分析工具
│   └── visualization/              # 绘图工具
│
└── main.py                         # [入口] 自动化流水线编排脚本
```

-----

## 2\. 数据处理流水线 (Data Pipeline Workflow)

整个系统由 `main.py` 统一编排，数据流向为单向流动：**Config -\> Raw -\> Processed**。

### Phase 1: 配置管理 (Configuration)

  * **输入**: `config/etf_bundles.py` (预设代码集合) 或 用户手动输入。
  * **执行者**: `src/data_loader/universe_manager.py`。
  * **动作**:
    1.  从 Bundles 导入或手动添加 Ticker。
    2.  调用 Yahoo Finance API 获取元数据（名称、分类）。
    3.  查重并写入/更新配置 CSV。
  * **输出**: `config/etf_universe.csv`。

### Phase 2: 数据获取 (Ingestion)

  * **输入**: `config/etf_universe.csv` 和 `config/macro_universe.csv`。
  * **执行者**: `src/data_loader/downloader.py` (由 `main.py` 调度)。
  * **动作**:
    1.  **增量检查**: 读取 `data/raw/daily/{ticker}.csv` 检查最后日期。
    2.  **多源下载**:
          * 权益类 -\> `yfinance` (Yahoo)。
          * 宏观类 -\> `pandas_datareader` (FRED)。
    3.  **标准化**: 统一清洗为 OHLCV 格式，去除时区，处理空值。
  * **输出**: `data/raw/daily/*.csv` (标准化单资产文件)。

### Phase 3: 质量控制 (Validation)

  * **输入**: `data/raw/daily/*.csv`。
  * **执行者**: `src/data_processor/validator.py`。
  * **动作**: 扫描所有 CSV，检查数据过期 (Staleness)、逻辑错误 (High \< Low)、缺失值 (NaNs)。
  * **输出**: `data/processed/quality_report.csv`。

### Phase 4: 对齐与矩阵化 (Alignment)

  * **输入**: `data/raw/daily/*.csv`。
  * **执行者**: `src/data_loader/alignment.py` (由 `main.py` 调度)。
  * **动作**:
    1.  **资产端 (Tradable)**: 读取 `etf_universe`，提取 `Adj Close`，合并为宽矩阵。剔除全休市日，前值填充 (`ffill`) 修复微小假期差异。生成价格和收益率矩阵。
    2.  **宏观端 (Macro)**: 读取 `macro_universe`，提取 `Close` (Level)。
    3.  **强制对齐**: 将宏观数据的索引强制 Reindex 为资产端的交易日历 (Left Join)。非交易日的宏观数据被丢弃，交易日缺失的宏观数据用前值填充。
  * **输出**:
      * `data/processed/asset_prices.csv`
      * `data/processed/asset_returns.csv`
      * `data/processed/macro_features.csv`

-----

## 3\. 核心数据模式 (Data Schema)

### A. 配置文件 (`etf_universe.csv`)

| Column | Type | Description |
| :--- | :--- | :--- |
| `ticker` | String | 本地文件名索引 (如 `BTC`)，不含特殊字符。 |
| `yf_ticker` | String | 下载源使用的代码 (如 `BTC-USD`, `^VIX`)。 |
| `name` | String | 资产全名。 |
| `asset_class` | String | 资产大类 (Equity, Fixed Income, Alternative)。 |
| `category` | String | 细分类型 (US Treasury, Crypto, Sector)。 |
| `source` | String | 数据源标识 (`yahoo` 或 `fred`)。 |

### B. 原始数据 (`data/raw/daily/{ticker}.csv`)

| Column | Type | Description |
| :--- | :--- | :--- |
| `Date` | DateTime | 索引，格式 YYYY-MM-DD (无时区)。 |
| `Open` | Float | 开盘价。 |
| `High` | Float | 最高价。 |
| `Low` | Float | 最低价。 |
| `Close` | Float | 收盘价。 |
| `Adj Close` | Float | **复权收盘价** (核心字段，含分红)。 |
| `Volume` | Float | 成交量。 |

### C. 价格矩阵 (`data/processed/asset_prices.csv`)

  * **Index**: Date (统一的交易日历)。
  * **Columns**: Tickers (SPY, TLT, GLD...)。
  * **Values**: `Adj Close` 价格。

### D. 收益率矩阵 (`data/processed/asset_returns.csv`)

  * **Index**: Date。
  * **Columns**: Tickers。
  * **Values**: `Pct Change` (日收益率，如 0.01 代表 1%)。

### E. 宏观特征矩阵 (`data/processed/macro_features.csv`)

  * **Index**: Date (与 Asset Prices 完全一致)。
  * **Columns**: Macro Tickers (DGS3MO, VIX...)。
  * **Values**: 指标数值 (Level, 如 4.5 代表 4.5%)。