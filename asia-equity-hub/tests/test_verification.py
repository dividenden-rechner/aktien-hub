from app.verification import compare_with_reference

REFS = [
    {'symbol': '0019.HK', 'fiscal_year': 2025, 'field': 'revenue', 'value': '90467', 'unit': 'million', 'currency': 'HKD'},
    {'symbol': '0019.HK', 'fiscal_year': 2025, 'field': 'net_debt', 'value': '65000', 'unit': 'million', 'currency': 'HKD'},
    {'symbol': '0019.HK', 'fiscal_year': 2025, 'field': 'eps_basic', 'value': '2.17', 'unit': 'units', 'currency': 'HKD'},
    {'symbol': '0019.HK', 'fiscal_year': 2025, 'field': 'x', 'value': '1', 'unit': 'million', 'currency': 'HKD',
     'comparable_with_pdf_field': False},
    {'symbol': '0001.HK', 'fiscal_year': 2025, 'field': 'revenue', 'value': '1', 'unit': 'million', 'currency': 'HKD'},
]


def test_reference_comparison_outcomes():
    facts = {'revenue': {'value': '90467', 'unit': 'million', 'currency': 'HKD', 'pdf_page': 147},
             'net_debt': {'value': '65264', 'unit': 'million', 'currency': 'HKD'},
             'eps_basic': {'value': '217', 'unit': 'cents', 'currency': 'HKD'}}
    out = {r['field']: r['result'] for r in compare_with_reference(facts, REFS, '0019.HK', 2025)}
    assert out == {'revenue': 'match', 'net_debt': 'mismatch', 'eps_basic': 'unit_or_currency_mismatch',
                   'x': 'not_comparable'}
