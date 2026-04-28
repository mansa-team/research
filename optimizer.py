import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import requests

from sklearn.pipeline import Pipeline

from skfolio.pre_selection import DropCorrelated, DropZeroVariance, SelectKExtremes
from skfolio.optimization import MeanRisk, ObjectiveFunction
from skfolio.prior import EmpiricalPrior
from skfolio.preprocessing import prices_to_returns
from skfolio.moments.covariance import LedoitWolf
from skfolio.measures import PerfMeasure

np.random.seed(42)

selic = pd.DataFrame(requests.get("https://api.bcb.gov.br/dados/serie/bcdata.sgs.4189/dados?formato=json").json())

N_STOCKS = 18
RISK_FREE_RATE = float(selic['valor'].iloc[-1]) / 100

df = pd.read_json("b3_stocks.json")
df = df[(df["VALUE INVESTING SCORE"] > 60) & (df["TICKER"].str.endswith("3"))]

price_data = [
    {"TICKER": row["TICKER"], "DATA": price_entry["DATA"], "PRECO": price_entry["PRECO"]}
    for _, row in df.iterrows() for price_entry in row["COTACAO 10Y AJUSTADA"]
]

price_p = pd.DataFrame(price_data).pivot_table(index="DATA", columns="TICKER", values="PRECO", aggfunc="last")
price_p.index = pd.to_datetime(price_p.index, dayfirst=True)

X_prices_all = price_p.resample("ME").last().ffill().dropna(axis=1)
X_returns_candidates = prices_to_returns(X_prices_all)

all_tickers = X_returns_candidates.columns.tolist()

pre_selection = Pipeline([
    ("drop_zero_var", DropZeroVariance()),
    ("drop_corr", DropCorrelated(threshold=0.67, absolute=True)),
    ("select_k", SelectKExtremes(k=N_STOCKS, measure=PerfMeasure.MEAN, highest=True)),
]).fit(X_returns_candidates)

steps = list(pre_selection.named_steps.values())
selected_tickers = all_tickers
for step in steps:
    selected_tickers = [t for t, m in zip(selected_tickers, step.get_support()) if m]

X_returns_selected = X_returns_candidates[selected_tickers]

scores = df.set_index("TICKER")["VALUE INVESTING SCORE"].reindex(selected_tickers)
w_base = scores.values / scores.sum()

model = MeanRisk(
    objective_function=ObjectiveFunction.MAXIMIZE_UTILITY,
    prior_estimator=EmpiricalPrior(
        covariance_estimator=LedoitWolf()
    ),
    risk_aversion=0.30,
    l2_coef=0.05,
    target_weights=w_base,
    max_weights=100 / N_STOCKS / 100 * 1.5,
    min_weights=100 / N_STOCKS / 100 * 0.5
).fit(X_returns_selected)
weights = model.weights_

results = pd.DataFrame({
    "TICKER": X_returns_selected.columns,
    "WEIGHT": (weights / weights.sum() * 1000).round(2).astype(int)
}).sort_values("WEIGHT", ascending=False)

results["ALLOCATION (%)"] = (results["WEIGHT"] / results["WEIGHT"].sum() * 100).round(4)
print(results[["TICKER", "WEIGHT", "ALLOCATION (%)"]])

weights_series = pd.Series(weights, index=X_returns_selected.columns)
selected_weights = weights_series[selected_tickers].values

X_returns_selected = X_returns_selected[selected_tickers]

generate_graphs = True
if generate_graphs:
    corr_matrix = X_returns_selected.corr()
    plt.figure(figsize=(12, 10))
    sns.heatmap(corr_matrix, cmap="coolwarm", center=0, annot=True, 
                fmt=".2f", xticklabels=True, yticklabels=True,
                cbar_kws={"label": "Correlation"})
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

    print(f"\nreturn: {opt_return * 12 * 100:.2f}%")
    print(f"volatility: {opt_vol * np.sqrt(12) * 100:.2f}%")