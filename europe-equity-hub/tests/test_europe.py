"""Tests required by CLAUDE_CODE_AUFTRAG.md (v0.7) plus checks of the committed outputs."""
import copy
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.history import coverage, derive, facts_from_reports, plausibility  # noqa: E402
from app.isin import is_valid_isin  # noqa: E402
from app.official_lists import enrich, parse_firds_solr  # noqa: E402
from app.universe import build_model, index_membership_status, match_candidates, norm_name  # noqa: E402

ASOF = datetime(2026, 11, 18, tzinfo=timezone.utc)
UNI = ROOT / 'data' / 'universe'
HIST = ROOT / 'data' / 'history'


def L(isin, mic, name='X', lei='529900ABCDEFGHIJKL01', end=None, ccy='EUR', cfi='ESVUFR'):
    return parse_firds_solr([{'isin': isin, 'mic': mic, 'gnr_full_name': name, 'gnr_cfi_code': cfi, 'gnr_notional_curr_code': ccy,
                              'lei': lei, 'mrkt_trdng_start_date': '2010-01-04T00:00:00Z', 'mrkt_trdng_trmination_date': end}], ASOF)[0]


# --- ISIN -----------------------------------------------------------------------------------------
@pytest.mark.parametrize('isin,ok', [('DE0007164600', True), ('NL0010273215', True), ('GB00BP6MXD84', True),
                                     ('CH0012005267', True), ('DE0007164601', False), ('DE000716460', False),
                                     ('de0007164600', False), ('', False), (None, False)])
def test_isin_check_digit(isin, ok):
    assert is_valid_isin(isin) is ok


def test_missing_or_invalid_isin_is_rejected_not_imported():
    rows = [L('DE0007164600', 'XETA', 'SAP SE'), dict(L('DE0007164600', 'XETA'), isin=None), dict(L('DE0007164600', 'XETA'), isin='DE0007164601')]
    m = build_model(rows)
    assert m['stats']['rejected_missing_or_invalid_isin'] == 2 and m['stats']['securities'] == 1


# --- identity model -------------------------------------------------------------------------------
def test_same_isin_on_two_venues_is_one_security_two_listings():
    m = build_model([L('CH0012221716', 'XSWX', 'ABB Ltd', lei='5493000LKVGOO9PELI61'),
                     L('CH0012221716', 'XSTO', 'ABB Ltd', lei='5493000LKVGOO9PELI61', ccy='SEK')])
    assert m['stats']['listings'] == 2 and m['stats']['securities'] == 1 and m['stats']['securities_multi_listed'] == 1
    assert {l['trading_currency'] for l in m['listings']} == {'EUR', 'SEK'}


def test_two_share_classes_of_one_issuer_stay_separate():
    lei = '529900ZLCYCVMC6FVM02'
    m = build_model([L('DE0005190003', 'XETA', 'BMW Stammaktien', lei=lei), L('DE0005190037', 'XETA', 'BMW Vorzugsaktien', lei=lei)])
    assert m['stats']['securities'] == 2 and m['stats']['issuers'] == 1 and m['stats']['issuers_multi_security'] == 1


def test_security_without_lei_gets_provisional_issuer():
    m = build_model([L('DE0007164600', 'XETA', lei=None)])
    assert m['issuers'][0]['issuer_id'] == 'NOLEI:DE0007164600' and m['issuers'][0]['identity_status'] == 'unresolved_no_lei'


def test_delisted_instrument_kept_and_flagged():
    m = build_model([L('PLPBKM000012', 'XWAR', 'PBKM', end='2022-04-07T23:59:59Z')])
    assert m['listings'][0]['listing_status'] == 'terminated' and m['stats']['listings_terminated'] == 1
    assert m['securities'][0]['active_listing_count'] == 0


def test_import_is_idempotent():
    rows = [L('CH0012221716', 'XSWX', 'ABB Ltd'), L('CH0012221716', 'XSTO', 'ABB Ltd'), L('DE0007164600', 'XETA', 'SAP SE')]
    a = build_model(copy.deepcopy(rows))
    b = build_model(copy.deepcopy(rows))
    assert json.dumps(a, sort_keys=True, default=str) == json.dumps(b, sort_keys=True, default=str)


def test_enrichment_adds_ticker_by_isin_and_mic_only():
    rows = [L('NL0010273215', 'XAMS', 'ASML HOLDING'), L('NL0010273215', 'XETB', 'ASML')]
    enrich(rows, {}, {('NL0010273215', 'XAMS'): {'ticker': 'ASML'}}, {})
    assert rows[0]['ticker'] == 'ASML' and rows[0]['ticker_source'] == 'euronext_equities' and rows[1]['ticker'] is None


# --- matching -------------------------------------------------------------------------------------
def test_matching_never_verifies_and_fuzzy_goes_to_review():
    listings = build_model([L('ES0113900J37', 'XMAD', 'BANCO SANTANDER S.A.'), L('ES0113860A34', 'XMAD', 'BANCO DE SABADELL S.A.')])['listings']
    out = match_candidates([{'candidate_id': 'a', 'name': 'Banco Santander', 'country': 'ES'},
                            {'candidate_id': 'b', 'name': 'Banco Santandr', 'country': 'ES'},
                            {'candidate_id': 'c', 'name': 'Nestle', 'country': 'ES'},
                            {'candidate_id': 'd', 'symbol': 'NVS', 'name': 'Novartis ADR', 'country': 'CH'}], listings)
    st = {o['candidate_id']: o['match_status'] for o in out}
    assert st == {'a': 'matched_exact_name', 'b': 'review_fuzzy', 'c': 'review_not_found', 'd': 'non_european_listing'}
    assert all(o['human_review'] == 'pending' and o['match_status'] != 'verified' for o in out)


def test_ambiguous_name_with_two_share_classes_goes_to_review():
    lei = '529900ZLCYCVMC6FVM02'
    listings = build_model([L('SE0000108656', 'XSTO', 'Ericsson', lei=lei), L('SE0000108649', 'XSTO', 'Ericsson', lei=lei)])['listings']
    out = match_candidates([{'candidate_id': 'x', 'name': 'Ericsson', 'country': 'SE'}], listings)
    assert out[0]['match_status'] == 'review_multiple_securities'


def test_name_normalisation_handles_firds_nominal_tokens():
    assert norm_name('SHELL PLC ORD EUR0.07') == norm_name('Shell') == 'shell'
    assert norm_name('E.ON SE Namens-Aktien o.N.') == norm_name('E.ON')
    assert norm_name('3i Group plc') == '3i' and norm_name('A2A') == 'a2a'


# --- index membership is dated --------------------------------------------------------------------
def test_index_membership_is_not_extrapolated():
    rows = [{'index': 'MDAX', 'isin': 'DE000A0WMPJ6', 'as_of': '2026-11-10'}]
    assert index_membership_status(rows, 'MDAX', 'DE000A0WMPJ6', '2026-11-10') == 'member'
    assert index_membership_status(rows, 'MDAX', 'DE0007164600', '2026-11-10') == 'not_member'
    assert index_membership_status(rows, 'MDAX', 'DE000A0WMPJ6', '2015-06-30') == 'unknown'
    interval = [{'index': 'DAX', 'isin': 'DE0007164600', 'valid_from': '1995-01-01', 'valid_to': None}]
    assert index_membership_status(interval, 'DAX', 'DE0007164600', '2020-01-01') == 'member'


# --- financial history ----------------------------------------------------------------------------
REPORTS = {'/LEI1/2021-12-31/ESEF/X/0/a.json': {'lei': 'LEI1', 'ende': '2021-12-31', 'roh': {
    'Revenue': {'2021-12-31': [100.0, 'iso4217:EUR', True], '2020-12-31': [90.0, 'iso4217:EUR', True]},
    'BasicEarningsLossPerShare': {'2021-12-31': [1.5, 'iso4217:EUR/xbrli:shares', True]},
    'CashFlowsFromUsedInOperatingActivities': {'2021-12-31': [30.0, 'iso4217:EUR', True]},
    'PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities': {'2021-12-31': [-10.0, 'iso4217:EUR', True]}}},
           '/LEI1/2022-12-31/ESEF/X/0/b.json': {'lei': 'LEI1', 'ende': '2022-12-31', 'roh': {
    'Revenue': {'2022-12-31': [120.0, 'iso4217:EUR', True], '2021-12-31': [101.0, 'iso4217:EUR', True]}}}}


def test_history_provenance_currency_unit_and_comparatives():
    facts = facts_from_reports(REPORTS)
    rev = {f['fiscal_year']: f for f in facts if f['field'] == 'revenue'}
    assert rev[2021]['value'] == 100.0 and not rev[2021]['is_comparative']   # own report beats later comparative (restated 101)
    assert rev[2020]['is_comparative'] and rev[2020]['report_period_end'] == '2021-12-31'
    eps = next(f for f in facts if f['field'] == 'eps_basic')
    assert eps['currency'] == 'EUR' and eps['unit'] == 'per_share'
    for f in facts:
        assert f['report_url'].startswith('https://filings.xbrl.org/') and f['xbrl_concept'].startswith('ifrs-full:')
        assert f['verification_status'] == 'machine_extracted' and f['human_review'] == 'pending'


def test_derived_free_cash_flow_documents_formula():
    d = derive(facts_from_reports(REPORTS))
    fcf = next(x for x in d if x['field'] == 'free_cash_flow')
    assert fcf['value'] == 20.0 and 'capex' in fcf['derivation'] and fcf['extraction_method'] == 'derived'


def test_missing_years_are_missing_not_zero():
    cov = coverage(['LEI1', 'LEI2'], facts_from_reports(REPORTS))
    assert cov['matrix']['LEI1']['2010'] == 'missing' and cov['matrix']['LEI2']['2021'] == 'missing'
    assert cov['matrix']['LEI1']['2021'] == 'partial'
    assert all(v in ('complete', 'partial', 'missing') for row in cov['matrix'].values() for v in row.values())


def test_plausibility_flags_mixed_currency():
    facts = facts_from_reports({'/L/2021-12-31/a.json': {'lei': 'L', 'ende': '2021-12-31', 'roh': {
        'Revenue': {'2021-12-31': [1.0, 'iso4217:DKK', True]}, 'Assets': {'2021-12-31': [5.0, 'iso4217:EUR', False]}}}})
    assert any(i['issue'].startswith('mixed_currencies') for i in plausibility(facts))


# --- committed outputs ----------------------------------------------------------------------------
def _load(name):
    return json.loads((UNI / name).read_text(encoding='utf-8'))


def test_committed_universe_consistent():
    s = json.loads((UNI / 'summary.json').read_text(encoding='utf-8'))
    listings, secs, issuers = _load('listings.json'), _load('securities.json'), _load('issuers.json')
    assert len(listings) == s['listings'] and len(secs) == s['securities'] and len(issuers) == s['issuers']
    assert s['invalid_isins'] == 0 and all(is_valid_isin(x['isin']) for x in secs)
    assert len({l['listing_id'] for l in listings}) == len(listings)
    assert all(l['source'] in ('esma_firds', 'fca_firds', 'six_equity_issuers') for l in listings)
    assert s['verified'] == 0
    for coll in (listings, secs, issuers):
        assert all(x['human_review'] == 'pending' for x in coll)
        assert not any(v == 'verified' for x in coll for v in x.values() if isinstance(v, str))


def test_committed_candidates_and_known_matches():
    m = {c['candidate_id']: c for c in _load('candidates_matched.json')}
    assert len(m) == 1002
    by_sym = {c.get('symbol'): c for c in m.values() if c.get('symbol')}
    assert by_sym['ASML.AS']['isin'] == 'NL0010273215' and by_sym['NOVN.SW']['isin'] == 'CH0012005267'
    assert by_sym['SAP.DE']['isin'] == 'DE0007164600' and by_sym['MC.PA']['isin'] == 'FR0000121014'
    assert all(c['match_status'] != 'verified' and c['human_review'] == 'pending' for c in m.values())
    assert all(c['isin'] is None for c in m.values() if c['match_status'].startswith('review') or c['match_status'] == 'non_european_listing')


def test_committed_sources_documented():
    src = json.loads((ROOT / 'data' / 'official_lists' / 'sources.json').read_text(encoding='utf-8'))
    ok = [x for x in src['lists'] if 'error' not in x]
    assert ok and all(x['url'].startswith('https://') and len(x['sha256']) == 64 and x['retrieved_at'] for x in ok)
    assert src['known_gaps']


def test_committed_history_never_zero_fills():
    cov = json.loads((HIST / 'coverage_matrix.json').read_text(encoding='utf-8'))
    per = cov['handoff_scope']['per_year']
    assert per['2010']['complete'] == 0 and per['2010']['partial'] == 0       # no ESEF before FY2020 comparatives
    facts = json.loads((HIST / 'financials_esef.json').read_text(encoding='utf-8'))['facts']
    assert all(f['human_review'] == 'pending' and f['verification_status'] != 'verified' for f in facts)
    assert all(f['currency'] or f['unit'] == 'shares' for f in facts)


def test_list_download_retries_transient_errors_then_gives_up():
    # Regression: first GitHub run failed when one list (Xetra) returned a transient error.
    import importlib.util
    import httpx
    spec = importlib.util.spec_from_file_location('bol', ROOT / 'scripts' / 'build_official_lists.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    calls = []

    def flaky(req):
        calls.append(1)
        return httpx.Response(502 if len(calls) < 3 else 200, text='ok')
    assert mod.RetryClient(httpx.Client(transport=httpx.MockTransport(flaky)), pause=0).get('https://x').status_code == 200
    calls.clear()
    with pytest.raises(httpx.HTTPError):
        mod.RetryClient(httpx.Client(transport=httpx.MockTransport(lambda r: (calls.append(1), httpx.Response(502))[1])), pause=0).get('https://x')
    assert len(calls) == 3


def test_missing_supplementary_list_falls_back_to_previous_tickers(tmp_path, monkeypatch):
    # Regression: GitHub runners cannot download the Xetra list; tickers must come from the last build, not vanish.
    import importlib.util
    spec = importlib.util.spec_from_file_location('bu', ROOT / 'scripts' / 'build_universe.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    (tmp_path / 'listings.json').write_text(json.dumps([
        {'isin': 'DE0007164600', 'mic': 'XETA', 'ticker': 'SAP', 'wkn': '716460', 'ticker_source': 'xetra_all_tradable'},
        {'isin': 'NL0010273215', 'mic': 'XAMS', 'ticker': 'ASML', 'ticker_source': 'euronext_equities'},
        {'isin': 'GB00BP6MXD84', 'mic': 'XLON', 'ticker': None, 'ticker_source': None}]), encoding='utf-8')
    monkeypatch.setattr(mod, 'OUT', tmp_path)
    prev = mod.previous_tickers()
    assert prev['xetra_all_tradable'] == {'DE0007164600': {'ticker': 'SAP', 'wkn': '716460'}}
    assert prev['euronext_equities'][('NL0010273215', 'XAMS')]['ticker'] == 'ASML'
    rows = [L('DE0007164600', 'XETA', 'SAP SE')]
    enrich(rows, prev['xetra_all_tradable'], {}, {})
    assert rows[0]['ticker'] == 'SAP' and rows[0]['ticker_source'] == 'xetra_all_tradable'
