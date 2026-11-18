"""Download dated official European instrument lists (free sources) into data/official_lists/raw/.

Writes data/official_lists/sources.json with URL, retrieval time, HTTP status, bytes and SHA-256 per list,
and records failures instead of hiding them. Raw files are not committed (see .gitignore).
Usage: python scripts/build_official_lists.py
"""
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.official_lists import FIRDS_FIELDS, FIRDS_URL, VENUES  # noqa: E402

RAW = ROOT / 'data' / 'official_lists' / 'raw'
REQUIRED = {'esma_firds', 'fca_firds', 'six_equity_issuers'}
UA = 'Mozilla/5.0 (compatible; EuropeEquityHub/0.7; official-list research)'
TERMS = {
    'esma_firds': 'ESMA public register data (MiFIR Art. 27); see https://www.esma.europa.eu/legal-notice',
    'fca_firds': 'FCA FIRDS public data; see https://www.fca.org.uk/legal',
    'six_equity_issuers': 'SIX Swiss Exchange public website data; see https://www.six-group.com/en/legal.html',
    'xetra_all_tradable': 'Deutsche Börse public instrument list; see https://www.deutsche-boerse.com/dbg-en/meta/imprint',
    'euronext_equities': 'Euronext public market data download; see https://www.euronext.com/en/terms-use',
    'nasdaq_nordic_screener': 'Nasdaq public website data; see https://www.nasdaq.com/terms-of-use',
}


def record(meta, key, url, resp=None, path=None, error=None, **extra):
    entry = {'source': key, 'url': url, 'retrieved_at': datetime.now(timezone.utc).isoformat(), 'terms_note': TERMS.get(key.split(':')[0])}
    if resp is not None:
        entry['http_status'] = resp.status_code
    if path is not None and path.exists():
        data = path.read_bytes()
        entry.update({'file': str(path.relative_to(ROOT)), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
    if error:
        entry['error'] = error
    entry.update(extra)
    meta.append(entry)


class RetryClient:
    """httpx client that retries transient failures (5xx, proxy errors, timeouts) up to 3 times."""

    def __init__(self, client, attempts=3, pause=15):
        self.c, self.attempts, self.pause = client, attempts, pause

    def _call(self, fn, *a, **kw):
        last = None
        for i in range(self.attempts):
            try:
                r = fn(*a, **kw)
                if r.status_code < 500:
                    return r
                last = httpx.HTTPStatusError(f'{r.status_code}', request=r.request, response=r)
            except httpx.HTTPError as e:
                last = e
            time.sleep(self.pause * (i + 1))
        raise last

    def get(self, *a, **kw):
        return self._call(self.c.get, *a, **kw)

    def post(self, *a, **kw):
        return self._call(self.c.post, *a, **kw)


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    meta = []
    c = RetryClient(httpx.Client(timeout=300, follow_redirects=True, headers={'User-Agent': UA}))
    firds_mics = [m for m in VENUES if m not in ('XLON', 'AIMX', 'XSWX')]
    for mic in firds_mics:
        url = FIRDS_URL
        params = {'q': '*:*', 'fq': [f'mic:{mic}', 'gnr_cfi_code:ES*', 'latest_received_flag:1', 'type_s:parent'],
                  'rows': '20000', 'wt': 'json', 'fl': FIRDS_FIELDS}
        path = RAW / f'firds_{mic}.json'
        try:
            r = c.get(url, params=params)
            r.raise_for_status()
            path.write_bytes(r.content)
            record(meta, f'esma_firds:{mic}', str(r.url), r, path, rows=r.json()['response']['numFound'])
        except Exception as e:
            record(meta, f'esma_firds:{mic}', url, error=f'{type(e).__name__}: {str(e)[:200]}')
        time.sleep(0.4)
    try:  # FCA FIRDS: newest full equity file
        q = c.get('https://api.data.fca.org.uk/fca_data_firds_files', params={
            'q': '((file_type:FULINS) AND (file_name:FULINS_E*))', 'wt': 'json', 'rows': '100'}).json()
        files = sorted((h['_source'] for h in q['hits']['hits'] if h['_source']['file_name'].startswith('FULINS_E_')),
                       key=lambda s: s['publication_date'])
        newest_date = files[-1]['publication_date']
        for f in [x for x in files if x['publication_date'] == newest_date]:
            path = RAW / f['file_name']
            r = c.get(f['download_link'])
            r.raise_for_status()
            path.write_bytes(r.content)
            record(meta, 'fca_firds:FULINS_E', f['download_link'], r, path, publication_date=newest_date)
    except Exception as e:
        record(meta, 'fca_firds:FULINS_E', 'https://api.data.fca.org.uk/fca_data_firds_files', error=f'{type(e).__name__}: {str(e)[:200]}')
    simple = [
        ('six_equity_issuers', 'https://www.six-group.com/sheldon/equity_issuers/v1/equity_issuers.csv', 'six.csv', {}),
        ('xetra_all_tradable', 'https://www.xetra.com/xetra-en/instruments/instruments', None, {}),
        ('euronext_equities', 'https://live.euronext.com/en/pd_es/data/stocks/download?mics=dm_all_stock', 'euronext.csv',
         {'method': 'POST', 'data': {'args[fe_type]': 'csv', 'args[fe_layout]': 'ver', 'args[fe_decimal_separator]': '.',
                                     'args[fe_date_format]': 'd/m/Y'}}),
    ]
    for key, url, fname, opt in simple:
        try:
            if key == 'xetra_all_tradable':  # link with a content hash changes daily -> read it from the instruments page
                import re
                page = c.get(url).text
                href = re.search(r'href="([^"]*t7-xetr-allTradableInstruments\.csv)"', page).group(1)
                url = 'https://www.xetra.com' + href
                fname = 'xetra.csv'
            r = c.post(url, data=opt['data']) if opt.get('method') == 'POST' else c.get(url)
            r.raise_for_status()
            path = RAW / fname
            path.write_bytes(r.content)
            record(meta, key, url, r, path)
        except Exception as e:
            record(meta, key, url, error=f'{type(e).__name__}: {str(e)[:200]}')
    for cat in ('MAIN_MARKET', 'FIRST_NORTH'):
        for m in ('STO', 'HEL', 'CPH', 'ICE'):
            url = f'https://api.nasdaq.com/api/nordic/screener/shares?category={cat}&tableonly=false&market={m}'
            path = RAW / f'nasdaq_{cat}_{m}.json'
            try:
                r = c.get(url, headers={'Accept': 'application/json'})
                r.raise_for_status()
                path.write_bytes(r.content)
                record(meta, f'nasdaq_nordic_screener:{cat}:{m}', url, r, path)
            except Exception as e:
                record(meta, f'nasdaq_nordic_screener:{cat}:{m}', url, error=f'{type(e).__name__}: {str(e)[:200]}')
    gaps = [{'venue': 'LSE tickers (TIDM)', 'reason': 'FCA FIRDS has no local ticker; LSE instrument list is JavaScript-rendered'},
            {'venue': 'Wiener Börse, BME, GPW, Athens, CEE tickers', 'reason': 'covered by ESMA FIRDS (ISIN/MIC) but no free machine-readable ticker list retrieved'},
            {'venue': 'Index constituents (except MDAX/SDAX already in repo)', 'reason': 'not retrieved; index membership left empty'}]
    out = {'generated_at': datetime.now(timezone.utc).isoformat(), 'lists': meta, 'known_gaps': gaps}
    (ROOT / 'data' / 'official_lists' / 'sources.json').write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    ok = sum('error' not in m for m in meta)
    print(f'{ok}/{len(meta)} lists retrieved')
    failed = [m for m in meta if 'error' in m]
    for m in failed:
        print(f"FEHLGESCHLAGEN (nach 3 Versuchen): {m['source']} - {m['error']}")
    # Primary sources (identity: ISIN, MIC, status, issuer) are mandatory; supplementary lists only add tickers
    # and fall back to the previous build in build_universe.py.
    required_failed = [m['source'] for m in failed if m['source'].split(':')[0] in REQUIRED]
    if required_failed:
        print('Pflichtquelle fehlt - Abbruch ohne Teilstand:', ', '.join(required_failed))
        sys.exit(1)
    if failed:
        print('Zusatzquelle(n) fehlen - Kuerzel werden aus dem letzten Stand übernommen.')


if __name__ == '__main__':
    main()
