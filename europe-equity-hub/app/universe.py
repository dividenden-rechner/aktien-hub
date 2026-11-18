"""Issuer / security / listing / index-membership model and candidate matching (v0.7).

* listing  = ISIN + MIC (one row per venue; terminated listings kept and flagged)
* security = ISIN (share class); never merged with another ISIN
* issuer   = LEI from FIRDS (legal entity); securities without LEI get a provisional
             issuer key "NOLEI:<ISIN>" and are reported as unresolved issuers
* index_membership = index + as-of date + source (only from dated official/committed lists)

Candidate matching (handoff v0.5 rows) never marks anything verified:
* matched_ticker_code  - exchange suffix + local ticker found on that venue's official list
* matched_exact_name   - normalised name equals exactly one security on the expected venues
* review_*             - several securities, fuzzy similarity or nothing found -> review queue
* non_european_listing - US ADR / OTC symbols (no exchange suffix) are not European listings
"""
from __future__ import annotations

import difflib
import re
import unicodedata
from collections import Counter, defaultdict

from .isin import is_valid_isin

EUROPEAN_ISIN_PREFIXES = {
    'AT', 'BE', 'BG', 'CH', 'CY', 'CZ', 'DE', 'DK', 'EE', 'ES', 'FI', 'FO', 'FR', 'GB', 'GG', 'GI', 'GR', 'HR', 'HU', 'IE',
    'IM', 'IS', 'IT', 'JE', 'LI', 'LT', 'LU', 'LV', 'MC', 'MT', 'NL', 'NO', 'PL', 'PT', 'RO', 'SE', 'SI', 'SK'}
COUNTRY_VENUES = {
    'DE': {'XETA', 'XETB'}, 'FR': {'XPAR', 'ALXP'}, 'NL': {'XAMS'}, 'BE': {'XBRU'}, 'PT': {'XLIS'}, 'IE': {'XMSM', 'XLON'},
    'IT': {'MTAA', 'EXGM'}, 'NO': {'XOSL'}, 'ES': {'XMAD', 'MABX'}, 'AT': {'WBAH'}, 'SE': {'XSTO', 'XNGM'}, 'FI': {'XHEL'},
    'DK': {'XCSE'}, 'IS': {'XICE'}, 'PL': {'XWAR', 'XNCO'}, 'GR': {'XATH'}, 'EE': {'XTAL'}, 'LV': {'XRIS'}, 'LT': {'XLIT'},
    'CZ': {'XPRA'}, 'HU': {'XBUD'}, 'RO': {'XBSE'}, 'HR': {'XZAG'}, 'SI': {'XLJU'}, 'SK': {'XBRA'}, 'BG': {'XBUL'},
    'GB': {'XLON', 'AIMX'}, 'CH': {'XSWX'}, 'LU': {'XPAR', 'XAMS', 'XBRU', 'XETA'},
}
SUFFIX_VENUES = {
    'DE': {'XETA', 'XETB'}, 'F': {'XETA', 'XETB'}, 'PA': {'XPAR', 'ALXP'}, 'AS': {'XAMS'}, 'BR': {'XBRU'}, 'LS': {'XLIS'},
    'IR': {'XMSM'}, 'MI': {'MTAA', 'EXGM'}, 'OL': {'XOSL'}, 'MC': {'XMAD', 'MABX'}, 'VI': {'WBAH'}, 'ST': {'XSTO'},
    'HE': {'XHEL'}, 'CO': {'XCSE'}, 'IC': {'XICE'}, 'WA': {'XWAR', 'XNCO'}, 'AT': {'XATH'}, 'PR': {'XPRA'}, 'BD': {'XBUD'},
    'L': {'XLON', 'AIMX'}, 'SW': {'XSWX'}, 'TL': {'XTAL'}, 'RG': {'XRIS'}, 'VS': {'XLIT'},
}
LEGAL = re.compile(r'\b(ag|se|sa|s\.a|spa|s\.p\.a|nv|n\.v|plc|asa|as|ab|abp|oyj|oy|a/s|ltd|limited|holding|holdings|group|'
                   r'gruppe|kgaa|co|kg|inc|corp|corporation|company|the|et|cie|sca|bv|ag&co|publ|reg|na|o\.n|vz|st|'
                   r'eo|dl|sf|nam|akt|aktie|aktien|inhaber|namens|shs|ord|class|cl|series|ser)\b')


NOMINAL = re.compile(r'\b(?:(?:eur|gbp|gbx|usd|chf|sek|nok|dkk|pln|czk|huf|ron)[0-9]\S*|ord|par|vtg|fpd|npv|nom|ac|'
                     r'ordinary|shares|share|registered|bearer|stammaktien|vorzugsaktien|[0-9]+p|[0-9]+)\b')


def norm_name(s: str | None) -> str:
    if not s:
        return ''
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().lower()
    s = re.sub(r'\bo\.\s?n\.?(?=\s|$)', ' ', s)                # German "o.N." (ohne Nennwert)
    s = s.replace('&', ' and ').replace("'", '').replace('.', ' ').replace(',', ' ').replace('-', ' ').replace('/', ' ')
    s = re.sub(r'\(.*?\)', ' ', s)
    s = re.sub(r'\b([a-z]) (?=[a-z]\b)', r'\1', s)        # "s a" -> "sa", "n v" -> "nv", "e on" -> "eon"
    s = NOMINAL.sub(' ', s)                                  # share-class / nominal-value tokens from FIRDS names
    s = LEGAL.sub(' ', s)
    s = re.sub(r'[^a-z0-9 ]', ' ', s)
    return ' '.join(s.split())


def build_model(listings: list[dict], index_rows: list[dict] | None = None) -> dict:
    rejected = [l for l in listings if not is_valid_isin(l.get('isin'))]
    listings = [l for l in listings if is_valid_isin(l.get('isin'))]
    sec: dict[str, dict] = {}
    for l in listings:
        s = sec.setdefault(l['isin'], {'isin': l['isin'], 'isin_valid': l['isin_valid'], 'isin_country': l['isin'][:2],
                                       'names': Counter(), 'cfi': l.get('cfi'), 'issuer_lei': None, 'listings': []})
        s['names'][l['name'] or ''] += 1
        s['listings'].append(f"{l['isin']}@{l['mic']}")
        if l.get('issuer_lei') and not s['issuer_lei']:
            s['issuer_lei'] = l['issuer_lei']
        if not s['cfi'] and l.get('cfi'):
            s['cfi'] = l['cfi']
    securities, issuers = [], {}
    for s in sec.values():
        name = s['names'].most_common(1)[0][0]
        active = [x for x in listings if x['isin'] == s['isin'] and x['listing_status'] != 'terminated']
        issuer_id = f"LEI:{s['issuer_lei']}" if s['issuer_lei'] else f"NOLEI:{s['isin']}"
        securities.append({'isin': s['isin'], 'isin_valid': s['isin_valid'], 'isin_country': s['isin_country'],
                           'european_isin': s['isin_country'] in EUROPEAN_ISIN_PREFIXES, 'name': name, 'cfi': s['cfi'],
                           'issuer_id': issuer_id, 'listing_ids': sorted(s['listings']),
                           'active_listing_count': len(active), 'verification_status': 'official_list_unreviewed',
                           'human_review': 'pending'})
        iss = issuers.setdefault(issuer_id, {'issuer_id': issuer_id, 'lei': s['issuer_lei'], 'names': Counter(),
                                             'isins': [], 'identity_status': 'lei_from_firds' if s['issuer_lei'] else 'unresolved_no_lei',
                                             'human_review': 'pending'})
        iss['names'][name] += 1
        iss['isins'].append(s['isin'])
    issuer_list = [{**{k: v for k, v in i.items() if k != 'names'}, 'name': i['names'].most_common(1)[0][0],
                    'isins': sorted(i['isins'])} for i in issuers.values()]
    for l in listings:
        l['listing_id'] = f"{l['isin']}@{l['mic']}"
        l.setdefault('verification_status', 'official_list_unreviewed')
        l.setdefault('human_review', 'pending')
    dup_listings = Counter(l['listing_id'] for l in listings)
    return {'listings': listings, 'securities': securities, 'issuers': issuer_list,
            'index_memberships': index_rows or [], 'rejected_listings': rejected,
            'stats': {'listings': len(listings), 'listings_active': sum(l['listing_status'] != 'terminated' for l in listings),
                      'listings_terminated': sum(l['listing_status'] == 'terminated' for l in listings),
                      'securities': len(securities), 'securities_multi_listed': sum(s['active_listing_count'] > 1 for s in securities),
                      'issuers': len(issuer_list), 'issuers_without_lei': sum(i['lei'] is None for i in issuer_list),
                      'issuers_multi_security': sum(len(i['isins']) > 1 for i in issuer_list),
                      'invalid_isins': sum(not s['isin_valid'] for s in securities),
                      'duplicate_listing_rows': sum(c - 1 for c in dup_listings.values() if c > 1),
                      'index_memberships': len(index_rows or []), 'rejected_missing_or_invalid_isin': len(rejected)}}


def _index_names(listings: list[dict]) -> dict[str, dict[str, set]]:
    """venue -> normalised name -> set of ISINs (active listings only), using every official name variant."""
    idx: dict[str, dict[str, set]] = defaultdict(lambda: defaultdict(set))
    for l in listings:
        if l['listing_status'] == 'terminated':
            continue
        for field in ('name', 'short_name', 'euronext_name', 'nasdaq_name', 'xetra_name'):
            n = norm_name(l.get(field))
            if n:
                idx[l['mic']][n].add(l['isin'])
    return idx


def match_candidates(candidates: list[dict], listings: list[dict]) -> list[dict]:
    names = _index_names(listings)
    by_ticker = defaultdict(set)
    for l in listings:
        if l.get('ticker') and l['listing_status'] != 'terminated':
            by_ticker[(l['mic'], l['ticker'].upper().replace(' ', '-'))].add(l['isin'])
    out = []
    for c in candidates:
        rec = dict(c)
        rec['human_review'] = 'pending'
        sym = (c.get('symbol') or '').strip()
        venues = None
        if sym:
            if '.' in sym:
                local, suffix = sym.rsplit('.', 1)
                venues = SUFFIX_VENUES.get(suffix.upper())
                if venues:
                    hits = set()
                    for mic in venues:
                        hits |= by_ticker.get((mic, local.upper().replace('_', '-')), set())
                        hits |= by_ticker.get((mic, local.upper().replace('-', ' ').replace(' ', '-')), set())
                    if len(hits) == 1:
                        rec.update({'match_status': 'matched_ticker_code', 'isin': next(iter(hits)), 'match_basis': f'{local} on {sorted(venues)}'})
                        out.append(rec)
                        continue
            else:
                rec.update({'match_status': 'non_european_listing', 'isin': None,
                            'match_basis': 'symbol without exchange suffix (US ADR/OTC or US listing)'})
                out.append(rec)
                continue
        venues = venues or COUNTRY_VENUES.get(c.get('country'), set())
        n = norm_name(c.get('name'))
        exact = set()
        for mic in venues:
            exact |= names.get(mic, {}).get(n, set())
        if len(exact) == 1:
            rec.update({'match_status': 'matched_exact_name', 'isin': next(iter(exact)), 'match_basis': f'normalised name "{n}"'})
        elif len(exact) > 1:
            rec.update({'match_status': 'review_multiple_securities', 'isin': None, 'review_candidates': sorted(exact)[:6],
                        'match_basis': 'several share classes/ISINs with this name'})
        else:
            pool = [(k, isins) for mic in venues for k, isins in names.get(mic, {}).items()]
            scored = sorted(((difflib.SequenceMatcher(None, n, k).ratio(), k, isins) for k, isins in pool if n), reverse=True)[:3]
            if scored and scored[0][0] >= 0.8:
                rec.update({'match_status': 'review_fuzzy', 'isin': None,
                            'review_candidates': [{'name': k, 'isins': sorted(i)[:3], 'score': round(s, 3)} for s, k, i in scored],
                            'match_basis': 'fuzzy similarity only - never auto-confirmed'})
            else:
                rec.update({'match_status': 'review_not_found', 'isin': None,
                            'match_basis': 'no active listing with this name on expected venues (delisted, renamed, or not covered)'})
        out.append(rec)
    return out


def duplicate_report(matched: list[dict], securities: dict[str, dict]) -> dict:
    by_isin, by_issuer = defaultdict(list), defaultdict(list)
    for m in matched:
        if m.get('isin'):
            by_isin[m['isin']].append(m['candidate_id'])
            iss = securities.get(m['isin'], {}).get('issuer_id')
            if iss:
                by_issuer[iss].append(m['candidate_id'])
    same_isin = {k: v for k, v in by_isin.items() if len(v) > 1}
    same_issuer_diff_isin = {k: v for k, v in by_issuer.items()
                             if len({x for x in v}) > 1 and len({m['isin'] for m in matched if m['candidate_id'] in v}) > 1}
    return {'candidates_with_same_isin': same_isin, 'candidates_same_issuer_different_isin': same_issuer_diff_isin,
            'resolved_duplicate_groups': len(same_isin),
            'note': 'Same ISIN = same security (duplicates resolved to one security). Same issuer with different ISINs = '
                    'share classes, kept separate.'}


def validate_isins(values: list[str]) -> dict:
    bad = [v for v in values if not is_valid_isin(v)]
    return {'checked': len(values), 'invalid': len(bad), 'invalid_examples': bad[:10]}


def index_membership_status(rows: list[dict], index: str, isin: str, on_date: str) -> str:
    """'member' / 'not_member' only where a dated snapshot or validity interval covers the date, else 'unknown'.

    Index membership is never extrapolated from a single snapshot to other dates.
    """
    relevant = [r for r in rows if r['index'] == index]
    for r in relevant:
        start, end = r.get('valid_from'), r.get('valid_to')
        if start and start <= on_date and (not end or on_date <= end) and r['isin'] == isin:
            return 'member'
    snapshot_dates = {r.get('as_of') for r in relevant if r.get('as_of') and not r.get('valid_from')}
    if on_date in snapshot_dates:
        return 'member' if any(r['isin'] == isin and r.get('as_of') == on_date for r in relevant) else 'not_member'
    return 'unknown'
