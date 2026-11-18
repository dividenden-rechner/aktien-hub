"""v1.8: older annual reports (FY2019) extend the ten-year histories back to FY2010."""
import json
from pathlib import Path

import pytest

from app.multi_year import mark_comparability, merge_reports
from app.reports import load_catalog

ROOT = Path(__file__).resolve().parents[1]
MERGED = {i['symbol']: i for i in json.loads((ROOT / 'reports/history/ten_year_merged.json').read_text(encoding='utf-8'))['issuers']}


def fact(sym, field, year):
    return next(f for f in MERGED[sym]['facts'] if f['field'] == field and f['fiscal_year'] == year)


def test_fy2019_reports_registered_with_checksums():
    old = [e for e in load_catalog() if e['fiscal_year'] == 2019]
    assert {e['symbol'] for e in old} == {'0001.HK', '0019.HK', '0142.HK'}
    assert all(len(e['sha256']) == 64 and e['purpose'] == 'ten_year_summary' and e['url'].startswith('https://www1.hkexnews.hk/') for e in old)


@pytest.mark.parametrize('sym', ['0001.HK', '0019.HK', '0142.HK'])
def test_merged_history_covers_2010_2025_and_is_consistent(sym):
    m = MERGED[sym]
    assert m['status'] == 'extracted_consistent' and m['years'][0] == 2010 and m['years'][-1] == 2025
    assert {r['source_report_year'] for r in m['reports']} == {2019, 2025}
    assert all(r['second_engine']['not_found'] == 0 for r in m['reports'])
    assert all(f['human_review'] if 'human_review' in f else True for f in m['facts'])
    assert m['human_review'] == 'pending'


@pytest.mark.parametrize('sym,field,year,value,report', [
    ('0019.HK', 'revenue', 2010, '32837', 2019), ('0019.HK', 'dividend_per_share', 2011, '6.5', 2019),
    ('0142.HK', 'revenue', 2010, '4640.2', 2019), ('0142.HK', 'net_income_attributable', 2011, '574', 2019),
    ('0142.HK', 'revenue', 2019, '7585', 2025),            # restated in the FY2025 report -> newest wins
    ('0001.HK', 'revenue', 2016, '259842', 2025),
])
def test_golden_values_and_newest_report_wins(sym, field, year, value, report):
    f = fact(sym, field, year)
    assert f['value'] == value and f['source_report_year'] == report


def test_overlap_2016_2019_identical_for_ckh_and_swire_restatements_documented_for_fp():
    assert MERGED['0001.HK']['restatements'] == [] and MERGED['0019.HK']['restatements'] == []
    rs = {(r['field'], r['fiscal_year']) for r in MERGED['0142.HK']['restatements']}
    assert {('revenue', 2017), ('revenue', 2018), ('revenue', 2019)} <= rs


def test_ckh_predecessor_years_flagged_not_comparable():
    for y in range(2010, 2016):
        f = fact('0001.HK', 'revenue', y)
        assert f['comparable'] is False and 'Cheung Kong' in f['comparability_note'] or 'Reorganisation' in f['comparability_note']
    assert fact('0001.HK', 'revenue', 2016)['comparable'] is True


def test_merge_keeps_older_differing_value():
    a = {'source_report_year': 2019, 'source_url': 'u19', 'pdf_sha256': 'x', 'status': 'extracted_consistent', 'company': 'X',
         'facts': [{'field': 'revenue', 'fiscal_year': 2018, 'value': '10', 'source_report_year': 2019, 'pdf_page': 4, 'source_url': 'u19'}]}
    b = {'source_report_year': 2025, 'source_url': 'u25', 'pdf_sha256': 'y', 'status': 'extracted_consistent', 'company': 'X',
         'facts': [{'field': 'revenue', 'fiscal_year': 2018, 'value': '9', 'source_report_year': 2025, 'pdf_page': 4, 'source_url': 'u25'}]}
    m = merge_reports('X', [b, a])
    assert m['facts'][0]['value'] == '9' and m['restatements'][0]['used'] == 2025
    assert [v['value'] for v in m['restatements'][0]['values']] == ['10', '9']


def test_mark_comparability():
    r = mark_comparability({'facts': [{'fiscal_year': 2012}, {'fiscal_year': 2020}]}, {'not_comparable_years': {'2012': 'old entity'}})
    assert r['facts'][0]['comparable'] is False and r['facts'][1]['comparable'] is True
