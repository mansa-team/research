import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import requests

from skfolio.optimization import MeanRisk, ObjectiveFunction
from skfolio.prior import EmpiricalPrior
from skfolio.preprocessing import prices_to_returns
from skfolio.moments.covariance import LedoitWolf

np.random.seed(42)

selic = pd.DataFrame(requests.get("https://api.bcb.gov.br/dados/serie/bcdata.sgs.4189/dados?formato=json").json())

N_STOCKS = 18
K_MULTIPLIER = 3
RISK_FREE_RATE = float(selic['valor'].iloc[-1]) / 100

df = pd.read_json("b3_stocks.json")
df = df[(df["VALUE INVESTING SCORE"] > 60) & (df["TICKER"].str.endswith("3"))]

price_data = [
    {"TICKER": row["TICKER"], "DATA": price_entry["DATA"], "PRECO": price_entry["PRECO"]}
    for _, row in df.iterrows() for price_entry in row["COTACAO 10Y AJUSTADA"]
]
price_p = pd.DataFrame(price_data).pivot_table(index="DATA", columns="TICKER", values="PRECO", aggfunc="last")
price_p.index = pd.to_datetime(price_p.index, dayfirst=True)

# picks the top scoring stocks (no corr based)
# need to update the file to be used after the picker as been made so i can optimize the weights arround it with a proper weight balancing model (hierarchical risk parity)
K = K_MULTIPLIER * N_STOCKS
top_k_tickers = df.sort_values("VALUE INVESTING SCORE", ascending=False).head(K)["TICKER"]
X_prices = price_p[top_k_tickers].resample("ME").last().ffill().dropna(axis=1)
X_returns = prices_to_returns(X_prices)

scores = df.set_index("TICKER")["VALUE INVESTING SCORE"].reindex(X_returns.columns)
w_base = scores.values / scores.sum()

model = MeanRisk(
    objective_function=ObjectiveFunction.MAXIMIZE_UTILITY,
    prior_estimator=EmpiricalPrior(
        covariance_estimator=LedoitWolf()
    ),
    risk_aversion=0.35,
    l2_coef=0.01,
    target_weights=w_base,
    min_weights=0.02,
    max_weights=0.06,
)
model.fit(X_returns)
weights = model.weights_

results = pd.DataFrame({
    "TICKER": X_returns.columns,
    "WEIGHT": (weights / weights.sum() * 1000).astype(int)
}).sort_values("WEIGHT", ascending=False).head(N_STOCKS)

results["ALLOCATION (%)"] = (results["WEIGHT"] / results["WEIGHT"].sum() * 100).round(4)
print(results[["TICKER", "WEIGHT", "ALLOCATION (%)"]])

selected_tickers = results["TICKER"].tolist()
weights_series = pd.Series(weights, index=X_returns.columns)
selected_weights = weights_series[selected_tickers].values

X_returns_selected = X_returns[selected_tickers]

generate_graphs = True
if generate_graphs:
    corr_matrix = X_returns_selected.corr()
    plt.figure(figsize=(12, 10))
    sns.heatmap(corr_matrix, cmap="coolwarm", center=0, annot=True, 
                fmt=".2f", xticklabels=True, yticklabels=True,
                cbar_kws={"label": "Correlation"})
    plt.title("Stock Correlation Heatmap", fontsize=14)
    plt.tight_layout()
    plt.savefig("corr_heatmap.png", dpi=150)
    plt.close()

    n_portfolios = 1000
    m = len(selected_tickers)
    random_weights = np.random.dirichlet(np.ones(m), n_portfolios)

    mu_returns = X_returns_selected.mean().values
    lw = LedoitWolf().fit(X_returns_selected)
    Sigma = lw.covariance_

    portfolio_returns = random_weights @ mu_returns
    portfolio_vols = np.array([np.sqrt(w @ Sigma @ w) for w in random_weights])

    opt_return = selected_weights @ mu_returns
    opt_vol = np.sqrt(selected_weights @ Sigma @ selected_weights)

    min_var_idx = np.argmin(portfolio_vols)
    min_var_vol = portfolio_vols[min_var_idx]
    min_var_return = portfolio_returns[min_var_idx]

    max_sharpe_idx = np.argmax((portfolio_returns - RISK_FREE_RATE) / portfolio_vols)
    max_sharpe_vol = portfolio_vols[max_sharpe_idx]
    max_sharpe_return = portfolio_returns[max_sharpe_idx]

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.scatter(portfolio_vols * np.sqrt(12) * 100, portfolio_returns * 12 * 100, 
               alpha=0.5, s=20, label="Random Portfolios", c="gray")
    ax.scatter(min_var_vol * np.sqrt(12) * 100, min_var_return * 12 * 100, 
               marker="*", s=200, c="green", label="Min Variance", zorder=5)
    ax.scatter(max_sharpe_vol * np.sqrt(12) * 100, max_sharpe_return * 12 * 100, 
               marker="*", s=200, c="blue", label="Max Sharpe", zorder=5)
    ax.scatter(opt_vol * np.sqrt(12) * 100, opt_return * 12 * 100, 
               marker="*", s=200, c="red", label="Chosen Portfolio", zorder=5)
    ax.set_xlabel("Annualized Volatility (%)")
    ax.set_ylabel("Annualized Return (%)")
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig("efficient_frontier.png", dpi=150)
    plt.close()

    print(f"return: {opt_return * 12 * 100:.2f}%")
    print(f"volatility: {opt_vol * np.sqrt(12) * 100:.2f}%")