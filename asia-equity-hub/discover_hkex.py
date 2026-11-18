"""CLI: print unverified annual-report candidates from HKEXnews."""
import argparse
import json
from app.hkex import discover_hkex

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('symbol', help='e.g. 0700.HK')
    parser.add_argument('year', type=int, help='fiscal year')
    args = parser.parse_args()
    print(json.dumps(discover_hkex(args.symbol, args.year), ensure_ascii=False, indent=2))
