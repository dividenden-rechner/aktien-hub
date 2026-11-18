"""Export extracted FY values into the aktien-hub data format (data/asien-geschaeftsberichte.json).

Follows the conventions of aktien-hub's data/asien-fundamente.json: German keys,
top-level {stand, anzahl, firmen}, Yahoo-style tickers (0001.HK, D05.SI, 002594.SZ).
Only reports with status 'extracted_consistent' are exported; every value keeps its
PDF page, printed page, unit and currency. Nothing is converted between currencies.

Usage: python export_aktien_hub.py [--out PATH] [--fiscal-year 2025]
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from app.reports import ROOT

LAND = {'HK': 'Hongkong', 'SI': 'Singapur', 'SZ': 'China', 'SS': 'China'}
FELDER = {
    'revenue': 'umsatz', 'operating_profit': 'operativer_gewinn', 'profit_before_tax': 'gewinn_vor_steuern',
    'net_profit': 'jahresueberschuss', 'net_income_attributable': 'konzerngewinn_aktionaere',
    'total_assets': 'bilanzsumme', 'total_liabilities': 'verbindlichkeiten', 'total_equity': 'eigenkapital',
    'equity_attributable': 'eigenkapital_aktionaere', 'cash': 'liquide_mittel',
    'operating_cash_flow': 'operativer_cashflow', 'capex': 'investitionen', 'free_cash_flow': 'free_cashflow',
    'dividends_paid_to_shareholders': 'gezahlte_dividenden', 'net_debt': 'nettoverschuldung',
}


def export(fiscal_year: int) -> dict:
    firmen = []
    for path in sorted((ROOT / 'extracted').glob(f'*_{fiscal_year}.json')):
        r = json.loads(path.read_text(encoding='utf-8'))
        if r.get('status') != 'extracted_consistent':
            continue
        facts = {f['field']: f for f in r['facts'] + r['derived'] if f.get('value') is not None}
        werte = {}
        for field, key in FELDER.items():
            f = facts.get(field)
            if f:
                werte[key] = {'wert': float(f['value']), 'einheit': f['unit'], 'waehrung': f['currency'],
                              'pdf_seite': f['pdf_page'], 'druckseite': f.get('printed_page'),
                              'definition': f.get('definition'), 'methode': f['method']}
        eps, dps = facts.get('eps_basic'), facts.get('dividend_per_share')
        if r['symbol'] == '0142.HK':  # USD reporting; distributions also stated in U.S. cents
            dps = facts.get('dividend_per_share_usd_cents')
        firmen.append({
            'ticker': r['symbol'], 'name': r['company'], 'land': LAND.get(r['symbol'].rsplit('.', 1)[-1]),
            'quelle': 'Geschäftsbericht (PDF)', 'quelle_url': r['source_url'], 'pdf_sha256': r['pdf_sha256'],
            'geschaeftsjahr': r['fiscal_year'], 'stichtag': r['period_end'], 'rechnungslegung': r['accounting_standard'],
            'waehrung': r['currency'], 'einheit': r['unit'],
            'eps_jahr': float(eps['value']) if eps else None, 'eps_einheit': eps['unit'] if eps else None,
            'eps_waehrung': eps['currency'] if eps else None,
            'dps_jahr': float(dps['value']) if dps else None, 'dps_einheit': dps['unit'] if dps else None,
            'dps_waehrung': dps['currency'] if dps else None,
            'werte': werte,
            'kennzahlen': {k: (float(v['value']) if v['value'] is not None else None) for k, v in r['ratios'].items()},
            'pruefungen': {c['name']: c['status'] for c in r['checks']},
            'pruefstatus': {'maschinell': r['status'], 'zweite_engine': r.get('second_engine', {}).get('summary'),
                            'mensch': (r.get('manual_review') or {}).get('human_review', 'pending')},
            'hinweise': r.get('caveats', []),
        })
    return {'stand': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'), 'geschaeftsjahr': fiscal_year,
            'anzahl': len(firmen), 'firmen': firmen,
            'hinweis': 'Maschinell aus offiziellen Geschäftsberichten extrahiert und rechnerisch geprüft; keine Anlageberatung.'}


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--out', default='export/asien-geschaeftsberichte.json')
    p.add_argument('--fiscal-year', type=int, default=2025)
    a = p.parse_args()
    data = export(a.fiscal_year)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(f'{data["anzahl"]} Firmen -> {out}')
