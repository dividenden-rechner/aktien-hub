"""Auditable, opt-in ingestion of official Asian issuer annual-report PDFs.

Discovery is deliberately separate: exchange search pages are not stable public APIs.
Operators supply verified filing URLs in reports/catalog.json, then run sync.
"""
from __future__ import annotations
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx
from pypdf import PdfReader
from .providers import valid_symbol

ROOT = Path(os.getenv('REPORT_DATA_DIR', Path(__file__).resolve().parent.parent / 'reports'))
CATALOG = ROOT / 'catalog.json'
# Only known official disclosure hosts; add vetted domains after checking publication rights.
OFFICIAL_HOSTS = {
    'hkexnews.hk', 'www.hkexnews.hk', 'www1.hkexnews.hk', 'doc.irasia.com', 'www.firstpacific.com', 'sgx.com', 'www.sgx.com',
    'links.sgx.com', 'cninfo.com.cn', 'www.cninfo.com.cn', 'static.cninfo.com.cn',
    'sse.com.cn', 'www.sse.com.cn', 'szse.cn', 'www.szse.cn', 'disc.static.szse.cn', 'www.dbs.com',
}
PORTALS = {
    'HK': {'name':'HKEXnews', 'url':'https://www.hkexnews.hk/'},
    'SI': {'name':'SGX announcements', 'url':'https://www.sgx.com/securities/company-announcements'},
    'SS': {'name':'Shanghai Stock Exchange', 'url':'https://www.sse.com.cn/'},
    'SZ': {'name':'CNINFO', 'url':'https://www.cninfo.com.cn/'},
}

def portal_for(symbol: str) -> dict:
    symbol = valid_symbol(symbol)
    suffix = symbol.rsplit('.', 1)[-1]
    return PORTALS.get(suffix, {'name':'Official issuer investor-relations site', 'url':None})

def _proxy_configured() -> bool:
    return any(os.environ.get(k) for k in ('HTTPS_PROXY', 'https_proxy', 'ALL_PROXY', 'all_proxy'))


def validate_url(url: str, resolve: bool = True) -> str:
    """Allowlist + scheme check, plus a defensive DNS check against private targets.

    v1.1 fix: behind an HTTP(S) proxy (corporate networks, some CI runners, sandboxes)
    the local resolver often cannot resolve public hosts; the proxy resolves them.
    v1.0 aborted every download with ``gaierror`` in that situation. Now a failed
    local lookup is tolerated *only* when a proxy is configured; a lookup that
    succeeds and returns a non-public address is still rejected.
    """
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.username or parsed.password or parsed.port not in (None,443):
        raise ValueError('Only standard HTTPS official filing URLs are permitted')
    host = (parsed.hostname or '').lower()
    if host not in OFFICIAL_HOSTS:
        raise ValueError('URL host is not on the vetted official filing host allowlist')
    if not resolve:
        return url
    try:
        infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except socket.gaierror:
        if _proxy_configured():
            return url  # the configured proxy performs resolution
        raise ValueError(f'DNS resolution failed for {host} and no HTTPS proxy is configured')
    for family, _, _, _, sockaddr in infos:
        addr = ipaddress.ip_address(sockaddr[0])
        if not addr.is_global:
            raise ValueError('Filing host resolved to a non-public IP')
    return url

def load_catalog() -> list[dict]:
    if not CATALOG.exists():
        return []
    items = json.loads(CATALOG.read_text(encoding='utf-8'))
    if not isinstance(items, list):
        raise ValueError('Report catalog must be a JSON array')
    for item in items:
        valid_symbol(item['symbol'])
        if not isinstance(item.get('fiscal_year'), int) or not 1990 <= item['fiscal_year'] <= 2100:
            raise ValueError('Invalid fiscal year')
        if item.get('report_type') not in ('annual', 'interim'):
            raise ValueError('Invalid report type')
        # Host syntax is checked at catalog read; network validation happens at download.
        parsed = urlparse(item['url'])
        if parsed.scheme != 'https' or (parsed.hostname or '').lower() not in OFFICIAL_HOSTS:
            raise ValueError('Non-official URL in catalog')
    return items

def list_reports(symbol: str) -> dict:
    symbol = valid_symbol(symbol)
    reports = []
    for entry in load_catalog():
        if entry['symbol'] != symbol:
            continue
        key = report_key(entry)
        meta = ROOT / 'cache' / f'{key}.json'
        record = dict(entry)
        record['status'] = 'ingested' if meta.exists() else 'registered'
        if meta.exists():
            record['ingestion'] = json.loads(meta.read_text(encoding='utf-8'))
        reports.append(record)
    return {'symbol':symbol,'official_portal':portal_for(symbol), 'reports':reports,
            'discovery_status':'manual_verified_url_registry',
            'note':'Official filing URLs must first be verified and registered. No automated exchange search is claimed.'}

def report_key(entry: dict) -> str:
    identity = f"{entry['symbol']}|{entry['fiscal_year']}|{entry['report_type']}|{entry['url']}"
    return hashlib.sha256(identity.encode()).hexdigest()[:24]

USER_AGENT = 'Mozilla/5.0 (compatible; AsiaEquityHub/1.1; annual-report research)'


def download_pdf(url: str, max_bytes: int = 45_000_000, timeout: float = 120) -> bytes:
    """Download one allowlisted PDF. Redirects are rejected, size is capped."""
    url = validate_url(url)
    with httpx.Client(timeout=timeout, follow_redirects=False, headers={'User-Agent': USER_AGENT}) as client:
        with client.stream('GET', url) as response:
            # v1.1 fix: check redirects *before* raise_for_status (httpx raises on 3xx,
            # which made the explicit redirect message unreachable in v1.0).
            if response.status_code in (301, 302, 303, 307, 308):
                raise ValueError(f'Redirect to {response.headers.get("location")!r} not followed; '
                                 'register the final official PDF URL instead')
            response.raise_for_status()
            declared = response.headers.get('content-length')
            if declared and declared.isdigit() and int(declared) > max_bytes:
                raise ValueError('Report exceeds maximum permitted download size')
            chunks, size = [], 0
            for chunk in response.iter_bytes():
                size += len(chunk)
                if size > max_bytes:
                    raise ValueError('Report exceeds maximum permitted download size')
                chunks.append(chunk)
    data = b''.join(chunks)
    if not data.startswith(b'%PDF-'):
        raise ValueError('Official URL did not return a PDF')
    return data


def pdf_page_texts(data: bytes, max_pages: int = 600) -> tuple[list[str], int]:
    """Text of every page (index 0 = PDF page 1). Empty pages stay as '' to keep numbering."""
    from io import BytesIO
    reader = PdfReader(BytesIO(data), strict=False)
    if reader.is_encrypted:
        raise ValueError('Encrypted reports are not supported')
    texts = [(page.extract_text() or '') for page in reader.pages[:max_pages]]
    return texts, len(reader.pages)


def sync_report(entry: dict, max_bytes: int = 45_000_000, max_pages: int = 600,
                max_chars_per_page: int = 60_000) -> dict:
    """Download, checksum and text-extract one registered report into reports/cache/.

    v1.1 changes: limits raised (CKH's report has 352 pages; v1.0 stopped at 350),
    all pages are stored (also empty ones) so list position == PDF page number - 1,
    truncation is recorded instead of silent, and an expected SHA-256 in the catalog
    is enforced.
    """
    url = entry['url']
    key = report_key(entry)
    cache = ROOT / 'cache'
    cache.mkdir(parents=True, exist_ok=True)
    data = download_pdf(url, max_bytes=max_bytes)
    digest = hashlib.sha256(data).hexdigest()
    expected = entry.get('sha256')
    if expected and expected != digest:
        raise ValueError(f'SHA-256 mismatch: catalog {expected[:12]}…, downloaded {digest[:12]}… '
                         '(issuer may have replaced the PDF; re-verify before use)')
    texts, page_count = pdf_page_texts(data, max_pages=max_pages)
    truncated = [i + 1 for i, t in enumerate(texts) if len(t) > max_chars_per_page]
    pages = [{'page': i + 1, 'text': t[:max_chars_per_page]} for i, t in enumerate(texts)]
    pdf_path = cache / f'{key}.pdf'
    pdf_path.write_bytes(data)
    (cache / f'{key}.pages.json').write_text(json.dumps(pages, ensure_ascii=False), encoding='utf-8')
    meta = {'id': key, 'symbol': entry['symbol'], 'fiscal_year': entry['fiscal_year'],
            'report_type': entry['report_type'], 'source_url': url,
            'sha256': digest, 'sha256_expected': expected,
            'bytes': len(data), 'page_count': page_count,
            'extracted_pages': len(pages),
            'pages_with_text': sum(1 for t in texts if t.strip()),
            'pages_not_extracted': max(0, page_count - len(pages)),
            'text_truncated_pages': truncated,
            'ingested_at': datetime.now(timezone.utc).isoformat(),
            'extraction_status': 'raw_text',
            'warning': 'Raw page text. Use the profile-based statement extractor for figures; OCR is not implemented.'}
    (cache / f'{key}.json').write_text(json.dumps(meta, indent=2), encoding='utf-8')
    return meta


def cached_pages(entry: dict, root: Path | None = None) -> list[str] | None:
    """Page texts from cache as a list indexed by PDF page number - 1 (None if not ingested)."""
    root = root or ROOT
    path = root / 'cache' / f'{report_key(entry)}.pages.json'
    if not path.is_file():
        return None
    items = json.loads(path.read_text(encoding='utf-8'))
    if not items:
        return []
    size = max(int(x['page']) for x in items)
    out = [''] * size
    for x in items:
        out[int(x['page']) - 1] = x.get('text') or ''
    return out


def cached_pdf(entry: dict, root: Path | None = None) -> Path | None:
    root = root or ROOT
    path = root / 'cache' / f'{report_key(entry)}.pdf'
    return path if path.is_file() else None


def sync_registered(symbol: str, year: int | None = None) -> list[dict]:
    symbol = valid_symbol(symbol)
    return [sync_report(item) for item in load_catalog()
            if item['symbol']==symbol and (year is None or item['fiscal_year']==year)]
