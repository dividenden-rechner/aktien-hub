"""Unit tests for the profile-based statement extractor.

Text fixtures are short excerpts copied verbatim from the pypdf text of the real
FY2025 annual reports (page numbers in comments), so the tests exercise the
actual layouts: convenience-currency columns, unlabeled subtotals, wrapped labels,
Chinese labels with "( 1,234 )" negatives, footnote markers and two-page spreads.
"""
from decimal import Decimal

import pytest

from app.statement_extractor import (
    ExtractionError, extract_field, extract_report, extract_text_value, find_row, key_ratios,
    parse_amount, printed_page, split_row,
)

# CK Hutchison, PDF page 134 (US$ convenience column first, HK$ 2025/2024/2023 after)
CKH_IS = """Consolidated Income Statement
for the year ended 31 December 2025
2025 # 2025 2024 2023
US$ million Note HK$ million HK$ million HK$ million
 35,902 Revenue 5  280,036  281,351  275,575
 3,412 Profit before tax  26,607  28,570  33,554
2,483 Profit after tax  19,370  23,853  30,551
(965)
Profit attributable to non-controlling interests and
holders of perpetual capital securities  (7,529)  (6,765)  (6,712)
1,518 Profit attributable to ordinary shareholders  11,841  17,088  23,839
US$ 0.40
Earnings per share for profit attributable to ordinary
shareholders 11 HK$ 3.09 HK$ 4.46 HK$ 6.22
"""

# Swire Pacific, PDF page 149 (subtotals without labels)
SWIRE_BS = """31st December 2025 HK$M 31st December 2024 HK$M
 Deferred tax assets 32 1,009 711
 Retirement benefit assets 33 294 146
416,475 417,175
Current assets
 Bank balances and short-term deposits 27 23,172 21,028
59,938 54,364
 Assets classified as held for sale 28 – 5,022
59,938 59,386
"""

# BYD, PDF page 126 (Chinese labels, "(649,350 )" negatives)
BYD_IS = """  附注七  2025 年   2024 年
一、 营业收入 45  803,964,958     777,102,455
 财务费用 50  (649,350 )   1,216,206
四、 净利润   33,760,758     41,587,940
 持续经营净利润   33,760,758   41,587,940
 基本每股收益 60  3.58   4.61
"""

# DBS, PDF page 58 (income statement and OCI on one spread; repeated labels)
DBS_IS = """In $ millions Note 2025 2024
Net profit 10,934 11,290
Attributable to:
Shareholders of the parent 10,933 11,289
Non-controlling interests 1 1
In $ millions 2025 2024
Net profit 10,934 11,290
Attributable to:
Shareholders of the parent 10,770 12,860
Non-controlling interests (1) –
"""


@pytest.mark.parametrize('token,expected', [
    ('280,036', Decimal('280036')), ('(7,529)', Decimal('-7529')), ('10,232.5', Decimal('10232.5')),
    ('3.09', Decimal('3.09')), ('-12', Decimal('-12')), ('–', None), ('-', None),
])
def test_parse_amount(token, expected):
    assert parse_amount(token) == expected


@pytest.mark.parametrize('token', ['43(b)', 'HK$', '5%', '(Note', 'abc'])
def test_parse_amount_rejects_non_amounts(token):
    with pytest.raises(ValueError):
        parse_amount(token)


def test_split_row_strips_leading_convenience_column_and_note():
    row = split_row(' 35,902 Revenue 5  280,036  281,351  275,575')
    assert row.label == 'Revenue'
    assert row.amounts[-3:] == ['280,036', '281,351', '275,575']


def test_split_row_handles_chinese_spaced_parentheses():
    row = split_row(' 财务费用 50  (649,350 )   1,216,206')
    assert row.label == '财务费用'
    assert row.amounts[-2:] == ['(649,350)', '1,216,206']


def test_split_row_removes_currency_prefix_and_letter_note_refs():
    assert split_row('shareholders 11 HK$ 3.09 HK$ 4.46 HK$ 6.22').amounts[-3:] == ['3.09', '4.46', '6.22']
    row = split_row(' Purchase of property, plant and equipment and right-of-use assets 43(b) (5,595) (4,411)')
    assert row.label == 'Purchase of property, plant and equipment and right-of-use assets'
    assert split_row('Distributions paid to shareholders 33(I) (144.6) (133.2)').label == 'Distributions paid to shareholders'


def test_footnote_marker_is_not_taken_as_a_value_column():
    # DBS cash flow: "(1)" is a footnote reference; only the last two tokens are values.
    row = split_row('Net cash generated from operating activities (1) 11,024 15,341')
    assert row.amounts[-2:] == ['11,024', '15,341']


def test_wrapped_label_is_joined():
    row = find_row(CKH_IS, r'^Profit attributable to non-controlling interests and holders of perpetual capital securities$', 3)
    assert row.amounts[-3:] == ['(7,529)', '(6,765)', '(6,712)']


def test_exact_label_does_not_match_longer_label():
    row = find_row(BYD_IS, r'^四、\s*净利润$', 2)
    assert row.amounts[-2:] == ['33,760,758', '41,587,940']


def test_ambiguous_label_is_rejected_not_guessed():
    with pytest.raises(ExtractionError) as exc:
        find_row(DBS_IS, r'^Shareholders of the parent$', 2)
    assert exc.value.reason == 'ambiguous_label'
    assert find_row(DBS_IS, r'^Shareholders of the parent$', 2, occurrence=1).amounts == ['10,933', '11,289']


def test_identical_repeated_rows_are_not_ambiguous():
    assert find_row(DBS_IS, r'^Net profit$', 2).amounts == ['10,934', '11,290']


def test_unlabeled_subtotal_via_anchor():
    assert find_row(SWIRE_BS, r'^$', 2, after='Retirement benefit assets').amounts == ['416,475', '417,175']
    assert find_row(SWIRE_BS, r'^$', 2, after='Assets classified as held for sale').amounts == ['59,938', '59,386']


def test_missing_label_and_anchor_raise():
    with pytest.raises(ExtractionError) as exc:
        find_row(SWIRE_BS, r'^Goodwill$', 2)
    assert exc.value.reason == 'label_not_found'
    with pytest.raises(ExtractionError) as exc:
        find_row(SWIRE_BS, r'^$', 2, after='Nonexistent anchor')
    assert exc.value.reason == 'anchor_not_found'


def test_text_value_keeps_printed_precision():
    value, line, evidence, printed = extract_text_value(
        'Interim dividend, paid of HK$0.710 per share\n', r'Interim dividend, paid of HK\$([\d.]+) per share')
    assert value == Decimal('0.710') and printed == '0.710' and line == 1


def test_printed_page_rules():
    assert printed_page({'printed_page_rule': {'offset': -2}}, 134) == '132'
    assert printed_page({'printed_page_rule': {'offset': -4, 'spread': True}}, 58) == '112-113'
    assert printed_page({}, 10) is None
    assert printed_page({'printed_page_rule': {'offset': -2}}, 1) is None


def _mini_profile(**overrides):
    profile = {
        'symbol': '0001.HK', 'fiscal_year': 2025, 'period_end': '2025-12-31', 'currency': 'HKD', 'unit': 'million',
        'source_url': 'https://doc.irasia.com/x.pdf', 'printed_page_rule': {'offset': -2},
        'statements': {'income': {'header_regex': r'2025 # 2025 2024 2023'}},
        'fields': [
            {'field': 'revenue', 'page': 1, 'label': r'^Revenue$', 'columns': 3, 'column': 0, 'statement': 'income'},
            {'field': 'net_profit', 'page': 1, 'label': r'^Profit after tax$', 'columns': 3, 'statement': 'income'},
            {'field': 'nci_profit', 'page': 1, 'label': r'^Profit attributable to non-controlling interests and holders of perpetual capital securities$',
             'columns': 3, 'statement': 'income', 'sign': 'abs'},
            {'field': 'net_income_attributable', 'page': 1, 'label': r'^Profit attributable to ordinary shareholders$', 'columns': 3, 'statement': 'income'},
            {'field': 'eps_basic', 'page': 1, 'label': r'^Earnings per share', 'columns': 3, 'statement': 'income', 'unit': 'units'},
        ],
        'checks': [{'name': 'profit_split', 'left': ['net_profit'], 'right': ['net_income_attributable', 'nci_profit'], 'tolerance': '1'}],
    }
    profile.update(overrides)
    return profile


def test_extract_report_end_to_end_with_provenance():
    result = extract_report([CKH_IS], _mini_profile(), pdf_sha256='abc')
    assert result['status'] == 'extracted_consistent'
    facts = {f['field']: f for f in result['facts']}
    assert facts['revenue']['value'] == '280036'
    assert facts['revenue']['value_in_units'] == '280036000000'
    assert facts['revenue']['pdf_page'] == 1 and facts['revenue']['printed_page'] is None  # cover page
    assert facts['revenue']['verification_status'] == 'machine_extracted'
    assert facts['nci_profit']['value'] == '7529'
    assert facts['eps_basic']['value'] == '3.09' and facts['eps_basic']['unit'] == 'units'
    assert result['checks'][0]['status'] == 'pass'


def test_wrong_column_header_is_rejected():
    profile = _mini_profile(statements={'income': {'header_regex': r'2026 2025'}})
    result = extract_report([CKH_IS], profile)
    assert result['status'] == 'extraction_incomplete'
    assert {e['reason'] for e in result['errors']} == {'column_header_not_found'}


def test_failed_consistency_check_changes_status():
    profile = _mini_profile(checks=[{'name': 'bad', 'left': ['revenue'], 'right': ['net_profit'], 'tolerance': '1'}])
    assert extract_report([CKH_IS], profile)['status'] == 'consistency_check_failed'


def test_changed_document_is_flagged():
    result = extract_report([CKH_IS], _mini_profile(pdf_sha256='expected'), pdf_sha256='other')
    assert result['status'] == 'document_changed'


def test_page_out_of_range():
    spec = {'field': 'x', 'page': 5, 'label': 'Revenue', 'columns': 3}
    with pytest.raises(ExtractionError) as exc:
        extract_field([CKH_IS], spec, _mini_profile())
    assert exc.value.reason == 'page_out_of_range'


def test_ratios_respect_units_and_exclusions():
    facts = {
        'net_income_attributable': {'value': '100', 'unit': 'million', 'currency': 'HKD'},
        'revenue': {'value': '1000', 'unit': 'million', 'currency': 'HKD'},
        'dividend_per_share': {'value': '27.0', 'unit': 'cents', 'currency': 'HKD'},
        'eps_basic': {'value': '15.53', 'unit': 'cents', 'currency': 'USD'},
    }
    ratios = key_ratios(facts, {'ratios_not_meaningful': ['operating_margin']})
    assert ratios['net_margin']['value'] == '0.1000'
    assert ratios['payout_ratio_per_share']['value'] is None  # HKD vs USD: never mixed
    assert ratios['operating_margin']['note'] == 'not meaningful for this issuer'
