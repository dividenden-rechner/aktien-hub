"""Official, free European instrument lists -> normalised listing records (v0.7).

Primary sources (regulatory, complete for their venues):
* ESMA FIRDS (EU trading venues; ISIN, MIC, CFI, currency, issuer LEI, admission/termination dates)
* FCA FIRDS FULINS_E (UK trading venues, same ISO 20022 schema)
* SIX Swiss Exchange equity issuers CSV (Switzerland is outside FIRDS)
Supplementary exchange lists (add local tickers/sectors; ISIN is the join key):
* Deutsche Börse Xetra "allTradableInstruments", Euronext equities CSV, Nasdaq Nordic screener

Every record keeps its source key; list metadata (URL, retrieval time, SHA-256) is stored separately.
Only shares (CFI category 'ES') are kept from FIRDS. Terminated listings are kept and flagged.
"""
from __future__ import annotations

import csv
import io
import json
import zipfile
from datetime import datetime, timezone
from xml.etree.ElementTree import iterparse

from .isin import is_valid_isin

# Venue MIC -> (country, venue name, segment). Growth/MTF segments are included on purpose.
VENUES = {
    'XETA': ('DE', 'Xetra (regulated market)', 'main'), 'XETB': ('DE', 'Xetra (open market / Scale)', 'open_market'),
    'XPAR': ('FR', 'Euronext Paris', 'main'), 'ALXP': ('FR', 'Euronext Growth Paris', 'growth'),
    'XAMS': ('NL', 'Euronext Amsterdam', 'main'), 'XBRU': ('BE', 'Euronext Brussels', 'main'),
    'XLIS': ('PT', 'Euronext Lisbon', 'main'), 'XMSM': ('IE', 'Euronext Dublin', 'main'),
    'MTAA': ('IT', 'Euronext Milan', 'main'), 'EXGM': ('IT', 'Euronext Growth Milan', 'growth'),
    'XOSL': ('NO', 'Oslo Børs', 'main'), 'XMAD': ('ES', 'BME Madrid', 'main'), 'MABX': ('ES', 'BME Growth', 'growth'),
    'WBAH': ('AT', 'Wiener Börse (Amtlicher Handel)', 'main'),
    'XSTO': ('SE', 'Nasdaq Stockholm', 'main'), 'XNGM': ('SE', 'Nordic Growth Market', 'growth'),
    'XHEL': ('FI', 'Nasdaq Helsinki', 'main'), 'XCSE': ('DK', 'Nasdaq Copenhagen', 'main'), 'XICE': ('IS', 'Nasdaq Iceland', 'main'),
    'XWAR': ('PL', 'GPW Warsaw', 'main'), 'XNCO': ('PL', 'GPW NewConnect', 'growth'), 'XATH': ('GR', 'Athens Exchange', 'main'),
    'XTAL': ('EE', 'Nasdaq Tallinn', 'main'), 'XRIS': ('LV', 'Nasdaq Riga', 'main'), 'XLIT': ('LT', 'Nasdaq Vilnius', 'main'),
    'XPRA': ('CZ', 'Prague Stock Exchange', 'main'), 'XBUD': ('HU', 'Budapest Stock Exchange', 'main'),
    'XBSE': ('RO', 'Bucharest Stock Exchange', 'main'), 'XZAG': ('HR', 'Zagreb Stock Exchange', 'main'),
    'XLJU': ('SI', 'Ljubljana Stock Exchange', 'main'), 'XBRA': ('SK', 'Bratislava Stock Exchange', 'main'),
    'XBUL': ('BG', 'Bulgarian Stock Exchange', 'main'),
    'XLON': ('GB', 'London Stock Exchange (Main Market)', 'main'), 'AIMX': ('GB', 'London Stock Exchange (AIM)', 'growth'),
    'XSWX': ('CH', 'SIX Swiss Exchange', 'main'),
}
FIRDS_URL = 'https://registers.esma.europa.eu/solr/esma_registers_firds/select'
FIRDS_FIELDS = ('isin,mic,gnr_full_name,gnr_short_name,gnr_cfi_code,gnr_notional_curr_code,lei,'
                'mrkt_trdng_start_date,mrkt_trdng_trmination_date,status_label,publication_date')


def _status(termination: str | None, asof: datetime) -> str:
    if not termination:
        return 'active'
    try:
        end = datetime.fromisoformat(termination.replace('Z', '+00:00'))
    except ValueError:
        return 'unknown'
    return 'terminated' if end < asof else 'active_with_end_date'


def _listing(isin, mic, name, short, cfi, ccy, lei, start, end, source, asof, **extra) -> dict:
    country, venue, segment = VENUES.get(mic, (None, mic, None))
    return {'isin': isin, 'isin_valid': is_valid_isin(isin), 'mic': mic, 'venue': venue, 'venue_country': country,
            'segment': segment, 'name': name, 'short_name': short, 'cfi': cfi, 'trading_currency': ccy,
            'issuer_lei': lei or None, 'first_trade': (start or '')[:10] or None, 'termination': (end or '')[:10] or None,
            'listing_status': _status(end, asof), 'source': source, **extra}


def parse_firds_solr(docs: list[dict], asof: datetime) -> list[dict]:
    return [_listing(d.get('isin'), d.get('mic'), d.get('gnr_full_name'), d.get('gnr_short_name'), d.get('gnr_cfi_code'),
                     d.get('gnr_notional_curr_code'), d.get('lei'), d.get('mrkt_trdng_start_date'),
                     d.get('mrkt_trdng_trmination_date'), 'esma_firds', asof)
            for d in docs if (d.get('gnr_cfi_code') or '').startswith('ES')]


def parse_fca_fulins(zip_bytes_or_path, mics: set[str], asof: datetime) -> list[dict]:
    out = []
    tag = lambda e: e.tag.split('}')[-1]
    with zipfile.ZipFile(zip_bytes_or_path if not isinstance(zip_bytes_or_path, bytes) else io.BytesIO(zip_bytes_or_path)) as z:
        with z.open(z.namelist()[0]) as fh:
            for _, el in iterparse(fh, events=('end',)):
                if tag(el) != 'RefData':
                    continue
                gen = el.find('{*}FinInstrmGnlAttrbts')
                ven = el.find('{*}TradgVnRltdAttrbts')
                iss = el.find('{*}Issr')
                g = {tag(x): (x.text or '').strip() for x in gen} if gen is not None else {}
                v = {tag(x): (x.text or '').strip() for x in ven} if ven is not None else {}
                lei = iss.text.strip() if iss is not None and iss.text else None
                el.clear()
                if v.get('Id') in mics and g.get('ClssfctnTp', '').startswith('ES'):
                    out.append(_listing(g.get('Id'), v.get('Id'), g.get('FullNm'), g.get('ShrtNm'), g.get('ClssfctnTp'),
                                        g.get('NtnlCcy'), lei, v.get('FrstTradDt'), v.get('TermntnDt'), 'fca_firds', asof))
    return out


def parse_six(text: str, asof: datetime) -> list[dict]:
    rows = csv.DictReader(io.StringIO(text), delimiter=';')
    out = []
    for r in rows:
        isin = (r.get('ISIN') or '').strip()
        if not isin:
            continue
        out.append(_listing(isin, 'XSWX', r.get('Company'), None, None, (r.get('Traded Currency') or '').strip() or None, None,
                            None, None, 'six_equity_issuers', asof, ticker=(r.get('Symbol') or '').strip() or None,
                            issuer_country=(r.get('Country') or '').strip() or None,
                            share_class=(r.get('Class of Share') or '').strip() or None,
                            listing_segment=(r.get('Listing Segment') or '').strip() or None,
                            primary_listing=(r.get('Primary listing') or '').strip() or None))
    return out


def parse_xetra(text: str) -> dict[str, dict]:
    lines = text.lstrip('﻿').splitlines()
    rows = list(csv.reader(lines[2:], delimiter=';'))
    head = rows[0]
    out = {}
    for v in rows[1:]:
        r = dict(zip(head, v))
        if r.get('Instrument Type') == 'CS' and r.get('ISIN'):
            out[r['ISIN']] = {'ticker': r.get('Mnemonic') or None, 'wkn': (r.get('WKN') or '').lstrip('0') or None,
                              'xetra_name': r.get('Instrument'), 'xetra_group': r.get('Product Assignment Group Description')}
    return out


EURONEXT_MARKETS = {'Euronext Paris': 'XPAR', 'Euronext Growth Paris': 'ALXP', 'Euronext Amsterdam': 'XAMS',
                    'Euronext Brussels': 'XBRU', 'Euronext Lisbon': 'XLIS', 'Euronext Dublin': 'XMSM',
                    'Euronext Milan': 'MTAA', 'Euronext Growth Milan': 'EXGM', 'Oslo Børs': 'XOSL'}


def parse_euronext(text: str) -> dict[tuple[str, str], dict]:
    lines = text.lstrip('﻿').splitlines()
    out = {}
    for v in csv.reader(lines[4:], delimiter=';'):
        if len(v) < 5:
            continue
        mic = EURONEXT_MARKETS.get(v[3])
        if mic and v[1]:
            out[(v[1], mic)] = {'ticker': v[2] or None, 'euronext_name': v[0], 'euronext_market': v[3], 'currency': v[4]}
    return out


NORDIC_MARKETS = {'STO': 'XSTO', 'HEL': 'XHEL', 'CPH': 'XCSE', 'ICE': 'XICE'}


def parse_nasdaq_nordic(payload: dict, market: str) -> dict[tuple[str, str], dict]:
    mic = NORDIC_MARKETS[market]
    rows = ((payload.get('data') or {}).get('instrumentListing') or {}).get('rows') or []
    return {(r['isin'], mic): {'ticker': r.get('symbol') or None, 'nasdaq_name': r.get('fullName'),
                               'sector': r.get('sector') or None, 'currency': r.get('currency')}
            for r in rows if r.get('isin')}


def enrich(listings: list[dict], xetra: dict, euronext: dict, nordic: dict) -> list[dict]:
    """Add tickers/sectors from exchange lists (joined on ISIN, and MIC where the list is venue-specific)."""
    for l in listings:
        extra = None
        if l['mic'] in ('XETA', 'XETB'):
            extra = xetra.get(l['isin'])
            if extra:
                l['ticker_source'] = 'xetra_all_tradable'
        elif (l['isin'], l['mic']) in euronext:
            extra = euronext[(l['isin'], l['mic'])]
            l['ticker_source'] = 'euronext_equities'
        elif (l['isin'], l['mic']) in nordic:
            extra = nordic[(l['isin'], l['mic'])]
            l['ticker_source'] = 'nasdaq_nordic_screener'
        if extra:
            l['ticker'] = l.get('ticker') or extra.get('ticker')
            if extra.get('sector'):
                l['sector'] = extra['sector']
            if extra.get('wkn'):
                l['wkn'] = extra['wkn']
        if l.get('ticker') and not l.get('ticker_source'):
            l['ticker_source'] = l['source']
        l.setdefault('ticker', None)
    return listings


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def dump(obj, path):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
