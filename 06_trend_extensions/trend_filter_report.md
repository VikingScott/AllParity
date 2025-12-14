Trend Filtering Methodology (Cash-Reserve Approach)

In our implementation, we adopt a "Cash-Reserve" trend filtering mechanism rather than a renormalized approach. When an asset's trend turns negative (Price < MA10), its allocation is reduced to zero, and the released capital is effectively allocated to the risk-free asset (Cash).

We explicitly choose not to reallocate (renormalize) this capital to the remaining risk-on assets. This design choice ensures that:

Diversification Integrity: We avoid increasing concentration risk in a single asset class (e.g., Commodities) during simultaneous bond/equity drawdowns.

Risk Reduction: The strategy acts as a true "volatility dampener" during crisis periods, prioritizing capital preservation over aggressive return seeking.

Financing Efficiency: Leverage and borrowing costs are calculated based on the actual gross exposure. During risk-off periods, the effective leverage decreases, automatically reducing the financing drag on the portfolio.