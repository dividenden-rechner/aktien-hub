"""Build 2016-2025 histories from ten-year summaries in the pinned FY2025 reports (v1.6).

Usage: python process_reports.py --download   (once, to cache the PDFs)
       python build_ten_year_history.py [--no-second-engine]
Writes reports/history/ten_year_2016_2025.json. Exit code 1 if any issuer is not consistent.
"""
import argparse
import json
import logging
import sys
from datetime import datetime, timezone

from app.multi_year import build_history, load_multi_year_profile, mark_comparability, merge_reports
from app.reports import ROOT, cached_pages, cached_pdf, load_catalog
from app.statement_extractor import sha256_file
from app.verification import second_engine_check

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--no-second-engine', action='store_true')
    args = p.parse_args()
    logging.getLogger('pypdf').setLevel(logging.ERROR)
    catalog = {e['url']: e for e in load_catalog()}  # v1.8: several reports per issuer -> match by URL
    out = []
    for path in sorted((ROOT / 'profiles_history').glob('*.json')):
        prof = load_multi_year_profile(path)
        entry = catalog[prof['source_url']]
        pages, pdf = cached_pages(entry), cached_pdf(entry)
        if pages is None or pdf is None:
            out.append({'symbol': prof['symbol'], 'status': 'not_ingested'})
            continue
        single_path = ROOT / 'extracted' / f"{prof['symbol']}_{prof['source_report_year']}.json"
        single = json.loads(single_path.read_text(encoding='utf-8')) if single_path.is_file() else None
        res = build_history(pages, prof, sha256_file(pdf), single)
        if not args.no_second_engine:
            labels = {f['field']: f['label'] for f in prof['fields']}
            res['second_engine'] = second_engine_check(pdf, res['facts'], labels)
            res['second_engine'].pop('results', None)  # keep file compact; summary only
        out.append(mark_comparability(res, prof))
    now = datetime.now(timezone.utc).isoformat()
    latest = [r for r in out if r.get('source_report_year') == 2025]
    doc = {'generated_at': now, 'scope': 'FY2016-FY2025 from ten-year summaries', 'issuers': latest}
    (ROOT / 'history').mkdir(exist_ok=True)
    (ROOT / 'history' / 'ten_year_2016_2025.json').write_text(json.dumps(doc, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    by_symbol = {}
    for r in out:
        if 'facts' in r:
            by_symbol.setdefault(r['symbol'], []).append(r)
    merged = [merge_reports(sym, rs) for sym, rs in sorted(by_symbol.items())]
    (ROOT / 'history' / 'ten_year_merged.json').write_text(json.dumps(
        {'generated_at': now, 'scope': 'all registered ten-year summaries merged (newest report wins)', 'issuers': merged},
        ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    for m in merged:
        print('MERGED', m['symbol'], m['status'], 'years', m['years'][0], '-', m['years'][-1], 'facts', len(m['facts']),
              'restatements', len(m['restatements']))
    for r in out:
        print(r['symbol'], r['status'], 'facts', len(r.get('facts', [])), 'errors', r.get('errors'),
              'checks_failed', [c for c in r.get('checks', []) if c['status'] == 'fail'][:3],
              'cross', [(c['field'], c['result']) for c in r.get('cross_check_latest', []) if c['result'] != 'match'],
              'engine', r.get('second_engine', {}).get('summary'))
    sys.exit(0 if all(r['status'] == 'extracted_consistent' for r in out) else 1)
