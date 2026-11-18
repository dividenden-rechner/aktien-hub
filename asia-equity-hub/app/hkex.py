"""Best-effort HKEXnews title-search discovery. Results require issuer verification.

HKEX's public search interface is not a versioned API; it may change or block
non-browser requests. No scraping bypass, credential use or invented filings.
"""
from __future__ import annotations
from datetime import date
from html import unescape
from urllib.parse import urljoin, urlparse
import json
import re
import httpx
from .providers import valid_symbol

SEARCH_URL = 'https://www1.hkexnews.hk/search/titleSearchServlet.do'
PREFIX_URL = 'https://www1.hkexnews.hk/search/prefix.do'
# HKEXnews headline categories: 40000 = Financial Statements/ESG Information, 40100 = Annual Report.
T1_FINANCIAL_STATEMENTS = '40000'
T2_ANNUAL_REPORT = '40100'
USER_AGENT = 'Mozilla/5.0 (compatible; AsiaEquityHub/1.1; annual-report research)'
DOCUMENT_BASE = 'https://www1.hkexnews.hk'
REPORT_WORDS = re.compile(r'(?i)(annual\s+report|annual\s+results|年報|年度報告|年度报告)')
ANNUAL_REPORT_ONLY = re.compile(r'(?i)(annual\s+report|年報|年度報告|年度报告)')
VALID_PDF_HOSTS = {'www1.hkexnews.hk','www.hkexnews.hk','hkexnews.hk'}


def normalize_pdf_url(raw: str) -> str | None:
    if not isinstance(raw, str):
        return None
    raw = unescape(raw.strip())
    if not raw or raw.startswith('//'):
        return None
    url = urljoin(DOCUMENT_BASE, raw)
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname not in VALID_PDF_HOSTS or parsed.username or parsed.password or parsed.port not in (None, 443):
        return None
    if not parsed.path.lower().endswith('.pdf'):
        return None
    return url


def parse_search_results(payload: dict, symbol: str, fiscal_year: int) -> list[dict]:
    """Parse HKEX JSON announcement records, rejecting non-annual-report items."""
    if not isinstance(payload, dict):
        raise ValueError('Unexpected HKEX search response')
    rows = payload.get('result')
    # v1.1 fix (verified live 2026-11-18): HKEX returns `result` as a JSON-encoded
    # *string* ("[{...}]"), and the string "null" when nothing matches.
    if isinstance(rows, str):
        try:
            rows = json.loads(rows)
        except ValueError as exc:
            raise ValueError('HKEX search response has an undecodable result string') from exc
        if rows is None:
            rows = []
    if not isinstance(rows, list):
        raise ValueError('HKEX search response missing result array')
    result, seen = [], set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        title = re.sub(r'<[^>]*>', ' ', str(row.get('TITLE') or row.get('title') or ''))
        title = unescape(' '.join(title.split()))
        if not ANNUAL_REPORT_ONLY.search(title):
            continue
        # A report may be published in the following calendar year.
        # Do not infer its fiscal year from publication date alone.
        if str(fiscal_year) not in title:
            continue
        url = normalize_pdf_url(row.get('FILE_LINK') or row.get('fileLink') or row.get('url') or '')
        if not url or url in seen:
            continue
        seen.add(url)
        result.append({'symbol': symbol, 'fiscal_year': fiscal_year,
                       'report_type':'annual', 'url':url, 'title':title,
                       'published_at':row.get('DATE_TIME') or row.get('dateTime'),
                       'verification_status':'candidate_unverified',
                       'source':'HKEXnews title search'})
    return result


def lookup_stock_id(code: str, client: httpx.Client, include_inactive: bool = True) -> int:
    """Map an exchange code (e.g. "00019") to HKEXnews' internal stockId.

    v1.1 fix (verified live): titleSearchServlet expects this internal id, not the
    stock code. v1.6: falls back to HKEX's list of *inactive* securities (type=I), so
    filings of delisted issuers (e.g. Hang Seng Bank, 00011) remain discoverable.
    """
    for list_type in (('A', 'I') if include_inactive else ('A',)):
        response = client.get(PREFIX_URL, params={'callback': 'callback', 'lang': 'EN', 'type': list_type,
                                                  'name': code, 'market': 'SEHK'})
        response.raise_for_status()
        match = re.search(r'callback\((.*)\)\s*;?\s*$', response.text, re.S)
        if not match:
            raise ValueError('Unexpected HKEX stock lookup response')
        data = json.loads(match.group(1))
        for item in data.get('stockInfo') or []:
            if item.get('code') == code:
                return int(item['stockId'])
    raise ValueError(f'HKEX stock code {code} not found')


def discover_hkex_years(symbol: str, years: list[int], client: httpx.Client) -> dict:
    """One HKEXnews query for several fiscal years (v1.6); candidates grouped by fiscal year."""
    code = f'{int(symbol[:-3]):05d}'
    stock_id = lookup_stock_id(code, client)
    params = {'sortDir': '0', 'sortByOptions': 'DateTime', 'category': '0', 'market': 'SEHK',
              'stockId': str(stock_id), 'documentType': '-1', 'fromDate': f'{min(years)}0101',
              'toDate': f'{min(max(years) + 1, date.today().year)}1231', 'title': '', 'searchType': '1',
              't1code': T1_FINANCIAL_STATEMENTS, 't2Gcode': '-2', 't2code': T2_ANNUAL_REPORT,
              'rowRange': '200', 'lang': 'E'}
    response = client.get(SEARCH_URL, params=params)
    if response.is_redirect:
        raise ValueError('HKEX redirected the discovery request')
    response.raise_for_status()
    payload = response.json()
    by_year = {y: parse_search_results(payload, symbol, y) for y in years}
    # Some issuers (e.g. HK & China Gas) title every filing just "Annual Report". Those rows get a
    # fiscal year inferred from the publication date (Dec year-end assumption), flagged as such.
    for cand in undated_annual_reports(payload, symbol):
        if cand['fiscal_year'] in by_year and not by_year[cand['fiscal_year']]:
            by_year[cand['fiscal_year']].append(cand)
    return {'symbol': symbol, 'hkex_stock_id': stock_id, 'source_url': str(response.url), 'by_year': by_year}


def undated_annual_reports(payload: dict, symbol: str) -> list[dict]:
    rows = payload.get('result')
    if isinstance(rows, str):
        rows = json.loads(rows) or []
    out = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        title = unescape(' '.join(re.sub(r'<[^>]*>', ' ', str(row.get('TITLE') or '')).split()))
        if not ANNUAL_REPORT_ONLY.search(title) or re.search(r'(19|20)\d{2}', title):
            continue
        published = str(row.get('DATE_TIME') or '')
        m = re.match(r'\d{2}/\d{2}/(\d{4})', published)
        url = normalize_pdf_url(row.get('FILE_LINK') or '')
        if not m or not url:
            continue
        out.append({'symbol': symbol, 'fiscal_year': int(m.group(1)) - 1, 'report_type': 'annual', 'url': url,
                    'title': title, 'published_at': published, 'verification_status': 'candidate_unverified',
                    'fiscal_year_basis': 'publication_year_minus_one_unverified', 'source': 'HKEXnews title search'})
    return out


def discover_hkex(symbol: str, fiscal_year: int, *, client: httpx.Client | None = None) -> dict:
    symbol = valid_symbol(symbol)
    if not symbol.endswith('.HK') or not symbol[:-3].isdigit():
        raise ValueError('HKEX discovery requires numeric .HK ticker')
    if not 2000 <= fiscal_year <= date.today().year:
        raise ValueError('Invalid fiscal year')
    own = client is None
    if own:
        client = httpx.Client(timeout=30, follow_redirects=False, headers={'User-Agent': USER_AGENT})
    try:
        code = f'{int(symbol[:-3]):05d}'
        stock_id = lookup_stock_id(code, client)
        # Annual reports are published in the year after the fiscal year end (or later).
        params = {'sortDir': '0', 'sortByOptions': 'DateTime', 'category': '0', 'market': 'SEHK',
                  'stockId': str(stock_id), 'documentType': '-1',
                  'fromDate': f'{fiscal_year}0101', 'toDate': f'{min(fiscal_year + 2, date.today().year)}1231',
                  'title': '', 'searchType': '1', 't1code': T1_FINANCIAL_STATEMENTS, 't2Gcode': '-2',
                  't2code': T2_ANNUAL_REPORT, 'rowRange': '100', 'lang': 'E'}
        response = client.get(SEARCH_URL, params=params)
        if response.is_redirect:
            raise ValueError('HKEX redirected the discovery request')
        response.raise_for_status()
        candidates = parse_search_results(response.json(), symbol, fiscal_year)
        return {'symbol': symbol, 'fiscal_year': fiscal_year, 'status': 'candidates_unverified',
                'hkex_stock_id': stock_id, 'candidates': candidates, 'source_url': str(response.url),
                'note': 'Verify issuer, reporting period and document manually before registration. HKEX search is undocumented and may change.'}
    finally:
        if own:
            client.close()
