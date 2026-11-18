import json
from pathlib import Path
import pytest
from app.coverage import coverage_matrix, create_coverage

ROOT = Path(__file__).resolve().parents[1]

def test_2020_to_2025_missing_not_zero():
    history = json.loads((ROOT/'reports/history/history_2024_2025.json').read_text())
    queue = json.loads((ROOT/'reports/coverage/company_queue.json').read_text())
    result = coverage_matrix(history, queue)
    assert len(result['target_years']) == 6
    assert len(result['companies']) >= 10
    dbs = next(x for x in result['companies'] if x['symbol'] == 'D05.SI')
    assert dbs['years']['2020']['status'] == 'missing'
    assert dbs['years']['2020']['fact_count'] == 0
    assert dbs['years']['2024']['fact_count'] > 0
    assert dbs['years']['2025']['fact_count'] > 0
    assert dbs['years']['2024']['human_review'] == 'pending'

def test_jardine_and_new_candidates_have_no_fake_facts():
    history = json.loads((ROOT/'reports/history/history_2024_2025.json').read_text())
    queue = json.loads((ROOT/'reports/coverage/company_queue.json').read_text())
    result = coverage_matrix(history, queue)
    for symbol in ['J36.SI','O39.SI','U11.SI','600519.SS','600036.SS']:
        row = next(x for x in result['companies'] if x['symbol'] == symbol)
        assert all(y['status'] == 'missing' and y['fact_count'] == 0 for y in row['years'].values())

def test_reject_invalid_years():
    with pytest.raises(ValueError): coverage_matrix({}, {}, 2025, 2020)

def test_coverage_file_roundtrip(tmp_path):
    result = create_coverage(ROOT/'reports/history/history_2024_2025.json', ROOT/'reports/coverage/company_queue.json', tmp_path/'matrix.json')
    assert json.loads((tmp_path/'matrix.json').read_text()) == result
