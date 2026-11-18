"""Korea (OpenDART) and Japan (EDINET API v2) source registration (v1.7).

Runs where the free API keys are available (GitHub Actions secrets DART_API_KEY and
EDINET_API_KEY in dividenden-rechner/aktien-hub). Same endpoints as the repository's
tools/asien_fundamente.py.

Korea
* corpCode.xml (official DART company list) confirms or rejects every Korean ticker candidate
  by stock code; company.json adds the market (corp_cls Y = KOSPI, K = KOSDAQ) and English name.
* list.json (pblntf_detail_ty=A001, 사업보고서 = annual business report) lists filings 2016-2025.
Japan
* documents.json (daily filing index) is scanned for annual securities reports
  (docTypeCode 120, 有価証券報告書) of the confirmed EDINET codes.

Nothing is downloaded or extracted; no financial figures; human_review stays "pending".
API keys are never written to outputs or error messages.
"""
from __future__ import annotations

import datetime as dt
import io
import re
import time
import xml.etree.ElementTree as ET
import zipfile

import httpx

DART_BASE = 'https://opendart.fss.or.kr/api'
EDINET_BASE = 'https://api.edinet-fsa.go.jp/api/v2'
DART_VIEWER = 'https://dart.fss.or.kr/dsaf001/main.do?rcpNo={}'
EDINET_ANNUAL = '120'          # 有価証券報告書
EDINET_ANNUAL_AMENDED = '130'  # 訂正有価証券報告書 (recorded separately, not as the report)
CORP_CLS = {'Y': ('KOSPI', '.KS'), 'K': ('KOSDAQ', '.KQ'), 'N': ('KONEX', None), 'E': ('other', None)}


class KeyedClient:
    """Wraps httpx so that exceptions never expose the API key (httpx puts URLs in messages)."""

    def __init__(self, client: httpx.Client, secret: str):
        self.client, self.secret = client, secret

    def get(self, url: str, params: dict) -> httpx.Response:
        try:
            response = self.client.get(url, params=params)
            response.raise_for_status()
            return response
        except httpx.HTTPError as exc:
            message = str(exc).replace(self.secret, '***') if self.secret else str(exc)
            raise RuntimeError(f'{type(exc).__name__}: {message[:200]}') from None


# ---------------------------------------------------------------- Korea
def parse_corp_codes(zip_bytes: bytes) -> dict[str, dict]:
    """stock_code -> {corp_code, corp_name, corp_eng_name} for listed companies."""
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        root = ET.fromstring(z.read('CORPCODE.xml'))
    out = {}
    for e in root.iter('list'):
        stock = (e.findtext('stock_code') or '').strip()
        if stock:
            out[stock] = {'corp_code': (e.findtext('corp_code') or '').strip(),
                          'corp_name': (e.findtext('corp_name') or '').strip(),
                          'corp_eng_name': (e.findtext('corp_eng_name') or '').strip() or None}
    return out


REPORT_PERIOD = re.compile(r'\((\d{4})\.(\d{2})\)')


def parse_dart_reports(items: list[dict], years: list[int]) -> dict[str, list[dict]]:
    """Group 사업보고서 filings by the fiscal year in the title, e.g. '사업보고서 (2024.12)'."""
    by_year: dict[str, list[dict]] = {str(y): [] for y in years}
    for it in items:
        name = it.get('report_nm') or ''
        m = REPORT_PERIOD.search(name)
        if '사업보고서' not in name or not m:
            continue
        year = int(m.group(1))
        if str(year) not in by_year:
            continue
        by_year[str(year)].append({
            'url': DART_VIEWER.format(it.get('rcept_no')), 'title': name.strip(),
            'published_at': it.get('rcept_dt'), 'period_end': f'{m.group(1)}-{m.group(2)}',
            'is_amendment': name.strip().startswith('['), 'source': 'OpenDART list.json (A001)'})
    return by_year


def korea_sources(entries: list[dict], key: str, client: httpx.Client, years: list[int], pause: float = 0.2) -> dict:
    api = KeyedClient(client, key)
    corp = parse_corp_codes(api.get(f'{DART_BASE}/corpCode.xml', {'crtfc_key': key}).content)
    identities, sources = {}, {}
    for e in entries:
        code = e.get('exchange_code')
        hit = corp.get(code) if code else None
        if not hit:
            identities[e['id']] = {'status': 'not_in_current_official_list', 'ticker': None, 'former_code_hint': code,
                                   'evidence': 'dart_corpcode', 'note': 'Stock code not in OpenDART corpCode.xml'}
            continue
        info = api.get(f'{DART_BASE}/company.json', {'crtfc_key': key, 'corp_code': hit['corp_code']}).json()
        market, suffix = CORP_CLS.get(info.get('corp_cls'), ('unknown', None))
        identities[e['id']] = {
            'status': 'confirmed_official_list', 'ticker': f'{code}{suffix}' if suffix else None,
            'exchange_code': code, 'exchange': market, 'official_name_local': hit['corp_name'],
            'official_name': info.get('corp_name_eng') or hit['corp_eng_name'],
            'identifiers': {'dart_corp_code': hit['corp_code'], 'kr_jurir_no': info.get('jurir_no') or None},
            'evidence': 'dart_corpcode+company', 'match_method': 'assistant_candidate_confirmed_by_code'}
        listing = api.get(f'{DART_BASE}/list.json', {
            'crtfc_key': key, 'corp_code': hit['corp_code'], 'bgn_de': f'{min(years) + 1}0101',
            'end_de': f'{min(max(years) + 1, dt.date.today().year)}1231', 'pblntf_detail_ty': 'A001',
            'page_count': '100'}).json()
        items = (listing.get('list') or []) if listing.get('status') == '000' else []  # '013' = no filings
        docs = parse_dart_reports(items, years)
        sources[e['id']] = {'source_status': 'dart_queried', 'dart_corp_code': hit['corp_code'],
                            'documents_by_year': docs,
                            'years_with_candidates': sorted(int(y) for y, d in docs.items() if d)}
        time.sleep(pause)
    return {'identities': identities, 'sources': sources, 'corp_list_rows': len(corp)}


# ---------------------------------------------------------------- Japan
def parse_edinet_day(results: list[dict], wanted: set[str]) -> list[dict]:
    out = []
    for r in results or []:
        if r.get('edinetCode') not in wanted or r.get('docTypeCode') not in (EDINET_ANNUAL, EDINET_ANNUAL_AMENDED):
            continue
        if r.get('withdrawalStatus') not in (None, '0'):
            continue
        start, end = r.get('periodStart'), r.get('periodEnd')
        out.append({'edinet_code': r['edinetCode'], 'doc_id': r.get('docID'), 'title': r.get('docDescription'),
                    'published_at': r.get('submitDateTime'), 'period_start': start, 'period_end': end,
                    # Japanese fiscal years are named after their start year (e.g. Apr 2024 - Mar 2025 = FY2024).
                    'fiscal_year': int(start[:4]) if start else None, 'fiscal_year_basis': 'period_start_year',
                    'is_amendment': r.get('docTypeCode') == EDINET_ANNUAL_AMENDED,
                    'url': f'{EDINET_BASE}/documents/{r.get("docID")}?type=2',
                    'source': 'EDINET API v2 documents.json (docTypeCode 120/130)'})
    return out


def japan_sources(entries: list[dict], key: str, client: httpx.Client, years: list[int], start: dt.date, end: dt.date,
                  pause: float = 0.15, skip_weekends: bool = True) -> dict:
    api = KeyedClient(client, key)
    wanted = {e['identifiers']['edinet_code']: e['id'] for e in entries if e.get('identifiers', {}).get('edinet_code')}
    found: dict[str, list[dict]] = {i: [] for i in wanted.values()}
    days = failed = 0
    day = start
    while day <= end:
        if not (skip_weekends and day.weekday() >= 5):
            days += 1
            try:
                res = api.get(f'{EDINET_BASE}/documents.json', {'date': day.isoformat(), 'type': '2',
                                                                 'Subscription-Key': key}).json()
                for doc in parse_edinet_day(res.get('results'), set(wanted)):
                    found[wanted[doc['edinet_code']]].append(doc)
            except RuntimeError:
                failed += 1
            time.sleep(pause)
        day += dt.timedelta(days=1)
    sources = {}
    for entry_id, docs in found.items():
        by_year = {str(y): [d for d in docs if d['fiscal_year'] == y] for y in years}
        sources[entry_id] = {'source_status': 'edinet_queried', 'documents_by_year': by_year,
                             'years_with_candidates': sorted(int(y) for y, d in by_year.items()
                                                             if any(not x['is_amendment'] for x in d))}
    return {'sources': sources, 'days_scanned': days, 'days_failed': failed,
            'range': [start.isoformat(), end.isoformat()]}
