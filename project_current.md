这是一个非常明智的决定。与其在旧代码上修修补补，不如根据那份严格的 **Grading Rubric（评分标准）** 和 **AQR 论文** 从零构建一个干净、模块化、针对性强的 **“Risk Parity Lab”**。

既然是从零开始，我们的第一步不写代码，而是**定轨（Scope）和搭架子（Architecture）**。

我们将这个项目命名为：**"Replication & Reality Check: Leverage Aversion in the Retail Era"**。

以下是 Step 1 的具体规划：我们要做什么，以及怎么做。

-----

### 一、 我们要做什么？（双轨制目标）

为了拿满 Rubric 的分，我们需要同时运行两条逻辑线：

#### 轨 A：学术复刻 (The Academic Benchmark)

  * **目标**：像素级复刻 Asness, Frazzini, & Pedersen (2012) 的 Figure 1 和 Table 1。
  * **设定**：
      * 假设无摩擦（No Friction）。
      * 假设融资成本 = 无风险利率 ($R_f$)。
      * 杠杆系数 = 常数 $k$ (Ex-post Volatility Matching)。
  * **作用**：拿来做 Baseline，证明你的模型是对的，同时完成 Rubric 里的 "Specification" 和 "Benchmarks"。

#### 轨 B：散户实证 (The Retail Reality)

  * **目标**：回答“散户在 2024 年能赚钱吗？”
  * **设定**：
      * **高融资成本**：$Cost = R_f + Spread$ (e.g., +1.5% \~ 4%)。
      * **动态杠杆**：$L_t$ 基于 *Rolling* Volatility 计算（不能用未来数据）。
      * **杠杆上限**：设为 2x 或 3x（模拟 Margin 账户或 3x ETF 的限制）。
  * **作用**：完成 Rubric 里的 "Constraints"、"Extensions" 和 "Overfitting" 分析。

-----

### 二、 核心数据架构 (The Data Ingredients)

我们采用之前确定的 **"Broad-lite" (广义精简版)** 方案，覆盖 1990-2025。
**数据源**：Yahoo Finance (YF) + FRED (F)。

| 资产类别 | 代表代码 (Ticker) | 数据源 | 关键处理 (Critical Step) |
| :--- | :--- | :--- | :--- |
| **股票** | `^SP500TR` | YF | 必须是 Total Return (含分红) |
| **债券** | `DGS10` | F | **需自行合成** 10Y Constant Maturity Total Return |
| **信用** | `BAMLCC0A0CMTRIV` | F | ICE BofA US Corp Master TR (覆盖 1990+) |
| **商品** | `^SPGSCITR` | YF | S\&P GSCI Total Return |
| **无风险** | `TB3MS` | F | 3-Month T-Bill Rate (除以12转月频) |

-----

### 三、 项目目录结构 (Project Structure)

为了完美匹配教授的 10 个评分项，建议放弃传统的 `src/` 结构，改为**按分析流程**分文件夹。

**建议的新目录结构：**

```text
Risk_Parity_Lab/
├── 01_data_engineering/          # [Rubric: Data]
│   ├── download_raw.py           # 下载 Yahoo/FRED 数据
│   └── bond_pricing_model.py     # 核心：将 Yield 转换为 Total Return 的数学模型
│
├── 02_component_tests/           # [Rubric: Indicators, Signals] - 这里的代码最容易被忽视！
│   ├── test_vol_clustering.py    # 检验：波动率是否具有持续性？(Indicator Test)
│   └── test_risk_contribution.py # 检验：RP 真的能平配风险吗？(Signal Test)
│
├── 03_strategy_construction/     # [Rubric: Rules]
│   ├── strategy_academic.py      # 复刻 AQR (Static k, Rf cost)
│   └── strategy_retail.py        # 散户版 (Dynamic L, Margin cost)
│
├── 04_parameter_analysis/        # [Rubric: Parameter Search, Overfitting]
│   ├── sensitivity_check.py      # 循环测试 Window = [12, 24, 36, 60]
│   └── walk_forward.py           # 滚动窗口分析
│
├── 05_final_production/          # [Rubric: Summary, Extension]
│   ├── run_comparison.py         # 跑出 Academic vs Retail 的对比图
│   └── generate_report_plots.py  # 生成论文用的 Figure 1, 2, 3
│
└── data/                         # 存放 csv
    ├── raw/
    └── processed/
```

-----

