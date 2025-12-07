**`ARCHITECTURE_AND_WORKFLOW.md`**。

-----

# 🏗️ AllParity 量化系统架构与工作流详解

本文档详细描述了 AllParity 系统的内部构造、数据流转逻辑以及各个模块的职责边界。本系统基于 **Data-Oriented Programming (DOP)** 原则设计，强调数据与逻辑的分离，以及模块间的松耦合。

-----

## 1\. 系统全貌 (System Overview)

### 核心设计哲学

1.  **配置代码化 (Config-as-Code)**：所有的策略组合、回测参数（手续费、频率）都在配置文件中定义，而非硬编码在逻辑中。
2.  **依赖注入 (Dependency Injection)**：底层逻辑模块（如 Strategy, Engine）不直接读取硬盘文件，而是通过参数接收数据（DataFrame），方便测试和复用。
3.  **V字型数据流**：从原始数据 -\> 清洗对齐 -\> 特征计算 -\> 策略回测 -\> 绩效归因，单向流动，互不干扰。

### 目录结构图解

```text
AllParity/
├── config/                 # [大脑] 控制我们要测什么
│   ├── scenarios.py        # 🔥 核心：定义策略组合、基准、回测参数
│   ├── etf_bundles.py      # 预设资产包 (如 "US_Tech", "Global_Value")
│   ├── etf_universe.csv    # 资产清单 (Ticker, Name, Category)
│   └── macro_universe.csv  # 宏观指标清单
│
├── data/                   # [仓库] 存放所有数据 (Git Ignore)
│   ├── raw/daily/          # 原始下载数据 (每资产一个CSV)
│   ├── processed/          # 清洗后的宽矩阵 (Prices, Returns)
│   └── features/           # 预计算的信号因子 (如 signal_ma_200.csv)
│
├── src/                    # [车间] 核心逻辑代码库
│   ├── core/               # 基础设施 (数据IO标准)
│   ├── data_loader/        # ETL工具 (下载、清洗)
│   ├── features/           # 数学计算 (均线、波动率逻辑)
│   ├── strategy/           # 交易决策 (根据信号定仓位)
│   ├── backtester/         # 撮合引擎 (资金流转、摩擦成本)
│   └── analysis/           # 绩效分析 (指标计算、报表生成)
│
└── scripts/                # [控制台] 用户操作入口
    ├── update_data.py      # 一键更新数据 & 特征
    ├── run_research.py     # 运行回测 & 生成报告
    ├── build_features.py   # 单独重算特征
    └── visualize_results.py# 画图工具
```

-----

## 2\. 数据流向详解 (Data Pipeline)

整个系统的数据流是一个标准的 ETL + 分析流程。

### Phase 1: 数据准备 (Data Ingestion)

  * **目标**：将互联网上的杂乱数据转化为本地标准化的矩阵。
  * **涉及文件**：`scripts/update_data.py` -\> `src/data_loader/*`
  * **流程**：
    1.  **读取配置**：从 `config/etf_universe.csv` 获取目标资产列表。
    2.  **并发下载**：`Downloader` 使用多线程从 Yahoo Finance/FRED 下载 OHLCV 数据，保存到 `data/raw/daily/`。
    3.  **清洗对齐**：`Aligner` 读取所有 Raw CSV，剔除休市日，对齐时间轴，生成两个核心矩阵：
          * `data/processed/asset_prices.csv` (Adj Close)
          * `data/processed/asset_returns.csv` (Pct Change)

### Phase 2: 特征工程 (Feature Engineering)

  * **目标**：预先计算耗时的数学指标，避免回测时重复计算。
  * **涉及文件**：`scripts/build_features.py` -\> `src/features/*`
  * **流程**：
    1.  读取 `asset_prices.csv`。
    2.  调用 `TrendFeatures` 计算逻辑（如 MA200）。
    3.  **防未来函数处理**：对计算结果进行 `.shift(1)`，确保 T 日的信号是基于 T-1 日收盘价生成的。
    4.  **持久化**：将 0/1 信号矩阵保存为 `data/features/signal_ma_200.csv`。

### Phase 3: 策略回测 (Backtesting)

  * **目标**：模拟交易，生成净值曲线。
  * **涉及文件**：`scripts/run_research.py` -\> `src/strategy/`, `src/backtester/`
  * **流程**：
    1.  **加载阶段**：`run_research.py` 一次性加载 `asset_returns.csv` 和 `signal_ma_200.csv` 到内存。
    2.  **组装阶段**：根据 `config/scenarios.py` 的定义，将信号数据注入到 `SimpleMAStrategy` 实例中。
    3.  **执行阶段**：`BacktestEngine` 按日循环：
          * 询问策略目标仓位。
          * 检查是否触发调仓（基于时间或基于漂移阈值）。
          * 计算换手率，扣除手续费和滑点。
          * 更新每日净值和持仓。

### Phase 4: 绩效归因 (Analysis & Reporting)

  * **目标**：将冷冰冰的净值数据转化为可视化的报表。
  * **涉及文件**：`src/analysis/reporting.py`
  * **流程**：
    1.  接收引擎输出的日收益率序列。
    2.  **静态指标**：计算 CAGR, Sharpe, MaxDD。
    3.  **滚动分析**：计算 Rolling Sharpe (3年), Rolling MaxDD (1周/1月/1年)。
    4.  **输出**：在 `reports/data/batch_xxx/` 下生成全套 CSV（年度对比表、月度矩阵表、滚动分析表）。

-----

## 3\. 核心文件指引 (Module Reference)

### 📂 Config (配置层)

  * **`config/scenarios.py`**：**[最重要]** 这是你的实验台。在这里定义你要跑哪些策略、对比什么基准、使用多少手续费。
  * **`config/etf_universe.csv`**：资产数据库。定义了所有可用的 ETF 及其分类。

### 🧠 Src (逻辑层)

#### `src/core/` (地基)

  * **`data.py`**：**数据网关**。负责统一读取 CSV，并强制清洗日期索引（转换为无时区 Timestamp），防止回测时因索引格式不同导致数据匹配失败。
  * **`utils.py`**：通用工具。如“自动寻找多个策略的最大公共时间窗口”。

#### `src/features/` (特征工厂)

  * **`trend.py`**：**纯数学逻辑**。接收价格 DataFrame，计算均线、突破信号，处理 NaN 和 Shift。不涉及任何 IO 操作。

#### `src/strategy/` (指挥官)

  * **`base.py`**：接口契约。规定所有策略必须有 `get_weights(date)` 方法。
  * **`simple_ma.py`**：趋势策略实现。**不计算均线**，而是读取外部传入的信号 DataFrame，根据日期返回 `{'SPY': 0.5, 'TLT': 0.5}`。
  * **`buy_hold.py`**：定投策略实现。返回固定的权重字典。
  * **`composite.py`**：组合策略。可以将 "50% 趋势策略 + 50% 定投策略" 打包成一个新的策略对象。

#### `src/backtester/` (流水线)

  * **`config.py`**：定义回测环境参数的数据类（`transaction_cost`, `rebalance_freq`）。
  * **`engine.py`**：**纯撮合逻辑**。接收全量收益率数据，按日模拟资金流转。处理复杂的“权重漂移”和“再平衡触发机制”。

#### `src/analysis/` (分析师)

  * **`metrics.py`**：数学公式库（CAGR, Volatility, Sharpe 等）。
  * **`rolling.py`**：时间序列分析库。处理滚动窗口计算。
  * **`reporting.py`**：报表生成器。负责调用上述两个库，并将结果格式化保存为 CSV。

### 📜 Scripts (操作入口)

  * **`scripts/update_data.py`**：**[日常使用]** 全自动流水线：下载 -\> 清洗 -\> 对齐 -\> 计算特征。
  * **`scripts/run_research.py`**：**[核心入口]** 读取 `scenarios.py`，运行回测，生成所有报表。
  * **`scripts/build_features.py`**：独立重算特征（当你修改了均线算法或添加了新指标时用）。
  * **`scripts/scan_market.py`**：市场扫描仪。不跑策略，只看最近一年谁涨得最好，谁回撤最大。
  * **`scripts/visualize_results.py`**：画图工具。读取最近一次的回测结果，画出净值图和水下回撤图。