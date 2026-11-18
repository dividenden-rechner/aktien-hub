"""FY2010-FY2025 financial history (official ESEF), price/dividend coverage and coverage matrix.

Usage: python scripts/build_history.py
Reads aktien-hub data/esef/speicher.json (not modified) and data/universe/*.json.
Writes data/history/financials_esef.json, plausibility.json, coverage_matrix.json, price_dividend_coverage.json.
"""
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
sys.path.insert(0, str(ROOT))
from app.history import NOT_AVAILABLE_FROM_ESEF, YEARS, coverage, derive, facts_from_reports, plausibility  # noqa: E402

OUT = ROOT / 'data' / 'history'


def main():
    sp = json.loads((REPO / 'data' / 'esef' / 'speicher.json').read_text(encoding='utf-8'))
    facts = facts_from_reports(sp['berichte'])
    derived = derive(facts)
    allf = facts + derived
    issuers = {i['issuer_id']: i for i in json.loads((ROOT / 'data' / 'universe' / 'issuers.json').read_text(encoding='utf-8'))}
    matched = json.loads((ROOT / 'data' / 'universe' / 'candidates_matched.json').read_text(encoding='utf-8'))
    scope_leis = sorted({m['issuer_id'][4:] for m in matched if (m.get('issuer_id') or '').startswith('LEI:')})
    esef_leis = sorted({f['issuer_lei'] for f in facts})
    in_universe = [l for l in esef_leis if f'LEI:{l}' in issuers]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'financials_esef.json').write_text(json.dumps(
        {'generated_at': datetime.now(timezone.utc).isoformat(), 'source': 'ESEF annual financial reports via filings.xbrl.org '
         '(repo cache data/esef/speicher.json)', 'not_available': NOT_AVAILABLE_FROM_ESEF, 'facts': allf},
        ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    plaus = plausibility(facts)
    (OUT / 'plausibility.json').write_text(json.dumps({'issues': plaus, 'count': len(plaus),
                                                       'by_issue': dict(Counter(i['issue'].split(':')[0] for i in plaus))},
                                                      ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    cov_scope = coverage(scope_leis, allf)
    cov_esef = coverage(esef_leis, allf)
    (OUT / 'coverage_matrix.json').write_text(json.dumps({
        'counting_method': ('one row per issuer (LEI); a year is "complete" if all required fields exist, "partial" if at '
                            'least one field exists, else "missing" (never 0)'),
        'handoff_scope': {'issuers': len(scope_leis), **{k: v for k, v in cov_scope.items() if k != 'matrix'},
                          'matrix': cov_scope['matrix']},
        'all_esef_issuers': {'issuers': len(esef_leis), 'in_official_universe': len(in_universe),
                             **{k: v for k, v in cov_esef.items() if k != 'matrix'}}},
        ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    # prices & dividends: only what exists, never claimed beyond
    hist_dir = REPO / 'data' / 'kurse' / 'historie'
    av = []
    for f in sorted(hist_dir.glob('*.json')):
        if f.name == 'queue.json':
            continue
        d = json.loads(f.read_text(encoding='utf-8'))
        av.append({'symbol': d.get('hub'), 'source': d.get('quelle'), 'as_of': d.get('stand'),
                   'adjustment': 'unadjusted weekly closes (per source description)', 'licence_note': 'Alpha Vantage free tier; check terms before republication'})
    dps = defaultdict(set)
    for fct in facts:
        if fct['field'] in ('dps_recognised_in_year', 'dps_proposed_for_year'):
            dps[fct['issuer_lei']].add(fct['fiscal_year'])
    price_cov = {
        'prices': {'official_free_series_2010_2025': 'missing',
                   'note': ('No free, redistributable official end-of-day history 2010-2025 was retrieved for European venues. '
                            'Existing repo series are listed below as third-party data; no adjusted/unadjusted mixing.'),
                   'existing_repo_series': av,
                   'xetra_daily_repo': 'aktien-hub data/kurse/xetra (recent daily snapshots from Deutsche Börse, not a 2010-2025 history)'},
        'dividends': {'source': 'ESEF per-share dividend facts (recognised in year / proposed for year)',
                      'issuers_with_any_dps_fact': len(dps),
                      'per_year': {str(y): sum(1 for s in dps.values() if y in s) for y in YEARS},
                      'not_available': 'ex-date, payment date, gross/net and special/ordinary split are not in these facts'},
        'corporate_actions': {'status': 'missing', 'note': 'splits/capital measures not imported'}}
    (OUT / 'price_dividend_coverage.json').write_text(json.dumps(price_cov, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(json.dumps({'facts': len(facts), 'derived': len(derived), 'esef_issuers': len(esef_leis), 'esef_issuers_in_universe': len(in_universe),
                      'handoff_scope_issuers': len(scope_leis), 'scope_per_year': cov_scope['per_year'],
                      'plausibility_issues': len(plaus), 'dps_issuers': len(dps)}, indent=1))


if __name__ == '__main__':
    main()
