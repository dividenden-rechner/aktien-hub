"""v1.6 ten-year histories: committed output + extractor unit tests."""
import json
from pathlib import Path

import pytest

from app.multi_year import extract_multi_year, run_year_checks

ROOT = Path(__file__).resolve().parents[1]
HIST = json.loads((ROOT / 'reports/history/ten_year_2016_2025.json').read_text(encoding='utf-8'))
BY = {i['symbol']: i for i in HIST['issuers']}

# Golden values read from the ten-year summaries (PDF pages: CKH 349/350, Swire 242, First Pacific 4/5)
GOLDEN = [
    ('0001.HK', 'revenue', 2016, '259842'), ('0001.HK', 'revenue', 2020, '266396'),
    ('0001.HK', 'total_assets', 2018, '1232244'), ('0001.HK', 'dividend_per_share', 2020, '2.314'),
    ('0001.HK', 'perpetual_capital_securities', 2025, None),
    ('0019.HK', 'revenue', 2016, '62389'), ('0019.HK', 'net_income_attributable', 2020, '-11420'),
    ('0019.HK', 'dividend_per_share', 2023, '11.32'), ('0019.HK', 'lease_liabilities', 2016, None),
    ('0142.HK', 'revenue', 2016, '6779'), ('0142.HK', 'net_income_attributable', 2019, '-253.9'),
    ('0142.HK', 'total_assets', 2016, '17215.4'), ('0142.HK', 'capex_issuer_defined', 2025, '1407.1'),
]


@pytest.mark.parametrize('symbol', ['0001.HK', '0019.HK', '0142.HK'])
def test_issuer_consistent_and_complete(symbol):
    r = BY[symbol]
    assert r['status'] == 'extracted_consistent' and r['errors'] == []
    assert r['years'] == list(range(2016, 2026))
    assert all(c['status'] == 'pass' for c in r['checks'])
    assert r['cross_check_latest'] and all(c['result'] == 'match' for c in r['cross_check_latest'])
    assert r['second_engine']['summary']['not_found'] == 0
    assert all(f['verification_status'] == 'machine_extracted' for f in r['facts'])
    assert r['human_review'] == 'pending'


@pytest.mark.parametrize('symbol,field,year,value', GOLDEN)
def test_golden_values(symbol, field, year, value):
    fact = next(f for f in BY[symbol]['facts'] if f['field'] == field and f['fiscal_year'] == year)
    assert fact['value'] == value
    assert fact['source_report_year'] == 2025 and fact['pdf_page'] and fact['source_url'].startswith('https://')


def test_restatement_notes_are_kept():
    f = next(f for f in BY['0019.HK']['facts'] if f['field'] == 'revenue' and f['fiscal_year'] == 2020)
    assert f['presentation_note'] == 'Restated (^)'
    g = next(f for f in BY['0001.HK']['facts'] if f['field'] == 'revenue' and f['fiscal_year'] == 2016)
    assert 'HKFRS' in g['presentation_note']


PAGE = """2025 2024 2023
Revenue 10.0 9.0 8.0
Total assets 50.0 40.0 30.0
Total liabilities 20.0 15.0 10.0
Total equity 30.0 25.0 21.0
"""
PROFILE = {'symbol': 'X.HK', 'source_url': 'https://x', 'source_report_year': 2025, 'currency': 'USD', 'unit': 'million',
           'tables': [{'id': 't', 'page': 1, 'years': [2025, 2024, 2023], 'header_regex': r'2025 2024 2023'}],
           'fields': [{'field': 'revenue', 'table': 't', 'label': '^Revenue$'},
                      {'field': 'total_assets', 'table': 't', 'label': '^Total assets$'},
                      {'field': 'total_liabilities', 'table': 't', 'label': '^Total liabilities$'},
                      {'field': 'total_equity', 'table': 't', 'label': '^Total equity$'}]}


def test_descending_columns_map_to_years_and_checks_catch_errors():
    out = extract_multi_year([PAGE], PROFILE)
    rev = {f['fiscal_year']: f['value'] for f in out['facts'] if f['field'] == 'revenue'}
    assert rev == {2025: '10', 2024: '9', 2023: '8'}
    checks = run_year_checks(out['facts'], [{'name': 'bs', 'left': ['total_assets'], 'right': ['total_liabilities', 'total_equity'], 'tolerance': '0.1'}])
    assert {c['fiscal_year']: c['status'] for c in checks} == {2025: 'pass', 2024: 'pass', 2023: 'fail'}


def test_missing_header_is_an_error_not_a_guess():
    bad = dict(PROFILE, tables=[dict(PROFILE['tables'][0], header_regex='2026 2025 2024')])
    out = extract_multi_year([PAGE], bad)
    assert out['facts'] == [] and {e['reason'] for e in out['errors']} == {'column_header_not_found'}
