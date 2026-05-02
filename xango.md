# Xangô: Mansa's Alpha Scoring Algorithm

In classical quantitative finance, the search for "Alpha" (excess return) is often hindered by the Growth-Volatility Paradox. Conventional screening methods, such as CAGR (Compound Annual Growth Rate) or simple average ROIC, are "point-to-point" measurements. They measure the destination but ignore the journey. This lack of granularity often leads to the inclusion of "Wobbly Growth" stocks: companies that show high returns over a decade but achieve them through erratic, boom-and-bust cycles that indicate high structural risk.

Most retail and institutional algorithms fail to implement a true "Quality Engine" for two reasons:

- **Scale-Normalization Complexity**: It is mathematically difficult to compare the growth of a micro-cap company with a mega-cap blue chip without introducing "MinMax" distortions that erase volatility data.
- **Linear Regression Bias**: Standard volatility metrics (Standard Deviation) punish all price movement equally. They cannot distinguish between "Good Volatility" (steady, fast upward growth) and "Bad Volatility" (unpredictable deviation from a trend).

The Xangô Algorithm solves this by utilizing a modular, non-compensatory engine architecture. By treating Growth, Risk, and Market Constraints as independent stochastic kernels linked by multiplication rather than addition, Xangô ensures that a failure in structural quality cannot be "averaged out" by high historical returns.

### The Global Score Function

The final score is a bounded product of three distinct engines. This multiplicative structure acts as a logical gate; if any engine returns a near-zero value, the asset is mathematically disqualified from the MUSA ecosystem.

$$
f(P, L, c) = \min(100, \max(0, \Phi(P) \cdot \Omega(P) \cdot \Lambda(L, c)))
$$

Where:

- $P$: 10-year profit vector $\{p_1, p_2, \dots, p_{10}\}$
- $L$: Average daily liquidity
- $c$: Ticker class identifier (Suffix)

### Fundamental Engine: $\Phi(P)$

The Fundamental Engine evaluates the "Intrinsic Velocity" of the business. It eliminates size-bias by normalizing the regression slope against the company's average earnings.

$$
\Phi(P) = 0.45 \cdot S_{growth}(P) + 0.55 \cdot S_{cons}(P)
$$

#### Relative Growth ($S_{growth}$)

Measures the OLS (Ordinary Least Squares) regression slope ($\beta$) normalized by mean profit ($\mu_p$), capped at a 7% relative growth threshold:

$$
S_{growth}(P) = \min\left(100, \max\left(0, \frac{\beta}{0.07 \mu_p} \cdot 100\right)\right)
$$

#### Consistency ($S_{cons}$)

A weighted metric assessing the reliability of capital generation:

$$
S_{cons}(P) = 60 \left(\frac{1}{10} \sum \mathbf{1}_{\{p_t > 0\}}\right) + 40\left(\frac{1}{9} \sum \mathbf{1}_{\{p_t > p_{t-1}\}}\right)
$$

### Risk-Quality Engine: $\Omega(P)$

The Risk Engine is the "Surgical Filter." It utilizes the CV-RMSE (Coefficient of Variation of the Root Mean Square Error) to measure "Trend Adherence."

$$
\Omega(P) = M_{vol}(P) \cdot M_{DD}(P)
$$

#### Volatility Multiplier ($M_{vol}$)

Unlike standard deviation, $M_{vol}$ only penalizes the residuals of the trendline. If a stock grows perfectly linearly, it receives no penalty, regardless of how "fast" it moves.

$$
M_{vol}(P) = \max\left(0.3, \;\; 1 - 2 \cdot \max\left(0, \frac{RMSE}{\mu_p} - 0.15\right)\right)
$$

#### Recovery-Aware Drawdown ($M_{DD}$)

This factor rewards "Anti-fragility." While it punishes large profit drops, it includes a 75% forgiveness factor for companies that demonstrate the resilience to recover to $\ge 90\%$ of their historical peak ($p_{max}$).

### Constraint Engine: $\Lambda(L, c)$

The Constraint Engine ensures that the theoretical Alpha identified by $\Phi$ and $\Omega$ can be realized in the physical market. It adjusts for "Slippage Risk" (Liquidity) and "Governance Risk" (Ticker Class).

$$
\Lambda(L, c) = M_{liq}(L) \cdot M_{class}(c)
$$

#### Liquidity Damping ($M_{liq}$)

Assets must meet a minimum average daily liquidity of R$ 10,000,000. For assets below this threshold, a square-root decay function is applied to simulate the increased cost of entry and exit:

$$
M_{liq}(L) = \begin{cases}
1.0 & \text{if } L \ge 10^7 \\
\max\left(0.5, \sqrt{\frac{L}{10^7}}\right) & \text{if } L < 10^7
\end{cases}
$$

#### Governance and Class Factor ($M_{class}$)

In the Brazilian market (B3), ticker suffixes represent different voting rights and tag-along protections. Xangô prioritizes Common Shares (Suffix 3) to align with best-practice corporate governance:

$$
M_{class}(c) = \begin{cases}
1.0 & \text{if } c = 3 \\
0.75 & \text{otherwise}
\end{cases}
$$

## License
Mansa Team's MODIFIED GPL 3.0 License. See LICENSE for details.