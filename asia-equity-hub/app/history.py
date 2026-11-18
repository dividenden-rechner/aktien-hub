"""Conservative FY2024 comparative extraction from FY2025 report evidence.

No PDFs or values are fabricated. Only explicit table tokens already captured by the
v1.1 profile extractor are eligible; source report year and column are retained.
"""
from __future__ import annotations

import json
from pathlib import Path
from .statement_extractor import parse_amount, _fmt, _scale

# The 2025 profiles have been checked for column order. Special layouts are
# explicitly named instead of guessing from column counts.
COMPARATIVE_COLUMNS = {
    '0001.HK': {'default': 1},
    '0019.HK': {'default': 1, 'dividend_per_share_ten_year': 8},
    '0142.HK': {'default': 1},
    'D05.SI': {'default': 1, 'dividend_per_share': 1},
    '002594.SZ': {'default': 1},
}


def comparative_history(report: dict, year: int = 2024) -> dict:
    if report.get('fiscal_year') != year + 1:
        raise ValueError('Only immediate prior-year comparatives from the FY2025 report are supported')
    symbol = report['symbol']
    if symbol not in COMPARATIVE_COLUMNS:
        raise ValueError(f'No explicit comparative-column mapping for {symbol}')
    if report.get('status') != 'extracted_consistent' or report.get('pdf_sha256_status') != 'match':
        raise ValueError('Source report must be consistent and match its pinned PDF hash')
    facts, omitted = [], []
    for fact in report['facts']:
        field = fact['field']
        tokens = fact.get('row_values')
        if fact.get('method') != 'table_row' or not isinstance(tokens, list):
            omitted.append({'field': field, 'reason': 'no_comparative_table_row'})
            continue
        idx = COMPARATIVE_COLUMNS[symbol].get(field, COMPARATIVE_COLUMNS[symbol]['default'])
        if idx >= len(tokens) or idx == fact.get('column_index'):
            omitted.append({'field': field, 'reason': 'comparative_column_unavailable'})
            continue
        try:
            amount = parse_amount(tokens[idx])
        except ValueError:
            omitted.append({'field': field, 'reason': 'invalid_comparative_token'})
            continue
        if amount is None:
            omitted.append({'field': field, 'reason': 'blank_comparative_value'})
            continue
        if fact.get('unit') not in ('cents', 'units', 'thousand', 'million', 'billion'):
            omitted.append({'field': field, 'reason': 'unsupported_unit'})
            continue
        # A positive capex or dividend outflow in 2025 may be normalized via
        # profile sign='abs'. Do not silently change the 2024 sign.
        value = abs(amount) if fact.get('value') and fact.get('raw_token', '').startswith('(') and not str(fact['value']).startswith('-') else amount
        facts.append({
            'field': field, 'value': _fmt(value), 'value_in_units': _fmt(_scale(value, fact['unit'])),
            'currency': fact['currency'], 'unit': fact['unit'], 'fiscal_year': year,
            'source_report_year': report['fiscal_year'], 'source_url': fact['source_url'],
            'pdf_sha256': report['pdf_sha256'], 'pdf_page': fact['pdf_page'],
            'printed_page': fact.get('printed_page'), 'evidence': fact.get('evidence'),
            'raw_token': tokens[idx], 'column_index': idx, 'row_values': tokens,
            'method': 'comparative_table_column', 'verification_status': 'machine_extracted',
        })
    return {
        'symbol': symbol, 'company': report.get('company'), 'fiscal_year': year,
        'source_report_year': report['fiscal_year'], 'source_url': report['source_url'],
        'currency': report['currency'], 'unit': report['unit'],
        'status': 'comparative_extracted_pending_review', 'human_review': 'pending',
        'facts': facts, 'omitted': omitted,
        'warning': 'Comparative column from FY2025 PDF; not independently checked against FY2024 annual report or a second PDF engine.',
    }


def build_history(directory: Path) -> dict:
    companies = []
    for path in sorted(directory.glob('*_2025.json')):
        report = json.loads(path.read_text(encoding='utf-8'))
        if 'facts' not in report:
            continue
        previous = comparative_history(report)
        current = [{k: f.get(k) for k in ('field', 'value', 'currency', 'unit', 'pdf_page', 'source_url', 'verification_status')}
                   for f in report['facts'] if f.get('value') is not None]
        companies.append({'symbol': report['symbol'], 'company': report.get('company'),
                          'years': {'2024': previous, '2025': {
                              'fiscal_year': 2025, 'status': report['status'],
                              'human_review': (report.get('manual_review') or {}).get('human_review', 'pending'),
                              'facts': current}}})
    return {'schema_version': 1, 'companies': companies,
            'note': '2024 comparative figures from 2025 reports, not independently verified; no currency conversion.'}
