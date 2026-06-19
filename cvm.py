import pandas as pd
import numpy as np
import re
from unicodedata import normalize

import requests

tickers = pd.DataFrame(requests.get('http://localhost:3200/stocks/fundamental?fields=NOME&dates=2026-06-19').json()['data'])[['TICKER', 'NOME']]

df = pd.read_csv('https://dados.cvm.gov.br/dados/CIA_ABERTA/CAD/DADOS/cad_cia_aberta.csv', sep=';', encoding='ISO-8859-1')
df = df[df['TP_MERC'] == 'BOLSA'][['CNPJ_CIA', 'DENOM_SOCIAL', 'CD_CVM']].drop_duplicates()

for index, row in tickers.iterrows():
    search = row['NOME']
    
    search_expanded = re.sub(r'[^A-Z0-9]', '', search.upper()) if pd.notna(search) else ''
    search_expanded = search_expanded.replace('BCO', 'BANCO').replace('CIA', 'COMPANHIA') if search_expanded else ''
    
    # optimized by minimax m3 with autoresearch
    matches = df[df['DENOM_SOCIAL'].apply(lambda x: re.sub(r'[^A-Z0-9]', '', normalize('NFKD', str(x).upper()).encode('ASCII', 'ignore').decode('ASCII')).replace('BCO', 'BANCO').replace('CIA', 'COMPANHIA').replace('DE', '').replace('DA', '').replace('DO', '').replace('DAS', '').replace('DOS', '').replace('E', '').replace('LTDA', '')).str.contains(search_expanded[:5].replace('DE', '').replace('DA', '').replace('DO', '').replace('DAS', '').replace('DOS', '').replace('E', '').replace('LTDA', '') if len(search_expanded) > 5 else search_expanded.replace('DE', '').replace('DA', '').replace('DO', '').replace('DAS', '').replace('DOS', '').replace('E', '').replace('LTDA', ''), na=False)]
    
    if len(matches) == 0:
        print(f"unmatched: {row['TICKER']} | {row['NOME']}")
        continue
    
    answer = matches.iloc[0]
    print(f"ticker: {row['TICKER']} | cnpj: {answer['CNPJ_CIA']} | id: {answer['CD_CVM']}")