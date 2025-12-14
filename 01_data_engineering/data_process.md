# 3. Data Description

To replicate the results of Asness et al. (2012) while assessing the feasibility for modern retail investors, we constructed a comprehensive dataset covering the period from **January 1990 to Present**. The data frequency is **monthly**, aligned to the last business day of each month.

Our data architecture adopts a **"Dual-Track" approach**:
1.  **Historical Proxy Track (1990–2025)**: Utilizes long-term indices and synthetic models to extend the backtest history to cover multiple economic cycles (e.g., the 2008 Financial Crisis, the 2022 Inflationary Shock).
2.  **Investable ETF Track (2002/2006–2025)**: Utilizes actual ETF price data to validate the strategy's implementability and track real-world trading friction.

## 3.1 Data Sources and Tickers

We sourced raw data from **Yahoo Finance** and the **Federal Reserve Economic Data (FRED)** database. The specific instruments for each asset class are detailed in Table 1 below.

| Asset Class | Historical Proxy (Index/Model) | Source | Investable Asset (ETF) | ETF Start Date |
| :--- | :--- | :--- | :--- | :--- |
| **Global Equities** | S&P 500 Total Return Index (`^SP500TR`) | Yahoo | SPDR S&P 500 ETF (`SPY`) | 1993-01 |
| **Global Bonds** | **Synthetic** 10-Year Treasury Total Return | FRED/Model | iShares 7-10 Year Treasury (`IEF`) | 2002-07 |
| **Credit** | ICE BofA US Corp Master TR Index (`BAMLCC0A0CMTRIV`) | FRED | iShares iBoxx $ Inv Grade Corp (`LQD`) | 2002-07 |
| **Commodities** | S&P GSCI Total Return Index | Investing/Yahoo | iShares S&P GSCI Commodity (`GSG`) | 2006-07 |
| **Risk-Free Rate** | 3-Month Treasury Bill Rate (`TB3MS`) | FRED | N/A | 1954-01 |

## 3.2 Data Construction Methodology

### 3.2.1 Synthetic Treasury Pricing Model
A significant challenge in replicating long-term bond returns is the unavailability of free Total Return indices prior to the ETF era. FRED provides only Constant Maturity Yields (e.g., DGS10). To address this, we developed a **Constant Maturity Par Bond Pricing Engine**:

* **Assumption**: The strategy holds a hypothetical 10-year par bond, rolling it over monthly to maintain a constant duration exposure.
* **Pricing Logic**:
    1.  At month $t-1$, we purchase a newly issued 10-year bond at Par ($P=100$), with a coupon rate equal to the market yield $y_{t-1}$.
    2.  At month $t$, the bond becomes a 9-year 11-month bond. We reprice it using the new market yield $y_t$ via the Present Value (PV) formula for annuities and principal.
    3.  Total Return is calculated as the price change plus the accrued coupon payment.
* **Validation**: This synthetic series shows a correlation of **>0.98** with the `IEF` ETF during the overlapping period (2002–2025), validating its accuracy for the pre-ETF period.

### 3.2.2 Commodities Splicing
Following Asness et al. (2012), we utilize the **S&P GSCI Total Return Index** to capture the broad commodity market (including energy). We splice the historical index data (1990–2006) with the `GSG` ETF (2006–Present) to form a continuous time series for the "Retail Feasibility" analysis.

### 3.2.3 Risk-Free Rate
The Risk-Free Rate ($R_f$) is derived from the **3-Month Treasury Bill Secondary Market Rate (TB3MS)**. We convert the annualized percentage rate into a monthly geometric return using the formula:
$$R_{f, monthly} = (1 + \frac{R_{annual}}{100})^{1/12} - 1$$
This serves as both the baseline for Excess Return calculations and the financing cost for the leverage simulation.

***