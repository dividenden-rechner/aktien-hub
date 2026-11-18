"""End-to-end report processing, preserving review boundaries.

No extracted PDF fact is silently promoted to a verified financial statement.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from .reports import ROOT, load_catalog, report_key, sync_report
from .table_financials import extract_year_tables
from .extract import candidates_from_pages
from .statement_metrics import calculate_reviewed

REFERENCE = ROOT / 'reference_ir_2025.json'
_UNIT_MULTIPLIER = {'units': 1, 'cents': Decimal('0.01'), 'thousand': 1000, 'million': 1000000, 'billion': 1000000000}


def _reference_rows(path: Path = REFERENCE) -> list[dict]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding='utf-8'))
    return data if isinstance(data, list) else data.get('facts', []) if isinstance(data, dict) else []


def _normalize_reference(rows: list[dict], symbol: str) -> list[dict]:
    """Only explicitly field-tagged reference facts can be compared.

    v1.1 fix: reference values may carry a ``unit`` (e.g. "million"); they are converted
    to currency units, because the table parser emits currency units. v1.0 compared
    millions with units, so every real comparison would have been a "mismatch".
    Rows flagged ``comparable_with_pdf_field: false`` are skipped.
    """
    out = []
    for r in rows:
        if not isinstance(r, dict) or r.get('symbol') != symbol:
            continue
        if not all(k in r for k in ('field', 'fiscal_year', 'currency', 'value')):
            continue
        if r.get('comparable_with_pdf_field') is False:
            continue
        try:
            value = Decimal(str(r['value'])) * Decimal(_UNIT_MULTIPLIER.get(r.get('unit', 'units'), 1))
        except (InvalidOperation, ValueError):
            continue
        out.append({**r, 'value': str(value)})
    return out


def compare_facts(candidates: list[dict], reference: list[dict], relative_tolerance: str = '0.005') -> list[dict]:
    """Compare matching field/year/currency; never auto-verify candidates."""
    refs = {(r['field'], r['fiscal_year'], r['currency']): r for r in reference}
    result = []
    tol = Decimal(relative_tolerance)
    for c in candidates:
        k = (c['field'], c['fiscal_year'], c['currency'])
        ref = refs.get(k)
        record = {'field': c['field'], 'fiscal_year': c['fiscal_year'], 'currency': c['currency'],
                  'extracted_value': c['value'], 'page': c.get('page'), 'source_url': c.get('source_url'),
                  'verification_status': 'requires_manual_review'}
        if ref is None:
            record['comparison'] = 'no_reference'
        else:
            a, b = Decimal(c['value']), Decimal(ref['value'])
            difference = abs(a - b)
            record['reference_value'] = str(b)
            record['reference_source'] = ref.get('source_url')
            record['comparison'] = 'within_tolerance' if difference <= tol * max(abs(b), Decimal('1')) else 'mismatch'
        result.append(record)
    return result


def process_cached(entry: dict, root: Path = ROOT, reference_rows: list[dict] | None = None) -> dict:
    key = report_key(entry)
    pages_path = root / 'cache' / f'{key}.pages.json'
    if not pages_path.is_file():
        return {'symbol': entry['symbol'], 'fiscal_year': entry['fiscal_year'], 'status': 'not_ingested',
                'source_url': entry['url'], 'report_id': key}
    pages = json.loads(pages_path.read_text(encoding='utf-8'))
    tables = extract_year_tables(pages, entry['url'])
    candidates = candidates_from_pages(pages)
    references = _normalize_reference(reference_rows if reference_rows is not None else _reference_rows(), entry['symbol'])
    comparisons = compare_facts(tables['facts'], references)
    result = {'symbol': entry['symbol'], 'fiscal_year': entry['fiscal_year'], 'report_id': key,
              'source_url': entry['url'], 'processed_at': datetime.now(timezone.utc).isoformat(),
              'status': 'requires_review', 'page_count_with_text': len(pages),
              'structured_candidates': tables['facts'], 'conflicts': tables['conflicts'],
              'rejected_rows': tables['rejected_rows'], 'reference_comparisons': comparisons,
              'text_candidate_counts': {k: len(v) for k, v in candidates['fields'].items()},
              'metrics': calculate_reviewed([]),
              'warning': 'No financial facts are auto-approved. Complex PDF layouts and consolidated vs segment statements need human review.'}
    output = root / 'review'
    output.mkdir(parents=True, exist_ok=True)
    (output / f'{key}.review.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return result


def run_pipeline(symbols: list[str] | None = None, download: bool = False, root: Path = ROOT) -> dict:
    results = []
    for entry in load_catalog():
        if symbols and entry['symbol'] not in symbols:
            continue
        if download:
            try:
                sync_report(entry)
            except Exception as exc:
                results.append({'symbol': entry['symbol'], 'status': 'download_failed',
                                'error_type': type(exc).__name__, 'message': str(exc)[:400]})
                continue
        results.append(process_cached(entry, root=root))
    return {'results': results, 'summary': {'total': len(results),
            'download_failed': sum(x['status'] == 'download_failed' for x in results),
            'not_ingested': sum(x['status'] == 'not_ingested' for x in results),
            'requires_review': sum(x['status'] == 'requires_review' for x in results)}}
