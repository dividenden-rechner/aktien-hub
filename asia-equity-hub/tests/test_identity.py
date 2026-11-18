"""v1.6 identity mapping: committed identity_map.json plus resolver unit tests (no network)."""
import json
from pathlib import Path

from app.identity import build_identity_map, norm

ROOT = Path(__file__).resolve().parents[1]
IDMAP = json.loads((ROOT / 'reports/universe/identity_map.json').read_text(encoding='utf-8'))
UNIVERSE = json.loads((ROOT / 'reports/universe/companies.json').read_text(encoding='utf-8'))


def test_every_universe_entry_mapped_once_and_universe_unchanged():
    assert [e['id'] for e in IDMAP['entries']] == [e['id'] for e in UNIVERSE['entries']]
    assert all(e['ticker'] is None for e in UNIVERSE['entries'])  # raw universe stays untouched


def test_status_vocabulary_and_human_review():
    allowed = {'confirmed_official_list', 'not_in_current_official_list', 'not_listed', 'ambiguous',
               'unresolved', 'candidate_unverified'}
    assert {e['status'] for e in IDMAP['entries']} <= allowed
    assert all(e['human_review'] == 'pending' for e in IDMAP['entries'])
    assert not any(v == 'verified' for e in IDMAP['entries'] for v in e.values() if isinstance(v, str))


def test_confirmed_entries_carry_official_evidence():
    for e in IDMAP['entries']:
        if e['status'] != 'confirmed_official_list':
            continue
        assert e['ticker'] and e['evidence'] in IDMAP['official_lists'] or e['evidence'] == 'jpx+edinet'
        if e['market'] == 'Hongkong':
            assert len(e['identifiers']['isin']) == 12
        if e['market'] == 'China':
            assert e['identifiers']['cninfo_org_id']
        if e['market'] == 'Japan':
            assert e['identifiers']['edinet_code'].startswith('E') and len(e['identifiers']['jp_corporate_number']) == 13


def test_no_duplicate_tickers_within_market():
    seen = set()
    for e in IDMAP['entries']:
        if e.get('ticker'):
            key = (e['market'], e['ticker'])
            assert key not in seen, key
            seen.add(key)


def test_known_mappings_and_documented_exceptions():
    by = {(e['market'], e['requested_name']): e for e in IDMAP['entries']}
    assert by[('Hongkong', 'Tencent Holdings')]['ticker'] == '0700.HK'
    assert by[('Hongkong', 'Tencent Holdings')]['identifiers']['isin'] == 'KYG875721634'
    assert by[('Singapur', 'DBS Group Holdings')]['ticker'] == 'D05.SI'
    assert by[('China', 'BYD')]['ticker'] == '002594.SZ'
    assert by[('China', 'Kweichow Moutai')]['ticker'] == '600519.SS'
    assert by[('Japan', 'Toyota Motor')]['ticker'] == '7203.T'
    # automatic prefix match Toshiba -> Toshiba TEC must stay rejected
    assert by[('Japan', 'Toshiba')]['status'] == 'not_in_current_official_list' and by[('Japan', 'Toshiba')]['ticker'] is None
    assert by[('Japan', 'Nikkei')]['status'] == 'not_listed'
    assert by[('Hongkong', 'Hang Seng Bank')]['status'] == 'not_in_current_official_list'
    assert all(e['status'] == 'candidate_unverified' for e in IDMAP['entries'] if e['market'] == 'Südkorea')


def test_counts_match_entries():
    total = sum(sum(v.values()) for v in IDMAP['counts'].values())
    assert total == len(IDMAP['entries']) == 451


def test_resolver_with_synthetic_lists():
    universe = {'entries': [
        {'id': 'japan-1', 'requested_name': 'Kao', 'market': 'Japan', 'exchange': 'TSE'},
        {'id': 'japan-2', 'requested_name': 'Toshiba', 'market': 'Japan', 'exchange': 'TSE'},
        {'id': 'hongkong-1', 'requested_name': 'Foo', 'market': 'Hongkong', 'exchange': 'HKEX'},
    ]}
    candidates = {'hongkong': {'Foo': '0011'}, 'singapur': {}, 'china': {}, 'suedkorea': {},
                  'japan_overrides': {'Toshiba': {'status': 'not_in_current_official_list', 'former_code': '6502'}}}
    lists = {'meta': {}, 'hkex': {}, 'sgx': {}, 'cninfo': {},
             'jpx': {'4452': {'code': '4452', 'name': 'Kao Corporation', 'section': 'Prime Market (Domestic)'},
                     '6588': {'code': '6588', 'name': 'TOSHIBA TEC CORPORATION', 'section': 'Prime'}},
             'edinet': [{'edinet_code': 'E00000', 'listed': '上場', 'name_ja': '花王', 'name_en': 'Kao',
                         'securities_code': '4452', 'corporate_number': '1234567890123'}]}
    out = {e['id']: e for e in build_identity_map(universe, candidates, lists)['entries']}
    assert out['japan-1']['ticker'] == '4452.T' and out['japan-1']['identifiers']['edinet_code'] == 'E00000'
    assert out['japan-2']['ticker'] is None
    assert out['hongkong-1']['status'] == 'not_in_current_official_list'


def test_norm():
    assert norm('MS&AD Insurance Group Holdings,Inc.') == 'MS AND AD INSURANCE GROUP HOLDINGS'
    assert norm('KAO CORPORATION') == norm('Kao')
