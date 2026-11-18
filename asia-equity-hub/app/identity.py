"""Issuer identity and ticker resolution against official, free exchange/regulator lists (v1.6).

Inputs
* reports/universe/companies.json        - the lossless requested universe (unchanged)
* reports/universe/ticker_candidates.json - candidates proposed by the assistant (NOT evidence)
* official lists (downloaded by build_identity_map.py --download):
    HKEX  List of Securities (xlsx, incl. ISIN)
    SGX   securities list (api.sgx.com, as used by sgx.com)
    CNINFO stock list (CSRC-designated disclosure platform; code + orgId)
    JPX   listed companies (English, xlsx)
    EDINET code list (FSA; EDINET code, corporate number, securities code)

Rules
* A ticker is only "confirmed_official_list" if the code exists in the official list.
* Japanese names are matched exactly (normalised) against JPX; prefix-only matches and
  overrides are recorded with a note. Candidates absent from current lists are reported as
  "not_in_current_official_list" with the former code as an unverified hint.
* Korea: KRX lists require a login and DART requires an API key, so Korean candidates stay
  "candidate_unverified" (verify with tools in the target repo, which holds DART_API_KEY).
* human_review is always "pending".
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import unicodedata
import zipfile
from pathlib import Path

OFFICIAL_LISTS = {
    'hkex': {'file': 'hkex.xlsx', 'url': 'https://www.hkex.com.hk/eng/services/trading/securities/securitieslists/ListOfSecurities.xlsx',
             'publisher': 'Hong Kong Exchanges and Clearing'},
    'sgx': {'file': 'sgx.json', 'url': 'https://api.sgx.com/securities/v1.1?excludetypes=bonds&params=nc,n,type,ls,m,sc',
            'publisher': 'Singapore Exchange (data feed of sgx.com)'},
    'cninfo': {'file': 'cninfo_szse.json', 'url': 'https://www.cninfo.com.cn/new/data/szse_stock.json',
               'publisher': 'CNINFO (CSRC-designated disclosure platform)'},
    'jpx': {'file': 'jpx_e.xlsx', 'url': 'https://www.jpx.co.jp/english/markets/statistics-equities/misc/tvdivq0000001vg2-att/data_e.xlsx',
            'publisher': 'Japan Exchange Group'},
    'edinet': {'file': 'edinet.zip', 'url': 'https://disclosure2dl.edinet-fsa.go.jp/searchdocument/codelist/Edinetcode.zip',
               'publisher': 'Financial Services Agency Japan (EDINET)'},
}
KOREA_NOTE = ('KRX listing downloads (kind.krx.co.kr, data.krx.co.kr) returned 403 / require login and OpenDART '
              'corpCode.xml requires an API key; candidate not verified against an official list in this run.')


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _xlsx_rows(path: Path):
    import openpyxl
    ws = openpyxl.load_workbook(path, read_only=True).active
    ws.reset_dimensions()  # some official files declare a wrong sheet size
    return list(ws.iter_rows(values_only=True))


def load_official_lists(folder: Path) -> dict:
    lists: dict = {'meta': {}}
    hk = {r[0]: {'code': r[0], 'name': r[1], 'category': r[2], 'sub_category': r[3], 'isin': r[5]}
          for r in _xlsx_rows(folder / 'hkex.xlsx') if r and isinstance(r[0], str) and r[0].isdigit()}
    sg = {x['nc']: {'code': x['nc'], 'name': x['n'], 'type': x['type'], 'board': x.get('m')}
          for x in json.loads((folder / 'sgx.json').read_text(encoding='utf-8'))['data']['prices']
          if x.get('nc') and x.get('type') in ('stocks', 'reits', 'businesstrusts')}
    cn = {x['code']: {'code': x['code'], 'name_zh': x['zwjc'], 'org_id': x['orgId'], 'category': x['category']}
          for x in json.loads((folder / 'cninfo_szse.json').read_text(encoding='utf-8'))['stockList']}
    jpx = {}
    for r in _xlsx_rows(folder / 'jpx_e.xlsx')[1:]:
        if r and r[1] is not None:
            jpx[str(r[1])] = {'code': str(r[1]), 'name': r[2], 'section': r[3]}
    with zipfile.ZipFile(folder / 'edinet.zip') as z:
        name = next(n for n in z.namelist() if n.endswith('.csv'))
        rows = list(csv.reader(io.TextIOWrapper(z.open(name), encoding='cp932')))[2:]
    edinet = [{'edinet_code': r[0], 'listed': r[2], 'name_ja': r[6], 'name_en': r[7],
               'securities_code': r[11][:4] if r[11] else '', 'corporate_number': r[12]} for r in rows]
    lists.update({'hkex': hk, 'sgx': sg, 'cninfo': cn, 'jpx': jpx, 'edinet': edinet})
    for key, info in OFFICIAL_LISTS.items():
        path = folder / info['file']
        lists['meta'][key] = {**info, 'sha256': _sha(path), 'bytes': path.stat().st_size,
                              'rows': len(lists[key])}
    return lists


def norm(name: str) -> str:
    s = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode().upper()
    for a, b in (('&', ' AND '), ('-', ' '), ('.', ' '), (',', ' '), ("'", ' ')):
        s = s.replace(a, b)
    s = re.sub(r'\b(CO|LTD|LIMITED|INC|INCORPORATED|CORPORATION|CORP|KABUSHIKI KAISHA|K K|THE|COMPANY)\b', ' ', s)
    return ' '.join(s.split())


def _yahoo(market: str, code: str) -> str:
    if market == 'Hongkong':
        return f'{int(code):04d}.HK'
    if market == 'Singapur':
        return f'{code}.SI'
    if market == 'China':
        return f'{code}.SS' if code.startswith(('6', '9')) else f'{code}.SZ'
    if market == 'Japan':
        return f'{code}.T'
    if market == 'Südkorea':
        return f'{code}.KS'
    raise ValueError(market)


def _base(entry: dict) -> dict:
    return {'id': entry['id'], 'requested_name': entry['requested_name'], 'market': entry['market'],
            'exchange': entry['exchange'], 'human_review': 'pending'}


def resolve_entry(entry: dict, candidates: dict, lists: dict, jp_index: dict) -> dict:
    market, name = entry['market'], entry['requested_name']
    rec = _base(entry)
    key = {'Hongkong': 'hongkong', 'Singapur': 'singapur', 'China': 'china', 'Südkorea': 'suedkorea'}.get(market)
    if market == 'Hongkong':
        code = candidates['hongkong'].get(name)
        row = lists['hkex'].get(code.zfill(5)) if code else None
        if row:
            return {**rec, 'status': 'confirmed_official_list', 'ticker': _yahoo(market, code), 'exchange_code': row['code'],
                    'official_name': row['name'], 'identifiers': {'isin': row['isin']}, 'evidence': 'hkex',
                    'match_method': 'assistant_candidate_confirmed_by_code'}
        return {**rec, 'status': 'not_in_current_official_list', 'ticker': None, 'former_code_hint': code,
                'evidence': 'hkex', 'note': 'Code not in current HKEX List of Securities'}
    if market == 'Singapur':
        code = candidates['singapur'].get(name)
        row = lists['sgx'].get(code) if code else None
        if row:
            return {**rec, 'status': 'confirmed_official_list', 'ticker': _yahoo(market, code), 'exchange_code': code,
                    'official_name': row['name'], 'identifiers': {'sgx_code': code, 'security_type': row['type']},
                    'evidence': 'sgx', 'match_method': 'assistant_candidate_confirmed_by_code'}
        return {**rec, 'status': 'not_in_current_official_list', 'ticker': None, 'former_code_hint': code, 'evidence': 'sgx'}
    if market == 'China':
        code = candidates['china'].get(name)
        row = lists['cninfo'].get(code) if code else None
        if row:
            return {**rec, 'status': 'confirmed_official_list', 'ticker': _yahoo(market, code), 'exchange_code': code,
                    'exchange': 'SSE' if code.startswith('6') else 'SZSE', 'official_name_local': row['name_zh'],
                    'identifiers': {'cninfo_org_id': row['org_id']}, 'evidence': 'cninfo',
                    'match_method': 'assistant_candidate_confirmed_by_code'}
        return {**rec, 'status': 'not_in_current_official_list', 'ticker': None, 'former_code_hint': code, 'evidence': 'cninfo'}
    if market == 'Südkorea':
        code = candidates[key].get(name)
        return {**rec, 'status': 'candidate_unverified', 'ticker': _yahoo(market, code) if code else None,
                'exchange_code': code, 'evidence': None, 'match_method': 'assistant_candidate_only', 'note': KOREA_NOTE}
    # Japan
    override = candidates['japan_overrides'].get(name)
    code = None
    method = 'exact_normalised_name_match_jpx'
    note = None
    if override:
        if 'code' not in override:
            return {**rec, 'status': override['status'], 'ticker': None, 'former_code_hint': override.get('former_code'),
                    'evidence': 'jpx+edinet', 'note': override.get('note')}
        code, method, note = override['code'], 'manual_override_confirmed_by_code', override.get('note')
    else:
        hits = jp_index['exact'].get(norm(name), [])
        if not hits:
            hits = jp_index['prefix'](norm(name))
            method = 'prefix_normalised_name_match_jpx'
        if len(hits) == 1:
            code = hits[0]['code']
    row = lists['jpx'].get(code) if code else None
    if not row:
        return {**rec, 'status': 'unresolved', 'ticker': None, 'evidence': 'jpx', 'note': 'No unique JPX match'}
    ed = jp_index['edinet_by_code'].get(code, [])
    ids = {'jpx_code': code}
    if len(ed) == 1:
        ids.update({'edinet_code': ed[0]['edinet_code'], 'jp_corporate_number': ed[0]['corporate_number']})
    return {**rec, 'status': 'confirmed_official_list', 'ticker': _yahoo(market, code), 'exchange_code': code,
            'official_name': row['name'], 'official_name_local': ed[0]['name_ja'] if len(ed) == 1 else None,
            'listing_section': row['section'], 'identifiers': ids, 'evidence': 'jpx+edinet',
            'match_method': method, 'note': note}


def build_identity_map(universe: dict, candidates: dict, lists: dict) -> dict:
    exact: dict[str, list] = {}
    for x in lists['jpx'].values():
        exact.setdefault(norm(x['name']), []).append(x)

    def prefix(n: str):
        return [x for k, v in exact.items() if k.startswith(n + ' ') for x in v]

    edinet_by_code: dict[str, list] = {}
    for x in lists['edinet']:
        if x['securities_code'] and x['listed'] == '上場':
            edinet_by_code.setdefault(x['securities_code'], []).append(x)
    jp_index = {'exact': exact, 'prefix': prefix, 'edinet_by_code': edinet_by_code}
    records = [resolve_entry(e, candidates, lists, jp_index) for e in universe['entries']]
    counts: dict[str, dict[str, int]] = {}
    for r in records:
        counts.setdefault(r['market'], {}).setdefault(r['status'], 0)
        counts[r['market']][r['status']] += 1
    return {'schema_version': 1, 'source_universe': 'companies.json', 'official_lists': lists['meta'],
            'counts': counts, 'entries': records,
            'note': 'Identity mapping only. No financial data. human_review pending for every entry.'}
