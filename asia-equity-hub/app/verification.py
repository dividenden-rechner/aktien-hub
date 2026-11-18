"""Independent verification of extracted values.

1. Second PDF engine: re-reads each cited page with pdfplumber (a different text
   extraction implementation than pypdf) and checks that the printed token appears
   on the same page - ideally on a line that also matches the row label.
2. Reference comparison: compares extracted values with secondary reference values
   (issuer IR web pages) that use the *same* field definition, currency and unit.

Neither step marks a value as "verified": only a human reviewer does that.
"""
from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

from .statement_extractor import split_row


def _core(token: str) -> str:
    return token.strip().strip('()').strip()


def second_engine_check(pdf_path: Path, facts: list[dict], label_patterns: dict[str, str] | None = None) -> dict:
    try:
        import pdfplumber  # optional dependency
    except ImportError:
        return {'engine': 'pdfplumber', 'status': 'unavailable', 'results': []}
    label_patterns = label_patterns or {}
    results = []
    page_cache: dict[int, list[str]] = {}
    with pdfplumber.open(str(pdf_path)) as pdf:
        for fact in facts:
            page = fact.get('pdf_page')
            if not isinstance(page, int):
                continue
            if page not in page_cache:
                text = pdf.pages[page - 1].extract_text() or ''
                page_cache[page] = [' '.join(line.split()) for line in text.splitlines()]
            lines = page_cache[page]
            token = fact.get('raw_token') or fact.get('value')
            if token is None:
                continue
            core = _core(token)
            # Text-regex values (e.g. "0.710") may be printed with other precision; also try value.
            candidates = {core}
            if fact.get('method') == 'text_regex':
                candidates.add(_core(fact['value']))
                try:
                    candidates.add(f"{Decimal(fact['value']):.2f}")
                except Exception:  # pragma: no cover
                    pass
            pattern = label_patterns.get(fact['field'])
            label_re = re.compile(pattern, re.I) if pattern and pattern != '^$' else None
            status = 'not_found'
            for line in lines:
                if not any(re.search(r'(?<![\d,.])' + re.escape(c) + r'(?![\d,]|\.\d)', line) for c in candidates):
                    continue
                if label_re is None:
                    status = 'token_on_page'
                    if fact.get('method') == 'text_regex':
                        break
                    continue
                label_text = split_row(line).label
                if label_re.search(label_text):
                    status = 'row_confirmed'
                    break
                status = 'token_on_page'
            results.append({'field': fact['field'], 'pdf_page': page, 'token': token, 'status': status})
    summary = {s: sum(1 for r in results if r['status'] == s) for s in ('row_confirmed', 'token_on_page', 'not_found')}
    return {'engine': 'pdfplumber', 'status': 'ok' if not summary['not_found'] else 'discrepancies',
            'summary': summary, 'results': results}


def compare_with_reference(facts: dict[str, dict], references: list[dict], symbol: str, fiscal_year: int) -> list[dict]:
    out = []
    for ref in references:
        if ref.get('symbol') != symbol or ref.get('fiscal_year') != fiscal_year:
            continue
        fact = facts.get(ref['field'])
        row = {'field': ref['field'], 'reference_value': ref['value'], 'reference_unit': ref.get('unit'),
               'reference_currency': ref.get('currency'), 'reference_source': ref.get('source_url'),
               'reference_rechecked_on': ref.get('rechecked_on')}
        if not ref.get('comparable_with_pdf_field', True):
            row['result'] = 'not_comparable'
            row['note'] = ref.get('definition')
        elif fact is None or fact.get('value') is None:
            row['result'] = 'no_extracted_value'
        elif fact.get('unit') != ref.get('unit') or fact.get('currency') != ref.get('currency'):
            row['result'] = 'unit_or_currency_mismatch'
            row['extracted_value'] = fact['value']
        else:
            a, b = Decimal(fact['value']), Decimal(ref['value'])
            row['extracted_value'] = fact['value']
            row['difference'] = str(a - b)
            row['result'] = 'match' if a == b else 'mismatch'
            row['pdf_page'] = fact.get('pdf_page')
        out.append(row)
    return out
