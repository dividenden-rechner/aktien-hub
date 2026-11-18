"""v1.6 annual-report source registry (committed output)."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = json.loads((ROOT / 'reports/sources/annual_report_sources.json').read_text(encoding='utf-8'))
IDMAP = json.loads((ROOT / 'reports/universe/identity_map.json').read_text(encoding='utf-8'))


def test_one_source_record_per_universe_entry():
    assert [e['id'] for e in SRC['entries']] == [e['id'] for e in IDMAP['entries']]
    assert SRC['fiscal_years'] == list(range(2016, 2026))


def test_market_specific_source_status():
    status = {e['market']: set() for e in SRC['entries']}
    for e in SRC['entries']:
        status[e['market']].add(e['source_status'])
    assert status['Singapur'] == {'manual_source_required'}
    assert status['Südkorea'] <= {'dart_api_key_required', 'dart_queried', 'no_identity_no_source'}
    assert status['Japan'] <= {'edinet_code_known_api_key_required', 'edinet_queried', 'no_identity_no_source'}


def test_candidates_are_official_hosts_and_unverified():
    for e in SRC['entries']:
        assert e['verification_status'] == 'candidates_unverified'
        for docs in (e.get('documents_by_year') or {}).values():
            for d in docs:
                assert d['url'].startswith(('https://www1.hkexnews.hk/', 'https://static.cninfo.com.cn/',
                                            'https://dart.fss.or.kr/', 'https://api.edinet-fsa.go.jp/'))
                assert 'crtfc_key' not in d['url'] and 'Subscription-Key' not in d['url']


def test_registered_reports_are_found_by_discovery():
    by = {e['ticker']: e for e in SRC['entries'] if e.get('ticker')}
    # CKH, Swire and First Pacific are not part of the 451-entry universe; DBS and BYD are.
    assert '0019.HK' not in by and 'D05.SI' in by
    if by['0700.HK']['source_status'] == 'hkexnews_queried':
        assert any('2025' in d['title'] for d in by['0700.HK']['documents_by_year']['2025'])
    byd = 'https://static.cninfo.com.cn/finalpage/2026-03-28/1225045351.PDF'
    if by['002594.SZ']['source_status'] == 'cninfo_queried':
        assert byd in [d['url'] for d in by['002594.SZ']['documents_by_year']['2025']]
