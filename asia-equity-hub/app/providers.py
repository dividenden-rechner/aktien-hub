from __future__ import annotations
import math
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

# Provider is an MVP convenience adapter, NOT an exchange-licensed real-time feed.
# Financial statements and prices can be delayed, missing, or inconsistently tagged.
EXCHANGES = {
    'HK': ('Hong Kong', '.HK', 'HKD'),
    'SS': ('Shanghai', '.SS', 'CNY'),
    'SZ': ('Shenzhen', '.SZ', 'CNY'),
    'SI': ('Singapore', '.SI', 'SGD'),
    'T': ('Tokyo', '.T', 'JPY'),
    'KS': ('Korea KOSPI', '.KS', 'KRW'),
    'KQ': ('Korea KOSDAQ', '.KQ', 'KRW'),
    'TW': ('Taiwan', '.TW', 'TWD'),
    'TWO': ('Taiwan OTC', '.TWO', 'TWD'),
    'NS': ('India NSE', '.NS', 'INR'),
    'BO': ('India BSE', '.BO', 'INR'),
}

def valid_symbol(symbol: str) -> str:
    s = symbol.strip().upper()
    if not s or len(s) > 32 or not all(c.isalnum() or c in '.-^' for c in s):
        raise ValueError('Invalid ticker symbol')
    if not any(s.endswith(ext) for _, ext, _ in EXCHANGES.values()):
        raise ValueError('Use an Asian exchange suffix, e.g. 0700.HK, D05.SI, 7203.T, 600519.SS')
    return s

def clean(v: Any):
    if v is None:
        return None
    try:
        if hasattr(v, 'item'):
            v = v.item()
        if isinstance(v, (int, float)):
            return float(v) if math.isfinite(float(v)) else None
    except (ValueError, TypeError, OverflowError):
        pass
    return str(v) if not isinstance(v, (str, bool)) else v

def statement_value(frame, labels: tuple[str, ...], column) -> float | None:
    if frame is None or frame.empty or column is None:
        return None
    for label in labels:
        if label in frame.index:
            value = clean(frame.at[label, column])
            if isinstance(value, float):
                return value
    return None

FIELDS = {
    'revenue': ('Total Revenue', 'Operating Revenue'),
    'cost_of_revenue': ('Cost Of Revenue',),
    'gross_profit': ('Gross Profit',),
    'operating_income': ('Operating Income', 'EBIT'),
    'net_income': ('Net Income', 'Net Income Common Stockholders'),
    'ebitda': ('EBITDA', 'Normalized EBITDA'),
    'interest_expense': ('Interest Expense', 'Interest Expense Non Operating'),
    'equity': ('Stockholders Equity', 'Total Equity Gross Minority Interest'),
    'current_assets': ('Current Assets',),
    'current_liabilities': ('Current Liabilities',),
    'total_debt': ('Total Debt',),
    'cash': ('Cash And Cash Equivalents', 'Cash Cash Equivalents And Short Term Investments'),
    'operating_cash_flow': ('Operating Cash Flow',),
    'capex': ('Capital Expenditure',),
    'dividends_paid': ('Cash Dividends Paid', 'Common Stock Dividend Paid'),
    'diluted_eps': ('Diluted EPS',),
}
INCOME = {'revenue','cost_of_revenue','gross_profit','operating_income','net_income','ebitda','interest_expense','diluted_eps'}
BALANCE = {'equity','current_assets','current_liabilities','total_debt','cash'}

def _iso(dt):
    return dt.isoformat() if dt is not None else None

def get_profile(symbol: str):
    import yfinance as yf
    t = yf.Ticker(symbol)
    info = t.info or {}
    return {'symbol':symbol,'name':info.get('longName') or info.get('shortName'),
            'exchange':info.get('exchange'),'currency':info.get('currency'),
            'country':info.get('country'),'sector':info.get('sector'),'industry':info.get('industry'),
            'website':info.get('website'),'description':info.get('longBusinessSummary'),
            'employees':info.get('fullTimeEmployees'),'market_cap':clean(info.get('marketCap')),
            'enterprise_value':clean(info.get('enterpriseValue')),
            'trailing_pe':clean(info.get('trailingPE')),'price_to_book':clean(info.get('priceToBook')),
            'price_to_sales':clean(info.get('priceToSalesTrailing12Months')),
            'dividend_yield':clean(info.get('dividendYield')),
            'data_source':'Yahoo Finance via yfinance (unofficial)',
            'retrieved_at':datetime.now(timezone.utc).isoformat()}

def get_prices(symbol: str, period: str):
    import yfinance as yf
    t = yf.Ticker(symbol)
    hist = t.history(period=period, auto_adjust=False, actions=False)
    if hist.empty:
        return {'symbol':symbol,'currency':None,'bars':[],'source':'Yahoo Finance via yfinance (unofficial)',
                'retrieved_at':datetime.now(timezone.utc).isoformat(),'warning':'No price history available'}
    bars=[]
    for idx,row in hist.iterrows():
        bars.append({'time':_iso(idx),'open':clean(row.get('Open')),'high':clean(row.get('High')),
                     'low':clean(row.get('Low')),'close':clean(row.get('Close')),
                     'volume':clean(row.get('Volume'))})
    return {'symbol':symbol,'currency':(t.fast_info.get('currency') if t.fast_info else None),
            'bars':bars,'source':'Yahoo Finance via yfinance (unofficial)',
            'retrieved_at':datetime.now(timezone.utc).isoformat(),
            'warning':'Not guaranteed live; exchange delays and provider restrictions may apply'}

def get_financials(symbol: str):
    import yfinance as yf
    t=yf.Ticker(symbol)
    inc=t.income_stmt
    bal=t.balance_sheet
    cash=t.cashflow
    columns=sorted(set(inc.columns if inc is not None else []).union(
        bal.columns if bal is not None else []).union(cash.columns if cash is not None else []))
    rows=[]
    for col in columns:
        values={}
        for key,labels in FIELDS.items():
            frame=inc if key in INCOME else bal if key in BALANCE else cash
            values[key]=statement_value(frame,labels,col)
        rows.append({'fiscal_period_end':_iso(col),'values':values})
    return {'symbol':symbol,'period':'annual','currency':(t.info or {}).get('financialCurrency'),
            'years':rows,'source':'Yahoo Finance via yfinance (unofficial; verify against issuer filings)',
            'retrieved_at':datetime.now(timezone.utc).isoformat(),
            'warning':'Coverage and line-item definitions vary by exchange and accounting standard'}

def get_dividends(symbol: str):
    import yfinance as yf
    s=yf.Ticker(symbol).dividends
    events=[{'date':_iso(idx),'amount_per_share':clean(value)} for idx,value in s.items()]
    return {'symbol':symbol,'events':events,'source':'Yahoo Finance via yfinance (unofficial)',
            'retrieved_at':datetime.now(timezone.utc).isoformat(),
            'warning':'May include special dividends; verify split/currency adjustments'}
