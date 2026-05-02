import pandas as pd
import numpy as np
import asyncio
import aiohttp
import time
from datetime import datetime
from sklearn.linear_model import LinearRegression

start_time = time.time()
semaphore = asyncio.Semaphore(10)

tickers = [
    "WEGE3", "RADL3", "EGIE3", "ITUB3", "LREN3", "BBAS3", "VALE3",
    "EQTL3", "RENT3", "FLRY3", "LEVE3", "B3SA3", "PSSA3", "TOTS3",
    "BBSE3", "TAEE11", "FRAS3", "SAPR11", "BRAP4", "CPFE3", "CSUD3",
    "SLCE3", "ODPV3", "PNVL3",
    "CMIG3", "MDIA3", "CXSE3", "GRND3", "PRIO3", "SMTO3", "UGPA3",
    "SBSP3", "ABCB4", "TIMS3", "VIVT3", "SANB11", "CSMG3", "YDUQ3",
    "VBBR3", "HYPE3", "VIVA3", "GOAU4", "RANI3", "SUZB3", "BRFS3", "INTB3",
    "TUPY3", "EMBR3", "ALUP11", "MGLU3", "AURE3", "KEPL3", "CSAN3",
    "UNIP6", "TRPL4", "BPAC11", "CSNA3", "KLBN11", "DXCO3", "CYRE3",
    "DIRR3", "ENGI11", "BRKM5", "MYPK3",
    "OIBR3", "TASA4", "PETZ3", "CASH3", "RAIZ4", "LIGT3", "GOLL4",
    "AZUL4", "USIM5", "JALL3", "NGRD3", "AERI3", "BHIA3", "HBSA3"
]

cache = {}

async def fetch_with_cache(session, url, cache_key):
    if cache_key in cache:
        return cache[cache_key]
    async with semaphore:
        try:
            async with session.get(url) as response:
                data = await response.json()
                cache[cache_key] = data
                return data
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            return {"data": []}

async def fetch_all_data(tickers):
    unique_prefixes = list({t[:4] for t in tickers})
    
    connector = aiohttp.TCPConnector(limit=10, limit_per_host=5)
    timeout = aiohttp.ClientTimeout(total=30)
    
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        batch_size = 15
        hist_results = []
        for i in range(0, len(tickers), batch_size):
            batch = tickers[i:i+batch_size]
            tasks = [fetch_with_cache(session, f"http://localhost:3200/stocks/historical?search={t}", f"hist_{t}") for t in batch]
            hist_results.extend(await asyncio.gather(*tasks))
            if i + batch_size < len(tickers):
                await asyncio.sleep(0.5)
        
        # Fetch fundamental in smaller batches
        fund_results = []
        for i in range(0, len(unique_prefixes), batch_size):
            batch = unique_prefixes[i:i+batch_size]
            tasks = [fetch_with_cache(session, f"http://localhost:3200/stocks/fundamental?search={p}&dates=2026-04-16", f"fund_{p}") for p in batch]
            fund_results.extend(await asyncio.gather(*tasks))
            if i + batch_size < len(unique_prefixes):
                await asyncio.sleep(0.5)
        
        fund_lookup = {p: r for p, r in zip(unique_prefixes, fund_results)}
        
    return hist_results, fund_lookup

hist_results, fund_lookup = asyncio.run(fetch_all_data(tickers))

results = []
current_year = datetime.now().year
years = range(current_year - 10, current_year)

for idx, ticker in enumerate(tickers):
    historical = hist_results[idx].get("data", [])
    if not historical:
        continue
    
    prefix = ticker[:4]
    fundamental = fund_lookup.get(prefix, {}).get("data", [])
    if not fundamental:
        continue
    
    total_liq = sum(i.get("LIQUIDEZ MEDIA DIARIA", 0) or 0 for i in fundamental)
    
    df_fund = pd.DataFrame([i for i in fundamental if i.get("TICKER") == ticker])
    if df_fund.empty:
        continue
    
    df_fund = df_fund.drop(columns=["COTACAO 10Y PADRAO", "COTACAO 10Y AJUSTADA", "HISTORICO DIVIDENDOS"], errors="ignore")
    if "TIME" in df_fund.columns:
        df_fund = df_fund.loc[df_fund.groupby("TICKER")["TIME"].idxmax()]
    
    df_hist = pd.DataFrame(historical)
    df = pd.merge(df_hist, df_fund, on="TICKER")

    score = 0
    n_years = 0
    growth_score = 0
    consistency_score = 0
    m_vol = 1.0
    m_dd = 1.0
    m_liq = 1.0
    m_class = 1.0
    
    row = df.iloc[0]
    profit_cols = [col for col in row.keys() if str(col).startswith("LUCRO LIQUIDO") and str(col)[-1].isdigit()]

    profit_data = []
    for col in profit_cols:
        try:
            year_val = int(col.split()[-1])
            lucro_val = row[col]
            if not pd.isna(lucro_val):
                profit_data.append({"YEAR": year_val, "LUCRO LIQUIDO": lucro_val})
        except (ValueError, IndexError):
            continue
    
    profit_df = pd.DataFrame(profit_data).sort_values("YEAR").reset_index(drop=True)
    profit10y_df = profit_df[profit_df['YEAR'].isin(years)].dropna().copy().reset_index(drop=True)
    n_years = len(profit10y_df)
    
    if len(profit10y_df) >= 10:
        profits = profit10y_df["LUCRO LIQUIDO"].astype(float).values
        X = np.arange(len(profits)).reshape(-1, 1)
        
        mean_profit = np.mean(profits)
        
        if mean_profit > 0:
            model = LinearRegression().fit(X, profits)
            slope = model.coef_[0]
            
            relative_growth = slope / mean_profit
            growth_score = min(100, max(0, (relative_growth / 0.07) * 100))
            
            preds = model.predict(X)
            residuals = profits - preds
            cv_rmse = np.sqrt(np.mean(residuals**2)) / mean_profit
            
            volatility_penalty = max(0, cv_rmse - 0.15) * 2.0
            m_vol = max(0.3, 1.0 - volatility_penalty)
            
            yearly_growth = pd.Series(profits).pct_change().dropna()
            positive_years_ratio = (yearly_growth > 0).sum() / len(yearly_growth) if len(yearly_growth) > 0 else 0
            profitable_years_ratio = (profits > 0).sum() / len(profits)
            consistency_score = (profitable_years_ratio * 60) + (positive_years_ratio * 40)
            
            running_max = np.maximum.accumulate(profits)
            safe_running_max = np.where(running_max <= 0, 1e-9, running_max)
            drawdowns = (profits - safe_running_max) / safe_running_max
            max_dd = abs(np.min(drawdowns))
            current_profit = profits[-1]
            max_profit = np.max(profits)
            
            if max_profit > 0 and (current_profit / max_profit) >= 0.90:
                effective_dd = max_dd * 0.25
            else:
                effective_dd = max_dd
            
            m_dd = max(0.4, 1.0 - effective_dd)
            
            base_score = (growth_score * 0.45) + (consistency_score * 0.55)
            score = base_score * m_vol * m_dd
            
            target_liquidity = 10_000_000
            if total_liq < target_liquidity:
                ratio = total_liq / target_liquidity
                m_liq = max(0.5, np.sqrt(min(1.0, ratio)))
                score *= m_liq
            
            if not ticker.endswith("3"):
                m_class = 0.75
                score *= 0.75
    
    score = min(max(score, 0), 100)
    results.append({
        "TICKER": ticker,
        "SCORE": score,
        "GROWTH_SCORE": growth_score,
        "CONSISTENCY_SCORE": consistency_score,
        "M_VOL": m_vol,
        "M_DD": m_dd,
        "M_LIQ": m_liq,
        "M_CLASS": m_class,
        "N_YEARS": n_years
    })

results.sort(key=lambda x: x["SCORE"], reverse=True)

results_df = pd.DataFrame(results)
pd.set_option('display.max_columns', None)
pd.set_option('display.width', None)
print(results_df.to_string(index=False))

print(f"\nelapsed: {time.time() - start_time:.2f}s")