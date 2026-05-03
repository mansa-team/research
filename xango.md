# Xangô: Mansa's Alpha Scoring Algorithm

In classical quantitative finance, the search for "Alpha" (excess return) is often hindered by the Growth-Volatility Paradox. Conventional screening methods, such as CAGR (Compound Annual Growth Rate) or simple average ROIC, are "point-to-point" measurements. They measure the destination but ignore the journey. This lack of granularity often leads to the inclusion of "Wobbly Growth" stocks: companies that show high returns over a decade but achieve them through erratic, boom-and-bust cycles that indicate high structural risk.

The Xangô Algorithm solves this by utilizing a modular, non-compensatory engine architecture. By treating Growth, Risk, and Market Constraints as independent stochastic kernels linked by multiplication rather than addition, Xangô ensures that a failure in structural quality cannot be "averaged out" by high historical returns.

---

## 1. Introduction

Most retail and institutional algorithms fail to implement a true "Quality Engine" for two reasons:

- **Scale-Normalization Complexity**: It is mathematically difficult to compare the growth of a micro-cap company with a mega-cap blue chip without introducing "MinMax" distortions that erase volatility data.
- **Linear Regression Bias**: Standard volatility metrics (Standard Deviation) punish all price movement equally. They cannot distinguish between "Good Volatility" (steady, fast upward growth) and "Bad Volatility" (unpredictable deviation from a trend).

This paper presents Xangô, a modular scoring system designed specifically for the Brazilian B3 stock market that addresses these limitations through:

1. Scale-invariant metrics using normalized residuals
2. Recovery-aware drawdown forgiveness
3. Non-compensatory multiplicative scoring
4. Simplified parameterization (11 configurable parameters)

---

## 2. The Global Score Function

The final score is a bounded product of four distinct engines. This multiplicative structure acts as a logical gate; if any engine returns a near-zero value, the asset is mathematically disqualified from the portfolio.

$$f(P, L, c) = \min(100, \max(0, \Phi(P) \cdot \Omega(P) \cdot \Lambda(L, c) \cdot M_{profit}(P)))$$

**Where:**

- $P$: 10-year profit vector $\{p_1, p_2, \dots, p_{10}\}$ (ordered from oldest to newest: $p_1 = 2016$, $p_{10} = 2025$)
- $L$: Average daily liquidity (R$)
- $c$: Ticker class identifier (Suffix: 3 = common shares, other = preferred/unit)

---

## 3. Profit Quality Gate: $M_{profit}(P)$

Before any calculation, the algorithm applies a penalty to stocks with any negative annual profit:

$$M_{profit}(P) = \begin{cases}
\alpha_{profit} & \text{if } \exists \; p_t \leq 0 \\
1.0 & \text{otherwise}
\end{cases}$$

Where $\alpha_{profit}$ is the profit penalty multiplier (default: 0.5).

**Rationale:** Companies with any annual loss in the analyzed period demonstrate structural weakness. This penalty ensures that erratic or negative earnings are reflected in the final score regardless of other positive metrics.

---

## 4. Fundamental Engine: $\Phi(P)$

The Fundamental Engine evaluates the "Intrinsic Velocity" of the business. It eliminates size-bias by normalizing the regression slope against the company's mean earnings.

$$\Phi(P) = \omega_{growth} \cdot S_{growth}(P) + (1 - \omega_{growth}) \cdot S_{cons}(P)$$

Where $\omega_{growth}$ is the growth weight (consistency weight is derived as $1 - \omega_{growth}$).

**Default:** $\omega_{growth} = 0.75$ (consistency weight = 0.25)

### 4.1 Relative Growth ($S_{growth}$)

Measures the OLS (Ordinary Least Squares) regression slope ($\beta$) normalized by mean profit ($\mu_p$), capped at a configurable relative growth threshold ($T_{growth}$). Uses the maximum of both linear and log-linear (CAGR) approaches to capture both absolute growth and compound velocity:

$$S_{growth}(P) = \min\left(100, \max\left(0, \frac{\max(\beta / \mu_p, \; e^{\hat{\beta}} - 1)}{T_{growth}} \cdot 100\right)\right)$$

**Default parameter:**
- $T_{growth} = 0.07$ (7% threshold)

Where $\hat{\beta}$ is the slope from regressing $\ln(P)$ on time.

### 4.2 Consistency ($S_{cons}$)

A weighted metric assessing the reliability of capital generation with fixed internal weights:

$$S_{cons}(P) = 60 \cdot \left(\frac{1}{n} \sum \mathbf{1}_{\{p_t > 0\}}\right) + 40 \cdot \left(\frac{1}{n-1} \sum \mathbf{1}_{\{p_t > p_{t-1}\}}\right)$$

The 60/40 ratio represents the relative importance of profit positivity vs. year-over-year growth consistency.

---

## 5. Risk-Quality Engine: $\Omega(P)$

The Risk Engine is the "Surgical Filter." It utilizes the CV-RMSE (Coefficient of Variation of the Root Mean Square Error) to measure "Trend Adherence."

$$\Omega(P) = M_{vol}(P) \cdot M_{DD}(P)$$

### 5.1 Volatility Multiplier ($M_{vol}$)

Unlike standard deviation, $M_{vol}$ only penalizes the residuals from the linear trend. If a stock grows perfectly linearly, it receives no penalty, regardless of how "fast" it moves. The CV-RMSE is calculated using raw residuals normalized by mean profit for scale-invariance while capturing all oscillation:

$$M_{vol}(P) = \max\left(F_{vol}, \;\; 1 - 2 \cdot \max\left(0, \frac{RMSE}{\mu_p} - T_{cv}\right)\right)$$

**Default parameters:**
- $T_{cv} = 0.16$ (CV-RMSE threshold)
- $F_{vol} = 0.40$ (volatility floor)

Where $RMSE = \sqrt{\frac{1}{n} \sum (p_t - \hat{p}_t)^2}$ is the root mean square error from the linear trend.

### 5.2 Recovery-Aware Drawdown ($M_{DD}$)

This factor rewards "Anti-fragility." It uses continuous interpolation with a single threshold to handle mature companies that stabilize below their all-time peak:

$$M_{DD}(P) = \max\left(F_{dd}, \;\; 1 - \hat{DD}_{effective}\right)$$

**Default parameters:**
- $F_{dd} = 0.60$ (drawdown floor)
- $T_{recovery} = 0.45$ (recovery threshold for full forgiveness)

The effective drawdown $\hat{DD}_{effective}$ uses a derived lower threshold $T_{low} = T_{recovery} \cdot 0.55$:

$$\hat{DD}_{effective} = \begin{cases}
0.25 \cdot DD_{max} & \text{if } \rho \geq T_{recovery} \\
\left(1 - 0.6 \cdot \frac{\rho - T_{low}}{T_{recovery} - T_{low}}\right) \cdot DD_{max} & \text{if } T_{low} \leq \rho < T_{recovery} \\
\frac{\rho}{T_{low}} \cdot DD_{max} & \text{if } \rho < T_{low}
\end{cases}$$

With $\rho = p_{current} / p_{max}$ being the recovery ratio and $DD_{max} = 1 - \min(P / \max(\text{cummax}(P), 1))$.

---

## 6. Constraint Engine: $\Lambda(L, c)$

The Constraint Engine ensures that the theoretical Alpha identified by $\Phi$ and $\Omega$ can be realized in the physical market. It adjusts for "Slippage Risk" (Liquidity) and "Governance Risk" (Ticker Class).

$$\Lambda(L, c) = M_{liq}(L) \cdot M_{class}(c)$$

### 6.1 Liquidity Damping ($M_{liq}$)

Assets must meet a minimum average daily liquidity threshold ($T_{liq}$). For assets below this threshold, a square-root decay function simulates the increased cost of entry and exit:

$$M_{liq}(L) = \begin{cases}
1.0 & \text{if } L \geq T_{liq} \\
\max\left(F_{liq}, \sqrt{\frac{L}{T_{liq}}}\right) & \text{if } L < T_{liq}
\end{cases}$$

**Default parameters:**
- $T_{liq} = 10,000,000$ (R$ 10 million)
- $F_{liq} = 0.5$ (liquidity floor)

### 6.2 Governance and Class Factor ($M_{class}$)

In the Brazilian market (B3), ticker suffixes represent different voting rights and tag-along protections. Xangô prioritizes Common Shares (Suffix 3) to align with best-practice corporate governance:

$$M_{class}(c) = \begin{cases}
1.0 & \text{if } c = 3 \\
\alpha_{class} & \text{otherwise}
\end{cases}$$

Where $\alpha_{class} = 0.75$ (default class multiplier for non-common shares).

---

## 7. Simplified Configuration Parameters

The algorithm uses a reduced parameter set of **11 configurable parameters**:

### 7.1 Data Requirements

| Parameter | Default | Description |
|-----------|---------|-------------|
| `MIN_YEARS` | 10 | Minimum years of data required |

### 7.2 Growth & Consistency

| Parameter | Default | Description |
|-----------|---------|-------------|
| `GROWTH_WEIGHT` | 0.75 | Weight for growth (consistency = 1 - growth) |
| `GROWTH_THRESHOLD` | 0.07 | Growth threshold (7%) |

### 7.3 Volatility

| Parameter | Default | Description |
|-----------|---------|-------------|
| `VOLATILITY_THRESHOLD` | 0.16 | CV-RMSE threshold |
| `VOLATILITY_FLOOR` | 0.40 | Minimum volatility multiplier |

### 7.4 Drawdown

| Parameter | Default | Description |
|-----------|---------|-------------|
| `RECOVERY_THRESHOLD` | 0.45 | Recovery ratio for full forgiveness |
| `DRAWDOWN_FLOOR` | 0.60 | Minimum drawdown multiplier |

---

## Variable Glossary

| Symbol | Description |
|--------|-------------|
| $P$ | Profit vector |
| $\beta$ | Linear regression slope |
| $\hat{\beta}$ | Log-linear regression slope |
| $\mu_p$ | Mean profit |
| $RMSE$ | Root mean square error |
| $\rho$ | Recovery ratio |
| $DD_{max}$ | Maximum drawdown |
| $\omega_{growth}$ | Growth weight parameter |
| $T_{growth}$ | Growth threshold parameter |
| $T_{cv}$ | CV-RMSE threshold parameter |
| $F_{vol}$ | Volatility floor parameter |
| $T_{recovery}$ | Recovery threshold parameter |
| $F_{dd}$ | Drawdown floor parameter |
| $T_{liq}$ | Liquidity threshold parameter |
| $F_{liq}$ | Liquidity floor parameter |
| $\alpha_{profit}$ | Profit penalty parameter |
| $\alpha_{class}$ | Class penalty parameter |

---

## License

Mansa Team's MODIFIED GPL 3.0 License. See LICENSE for details.