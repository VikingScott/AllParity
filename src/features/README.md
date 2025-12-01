# 🏭 Feature Engineering Layer (特征工程层)

## 1. 核心职责 (Responsibilities)
Feature Layer 是整个量化系统的“数学计算中心”。它的任务是把原始的 **价格数据 (Price Data)** 转换为可供策略使用的 **信号/因子数据 (Signals/Factors)**。

**它只负责“算”，不负责“选”。**
* 它不知道哪个策略会用 MA20，哪个用 MA200，所以它把这两个都算出来存好。
* 它不知道今天要不要买，它只输出 `1.0` (Bullish) 或 `0.0` (Bearish)。

## 2. 输入与输出 (I/O)

### 输入 (Input)
* **来源**: `src/core/DataLoader.load_prices()`
* **格式**: `DataFrame (Date x Ticker)`，内容为 Adj Close 价格。
* **数据清洗**: 由 DataLoader 保证索引是标准 Timestamp。

### 输出 (Output)
* **目标**: `data/features/` 目录下的 CSV 文件。
* **格式**: 
    * 文件名规范：`signal_{type}_{param}.csv` (例如 `signal_ma_200.csv`)
    * 内容：`Date x Ticker` 的矩阵。
    * 值域：通常为 `1.0` (True/Long), `0.0` (False/Cash), `-1.0` (Short)。
* **时序约束**: 
    * **必须 Shift(1)**：T 日计算出的指标，必须下移到 T+1 日。
    * **含义**: "T+1 日早晨醒来，我看到昨晚收盘价触发了信号。"

## 3. 参数处理边界 (Parameter Boundary)

| 参数类型 | 处理位置 | 例子 |
| :--- | :--- | :--- |
| **数学参数** | **Feature Layer** | 均线窗口 (20/200), RSI 周期 (14), 波动率窗口 |
| **执行参数** | **Backtest Config** | 交易手续费 (5bps), 调仓频率 (Monthly) |
| **逻辑参数** | **Strategy Layer** | 比如“只有当 MA20 > MA200 时才买” (这是策略逻辑) |

---