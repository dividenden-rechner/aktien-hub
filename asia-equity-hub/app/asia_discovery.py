"""Best-effort official disclosure discovery for SGX and mainland China.

Only candidate URLs are returned. Nothing is considered audited or verified.
The public CNINFO endpoint is undocumented and may change without notice.
"""
from __future__ import annotations
import re
from datetime import date
from urllib.parse import urljoin, urlparse
import httpx
from .providers import valid_symbol

CNINFO_API = 'https://www.cninfo.com.cn/new/hisAnnouncement/query'
CNINFO_PDF_BASE = 'https://static.cninfo.com.cn/'
CNINFO_HOSTS = {'static.cninfo.com.cn', 'www.cninfo.com.cn'}
SGX_PORTAL = 'https://www.sgx.com/securities/company-announcements'
SGX_HOSTS = {'links.sgx.com', 'www.sgx.com', 'sgx.com'}
REPORT_TITLE = re.compile(r'(年度报告|年度報告|annual\s+report)', re.I)
# v1.1 fix: '半年度报告' (half-year report) contains '年度报告'; exclude it and
# announcements *about* the annual report (e.g. results briefings, 说明会).
EXCLUDE_TITLE = re.compile(r'(摘要|summary|更正|取消|修订|修訂|correction|withdraw|半年|中期|说明会|說明會|interim|关于|關於|《)', re.I)
# v1.6: '关于《2022年年度报告》…的公告' is an announcement *about* the report, not the report.
# CNINFO category code for annual reports (both exchanges). The trailing ';' is required.
CNINFO_ANNUAL_CATEGORY = 'category_ndbg_szsh;'


def safe_document_url(raw: str, base: str, hosts: set[str]) -> str | None:
    if not isinstance(raw, str) or not raw.strip() or raw.strip().startswith('//'):
        return None
    url = urljoin(base, raw.strip())
    p = urlparse(url)
    if (p.scheme != 'https' or p.hostname not in hosts or p.username or p.password
            or p.port not in (None, 443) or not p.path.lower().endswith('.pdf')):
        return None
    return url


def parse_cninfo(payload: dict, symbol: str, fiscal_year: int) -> list[dict]:
    """Parse CNINFO records, rejecting summaries and off-domain PDFs."""
    rows = payload.get('announcements') if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise ValueError('Unexpected CNINFO response: announcements missing')
    out, seen = [], set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        title = re.sub(r'<[^>]+>', '', str(row.get('announcementTitle') or ''))  # strips <em> highlights
        if not REPORT_TITLE.search(title) or EXCLUDE_TITLE.search(title):
            continue
        if str(fiscal_year) not in title:
            continue
        code = str(row.get('secCode') or '')
        if code and code != symbol.split('.')[0]:
            continue
        url = safe_document_url(row.get('adjunctUrl'), CNINFO_PDF_BASE, CNINFO_HOSTS)
        if not url or url in seen:
            continue
        seen.add(url)
        out.append({'symbol':symbol,'fiscal_year':fiscal_year,'report_type':'annual',
                    'title':title,'url':url,'source':'CNINFO public announcements',
                    'published_at':row.get('announcementTime'),
                    'verification_status':'candidate_unverified'})
    return out


def discover_cninfo(symbol: str, fiscal_year: int, *, client: httpx.Client | None = None) -> dict:
    symbol = valid_symbol(symbol)
    if not symbol.endswith(('.SZ', '.SS')) or not symbol.split('.')[0].isdigit():
        raise ValueError('CNINFO requires a numeric .SZ or .SS ticker')
    if not 2000 <= fiscal_year <= date.today().year:
        raise ValueError('Invalid fiscal year')
    own = client is None
    if own:
        client = httpx.Client(timeout=20, follow_redirects=False,
                              headers={'User-Agent':'Mozilla/5.0 (compatible; AsiaEquityHub/1.1; annual-report research)',
                                       'Referer':'https://www.cninfo.com.cn/'})
    try:
        # This is a public web endpoint, not a supported or versioned API.
        # v1.1 fix (verified live 2026-11-18): without the annual-report category the
        # first page holds only the 30 newest announcements of any kind, so the
        # annual report (published in March/April) was never returned.
        response = client.post(CNINFO_API, data={
            'pageNum':'1','pageSize':'30','column':'szse' if symbol.endswith('.SZ') else 'sse',
            'tabName':'fulltext','plate':'','stock':'','searchkey':symbol.split('.')[0],
            'secid':'','category':CNINFO_ANNUAL_CATEGORY,'trade':'',
            'seDate':f'{fiscal_year+1}-01-01~{fiscal_year+2}-12-31',
            'sortName':'','sortType':'','isHLtitle':'true'})
        if response.is_redirect:
            raise ValueError('CNINFO redirected the request')
        response.raise_for_status()
        candidates = parse_cninfo(response.json(), symbol, fiscal_year)
        return {'symbol':symbol,'fiscal_year':fiscal_year,'source_url':CNINFO_API,
                'status':'candidates_unverified','candidates':candidates,
                'note':'Public web endpoint is unstable. Verify issuer, year and PDF before import.'}
    finally:
        if own:
            client.close()


def sgx_discovery_guide(symbol: str, fiscal_year: int) -> dict:
    symbol = valid_symbol(symbol)
    if not symbol.endswith('.SI'):
        raise ValueError('SGX requires .SI ticker')
    if not 2000 <= fiscal_year <= date.today().year:
        raise ValueError('Invalid fiscal year')
    return {'symbol':symbol,'fiscal_year':fiscal_year,'status':'manual_search_required',
            'source_url':SGX_PORTAL,'candidates':[],
            'note':'SGX public announcement search does not provide a stable documented free API. '
                   'Find the annual-report PDF on SGXNet and register its verified URL; no guessed PDF links.'}


def discover_asia(symbol: str, fiscal_year: int, *, client: httpx.Client | None = None) -> dict:
    symbol = valid_symbol(symbol)
    if symbol.endswith(('.SS','.SZ')):
        return discover_cninfo(symbol,fiscal_year,client=client)
    if symbol.endswith('.SI'):
        return sgx_discovery_guide(symbol,fiscal_year)
    if symbol.endswith('.HK'):
        from .hkex import discover_hkex
        return discover_hkex(symbol,fiscal_year,client=client)
    raise ValueError('Report discovery currently supports HK, SG and mainland China')


def discover_cninfo_years(symbol: str, years: list[int], client: httpx.Client, max_pages: int = 4) -> dict:
    """CNINFO annual-report candidates for several fiscal years in one paged query (v1.6)."""
    symbol = valid_symbol(symbol)
    rows: list[dict] = []
    for page in range(1, max_pages + 1):
        response = client.post(CNINFO_API, data={
            'pageNum': str(page), 'pageSize': '30', 'column': 'szse' if symbol.endswith('.SZ') else 'sse',
            'tabName': 'fulltext', 'plate': '', 'stock': '', 'searchkey': symbol.split('.')[0], 'secid': '',
            'category': CNINFO_ANNUAL_CATEGORY, 'trade': '',
            'seDate': f'{min(years) + 1}-01-01~{min(max(years) + 1, date.today().year)}-12-31',
            'sortName': '', 'sortType': '', 'isHLtitle': 'true'})
        if response.is_redirect:
            raise ValueError('CNINFO redirected the request')
        response.raise_for_status()
        payload = response.json()
        rows += payload.get('announcements') or []
        if not payload.get('hasMore'):
            break
    by_year = {y: parse_cninfo({'announcements': rows}, symbol, y) for y in years}
    # CNINFO does not file every annual report under the annual-report category (verified live:
    # Yangtze Power FY2020). Fallback: full-text title search for the missing years only.
    missing = [y for y, c in by_year.items() if not c]
    fallback_used = False
    if missing:
        fallback_used = True
        extra: list[dict] = []
        for page in range(1, max_pages + 1):
            response = client.post(CNINFO_API, data={
                'pageNum': str(page), 'pageSize': '30', 'column': 'szse' if symbol.endswith('.SZ') else 'sse',
                'tabName': 'fulltext', 'plate': '', 'stock': '', 'searchkey': f"{symbol.split('.')[0]} 年度报告",
                'secid': '', 'category': '', 'trade': '',
                'seDate': f'{min(missing) + 1}-01-01~{min(max(missing) + 1, date.today().year)}-12-31',
                'sortName': '', 'sortType': '', 'isHLtitle': 'true'})
            response.raise_for_status()
            payload = response.json()
            extra += payload.get('announcements') or []
            if not payload.get('hasMore'):
                break
        for y in missing:
            by_year[y] = [dict(c, source='CNINFO full-text title search (fallback)')
                          for c in parse_cninfo({'announcements': extra}, symbol, y)]
    return {'symbol': symbol, 'source_url': CNINFO_API, 'fallback_used': fallback_used, 'by_year': by_year}
