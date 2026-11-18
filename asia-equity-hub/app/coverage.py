"""Evidence-based fiscal-year coverage; missing years are never synthetic facts."""
from __future__ import annotations
import json
from pathlib import Path


def coverage_matrix(history: dict, queue: dict, start_year: int = 2020, end_year: int = 2025, official_histories: list[dict] | None = None) -> dict:
    if not 1900 <= start_year <= end_year <= 2100:
        raise ValueError('Invalid fiscal-year range')
    indexed = {x['symbol']: x for x in history.get('companies', [])}
    rows = []
    for symbol, company in sorted(indexed.items()):
        years = {}
        for year in range(start_year, end_year + 1):
            source = company.get('years', {}).get(str(year))
            facts = source.get('facts', []) if source else []
            years[str(year)] = {
                'status': 'machine_extracted_pending_human_review' if facts else 'missing',
                'fact_count': len(facts),
                'source_report_year': source.get('source_report_year', year) if facts else None,
                'human_review': 'pending',
            }
        rows.append({'symbol': symbol, 'company': company.get('company'), 'onboarding_status': 'has_extracted_data', 'years': years})
    for candidate in queue.get('companies', []):
        symbol = candidate['symbol']
        if symbol in indexed:
            continue
        rows.append({'symbol': symbol, 'company': candidate['company'],
                     'onboarding_status': candidate.get('status', 'candidate_not_imported'),
                     'years': {str(y): {'status': 'missing', 'fact_count': 0, 'source_report_year': None,
                                        'human_review': 'pending'} for y in range(start_year, end_year + 1)}})
    for issuer in official_histories or []:
        from .official_history import validate_official_history
        validate_official_history(issuer)
        row = next((r for r in rows if r['symbol'] == issuer['symbol']), None)
        if row is None:
            raise ValueError('Official history issuer missing from tracked company queue')
        for year in range(start_year, end_year + 1):
            count = sum(f['fiscal_year'] == year for f in issuer['facts'])
            if count and row['years'][str(year)]['status'] == 'missing':
                row['years'][str(year)] = {
                    'status': 'issuer_web_transcribed_pending_pdf_review',
                    'fact_count': count, 'source_report_year': 2025, 'human_review': 'pending',
                }
    rows.sort(key=lambda r: r['symbol'])
    return {'schema_version': 1, 'target_years': list(range(start_year, end_year + 1)),
            'companies': rows, 'human_review': 'pending',
            'note': 'Coverage is evidence-based. Missing is not zero. No year is human-verified.'}


def create_coverage(history_path: Path, queue_path: Path, out: Path, start_year: int = 2020, end_year: int = 2025) -> dict:
    history = json.loads(history_path.read_text(encoding='utf-8'))
    queue = json.loads(queue_path.read_text(encoding='utf-8'))
    from .official_history import load_official_history
    issuer_path = history_path.parent / 'jardine_issuer_web_2021_2025.json'
    official = [load_official_history(issuer_path)] if issuer_path.exists() else []
    result = coverage_matrix(history, queue, start_year, end_year, official)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return result
