"""Augment identity_map.json and annual_report_sources.json with OpenDART (Korea) and EDINET (Japan).

Needs the free API keys as environment variables (GitHub Actions secrets in aktien-hub):
  DART_API_KEY    -> confirm 73 Korean tickers + list 사업보고서 2016-2025
  EDINET_API_KEY  -> list 有価証券報告書 2016-2025 for confirmed Japanese EDINET codes
Usage: python build_regulator_sources.py [--edinet-from 2017-01-01] [--edinet-to YYYY-MM-DD] [--skip-japan] [--skip-korea]
Without keys the corresponding market is skipped and the files stay unchanged for it.
"""
import argparse
import datetime as dt
import json
import os
import sys

import httpx

from app.regulator_sources import japan_sources, korea_sources
from app.reports import ROOT

YEARS = list(range(2016, 2026))
UA = 'Mozilla/5.0 (compatible; AsiaEquityHub/1.7; regulator filings research)'


def _recount(entries, key):
    counts = {}
    for e in entries:
        counts.setdefault(e['market'], {}).setdefault(e[key], 0)
        counts[e['market']][e[key]] += 1
    return counts


def apply_korea(ident: dict, src_by_id: dict, res: dict) -> None:
    """Merge DART results into identity/source records (v1.7.1: id read before the record is rebuilt)."""
    for e in ident['entries']:
        entry_id = e['id']
        if entry_id not in res['identities']:
            continue
        keep = {k: e[k] for k in ('id', 'requested_name', 'market', 'exchange', 'human_review') if k in e}
        e.clear()
        e.update({**keep, **res['identities'][entry_id], 'human_review': 'pending'})
        s = src_by_id[entry_id]
        s['ticker'] = e.get('ticker')
        s.update(res['sources'].get(entry_id, {'source_status': 'no_identity_no_source', 'documents_by_year': None}))
        s.pop('note', None)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--edinet-from', default='2017-01-01')
    p.add_argument('--edinet-to', default=dt.date.today().isoformat())
    p.add_argument('--skip-japan', action='store_true')
    p.add_argument('--skip-korea', action='store_true')
    a = p.parse_args()
    dart_key, edinet_key = os.environ.get('DART_API_KEY', ''), os.environ.get('EDINET_API_KEY', '')
    id_path, src_path = ROOT / 'universe' / 'identity_map.json', ROOT / 'sources' / 'annual_report_sources.json'
    ident = json.loads(id_path.read_text(encoding='utf-8'))
    src = json.loads(src_path.read_text(encoding='utf-8'))
    src_by_id = {e['id']: e for e in src['entries']}
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    report = {}
    with httpx.Client(timeout=120, follow_redirects=False, headers={'User-Agent': UA}) as client:
        if dart_key and not a.skip_korea:
            kr = [e for e in ident['entries'] if e['market'] == 'Südkorea']
            res = korea_sources(kr, dart_key, client, YEARS)
            apply_korea(ident, src_by_id, res)
            ident.setdefault('official_lists', {})['dart'] = {'url': 'https://opendart.fss.or.kr/api/corpCode.xml',
                                                              'publisher': 'Financial Supervisory Service Korea (OpenDART)',
                                                              'rows': res['corp_list_rows'], 'retrieved_at': now}
            report['korea'] = {s: sum(1 for x in res['identities'].values() if x['status'] == s)
                               for s in {x['status'] for x in res['identities'].values()}}
        elif not a.skip_korea:
            print('DART_API_KEY not set - Korea skipped', file=sys.stderr)
        if edinet_key and not a.skip_japan:
            jp = [e for e in ident['entries'] if e['market'] == 'Japan' and e['status'] == 'confirmed_official_list']
            res = japan_sources(jp, edinet_key, client, YEARS, dt.date.fromisoformat(a.edinet_from),
                                dt.date.fromisoformat(a.edinet_to))
            for entry_id, s in res['sources'].items():
                src_by_id[entry_id].update(s)
                src_by_id[entry_id].pop('note', None)
            src['edinet_scan'] = {k: res[k] for k in ('days_scanned', 'days_failed', 'range')}
            report['japan'] = {'days_scanned': res['days_scanned'], 'days_failed': res['days_failed'],
                               'companies_with_all_10_years': sum(len(s['years_with_candidates']) == 10 for s in res['sources'].values())}
        elif not a.skip_japan:
            print('EDINET_API_KEY not set - Japan skipped', file=sys.stderr)
    if not report:
        print('No API key available - nothing changed.')
        sys.exit(0)
    ident['counts'] = _recount(ident['entries'], 'status')
    src['counts'] = _recount(src['entries'], 'source_status')
    ident['regulator_update_at'] = src['regulator_update_at'] = now
    id_path.write_text(json.dumps(ident, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    src_path.write_text(json.dumps(src, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))
