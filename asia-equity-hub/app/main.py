from fastapi import FastAPI, HTTPException, Query
from .providers import valid_symbol, get_profile, get_prices, get_financials, get_dividends, EXCHANGES
from .metrics import derived

app=FastAPI(title='Asia Equity Data API',version='1.1.0',description='MVP. Delayed/unofficial market data; not investment advice.')

def check(symbol):
    try:
        return valid_symbol(symbol)
    except ValueError as e:
        raise HTTPException(status_code=422,detail=str(e))

def fetch(fn,*args):
    try:
        return fn(*args)
    except Exception as e:
        # Do not leak credentials, headers or provider tracebacks to clients.
        raise HTTPException(status_code=502,detail=f'Upstream market-data provider failed ({type(e).__name__})')

@app.get('/health')
def health():
    return {'ok':True,'version':'1.1.0'}

@app.get('/v1/exchanges')
def exchanges():
    return [{'code':k,'name':v[0],'suffix':v[1],'currency':v[2]} for k,v in EXCHANGES.items()]

@app.get('/v1/companies/{symbol}')
def company(symbol:str):
    return fetch(get_profile,check(symbol))

@app.get('/v1/prices/{symbol}')
def prices(symbol:str,period:str=Query('1y',pattern='^(1mo|3mo|6mo|1y|2y|5y|10y|max)$')):
    return fetch(get_prices,check(symbol),period)

@app.get('/v1/financials/{symbol}')
def financials(symbol:str):
    return fetch(get_financials,check(symbol))

@app.get('/v1/dividends/{symbol}')
def dividends(symbol:str):
    return fetch(get_dividends,check(symbol))

@app.get('/v1/metrics/{symbol}')
def metrics(symbol:str):
    s=check(symbol)
    p=fetch(get_profile,s)
    f=fetch(get_financials,s)
    years=f['years']
    latest=years[-1] if years else None
    return {'symbol':s,'fiscal_period_end':latest['fiscal_period_end'] if latest else None,
            'currency':f['currency'],'metrics':derived(latest['values'],p['market_cap'],p['enterprise_value']) if latest else {},
            'sources':[p['data_source'],f['source']],
            'warning':'Market capitalization is current while financial data is historical; ratios may mix periods.'}

@app.get('/v1/hub/{symbol}')
def hub(symbol: str, period: str = Query('1y', pattern='^(1mo|3mo|6mo|1y|2y|5y|10y|max)$')):
    """One-call payload for an equity dashboard; no guarantee of real-time data."""
    from .analytics import build_snapshot
    s = check(symbol)
    return build_snapshot(fetch(get_profile, s), fetch(get_prices, s, period),
                          fetch(get_financials, s), fetch(get_dividends, s))

@app.get('/v1/reports/{symbol}')
def reports(symbol: str):
    """Official filing registry and ingestion status (no fabricated report links)."""
    from .reports import list_reports
    try:
        return list_reports(check(symbol))
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=422, detail=str(e))

@app.get('/v1/reports/{symbol}/sources')
def report_sources(symbol: str):
    """Official disclosure portal for manual verification and registration."""
    from .reports import portal_for
    return {'symbol':check(symbol), 'portal':portal_for(symbol)}

@app.get('/v1/reports/{symbol}/discover')
def discover_reports(symbol: str, fiscal_year: int = Query(..., ge=2000, le=2100)):
    """Find unverified HKEX annual-report candidates; never auto-ingest."""
    from .hkex import discover_hkex
    try:
        return discover_hkex(check(symbol), fiscal_year)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f'Official discovery unavailable ({type(e).__name__})')

@app.get('/v1/reports/{symbol}/extract')
def extract_reports(symbol: str, fiscal_year: int | None = Query(None, ge=1990, le=2100)):
    """Return page-cited unverified metric candidates from ingested PDF text."""
    from .extract import extract_registered
    try:
        return extract_registered(check(symbol), fiscal_year)
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=422, detail=str(e))

@app.get('/v1/reports/{symbol}/tables')
def report_tables(symbol: str, fiscal_year: int | None = Query(None, ge=1990, le=2100)):
    """Year-aligned, source-cited extraction candidates; never silently verified."""
    import json
    from .reports import ROOT, load_catalog, report_key
    from .table_financials import extract_year_tables
    s=check(symbol)
    out=[]
    for entry in load_catalog():
        if entry['symbol'] != s or (fiscal_year is not None and entry['fiscal_year'] != fiscal_year):
            continue
        path=ROOT/'cache'/f'{report_key(entry)}.pages.json'
        if not path.is_file():
            out.append({'fiscal_year':entry['fiscal_year'],'status':'not_ingested'})
            continue
        pages=json.loads(path.read_text(encoding='utf-8'))
        out.append({'fiscal_year':entry['fiscal_year'],**extract_year_tables(pages,entry['url'])})
    return {'symbol':s,'reports':out}


@app.get('/v1/reports/{symbol}/discover-asia')
def discover_asian_reports(symbol: str, fiscal_year: int = Query(..., ge=2000, le=2100)):
    """Official-market candidates for HK/CN; SGX provides manual search portal."""
    from .asia_discovery import discover_asia
    try:
        return discover_asia(check(symbol), fiscal_year)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f'Discovery unavailable ({type(e).__name__})')


@app.get('/v1/reports/{symbol}/statements')
def report_statements(symbol: str, fiscal_year: int = Query(2025, ge=1990, le=2100)):
    """Profile-based statement values with PDF page provenance and check results.

    Served from reports/extracted/ (produced by `python extract_reports.py`), so the API
    works without the PDFs. Values are machine-extracted and arithmetic-checked; see
    `manual_review` for the human verification status.
    """
    import json
    from .reports import ROOT
    s = check(symbol)
    path = ROOT / 'extracted' / f'{s}_{fiscal_year}.json'
    if not path.is_file():
        raise HTTPException(status_code=404, detail='No extracted statements for this symbol/year; run extract_reports.py')
    return json.loads(path.read_text(encoding='utf-8'))
