"""Usage: python sync_reports.py 0700.HK [2025]"""
import json
import sys
from app.reports import sync_registered
if __name__ == '__main__':
    if len(sys.argv) not in (2,3):
        raise SystemExit('Usage: python sync_reports.py TICKER [YEAR]')
    print(json.dumps(sync_registered(sys.argv[1], int(sys.argv[2]) if len(sys.argv)==3 else None),indent=2))
