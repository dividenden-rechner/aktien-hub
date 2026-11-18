import json
import httpx
import pytest
from app.hkex import discover_hkex, parse_search_results, normalize_pdf_url


def test_parser_filters_and_deduplicates():
    data={'result':[
      {'TITLE':'ANNUAL REPORT 2025', 'FILE_LINK':'/listedco/listconews/sehk/2026/0401/202604010001.pdf', 'DATE_TIME':'2026-04-01'},
      {'TITLE':'ANNUAL REPORT 2025', 'FILE_LINK':'/listedco/listconews/sehk/2026/0401/202604010001.pdf'},
      {'TITLE':'INTERIM REPORT 2025', 'FILE_LINK':'/listedco/other.pdf'},
      {'TITLE':'ANNUAL REPORT 2024', 'FILE_LINK':'/listedco/2024.pdf'},
      {'TITLE':'ANNUAL REPORT 2025', 'FILE_LINK':'https://evil.example/steal.pdf'},
    ]}
    rows=parse_search_results(data,'0700.HK',2025)
    assert len(rows)==1
    assert rows[0]['verification_status']=='candidate_unverified'
    assert rows[0]['url'].startswith('https://www1.hkexnews.hk/')


def test_bad_host_and_missing_response():
    assert normalize_pdf_url('https://www1.hkexnews.hk.evil.test/a.pdf') is None
    assert normalize_pdf_url('http://www1.hkexnews.hk/a.pdf') is None
    with pytest.raises(ValueError):
        parse_search_results({'error':'blocked'},'0700.HK',2025)


def test_discovery_with_mock_transport():
    # Mirrors the live HKEX behaviour observed 2026-11-18: internal stockId lookup via
    # prefix.do (JSONP) and `result` delivered as a JSON-encoded string.
    def handler(request):
        assert request.url.host == 'www1.hkexnews.hk'
        if request.url.path == '/search/prefix.do':
            assert request.url.params['name'] == '00700'
            return httpx.Response(200, text='callback({"more":"0","stockInfo":[{"stockId":7609,"code":"00700","name":"TENCENT"}]});')
        assert request.url.params['stockId'] == '7609'
        assert request.url.params['t2code'] == '40100'
        return httpx.Response(200, json={'result': json.dumps([{'TITLE': '2025 ANNUAL REPORT', 'FILE_LINK': '/a.pdf'}])})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result=discover_hkex('0700.HK',2025,client=client)
    assert len(result['candidates'])==1
    assert result['hkex_stock_id'] == 7609
    assert result['status']=='candidates_unverified'


def test_null_result_string_means_no_candidates():
    assert parse_search_results({'result': 'null'}, '0019.HK', 2025) == []


def test_non_hk_rejected():
    with pytest.raises(ValueError):
        discover_hkex('D05.SI',2025)


def test_inactive_securities_fallback_and_undated_titles():
    from app.hkex import discover_hkex_years
    calls = []

    def handler(request):
        calls.append(request.url.params.get('type'))
        if request.url.path == '/search/prefix.do':
            if request.url.params['type'] == 'A':
                return httpx.Response(200, text='callback({"stockInfo":[{"stockId":44,"code":"00030","name":"X"}]});')
            return httpx.Response(200, text='callback({"stockInfo":[{"stockId":18,"code":"00011","name":"HANG SENG BANK"}]});')
        assert request.url.params['stockId'] == '18'
        return httpx.Response(200, json={'result': json.dumps([
            {'TITLE': 'Annual Report', 'FILE_LINK': '/listedco/a.pdf', 'DATE_TIME': '28/04/2026 12:00'},
            {'TITLE': 'Annual Report 2024', 'FILE_LINK': '/listedco/b.pdf', 'DATE_TIME': '20/03/2025 12:00'}])})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        out = discover_hkex_years('0011.HK', [2024, 2025], client)
    assert calls[:2] == ['A', 'I'] and out['hkex_stock_id'] == 18
    assert out['by_year'][2024][0]['url'].endswith('/b.pdf') and 'fiscal_year_basis' not in out['by_year'][2024][0]
    assert out['by_year'][2025][0]['fiscal_year_basis'] == 'publication_year_minus_one_unverified'
