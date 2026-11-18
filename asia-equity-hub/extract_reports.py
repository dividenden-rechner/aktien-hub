"""Extract primary financial statement values from cached official annual reports.

Usage:
  python process_reports.py --download          # 1. download + cache PDFs (network)
  python extract_reports.py                     # 2. extract, check, cross-verify (offline)
  python extract_reports.py --symbol D05.SI --no-second-engine

Writes reports/extracted/<SYMBOL>_<FY>.json, summary_<FY>.json and VERIFIKATION_<FY>.md.
Exit code 1 if any report is not 'extracted_consistent' (useful in CI).
"""
import argparse
import json
import sys

from app.extraction_run import run_extraction

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--symbol', action='append')
    p.add_argument('--no-second-engine', action='store_true')
    p.add_argument('--no-write', action='store_true')
    args = p.parse_args()
    out = run_extraction(args.symbol, second_engine=not args.no_second_engine, write=not args.no_write)
    compact = [{'symbol': r['symbol'], 'status': r.get('status'),
                'errors': r.get('errors', []),
                'failed_checks': [c['name'] for c in r.get('checks', []) if c['status'] == 'fail'],
                'second_engine': r.get('second_engine', {}).get('summary'),
                'reference': [f"{x['field']}:{x['result']}" for x in r.get('reference_comparison', [])]}
               for r in out['results']]
    print(json.dumps({'summary': out['summary'], 'results': compact}, ensure_ascii=False, indent=2))
    sys.exit(0 if all(r.get('status') == 'extracted_consistent' for r in out['results']) else 1)
