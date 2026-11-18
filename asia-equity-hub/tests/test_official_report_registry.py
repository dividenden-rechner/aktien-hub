from app.reports import load_catalog, OFFICIAL_HOSTS, report_key
from urllib.parse import urlparse


def test_singapore_china_official_2025_reports_registered():
    reports = {x['symbol']: x for x in load_catalog()}
    for ticker in ('D05.SI', '002594.SZ'):
        entry = reports[ticker]
        assert entry['fiscal_year'] == 2025
        assert entry['report_type'] == 'annual'
        assert urlparse(entry['url']).hostname in OFFICIAL_HOSTS
        assert len(report_key(entry)) == 24


def test_download_claims_are_backed_by_checksums():
    """v1.1: a 'downloaded' claim must come with a pinned SHA-256 and page count."""
    for entry in load_catalog():
        if 'downloaded' in entry['verification']:
            assert len(entry.get('sha256', '')) == 64
            assert entry.get('page_count', 0) > 0
