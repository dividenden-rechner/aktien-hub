"""v1.7 OpenDART / EDINET registration with mocked HTTP (the real run needs the API keys)."""
import datetime as dt
import io
import zipfile

import httpx
import pytest

from app.regulator_sources import japan_sources, korea_sources, parse_dart_reports, parse_edinet_day

KEY = 'SECRET-KEY-123'
CORPCODE = '''<?xml version="1.0" encoding="UTF-8"?><result>
<list><corp_code>00126380</corp_code><corp_name>삼성전자</corp_name><corp_eng_name>SAMSUNG ELECTRONICS CO,.LTD</corp_eng_name><stock_code>005930</stock_code></list>
<list><corp_code>00999999</corp_code><corp_name>비상장</corp_name><stock_code> </stock_code></list>
</result>'''


def _zip():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        z.writestr('CORPCODE.xml', CORPCODE)
    return buf.getvalue()


def test_korea_confirm_reject_and_reports():
    def handler(req):
        assert req.url.params['crtfc_key'] == KEY
        if req.url.path.endswith('corpCode.xml'):
            return httpx.Response(200, content=_zip())
        if req.url.path.endswith('company.json'):
            return httpx.Response(200, json={'status': '000', 'corp_cls': 'Y', 'corp_name_eng': 'SAMSUNG ELECTRONICS CO,.LTD', 'jurir_no': '1301110006246'})
        assert req.url.params['pblntf_detail_ty'] == 'A001'
        return httpx.Response(200, json={'status': '000', 'list': [
            {'report_nm': '사업보고서 (2024.12)', 'rcept_no': '20250311001085', 'rcept_dt': '20250311'},
            {'report_nm': '[기재정정]사업보고서 (2023.12)', 'rcept_no': '20240401000001', 'rcept_dt': '20240401'},
            {'report_nm': '반기보고서 (2025.06)', 'rcept_no': 'x', 'rcept_dt': '20250814'}]})
    entries = [{'id': 'k1', 'exchange_code': '005930'}, {'id': 'k2', 'exchange_code': '123456'}]
    with httpx.Client(transport=httpx.MockTransport(handler)) as c:
        out = korea_sources(entries, KEY, c, list(range(2016, 2026)), pause=0)
    assert out['identities']['k1']['ticker'] == '005930.KS' and out['identities']['k1']['identifiers']['dart_corp_code'] == '00126380'
    assert out['identities']['k2']['status'] == 'not_in_current_official_list'
    docs = out['sources']['k1']['documents_by_year']
    assert docs['2024'][0]['url'] == 'https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20250311001085'
    assert docs['2023'][0]['is_amendment'] and docs['2025'] == []
    assert KEY not in str(out)


def test_api_key_never_in_error_messages():
    def handler(req):
        return httpx.Response(500)
    with httpx.Client(transport=httpx.MockTransport(handler)) as c, pytest.raises(RuntimeError) as exc:
        korea_sources([], KEY, c, [2024], pause=0)
    assert KEY not in str(exc.value) and '***' in str(exc.value)


def test_kosdaq_suffix():
    def handler(req):
        if req.url.path.endswith('corpCode.xml'):
            return httpx.Response(200, content=_zip())
        if req.url.path.endswith('company.json'):
            return httpx.Response(200, json={'status': '000', 'corp_cls': 'K'})
        return httpx.Response(200, json={'status': '013'})
    with httpx.Client(transport=httpx.MockTransport(handler)) as c:
        out = korea_sources([{'id': 'k', 'exchange_code': '005930'}], KEY, c, [2024], pause=0)
    assert out['identities']['k']['ticker'] == '005930.KQ' and out['sources']['k']['years_with_candidates'] == []


def test_edinet_day_parsing_and_fiscal_year_basis():
    rows = [
        {'edinetCode': 'E02144', 'docTypeCode': '120', 'docID': 'S100A', 'periodStart': '2024-04-01', 'periodEnd': '2025-03-31',
         'submitDateTime': '2025-06-18 15:00', 'docDescription': '有価証券報告書－第121期', 'withdrawalStatus': '0'},
        {'edinetCode': 'E02144', 'docTypeCode': '130', 'docID': 'S100B', 'periodStart': '2024-04-01', 'periodEnd': '2025-03-31', 'withdrawalStatus': '0'},
        {'edinetCode': 'E02144', 'docTypeCode': '160', 'docID': 'S100C'},
        {'edinetCode': 'E99999', 'docTypeCode': '120', 'docID': 'S100D'},
        {'edinetCode': 'E02144', 'docTypeCode': '120', 'docID': 'S100E', 'periodStart': '2023-04-01', 'withdrawalStatus': '1'},
    ]
    out = parse_edinet_day(rows, {'E02144'})
    assert [d['doc_id'] for d in out] == ['S100A', 'S100B']
    assert out[0]['fiscal_year'] == 2024 and not out[0]['is_amendment'] and out[1]['is_amendment']
    assert out[0]['url'] == 'https://api.edinet-fsa.go.jp/api/v2/documents/S100A?type=2'


def test_edinet_scan_skips_weekends_and_counts_failures():
    dates = []

    def handler(req):
        assert req.url.params['Subscription-Key'] == KEY and req.url.params['type'] == '2'
        dates.append(req.url.params['date'])
        if req.url.params['date'] == '2025-06-19':
            return httpx.Response(503)
        return httpx.Response(200, json={'results': [
            {'edinetCode': 'E02144', 'docTypeCode': '120', 'docID': 'S1' + req.url.params['date'][-2:],
             'periodStart': '2024-04-01', 'periodEnd': '2025-03-31', 'withdrawalStatus': '0'}]})
    entries = [{'id': 'j1', 'identifiers': {'edinet_code': 'E02144'}}]
    with httpx.Client(transport=httpx.MockTransport(handler)) as c:
        out = japan_sources(entries, KEY, c, [2024], dt.date(2025, 6, 18), dt.date(2025, 6, 22), pause=0)
    assert dates == ['2025-06-18', '2025-06-19', '2025-06-20']  # 21/22 June 2025 = weekend
    assert out['days_scanned'] == 3 and out['days_failed'] == 1
    assert out['sources']['j1']['years_with_candidates'] == [2024]
    assert KEY not in str(out)


def test_dart_report_title_parsing():
    out = parse_dart_reports([{'report_nm': '사업보고서 (2019.03)', 'rcept_no': '1', 'rcept_dt': '20190615'}], [2019])
    assert out['2019'][0]['period_end'] == '2019-03'


def test_apply_korea_merges_without_losing_ids():
    # Regression for the first GitHub run (2026-11-18): KeyError 'id' after e.clear().
    from build_regulator_sources import apply_korea
    ident = {'entries': [
        {'id': 'k1', 'requested_name': 'Samsung Electronics', 'market': 'Südkorea', 'exchange': 'KRX',
         'human_review': 'pending', 'status': 'candidate_unverified', 'ticker': '005930.KS', 'exchange_code': '005930'},
        {'id': 'j1', 'requested_name': 'Kao', 'market': 'Japan', 'exchange': 'TSE', 'human_review': 'pending'}]}
    src = {'k1': {'id': 'k1', 'source_status': 'dart_api_key_required', 'note': 'x'}, 'j1': {'id': 'j1'}}
    res = {'identities': {'k1': {'status': 'confirmed_official_list', 'ticker': '005930.KS', 'exchange': 'KOSPI',
                                 'identifiers': {'dart_corp_code': '00126380'}}},
           'sources': {'k1': {'source_status': 'dart_queried', 'documents_by_year': {}, 'years_with_candidates': []}}}
    apply_korea(ident, src, res)
    k = ident['entries'][0]
    assert k['id'] == 'k1' and k['requested_name'] == 'Samsung Electronics' and k['exchange'] == 'KOSPI'
    assert k['status'] == 'confirmed_official_list' and k['human_review'] == 'pending'
    assert src['k1']['source_status'] == 'dart_queried' and 'note' not in src['k1']
    assert ident['entries'][1] == {'id': 'j1', 'requested_name': 'Kao', 'market': 'Japan', 'exchange': 'TSE', 'human_review': 'pending'}
