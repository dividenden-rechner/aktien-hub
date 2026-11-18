"""Resolve tickers and official identifiers for the requested universe (v1.6).

Usage:
  python build_identity_map.py --download   # fetch the 5 official lists (free), then resolve
  python build_identity_map.py              # resolve from previously downloaded lists
Writes reports/universe/identity_map.json. companies.json is not modified.
"""
import argparse
import json
from datetime import datetime, timezone

import httpx

from app.identity import OFFICIAL_LISTS, build_identity_map, load_official_lists
from app.reports import ROOT

FOLDER = ROOT / 'universe' / 'official_lists'
UA = 'Mozilla/5.0 (compatible; AsiaEquityHub/1.6; official-list research)'

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--download', action='store_true')
    a = p.parse_args()
    FOLDER.mkdir(parents=True, exist_ok=True)
    retrieved = {}
    if a.download:
        with httpx.Client(timeout=180, follow_redirects=True, headers={'User-Agent': UA}) as c:
            for key, info in OFFICIAL_LISTS.items():
                r = c.get(info['url'])
                r.raise_for_status()
                (FOLDER / info['file']).write_bytes(r.content)
                retrieved[key] = datetime.now(timezone.utc).isoformat()
    lists = load_official_lists(FOLDER)
    for key, ts in retrieved.items():
        lists['meta'][key]['retrieved_at'] = ts
    universe = json.loads((ROOT / 'universe' / 'companies.json').read_text(encoding='utf-8'))
    candidates = json.loads((ROOT / 'universe' / 'ticker_candidates.json').read_text(encoding='utf-8'))
    result = build_identity_map(universe, candidates, lists)
    result['generated_at'] = datetime.now(timezone.utc).isoformat()
    (ROOT / 'universe' / 'identity_map.json').write_text(json.dumps(result, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(json.dumps(result['counts'], ensure_ascii=False, indent=1))
