"""Register official annual-report sources for every universe entry (v1.6).

HK  : HKEXnews title search (stockId lookup incl. inactive securities), FY2016-2025 candidates
CN  : CNINFO annual-report category search, FY2016-2025 candidates
JP  : EDINET code from the FSA code list (document lists need a free EDINET API key)
KR  : OpenDART (needs a free API key) - not queried in this run
SG  : SGXNet has no stable free search API - manual source required
Candidates are unverified documents (no download, no hash). Writes reports/sources/annual_report_sources.json.
"""
import argparse
import json
import time
from datetime import datetime, timezone

import httpx

from app.asia_discovery import discover_cninfo_years
from app.hkex import discover_hkex_years
from app.reports import ROOT

YEARS = list(range(2016, 2026))
UA = 'Mozilla/5.0 (compatible; AsiaEquityHub/1.6; annual-report research)'
PORTALS = {
    'Hongkong': 'https://www.hkexnews.hk/', 'China': 'https://www.cninfo.com.cn/',
    'Japan': 'https://disclosure2.edinet-fsa.go.jp/', 'Südkorea': 'https://dart.fss.or.kr/',
    'Singapur': 'https://www.sgx.com/securities/company-announcements',
}


def _compact(cands):
    keep = ('url', 'title', 'published_at', 'fiscal_year_basis', 'source')
    return [{k: c[k] for k in keep if c.get(k) is not None} for c in cands]


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--offline', action='store_true', help='skip HKEX/CNINFO queries')
    a = p.parse_args()
    ident = json.loads((ROOT / 'universe' / 'identity_map.json').read_text(encoding='utf-8'))
    out = []
    with httpx.Client(timeout=40, follow_redirects=False, headers={'User-Agent': UA, 'Referer': 'https://www.cninfo.com.cn/'}) as client:
        for e in ident['entries']:
            rec = {'id': e['id'], 'requested_name': e['requested_name'], 'market': e['market'],
                   'ticker': e.get('ticker'), 'portal': PORTALS[e['market']], 'documents_by_year': None,
                   'verification_status': 'candidates_unverified'}
            code = e.get('exchange_code') or e.get('former_code_hint')
            try:
                if a.offline:
                    rec['source_status'] = 'not_queried_offline'
                elif e['market'] == 'Hongkong' and code:
                    sym = f'{int(code):04d}.HK'
                    r = discover_hkex_years(sym, YEARS, client)
                    rec.update({'hkex_stock_id': r['hkex_stock_id'], 'query_url': r['source_url'],
                                'documents_by_year': {str(y): _compact(c) for y, c in r['by_year'].items()},
                                'source_status': 'hkexnews_queried'})
                    time.sleep(0.4)
                elif e['market'] == 'China' and e.get('ticker'):
                    r = discover_cninfo_years(e['ticker'], YEARS, client)
                    rec.update({'cninfo_org_id': e['identifiers']['cninfo_org_id'], 'query_url': r['source_url'],
                                'documents_by_year': {str(y): _compact(c) for y, c in r['by_year'].items()},
                                'source_status': 'cninfo_queried'})
                    time.sleep(0.6)
                elif e['market'] == 'Japan' and e.get('identifiers', {}).get('edinet_code'):
                    rec.update({'edinet_code': e['identifiers']['edinet_code'],
                                'source_status': 'edinet_code_known_api_key_required',
                                'note': 'Annual securities reports (有価証券報告書) via EDINET API v2; needs EDINET_API_KEY (exists as a secret in aktien-hub).'})
                elif e['market'] == 'Südkorea':
                    rec.update({'source_status': 'dart_api_key_required',
                                'note': 'Business reports (사업보고서) via OpenDART; needs DART_API_KEY (exists as a secret in aktien-hub).'})
                elif e['market'] == 'Singapur':
                    rec.update({'source_status': 'manual_source_required',
                                'note': 'No stable free SGX search API. Register issuer IR annual-report PDFs manually (as done for DBS).'})
                else:
                    rec['source_status'] = 'no_identity_no_source'
            except Exception as exc:  # recorded, never hidden
                rec.update({'source_status': 'query_failed', 'error': f'{type(exc).__name__}: {str(exc)[:200]}'})
            if rec['documents_by_year'] is not None:
                rec['years_with_candidates'] = sorted(int(y) for y, c in rec['documents_by_year'].items() if c)
            out.append(rec)
    counts = {}
    for r in out:
        counts.setdefault(r['market'], {}).setdefault(r['source_status'], 0)
        counts[r['market']][r['source_status']] += 1
    doc = {'generated_at': datetime.now(timezone.utc).isoformat(), 'fiscal_years': YEARS, 'counts': counts, 'entries': out,
           'note': 'Candidate documents only: not downloaded, not hashed, not extracted. Verify issuer, year and report type before import.'}
    (ROOT / 'sources').mkdir(exist_ok=True)
    (ROOT / 'sources' / 'annual_report_sources.json').write_text(json.dumps(doc, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(json.dumps(counts, ensure_ascii=False))
    for m in ('Hongkong', 'China'):
        rs = [r for r in out if r['market'] == m and r.get('years_with_candidates') is not None]
        full = sum(len(r['years_with_candidates']) == 10 for r in rs)
        print(m, 'queried', len(rs), 'with all 10 years', full,
              'gaps', [(r['requested_name'], sorted(set(YEARS) - set(r['years_with_candidates']))) for r in rs if len(r['years_with_candidates']) < 10][:20])
