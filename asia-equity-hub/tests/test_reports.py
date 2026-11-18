import pytest
from app.reports import portal_for, validate_url, list_reports, report_key

def test_portals():
    assert portal_for('0700.HK')['name'] == 'HKEXnews'
    assert portal_for('D05.SI')['name'] == 'SGX announcements'
    assert portal_for('600519.SS')['name'] == 'Shanghai Stock Exchange'

def test_invalid_url_rejected_before_network():
    for url in ('http://www.hkexnews.hk/a.pdf','https://127.0.0.1/x.pdf',
                'https://example.com/a.pdf','https://www.hkexnews.hk.evil.test/a.pdf'):
        with pytest.raises(ValueError):
            validate_url(url)

def test_empty_catalog_and_status():
    result = list_reports('0700.HK')
    assert result['reports'] == []
    assert result['discovery_status'] == 'manual_verified_url_registry'

def test_stable_key():
    entry={'symbol':'0700.HK','fiscal_year':2025,'report_type':'annual','url':'https://www.hkexnews.hk/test.pdf'}
    assert report_key(entry) == report_key(entry)
