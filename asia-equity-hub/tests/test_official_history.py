import copy
from pathlib import Path
import pytest
from app.official_history import load_official_history, validate_official_history

PATH = Path(__file__).resolve().parents[1] / 'reports/history/jardine_issuer_web_2021_2025.json'

def test_jardine_series_and_evidence():
    result = load_official_history(PATH)
    assert len(result['facts']) == 26
    assert set(x['fiscal_year'] for x in result['facts']) == {2021, 2022, 2023, 2024, 2025}
    assert all(x['human_review'] == 'pending' for x in result['facts'])
    assert next(x['value'] for x in result['facts'] if x['field'] == 'reported_net_profit' and x['fiscal_year'] == 2024) == -468

def test_no_verified_status():
    x = load_official_history(PATH)
    x['facts'][0]['verification_status'] = 'verified'
    with pytest.raises(ValueError): validate_official_history(x)

def test_no_duplicate_or_cross_currency():
    x = load_official_history(PATH)
    x['facts'].append(copy.deepcopy(x['facts'][0]))
    with pytest.raises(ValueError): validate_official_history(x)
    x['facts'].pop()
    x['facts'][0]['currency'] = 'SGD'
    with pytest.raises(ValueError): validate_official_history(x)

def test_no_missing_source_or_estimated_year():
    x = load_official_history(PATH)
    x['facts'][0]['source_url'] = ''
    with pytest.raises(ValueError): validate_official_history(x)
    x = load_official_history(PATH)
    x['facts'][0]['fiscal_year'] = 2019
    with pytest.raises(ValueError): validate_official_history(x)

def test_coverage_marks_web_evidence_distinctly():
    from app.coverage import coverage_matrix
    x = load_official_history(PATH)
    queue = {'companies': [{'symbol': 'J36.SI', 'company': 'Jardine Matheson'}]}
    result = coverage_matrix({'companies': []}, queue, official_histories=[x])
    row = result['companies'][0]
    assert row['years']['2020']['status'] == 'missing'
    assert row['years']['2021']['status'] == 'issuer_web_transcribed_pending_pdf_review'
    assert row['years']['2025']['fact_count'] == 7
