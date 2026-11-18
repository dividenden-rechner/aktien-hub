"""Build issuers/securities/listings/index memberships from the downloaded official lists and match the
handoff candidates (422 screener rows + 580 research candidates). Idempotent: same inputs -> same outputs.

Usage: python scripts/build_universe.py [--no-gleif]
Outputs (data/universe/): listings.json, securities.json, issuers.json, index_memberships.json,
candidates_matched.json, review_queue.csv, duplicates.json, summary.json
"""
import argparse
import csv
import json
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import httpx
import openpyxl

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
sys.path.insert(0, str(ROOT))
from app.official_lists import (enrich, parse_euronext, parse_fca_fulins, parse_firds_solr,  # noqa: E402
                                parse_nasdaq_nordic, parse_six, parse_xetra)
from app.universe import build_model, duplicate_report, match_candidates  # noqa: E402

RAW = ROOT / 'data' / 'official_lists' / 'raw'
OUT = ROOT / 'data' / 'universe'


def load_listings():
    meta = json.loads((ROOT / 'data' / 'official_lists' / 'sources.json').read_text(encoding='utf-8'))
    asof = datetime.fromisoformat(meta['generated_at'])
    listings = []
    for f in sorted(RAW.glob('firds_*.json')):
        listings += parse_firds_solr(json.loads(f.read_text(encoding='utf-8'))['response']['docs'], asof)
    for f in sorted(RAW.glob('FULINS_E_*.zip')):
        listings += parse_fca_fulins(f, {'XLON', 'AIMX'}, asof)
    listings += parse_six((RAW / 'six.csv').read_bytes().decode('latin-1'), asof)
    xetra = parse_xetra((RAW / 'xetra.csv').read_text(encoding='utf-8-sig'))
    euronext = parse_euronext((RAW / 'euronext.csv').read_text(encoding='utf-8-sig'))
    nordic = {}
    for f in RAW.glob('nasdaq_*_*.json'):
        nordic.update(parse_nasdaq_nordic(json.loads(f.read_text(encoding='utf-8')), f.stem.rsplit('_', 1)[1]))
    listings = enrich(listings, xetra, euronext, nordic)
    # de-duplicate identical rows (same ISIN+MIC reported twice); keep the active / latest one
    best = {}
    for l in listings:
        k = (l['isin'], l['mic'])
        if k not in best or (best[k]['listing_status'] == 'terminated' and l['listing_status'] != 'terminated'):
            best[k] = l
    dropped = len(listings) - len(best)
    return sorted(best.values(), key=lambda x: (x['isin'], x['mic'])), meta, dropped


def gleif(leis, enabled=True):
    if not enabled:
        return {}
    cache_path = RAW / 'gleif_cache.json'
    out = json.loads(cache_path.read_text(encoding='utf-8')) if cache_path.exists() else {}
    c = httpx.Client(timeout=60, headers={'User-Agent': 'EuropeEquityHub/0.7', 'Accept': 'application/vnd.api+json'})
    leis = sorted(set(leis) - set(out))
    for i in range(0, len(leis), 100):
        chunk = leis[i:i + 100]
        try:
            r = c.get('https://api.gleif.org/api/v1/lei-records', params={'filter[lei]': ','.join(chunk), 'page[size]': '100'})
            r.raise_for_status()
            for rec in r.json().get('data', []):
                a = rec['attributes']['entity']
                out[rec['id']] = {'legal_name': a['legalName']['name'], 'legal_jurisdiction': a.get('jurisdiction'),
                                  'legal_address_country': a['legalAddress'].get('country'),
                                  'hq_country': (a.get('headquartersAddress') or {}).get('country'),
                                  'entity_status': a.get('status'), 'registration_status': rec['attributes']['registration']['status']}
        except Exception as e:
            print('GLEIF chunk failed', type(e).__name__, file=sys.stderr)
        time.sleep(0.3)
    cache_path.write_text(json.dumps(out, ensure_ascii=False), encoding='utf-8')
    return out


def index_rows():
    rows = []
    for name in ('mdax', 'sdax'):
        p = REPO / 'data' / 'indizes' / f'{name}.csv'
        if not p.exists():
            continue
        try:
            asof = subprocess.run(['git', '-C', str(REPO), 'log', '-1', '--format=%cs', '--', str(p)],
                                  capture_output=True, text=True).stdout.strip() or None
        except Exception:
            asof = None
        for r in csv.DictReader(p.open(encoding='utf-8'), delimiter=';'):
            rows.append({'index': name.upper(), 'isin': r.get('ISIN'), 'name': r.get('Unternehmen'),
                         'weight_raw': r.get('Indexgewichtung'), 'as_of': asof,
                         'as_of_basis': 'last git commit of the repo file (no publication date in file)',
                         'source': f'aktien-hub data/indizes/{name}.csv', 'verification_status': 'repo_data_unreviewed',
                         'human_review': 'pending'})
    return rows


def candidates():
    wb = openpyxl.load_workbook(ROOT / 'input' / 'europa_aktien_hub_v0_5_boersenabgleich.xlsx', read_only=True)
    out = []
    ws = wb['Bestand_422']; ws.reset_dimensions()
    rows = list(ws.iter_rows(values_only=True))
    for r in rows[1:]:
        d = dict(zip(rows[0], r))
        out.append({'candidate_id': f"bestand-{int(d['source_row']):04d}", 'source_tab': 'Bestand_422', 'symbol': d['symbol_raw'],
                    'name': d['name_raw'], 'country': d['country'], 'sector_raw': d['sector_raw']})
    for tab in ('Ergaenzung_IT_PL_GR', 'Ergaenzung_ES_IE_CH_AT', 'Ergaenzung_FR_GB_Nordics'):
        ws = wb[tab]; ws.reset_dimensions()
        rows = list(ws.iter_rows(values_only=True))
        for i, r in enumerate(rows[1:], 1):
            d = dict(zip(rows[0], r))
            if not d.get('company_candidate'):
                continue
            out.append({'candidate_id': f'{tab.lower()}-{i:04d}', 'source_tab': tab, 'symbol': None,
                        'name': d['company_candidate'], 'country': d['country'],
                        'suggested_index_family': d.get('suggested_index_family')})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--no-gleif', action='store_true')
    a = ap.parse_args()
    listings, meta, dropped = load_listings()
    model = build_model(listings, index_rows())
    leis = {i['lei'] for i in model['issuers'] if i['lei']}
    g = gleif(leis, not a.no_gleif)
    for i in model['issuers']:
        if i['lei'] in g:
            i.update(g[i['lei']])
            i['identity_status'] = 'lei_from_firds_confirmed_gleif'
    cands = candidates()
    matched = match_candidates(cands, model['listings'])
    secs = {s['isin']: s for s in model['securities']}
    issuer_by_id = {i['issuer_id']: i for i in model['issuers']}
    for m in matched:
        if m.get('isin'):
            s = secs[m['isin']]
            m['issuer_id'] = s['issuer_id']
            m['security_name'] = s['name']
            m['issuer_country'] = issuer_by_id[s['issuer_id']].get('legal_address_country')
    dups = duplicate_report(matched, secs)
    OUT.mkdir(parents=True, exist_ok=True)
    for name, obj in (('listings', model['listings']), ('securities', model['securities']), ('issuers', model['issuers']),
                      ('index_memberships', model['index_memberships']), ('candidates_matched', matched), ('duplicates', dups)):
        (OUT / f'{name}.json').write_text(json.dumps(obj, ensure_ascii=False, separators=(',', ':'), sort_keys=True) + '\n', encoding='utf-8')
    with (OUT / 'review_queue.csv').open('w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow(['candidate_id', 'source_tab', 'country', 'symbol', 'name', 'match_status', 'match_basis', 'review_candidates'])
        for m in matched:
            if m['match_status'].startswith('review') or m['match_status'] == 'non_european_listing':
                w.writerow([m['candidate_id'], m['source_tab'], m['country'], m.get('symbol') or '', m['name'], m['match_status'],
                            m['match_basis'], json.dumps(m.get('review_candidates') or '', ensure_ascii=False)])
    by_country = Counter(l['venue_country'] for l in model['listings'] if l['listing_status'] != 'terminated')
    by_venue = Counter(l['mic'] for l in model['listings'] if l['listing_status'] != 'terminated')
    summary = {'generated_at': datetime.now(timezone.utc).isoformat(), 'lists_generated_at': meta['generated_at'],
               'counting_method': {'listing': 'ISIN+MIC row from an official list', 'security': 'distinct ISIN',
                                   'issuer': 'distinct LEI (FIRDS); securities without LEI count as one provisional issuer each',
                                   'european_issuer': 'GLEIF legal address in a European country',
                                   'active': 'no termination date in the past at list retrieval time'},
               **model['stats'], 'duplicate_listing_rows_removed': dropped, 'gleif_records': len(g),
               'issuers_european_legal_address': sum(1 for i in model['issuers'] if (i.get('legal_address_country') or '') in
                                                     __import__('app.universe', fromlist=['x']).EUROPEAN_ISIN_PREFIXES),
               'active_listings_by_country': dict(sorted(by_country.items())), 'active_listings_by_venue': dict(sorted(by_venue.items())),
               'listings_with_ticker': sum(1 for l in model['listings'] if l.get('ticker')),
               'candidates': len(matched), 'candidate_status': dict(Counter(m['match_status'] for m in matched)),
               'candidate_status_by_country': {c: dict(Counter(m['match_status'] for m in matched if m['country'] == c))
                                               for c in sorted({m['country'] for m in matched if m['country']})},
               'resolved_duplicate_groups': dups['resolved_duplicate_groups'],
               'verified': 0}
    (OUT / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(json.dumps({k: summary[k] for k in ('listings', 'listings_active', 'securities', 'issuers', 'issuers_without_lei',
                                              'gleif_records', 'issuers_european_legal_address', 'listings_with_ticker',
                                              'candidate_status', 'resolved_duplicate_groups', 'invalid_isins')}, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
