"""Regression tests for the five FY2025 reports.

* Registry/profile consistency (always runs).
* Committed extraction outputs in reports/extracted/ (always runs): golden values that
  were cross-checked against the rendered PDF pages, a second PDF engine and, where
  available, the issuers' IR web pages.
* Live re-extraction from cached PDFs (runs only if `python process_reports.py --download`
  has populated reports/cache/; otherwise skipped, never faked).
"""
import json
from pathlib import Path

import pytest

from app.reports import ROOT, cached_pdf, load_catalog
from app.statement_extractor import load_profile

SYMBOLS = ['0001.HK', '0019.HK', '0142.HK', 'D05.SI', '002594.SZ']

# field -> (value, unit, currency, pdf_page)
GOLDEN = {
    '0001.HK': {'revenue': ('280036', 'million', 'HKD', 134), 'net_income_attributable': ('11841', 'million', 'HKD', 134),
                'total_assets': ('1155673', 'million', 'HKD', [136]), 'total_equity': ('688392', 'million', 'HKD', 137),
                'operating_cash_flow': ('62567', 'million', 'HKD', 141), 'dividend_per_share': ('2.312', 'units', 'HKD', 17),
                'eps_basic': ('3.09', 'units', 'HKD', 134)},
    '0019.HK': {'revenue': ('90467', 'million', 'HKD', 147), 'net_income_attributable': ('2938', 'million', 'HKD', 147),
                'total_assets': ('476413', 'million', 'HKD', [149]), 'total_equity': ('316235', 'million', 'HKD', 149),
                'operating_cash_flow': ('14551', 'million', 'HKD', 150), 'dividend_per_share': ('3.8', 'units', 'HKD', [170]),
                'net_debt': ('65264', 'million', 'HKD', 92)},
    '0142.HK': {'revenue': ('10232.5', 'million', 'USD', 103), 'net_income_attributable': ('661', 'million', 'USD', 103),
                'total_assets': ('30647.6', 'million', 'USD', [105]), 'total_equity': ('13123.6', 'million', 'USD', 105),
                'operating_cash_flow': ('1748.3', 'million', 'USD', 107), 'dividend_per_share_usd_cents': ('3.46', 'cents', 'USD', 14),
                'eps_basic': ('15.53', 'cents', 'USD', 103)},
    'D05.SI': {'revenue': ('22900', 'million', 'SGD', 58), 'net_income_attributable': ('10933', 'million', 'SGD', 58),
               'total_assets': ('897488', 'million', 'SGD', 59), 'total_equity': ('68916', 'million', 'SGD', 59),
               'operating_cash_flow': ('11024', 'million', 'SGD', 60), 'dividend_per_share': ('3.06', 'units', 'SGD', 89),
               'eps_basic': ('3.84', 'units', 'SGD', 58)},
    '002594.SZ': {'revenue': ('803964958', 'thousand', 'CNY', 126), 'net_income_attributable': ('32619022', 'thousand', 'CNY', 126),
                  'total_assets': ('883729883', 'thousand', 'CNY', 123), 'total_equity': ('258539185', 'thousand', 'CNY', 125),
                  'operating_cash_flow': ('59135544', 'thousand', 'CNY', 130), 'dividend_per_share': ('0.358', 'units', 'CNY', 249),
                  'eps_basic': ('3.58', 'units', 'CNY', 126)},
}


def _check_golden(result, symbol):
    facts = {f['field']: f for f in result['facts'] + result['derived']}
    for field, (value, unit, currency, page) in GOLDEN[symbol].items():
        fact = facts[field]
        assert fact['value'] == value, (symbol, field, fact['value'])
        assert fact['unit'] == unit and fact['currency'] == currency, (symbol, field)
        assert fact['pdf_page'] == page, (symbol, field, fact['pdf_page'])
        assert fact['fiscal_year'] == 2025 and fact['source_url'].startswith('https://')


def test_catalog_entries_are_pinned_and_downloaded():
    catalog = {e['symbol']: e for e in load_catalog()}
    assert set(SYMBOLS) <= set(catalog)
    for symbol in SYMBOLS:
        entry = catalog[symbol]
        assert entry['fiscal_year'] == 2025 and entry['report_type'] == 'annual'
        assert len(entry['sha256']) == 64 and entry['page_count'] > 100
        assert entry['download_verified_on'] == '2026-11-18'


@pytest.mark.parametrize('symbol', SYMBOLS)
def test_profile_matches_catalog(symbol):
    catalog = {e['symbol']: e for e in load_catalog()}
    profile = load_profile(ROOT / 'profiles' / f'{symbol}.json')
    assert profile['source_url'] == catalog[symbol]['url']
    assert profile['pdf_sha256'] == catalog[symbol]['sha256']
    assert profile['fiscal_year'] == 2025 and profile['period_end'] == '2025-12-31'
    for spec in profile['fields']:
        assert 1 <= spec['page'] <= profile['pdf_page_count'], spec
        assert ('pattern' in spec) != ('label' in spec), spec
    assert profile['manual_review']['human_review'] in ('pending', 'approved')


@pytest.mark.parametrize('symbol', SYMBOLS)
def test_committed_extraction_outputs(symbol):
    path = ROOT / 'extracted' / f'{symbol}_2025.json'
    result = json.loads(path.read_text(encoding='utf-8'))
    assert result['status'] == 'extracted_consistent'
    assert result['errors'] == []
    assert all(c['status'] == 'pass' for c in result['checks'])
    assert result['pdf_sha256_status'] == 'match'
    assert result['second_engine']['summary']['not_found'] == 0
    assert all(r['result'] in ('match', 'not_comparable') for r in result['reference_comparison'])
    assert all(f['verification_status'] == 'machine_extracted' for f in result['facts'])
    _check_golden(result, symbol)


def _cached():
    return all(cached_pdf(e) for e in load_catalog() if e['symbol'] in SYMBOLS)


@pytest.mark.skipif(not _cached(), reason='PDFs not cached; run `python process_reports.py --download` first')
def test_live_reextraction_from_cached_pdfs():
    from app.extraction_run import run_extraction
    out = run_extraction(SYMBOLS, second_engine=False, write=False)
    for result in out['results']:
        assert result['status'] == 'extracted_consistent', (result['symbol'], result.get('errors'))
        _check_golden(result, result['symbol'])


def test_aktien_hub_export_format():
    from export_aktien_hub import export
    data = export(2025)
    assert data['anzahl'] == 5 and {f['ticker'] for f in data['firmen']} == set(SYMBOLS)
    dbs = next(f for f in data['firmen'] if f['ticker'] == 'D05.SI')
    assert dbs['eps_jahr'] == 3.84 and dbs['dps_jahr'] == 3.06 and dbs['waehrung'] == 'SGD'
    assert dbs['werte']['bilanzsumme'] == {'wert': 897488.0, 'einheit': 'million', 'waehrung': 'SGD', 'pdf_seite': 59,
                                           'druckseite': '114-115', 'definition': None, 'methode': 'table_row'}
    fp = next(f for f in data['firmen'] if f['ticker'] == '0142.HK')
    assert fp['dps_jahr'] == 3.46 and fp['dps_einheit'] == 'cents' and fp['eps_einheit'] == 'cents'


def test_statements_api_endpoint():
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)
    r = client.get('/v1/reports/002594.SZ/statements?fiscal_year=2025')
    assert r.status_code == 200 and r.json()['status'] == 'extracted_consistent'
    assert client.get('/v1/reports/0700.HK/statements').status_code == 404
