import httpx
import pytest
from app.asia_discovery import parse_cninfo, safe_document_url, discover_cninfo, discover_asia


def test_cninfo_filters_summary_wrong_company_and_year():
    payload={'announcements':[
      {'secCode':'002594','announcementTitle':'2025年年度报告','adjunctUrl':'finalpage/2026-04-01/123.pdf'},
      {'secCode':'002594','announcementTitle':'2025年年度报告摘要','adjunctUrl':'summary.pdf'},
      {'secCode':'000001','announcementTitle':'2025年年度报告','adjunctUrl':'other.pdf'},
      {'secCode':'002594','announcementTitle':'2024年年度报告','adjunctUrl':'old.pdf'},
      {'secCode':'002594','announcementTitle':'2025年半<em>年度报告</em>','adjunctUrl':'half.pdf'},
      {'secCode':'002594','announcementTitle':'关于召开2025年<em>年度报告</em>网上说明会并征集问题的公告','adjunctUrl':'brief.pdf'},
    ]}
    rows=parse_cninfo(payload,'002594.SZ',2025)
    assert len(rows)==1
    assert rows[0]['url']=='https://static.cninfo.com.cn/finalpage/2026-04-01/123.pdf'
    assert rows[0]['verification_status']=='candidate_unverified'


def test_bad_pdf_hosts_rejected():
    assert safe_document_url('https://evil.example/a.pdf','https://static.cninfo.com.cn/',{'static.cninfo.com.cn'}) is None
    assert safe_document_url('//evil.example/a.pdf','https://static.cninfo.com.cn/',{'static.cninfo.com.cn'}) is None
    assert safe_document_url('x.html','https://static.cninfo.com.cn/',{'static.cninfo.com.cn'}) is None


def test_cninfo_mock_transport():
    def handler(req):
        assert req.method=='POST'
        assert req.url.host=='www.cninfo.com.cn'
        assert b'category=category_ndbg_szsh%3B' in req.content
        return httpx.Response(200,json={'announcements':[{'secCode':'600519','announcementTitle':'2025年年度报告','adjunctUrl':'2026/1.pdf'}]})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        out=discover_cninfo('600519.SS',2025,client=client)
    assert len(out['candidates'])==1


def test_sgx_honest_fallback():
    out=discover_asia('D05.SI',2025)
    assert out['status']=='manual_search_required'
    assert out['candidates']==[]


def test_invalid_market():
    with pytest.raises(ValueError):
        discover_asia('7203.T',2025)


def test_announcement_about_report_is_not_a_report():
    payload = {'announcements': [
        {'secCode': '600900', 'announcementTitle': '长江电力关于《2022年年度报告》《2023年第一季度报告》披露日期变更的公告', 'adjunctUrl': 'x.pdf'},
        {'secCode': '600900', 'announcementTitle': '长江电力2022年年度报告', 'adjunctUrl': 'finalpage/2023/1.pdf'}]}
    rows = parse_cninfo(payload, '600900.SS', 2022)
    assert [r['url'] for r in rows] == ['https://static.cninfo.com.cn/finalpage/2023/1.pdf']


def test_cninfo_multi_year_fallback_for_uncategorised_reports():
    from app.asia_discovery import discover_cninfo_years
    seen = []

    def handler(req):
        body = req.content.decode()
        seen.append('category=category_ndbg_szsh' in body)
        if 'category=category_ndbg_szsh' in body:
            return httpx.Response(200, json={'announcements': [{'secCode': '600900', 'announcementTitle': '2019年年度报告', 'adjunctUrl': 'a/2019.pdf'}], 'hasMore': False})
        return httpx.Response(200, json={'announcements': [{'secCode': '600900', 'announcementTitle': '2020年年度报告', 'adjunctUrl': 'a/2020.pdf'}], 'hasMore': False})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        out = discover_cninfo_years('600900.SS', [2019, 2020], client)
    assert seen == [True, False] and out['fallback_used']
    assert out['by_year'][2020][0]['source'] == 'CNINFO full-text title search (fallback)'
