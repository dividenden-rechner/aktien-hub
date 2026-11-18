"""Run profile-based extraction over cached official reports and write auditable outputs."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from .reports import ROOT, cached_pages, cached_pdf, load_catalog
from .statement_extractor import extract_report, load_profile, sha256_file
from .verification import compare_with_reference, second_engine_check

PROFILE_DIR = ROOT / 'profiles'
REFERENCE_FILE = ROOT / 'reference_ir_2025.json'
OUT_DIR = ROOT / 'extracted'

# Canonical fields shown in the summary table, in display order.
SUMMARY_FIELDS = [
    'revenue', 'operating_profit', 'profit_before_tax', 'net_profit', 'net_income_attributable', 'eps_basic',
    'total_assets', 'total_liabilities', 'total_equity', 'equity_attributable', 'cash',
    'operating_cash_flow', 'capex', 'free_cash_flow', 'dividends_paid_to_shareholders',
    'dividend_per_share', 'net_debt',
]

FIELD_LABELS_DE = {
    'revenue': 'Umsatz', 'operating_profit': 'Operativer Gewinn', 'profit_before_tax': 'Gewinn vor Steuern',
    'net_profit': 'Jahresüberschuss (inkl. Minderheiten)', 'net_income_attributable': 'Konzerngewinn (Aktionäre)',
    'eps_basic': 'Ergebnis je Aktie (unverwässert)', 'total_assets': 'Bilanzsumme',
    'total_liabilities': 'Verbindlichkeiten gesamt', 'total_equity': 'Eigenkapital gesamt',
    'equity_attributable': 'Eigenkapital (Aktionäre)', 'cash': 'Liquide Mittel (lt. Definition)',
    'operating_cash_flow': 'Operativer Cashflow', 'capex': 'Investitionen (Capex, lt. Definition)',
    'free_cash_flow': 'Free Cashflow (OCF − Capex)', 'dividends_paid_to_shareholders': 'Gezahlte Dividenden (Aktionäre)',
    'dividend_per_share': 'Dividende je Aktie (GJ)', 'net_debt': 'Nettoverschuldung (lt. Emittent)',
}

log = logging.getLogger(__name__)


def _references() -> list[dict]:
    if not REFERENCE_FILE.is_file():
        return []
    data = json.loads(REFERENCE_FILE.read_text(encoding='utf-8'))
    return data.get('facts', []) if isinstance(data, dict) else data


def profile_for(symbol: str) -> dict | None:
    path = PROFILE_DIR / f'{symbol}.json'
    return load_profile(path) if path.is_file() else None


def run_one(entry: dict, second_engine: bool = True, root: Path | None = None) -> dict:
    root = root or ROOT
    profile = profile_for(entry['symbol'])
    if profile is None:
        return {'symbol': entry['symbol'], 'status': 'no_profile'}
    pages = cached_pages(entry, root)
    pdf = cached_pdf(entry, root)
    if pages is None or pdf is None:
        return {'symbol': entry['symbol'], 'status': 'not_ingested', 'source_url': entry['url']}
    if profile['source_url'] != entry['url']:
        if entry.get('purpose') == 'ten_year_summary':
            # v1.8: older reports registered only for their ten-year summary (build_ten_year_history.py)
            return {'symbol': entry['symbol'], 'status': 'history_only_report', 'fiscal_year': entry['fiscal_year'],
                    'source_url': entry['url']}
        return {'symbol': entry['symbol'], 'status': 'profile_url_mismatch',
                'profile_url': profile['source_url'], 'catalog_url': entry['url']}
    result = extract_report(pages, profile, pdf_sha256=sha256_file(pdf))
    facts = {f['field']: f for f in result['facts'] + result['derived'] if f.get('value') is not None}
    if second_engine:
        labels = {s['field']: s.get('label') for s in profile['fields'] if s.get('label')}
        result['second_engine'] = second_engine_check(pdf, result['facts'], labels)
    result['reference_comparison'] = compare_with_reference(facts, _references(), profile['symbol'], profile['fiscal_year'])
    result['extracted_at'] = datetime.now(timezone.utc).isoformat()
    return result


def summary_rows(result: dict) -> list[dict]:
    facts = {f['field']: f for f in result.get('facts', []) + result.get('derived', [])}
    engine = {r['field']: r['status'] for r in result.get('second_engine', {}).get('results', [])}
    refs = {r['field']: r for r in result.get('reference_comparison', [])}
    rows = []
    for field in SUMMARY_FIELDS:
        f = facts.get(field)
        if f is None:
            continue
        rows.append({
            'symbol': result['symbol'], 'field': field, 'label_de': FIELD_LABELS_DE.get(field, field),
            'value': f.get('value'), 'currency': f.get('currency'), 'unit': f.get('unit'),
            'fiscal_year': f.get('fiscal_year'), 'pdf_page': f.get('pdf_page'), 'printed_page': f.get('printed_page'),
            'method': f.get('method'), 'definition': f.get('definition'),
            'second_engine': engine.get(field, 'n/a (derived)' if f.get('method') == 'derived' else 'not_run'),
            'reference': refs.get(field, {}).get('result'),
            'source_url': f.get('source_url'),
        })
    return rows


def _fmt_num(value: str | None) -> str:
    if value is None:
        return '–'
    if '.' in value:
        whole, frac = value.split('.')
        return f'{int(whole):,}'.replace(',', '.') + ',' + frac if whole.lstrip('-').isdigit() else value
    return f'{int(value):,}'.replace(',', '.')


UNIT_DE = {'million': 'Mio.', 'thousand': 'Tsd.', 'units': '', 'cents': 'Cent', 'billion': 'Mrd.'}


def markdown_report(results: list[dict], fiscal_year: int) -> str:
    lines = [f'# Verifikation Geschäftsberichte GJ {fiscal_year}', '',
             f'Erzeugt: {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")} durch `python extract_reports.py`.', '',
             'Legende Spalte „2. Engine“: `row_confirmed` = pdfplumber findet denselben Wert in einer Zeile mit passendem Label; '
             '`token_on_page` = Wert steht auf derselben Seite (Label nicht in derselben Zeile erkennbar); '
             '`not_found` = Abweichung, manuell prüfen. Spalte „Referenz“: Abgleich mit IR-Webseite des Emittenten.', '']
    for r in results:
        if r.get('status') == 'history_only_report':
            continue
        if r.get('status') in ('no_profile', 'not_ingested', 'profile_url_mismatch'):
            lines += [f'## {r["symbol"]}: {r["status"]}', '']
            continue
        lines += [f'## {r["company"]} ({r["symbol"]})', '',
                  f'- Geschäftsjahr: {r["fiscal_year"]} (Stichtag {r["period_end"]})',
                  f'- Rechnungslegung: {r["accounting_standard"]}',
                  f'- Berichtswährung/Einheit: {r["currency"]}, {r["unit"]}',
                  f'- Quelle: <{r["source_url"]}>',
                  f'- PDF: {r["page_count"]} Seiten, SHA-256 `{r["pdf_sha256"]}` (Profil: {r["pdf_sha256_status"]})',
                  f'- Status: **{r["status"]}**; Prüfungen: ' + ', '.join(f'{c["name"]}={c["status"]}' for c in r['checks']),
                  '']
        if 'second_engine' in r and r['second_engine'].get('summary'):
            s = r['second_engine']['summary']
            lines.append(f'- 2. PDF-Engine (pdfplumber): {s["row_confirmed"]} Zeile bestätigt, '
                         f'{s["token_on_page"]} Wert auf Seite, {s["not_found"]} nicht gefunden')
        if r.get('errors'):
            lines.append('- Nicht extrahiert: ' + ', '.join(f'{e["field"]} ({e["reason"]})' for e in r['errors']))
        lines += ['', '| Kennzahl | Wert | Einheit | PDF-S. | Druck-S. | 2. Engine | Referenz |', '|---|---:|---|---:|---:|---|---|']
        for row in summary_rows(r):
            unit = f'{row["currency"]} {UNIT_DE.get(row["unit"], row["unit"])}'.strip()
            page = row['pdf_page'] if not isinstance(row['pdf_page'], list) else '+'.join(map(str, row['pdf_page']))
            lines.append(f'| {row["label_de"]} | {_fmt_num(row["value"])} | {unit} | {page} | {row["printed_page"] or "–"} | '
                         f'{row["second_engine"]} | {row["reference"] or "–"} |')
        ratios = {k: v['value'] for k, v in r['ratios'].items() if v['value'] is not None}
        if ratios:
            lines += ['', 'Kennzahlen (berechnet aus obigen Werten): ' +
                      ', '.join(f'{k}={v}' for k, v in ratios.items())]
        if r.get('caveats'):
            lines += ['', 'Hinweise:'] + [f'- {c}' for c in r['caveats']]
        lines.append('')
    return '\n'.join(lines) + '\n'


def run_extraction(symbols: list[str] | None = None, second_engine: bool = True, write: bool = True,
                   root: Path | None = None) -> dict:
    root = root or ROOT
    logging.getLogger('pypdf').setLevel(logging.ERROR)
    results = []
    for entry in load_catalog():
        if symbols and entry['symbol'] not in symbols:
            continue
        results.append(run_one(entry, second_engine=second_engine, root=root))
    if write:
        out = root / 'extracted'
        out.mkdir(parents=True, exist_ok=True)
        rows = []
        for r in results:
            if 'facts' in r:
                (out / f'{r["symbol"]}_{r["fiscal_year"]}.json').write_text(
                    json.dumps(r, ensure_ascii=False, indent=2), encoding='utf-8')
                rows += summary_rows(r)
        years = sorted({r['fiscal_year'] for r in results if 'fiscal_year' in r}) or [0]
        (out / f'summary_{years[-1]}.json').write_text(json.dumps(
            {'generated_at': datetime.now(timezone.utc).isoformat(), 'rows': rows}, ensure_ascii=False, indent=2),
            encoding='utf-8')
        (out / f'VERIFIKATION_{years[-1]}.md').write_text(markdown_report(results, years[-1]), encoding='utf-8')
    return {'results': results,
            'summary': {s: sum(1 for r in results if r.get('status') == s) for s in
                        ('extracted_consistent', 'extraction_incomplete', 'consistency_check_failed',
                         'document_changed', 'not_ingested', 'no_profile', 'history_only_report')}}
