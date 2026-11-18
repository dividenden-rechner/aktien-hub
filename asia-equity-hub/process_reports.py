"""Download (optional) and pre-process all registered reports (5 issuers, FY2025).

For the verified statement values run `python extract_reports.py` afterwards.

Usage:
  python process_reports.py
  python process_reports.py --download
  python process_reports.py --download --symbol 0001.HK
"""
import argparse
import json
import logging
from app.report_pipeline import run_pipeline

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--download', action='store_true')
    p.add_argument('--symbol', action='append')
    args = p.parse_args()
    logging.getLogger('pypdf').setLevel(logging.ERROR)
    print(json.dumps(run_pipeline(args.symbol, download=args.download), ensure_ascii=False, indent=2))
