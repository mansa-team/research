import pandas as pd
import numpy as np
import requests
import asyncio
import time
from datetime import datetime

start_time = time.time()

TICKERS = [
    "WEGE3", "RADL3", "EGIE3", "ITUB3", "LREN3", "BBAS3", "VALE3", "EQTL3", "RENT3",
    "FLRY3", "LEVE3", "B3SA3", "PSSA3", "TOTS3", "BBSE3", "TAEE11", "FRAS3",
    "SAPR3", "BRAP4", "CPFE3", "CSUD3", "SLCE3", "ODPV3", "PNVL3", "CMIG3",
    "MDIA3", "CXSE3", "GRND3", "PRIO3", "SMTO3", "UGPA3", "SBSP3", "ABCB4",
    "TIMS3", "VIVT3", "SANB11", "CSMG3", "YDUQ3", "VBBR3", "HYPE3", "VIVA3",
    "GOAU4", "RANI3", "SUZB3", "BRFS3", "INTB3", "TUPY3", "EMBR3", "ALUP11",
    "MGLU3", "AURE3", "KEPL3", "CSAN3", "UNIP6", "TRPL4", "BPAC11", "CSNA3",
    "KLBN11", "DXCO3", "CYRE3", "DIRR3", "ENGI11", "BRKM5", "MYPK3", "OIBR3",
    "TASA4", "PETZ3", "CASH3", "RAIZ4", "LIGT3", "GOLL4", "AZUL4", "USIM5",
    "JALL3", "NGRD3", "AERI3", "BHIA3", "HBSA3"
]

cache = {}

def fetch(url):
    if url in cache:
        return cache.setdefault(url, requests.get(url).json())
    return requests.get(url).json()

def get_data(tickers):
    prefixes = list({t[:4] for t in tickers})

    hist = [fetch(f"http://localhost:3200/stocks/historical?search={t}&fields=LUCRO LIQUIDO") for t in tickers]
    fund = [fetch(f"http://localhost:3200/stocks/fundamental?search={p}&fields=LIQUIDEZ MEDIA DIARIA&dates=2026-04-16") for p in prefixes]
    
    return hist, {p: f for p, f in zip(prefixes, fund)}

def calc_score(profits: np.ndarray) -> dict:
    n = len(profits)
    if n < 10:
        return {"score": 0, "n_years": n, "growth": 0, "consistency": 0, "m_vol": 1, "m_dd": 1}
    
    x = np.arange(n)
    mean = np.mean(profits)
    
    # Linear + Log-linear growth
    slope = np.polyfit(x, profits, 1)[0]
    log_slope = np.polyfit(x, np.log(profits + 1), 1)[0]
    growth = min(100, max(0, max(slope / mean, np.exp(log_slope) - 1) / 0.07 * 100))
    
    # Volatility (CV-RMSE)
    pred = np.polyval(np.polyfit(x, profits, 1), x)
    cv_rmse = np.sqrt(np.mean((profits - pred) ** 2)) / mean
    m_vol = max(0.3, 1 - 2 * max(0, cv_rmse - 0.15))
    
    # Consistency
    yoy = np.diff(profits) / profits[:-1]
    pos_ratio = np.mean(yoy > 0)
    prof_ratio = np.mean(profits > 0)
    consistency = prof_ratio * 60 + pos_ratio * 40
    
    # Drawdown with continuous forgiveness
    running_max = np.maximum.accumulate(profits)
    max_dd = 1 - np.min(profits / np.maximum(running_max, 1))
    recovery = profits[-1] / np.max(profits)
    
    if recovery >= 0.90:
        m_dd = max(0.4, 1 - max_dd * 0.25)
    elif recovery >= 0.50:
        forgiveness = 0.6 * (recovery - 0.50) / 0.40
        m_dd = max(0.4, 1 - max_dd * (1 - forgiveness))
    else:
        m_dd = max(0.4, 1 - max_dd * recovery / 0.50)
    
    # Final score
    base = growth * 0.45 + consistency * 0.55
    return {
        "score": min(100, max(0, base * m_vol * m_dd)),
        "n_years": n, "growth": growth, "consistency": consistency,
        "m_vol": m_vol, "m_dd": m_dd
    }

if __name__ == "__main__":
    years = range(datetime.now().year - 10, datetime.now().year)
    hist_data, fund_data = get_data(TICKERS)
    
    # Process each ticker
    results = []
    for i, ticker in enumerate(TICKERS):
        hist = hist_data[i].get("data", [])
        if not hist:
            continue
        
        fund = fund_data.get(ticker[:4], {}).get("data", [])
        if not fund:
            continue
        
        # Extract profits (pandas vectorized)
        row = pd.Series(hist[0])
        profit_cols = row.index[row.index.str.contains("LUCRO LIQUIDO")]
        
        # Build year -> profit mapping
        profits_dict = {}
        for col in profit_cols:
            try:
                year = int(col.split()[-1])
                if year in years:
                    profits_dict[year] = row[col]
            except:
                continue
        
        if len(profits_dict) < 10:
            continue
        
        # Sort by year and get values (as float)
        profits = np.array([profits_dict[y] for y in sorted(profits_dict.keys())], dtype=float)
        
        # Handle NaN/zero
        profits = profits[~np.isnan(profits) & (profits > 0)]
        
        if len(profits) < 10:
            continue
        
        # Calculate score
        result = calc_score(profits)
        result["ticker"] = ticker
        
        # Liquidity & class multipliers
        liq = sum(f.get("LIQUIDEZ MEDIA DIARIA", 0) or 0 for f in fund)
        m_liq = max(0.5, np.sqrt(min(1, liq / 10_000_000))) if liq < 10_000_000 else 1
        m_class = 0.75 if not ticker.endswith("3") else 1
        
        result["score"] = min(100, result["score"] * m_liq * m_class)
        result["m_liq"] = m_liq
        result["m_class"] = m_class
        results.append(result)

    if results:
        df = pd.DataFrame(results)
        cols = ["ticker", "score", "growth", "consistency", "m_vol", "m_dd", "m_liq", "m_class", "n_years"]
        print(df[cols].sort_values("score", ascending=False).to_string(index=False))
    else:
        print("No results - check API status")
    
    print(f"\nElapsed: {time.time() - start_time:.2f}s")