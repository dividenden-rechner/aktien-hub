"""Download path hardening (no network: DNS and HTTP are mocked)."""
import socket

import httpx
import pytest

from app import reports

REAL_CLIENT = httpx.Client


def test_dns_failure_tolerated_only_behind_proxy(monkeypatch):
    def fail(*a, **k):
        raise socket.gaierror(-3, 'Temporary failure in name resolution')
    monkeypatch.setattr(reports.socket, 'getaddrinfo', fail)
    for key in ('HTTPS_PROXY', 'https_proxy', 'ALL_PROXY', 'all_proxy'):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(ValueError, match='DNS resolution failed'):
        reports.validate_url('https://www.dbs.com/a.pdf')
    monkeypatch.setenv('HTTPS_PROXY', 'http://proxy.local:3128')
    assert reports.validate_url('https://www.dbs.com/a.pdf') == 'https://www.dbs.com/a.pdf'


def test_private_resolution_still_rejected(monkeypatch):
    monkeypatch.setattr(reports.socket, 'getaddrinfo',
                        lambda *a, **k: [(socket.AF_INET, None, None, None, ('10.0.0.5', 443))])
    with pytest.raises(ValueError, match='non-public'):
        reports.validate_url('https://www.dbs.com/a.pdf')


def _patch_client(monkeypatch, handler):
    monkeypatch.setattr(reports.httpx, 'Client', lambda **kw: REAL_CLIENT(transport=httpx.MockTransport(handler), **kw))
    monkeypatch.setattr(reports, 'validate_url', lambda url, resolve=True: url)


def test_redirect_is_reported_not_followed(monkeypatch):
    _patch_client(monkeypatch, lambda req: httpx.Response(302, headers={'location': 'https://evil.test/x.pdf'}))
    with pytest.raises(ValueError, match='Redirect'):
        reports.download_pdf('https://www.dbs.com/a.pdf')


def test_non_pdf_and_oversize_rejected(monkeypatch):
    _patch_client(monkeypatch, lambda req: httpx.Response(200, content=b'<html>blocked</html>'))
    with pytest.raises(ValueError, match='did not return a PDF'):
        reports.download_pdf('https://www.dbs.com/a.pdf')
    _patch_client(monkeypatch, lambda req: httpx.Response(200, content=b'%PDF-' + b'0' * 2000))
    with pytest.raises(ValueError, match='maximum'):
        reports.download_pdf('https://www.dbs.com/a.pdf', max_bytes=1000)


def test_sha_mismatch_blocks_ingestion(monkeypatch, tmp_path):
    monkeypatch.setattr(reports, 'ROOT', tmp_path)
    monkeypatch.setattr(reports, 'download_pdf', lambda url, max_bytes=0: b'%PDF-1.7 different')
    entry = {'symbol': 'D05.SI', 'fiscal_year': 2025, 'report_type': 'annual',
             'url': 'https://www.dbs.com/a.pdf', 'sha256': '0' * 64}
    with pytest.raises(ValueError, match='SHA-256 mismatch'):
        reports.sync_report(entry)
    assert not (tmp_path / 'cache' / f'{reports.report_key(entry)}.pdf').exists()
