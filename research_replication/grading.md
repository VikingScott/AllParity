Based on the detailed grading rubric you provided, I have broken down the requirements into a comprehensive **Project Roadmap**.

This document maps your specific project (AQR Risk Parity Replication) to the specific learning outcomes required by the rubric. This will serve as our checklist moving forward.

***

# 📘 Research Replication Project: Grading Rubric Breakdown
**Target Strategy:** *Leverage Aversion and Risk Parity* (Asness et al., 2012)
**Extension:** Retail Feasibility Analysis (1990–2025)

---

## 1. Specification & Hypotheses
**Rubric Requirement:** Complete summary of hypotheses and tests for all components (theory, indicators, signals, rules).

* **The "Why":** You must state the core economic theory.
    * *Hypothesis:* Lower-risk assets (bonds) offer higher risk-adjusted returns than high-risk assets (stocks) due to leverage aversion.
    * *Prediction:* A leveraged portfolio of safe assets (Risk Parity) should outperform a concentration of risky assets (60/40 or 100% Equities) on a risk-adjusted basis.
* **Action Item:** We will write a clear "Methodology" section defining how we test this (e.g., "If the hypothesis is true, the Sharpe Ratio of RP should be significantly higher than SPY").

## 2. Constraints, Benchmarks, & Objectives
**Rubric Requirement:** Description of constraints, benchmarks, and objectives, and how they affect design.

* **Constraints:**
    * **Leverage Limits:** Retail investors cannot borrow at the Risk-Free rate + 0 spread, nor can they leverage 5x. We will set a constraint (e.g., Max Leverage = 200%).
    * **Transaction Costs:** Real-world friction.
* **Benchmarks:**
    * **60/40 Portfolio:** The industry standard.
    * **Market Cap Weighted:** S&P 500 (`SPY`).
* **Objective:** Maximize Sharpe Ratio (not just Total Return).

## 3. Data Description (✅ 90% Complete)
**Rubric Requirement:** Source citation, data dictionary, code for loading/cleaning.

* **Status:** **Excellent.** You have the "Dual-Track" system (Proxy vs. Investable) and the "Synthetic Treasury Engine."
* **Action Item:** Ensure the `Data Description` section in your report (which I provided earlier) is included. We need to explicitly mention the "splicing" technique for Commodities and the "Par Bond Pricing" for Treasuries.

## 4. Indicators (Component Testing Part 1)
**Rubric Requirement:** Detailed description, math, and **worked tests (separate from backtest)**.

* **What is the Indicator in Risk Parity?**
    * **Volatility ($\sigma$)**: The rolling standard deviation of each asset.
    * **Correlation ($\rho$)**: The relationship between assets.
* **How to Test It Separately?**
    * *Do not just use it.* Check if it has predictive power.
    * *Test:* "Does last month's realized volatility predict next month's volatility?" (Autocorrelation test).
    * *Test:* "Is the volatility estimation stable?" (Plot Rolling Volatility).
    * **Score Booster:** Show a plot of "Estimated Volatility vs. Realized Volatility" to prove your indicator works.

## 5. Signals (Component Testing Part 2)
**Rubric Requirement:** Test signal process separately including forecast error/loss statistics.

* **What is the Signal?**
    * In Risk Parity, the "Signal" is the **Inverse Volatility Weight**.
    * *Implied Prediction:* If I weight assets by $1/\sigma$, their risk contribution will be equal.
* **How to Test It Separately?**
    * Before running the portfolio backtest, calculate the **Ex-Ante Risk Contribution** vs. **Ex-Post Risk Contribution**.
    * *Pass Condition:* Did the signal actually equalize risk? Or did Correlations break the model?
    * **Score Booster:** Calculate the "Risk Parity Error" (how far the actual risk distribution deviated from the target 25%/25%/25%/25%).

## 6. Rules
**Rubric Requirement:** Entry/exit rules, rationale. Test with/without optional rules.

* **Core Rules:**
    * **Rebalancing Frequency:** Monthly (End of Month).
    * **Target Volatility:** Scale the whole portfolio to e.g., 10% Volatility.
* **Optional Rules (The "With/Without" Test):**
    * *Test A:* Pure Risk Parity (Naïve).
    * *Test B:* Risk Parity with a **Leverage Cap** (e.g., max 2.0x).
    * *Test C:* Risk Parity with **Transaction Costs**.
* **Rationale:** Show how adding the "Leverage Cap" rule protects the retail investor during 2022 (Bond crash).

## 7. Parameter Search & Optimization
**Rubric Requirement:** Describe free parameters, search process, and optimization methodology.

* **Free Parameters:**
    * **Lookback Window:** How many months do we use to calculate Volatility? (e.g., 12 months vs. 36 months vs. 60 months).
* **The Test:**
    * Run a "Sensitivity Analysis" (Grid Search).
    * Does a 12-month lookback perform better than a 36-month lookback?
    * *Chart:* X-axis = Lookback Window, Y-axis = Sharpe Ratio.

## 8. Walk Forward Analysis
**Rubric Requirement:** Apply walk forward analysis, discuss objective function.

* **Concept:** Instead of picking the best parameter for the whole 30 years (hindsight bias), we optimize as we go.
* **Implementation:**
    * Year 2000: Optimize lookback using 1990-1999 data.
    * Year 2001: Optimize using 1990-2000 data.
* **Reality Check:** For Vanilla Risk Parity, Walk Forward is often overkill. We might argue that a *fixed* parameter (e.g., 3-year rolling window) is robust enough, but running the analysis proves you know how to do it.

## 9. Overfitting Assessment
**Rubric Requirement:** In/Out of sample performance, probability of overfitting.

* **The Trap:** Did we tweak the model just to make the chart look good?
* **The Defense:**
    * Compare **In-Sample** (1990-2010, the original paper period) vs. **Out-of-Sample** (2011-2025).
    * If the strategy collapses after 2012 (when the paper was published), it was overfitted.
    * *Note:* Risk Parity struggled in 2022. Showing this honestly is better than hiding it. It proves you aren't overfitting.

## 10. Extensions and Conclusion (Distinction Point)
**Rubric Requirement:** Recent data, similar techniques, sophisticated models. Future research.

* **Extension 1 (Time):** Extending data from 2010 to 2025 (The "Inflation Stress Test").
* **Extension 2 (Instrument):** Switching from Theoretical Indices to Tradeable ETFs (`SPY`, `IEF`, `LQD`, `GSG`).
* **Conclusion:** Is Risk Parity dead after 2022? Or is it still a viable long-term strategy for retail investors?

***
