import json
from pathlib import Path
import pytest
from app.history import comparative_history, build_history

ROOT = Path(__file__).resolve().parents[1]

@pytest.mark.parametrize('symbol,field,expected', [
    ('D05.SI', 'revenue', '22297'),
    ('0019.HK', 'revenue', '81969'),
    ('0001.HK', 'revenue', '281351'),
    ('0142.HK', 'revenue', '10057.2'),
    ('002594.SZ', 'revenue', '777102455'),
])
def test_prior_year_from_original_evidence(symbol, field, expected):
    report = json.loads((ROOT / 'reports/extracted' / f'{symbol}_2025.json').read_text())
    result = comparative_history(report)
    found = {f['field']: f for f in result['facts']}
    assert found[field]['value'] == expected
    assert found[field]['fiscal_year'] == 2024
    assert found[field]['pdf_page'] > 0
    assert result['human_review'] == 'pending'

def test_no_guess_when_comparative_absent():
    r = json.loads((ROOT / 'reports/extracted/D05.SI_2025.json').read_text())
    r['facts'][0].pop('row_values')
    output = comparative_history(r)
    assert 'revenue' not in {x['field'] for x in output['facts']}
    assert any(x['field'] == 'revenue' for x in output['omitted'])

def test_reject_bad_source():
    r = json.loads((ROOT / 'reports/extracted/D05.SI_2025.json').read_text())
    r['pdf_sha256_status'] = 'mismatch'
    with pytest.raises(ValueError): comparative_history(r)

def test_jardine_not_pretended_extracted():
    queue = json.loads((ROOT / 'reports/coverage/company_queue.json').read_text())
    j = queue['companies'][0]
    assert j['symbol'] == 'J36.SI'
    assert j['pdf_sha256'] is None and j['extraction_profile'] is None
    assert j['human_review'] == 'pending'

def test_build_history_five_companies():
    result = build_history(ROOT / 'reports/extracted')
    assert len(result['companies']) == 5
    assert all('2024' in x['years'] and '2025' in x['years'] for x in result['companies'])
