"""Multi-year (e.g. ten-year summary) extraction from an already pinned annual-report PDF.

v1.6. Reuses the v1.1 row parser (`find_row`). A multi-year profile names the page,
the row label and the fiscal year of every column. Each extracted value becomes one
fact per fiscal year with page/line provenance. Nothing is guessed:

* the column header must be present on the page (``header_regex``),
* a row must have exactly the configured number of value columns,
* per-year arithmetic checks run on the extracted values,
* the latest year is compared with the independently extracted single-year values
  (reports/extracted/<SYMBOL>_<FY>.json),
* values are ``machine_extracted``; human review stays ``pending``.

Figures in a ten-year summary of a later report can be restated or re-presented
(e.g. new accounting standards); they are NOT automatically identical to the figures
originally published for that year. Every fact therefore records
``source_report_year`` and ``presentation_note``.
"""
from __future__ import annotations

import json
import re
from decimal import Decimal
from pathlib import Path

from .statement_extractor import ExtractionError, _fmt, find_row, parse_amount, printed_page


def extract_multi_year(pages: list[str], profile: dict) -> dict:
    facts: list[dict] = []
    errors: list[dict] = []
    tables = {t['id']: t for t in profile['tables']}
    for spec in profile['fields']:
        table = tables[spec['table']]
        page_no = table['page']
        text = pages[page_no - 1] if 1 <= page_no <= len(pages) else ''
        if not re.search(table['header_regex'], ' '.join(text.split())):
            errors.append({'field': spec['field'], 'pdf_page': page_no, 'reason': 'column_header_not_found'})
            continue
        years = table['years']
        try:
            row = find_row(text, spec['label'], len(years), after=spec.get('after'),
                           occurrence=spec.get('occurrence'), after_occurrence=spec.get('after_occurrence', 1))
        except ExtractionError as exc:
            errors.append({'field': spec['field'], 'pdf_page': page_no, 'reason': exc.reason, **exc.detail})
            continue
        tokens = row.amounts[-len(years):]
        for year, token in zip(years, tokens):
            value = parse_amount(token)
            facts.append({
                'field': spec['field'], 'fiscal_year': year, 'value': _fmt(value), 'raw_token': token,
                'currency': spec.get('currency', profile['currency']), 'unit': spec.get('unit', profile['unit']),
                'definition': spec.get('definition'), 'pdf_page': page_no,
                'printed_page': printed_page(profile, page_no), 'line': row.line_no, 'evidence': row.raw[:300],
                'source_url': profile['source_url'], 'source_report_year': profile['source_report_year'],
                'presentation_note': table.get('presentation_notes', {}).get(str(year)),
                'method': 'multi_year_table_row', 'verification_status': 'machine_extracted',
            })
    return {'facts': facts, 'errors': errors}


def _by_year(facts: list[dict]) -> dict[int, dict[str, dict]]:
    out: dict[int, dict[str, dict]] = {}
    for f in facts:
        out.setdefault(f['fiscal_year'], {})[f['field']] = f
    return out


def _sum(terms, row) -> Decimal | None:
    total = Decimal(0)
    for t in terms:
        sign = -1 if t.startswith('-') else 1
        f = row.get(t.lstrip('+-'))
        if f is None:
            return None
        total += sign * (Decimal(f['value']) if f['value'] is not None else Decimal(0))
    return total


def run_year_checks(facts: list[dict], checks: list[dict]) -> list[dict]:
    results = []
    for year, row in sorted(_by_year(facts).items()):
        for c in checks:
            left, right = _sum(c['left'], row), _sum(c['right'], row)
            tol = Decimal(str(c.get('tolerance', '1')))
            status = 'not_evaluated' if left is None or right is None else ('pass' if abs(left - right) <= tol else 'fail')
            results.append({'name': c['name'], 'fiscal_year': year, 'status': status,
                            'left_value': _fmt(left), 'right_value': _fmt(right)})
    return results


def cross_check_latest(facts: list[dict], single_year: dict | None, mapping: dict[str, str]) -> list[dict]:
    """Compare the latest-year multi-year values with the separately extracted statement values."""
    if not single_year:
        return []
    fy = single_year['fiscal_year']
    sy = {f['field']: f for f in single_year.get('facts', []) + single_year.get('derived', [])}
    mine = _by_year(facts).get(fy, {})
    out = []
    for field, other in mapping.items():
        a, b = mine.get(field), sy.get(other)
        if a is None or b is None or a['value'] is None or b.get('value') is None:
            out.append({'field': field, 'fiscal_year': fy, 'result': 'not_comparable'})
            continue
        same_unit = a['unit'] == b['unit'] and a['currency'] == b['currency']
        out.append({'field': field, 'fiscal_year': fy, 'statement_field': other,
                    'multi_year_value': a['value'], 'statement_value': b['value'],
                    'statement_pdf_page': b.get('pdf_page'),
                    'result': ('match' if Decimal(a['value']) == Decimal(b['value']) else 'mismatch') if same_unit
                    else 'unit_or_currency_mismatch'})
    return out


def build_history(pages: list[str], profile: dict, pdf_sha256: str | None, single_year: dict | None) -> dict:
    extracted = extract_multi_year(pages, profile)
    checks = run_year_checks(extracted['facts'], profile.get('checks', []))
    cross = cross_check_latest(extracted['facts'], single_year, profile.get('cross_check_latest', {}))
    sha_ok = pdf_sha256 is not None and pdf_sha256 == profile.get('pdf_sha256')
    if not sha_ok:
        status = 'document_changed_or_unverified'
    elif extracted['errors']:
        status = 'extraction_incomplete'
    elif any(c['status'] == 'fail' for c in checks) or any(c['result'] == 'mismatch' for c in cross):
        status = 'consistency_check_failed'
    else:
        status = 'extracted_consistent'
    years = sorted({f['fiscal_year'] for f in extracted['facts']})
    return {'symbol': profile['symbol'], 'company': profile.get('company'), 'source_url': profile['source_url'],
            'source_report_year': profile['source_report_year'], 'pdf_sha256': pdf_sha256,
            'pdf_sha256_status': 'match' if sha_ok else 'mismatch_or_missing', 'currency': profile['currency'],
            'unit': profile['unit'], 'years': years, 'status': status, 'facts': extracted['facts'],
            'errors': extracted['errors'], 'checks': checks, 'cross_check_latest': cross,
            'human_review': 'pending', 'caveats': profile.get('caveats', []),
            'warning': ('Ten-year summary figures as presented in the latest report; earlier years may be restated '
                        'and can differ from the originally published annual reports.')}


def load_multi_year_profile(path: Path) -> dict:
    profile = json.loads(path.read_text(encoding='utf-8'))
    for key in ('symbol', 'source_url', 'source_report_year', 'currency', 'unit', 'tables', 'fields'):
        if key not in profile:
            raise ValueError(f'{path.name}: missing {key}')
    for t in profile['tables']:
        if len(set(t['years'])) != len(t['years']):
            raise ValueError(f'{path.name}: duplicate years in table {t["id"]}')
    return profile
