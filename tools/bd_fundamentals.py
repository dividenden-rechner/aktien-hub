"""Wandelt data/<land>/boerse-de-reihen.json (boerse.de, Mio.) in das SEC/ESEF-Format um:
data/boerse-de/fundamentals.json. Der Aktien-Hub liest die Datei als dritte Quelle (füllt Lücken)."""
import json, os
M = 1e6
MAP = {'umsatz':('umsatz',M),'jahresueberschuss':('gewinn',M),'eps':('eps_verw',1),'dividende_je_aktie':('dividende_je_aktie',1),
       'dividendenausschuettung':('dividenden_gezahlt',M),'aktien_mio':('aktien_verw',M),'eigenkapital':('eigenkapital',M),
       'ebt':('ergebnis_vor_steuer',M),'eigenkapitalrendite_pct':('eigenkapitalrendite',1)}
LAND = {'DE':'DE','PA':'FR','AS':'NL','L':'GB'}
out = {}
for land in ('de','fr','uk'):
    p = f'data/{land}/boerse-de-reihen.json'
    d = json.load(open(p, encoding='utf-8'))
    jahre = d.get('jahre', list(range(2019, 2026)))
    for sym, f in d['firmen'].items():
        k = {}
        for src, (dst, fac) in MAP.items():
            vals = [[f'{j}-12-31', round(v*fac, 4) if fac != 1 else v] for j, v in zip(jahre, f.get(src) or []) if v is not None]
            if vals: k[dst] = vals
        e = {'n': f['name'], 'isin': f.get('isin'), 'land': LAND.get(sym.split('.')[-1], ''), 'gj': f'{jahre[-1]}-12-31',
             'w': f.get('waehrung') or d.get('waehrung') or 'EUR', 'quelle': 'boerse.de', 'k': k}
        if f.get('hinweis'): e['hinweis'] = f['hinweis']
        out[sym] = e
os.makedirs('data/boerse-de', exist_ok=True)
json.dump({'stand': __import__('datetime').date.today().isoformat(), 'quelle': 'boerse.de Fundamentalanalyse', 'firmen': out},
          open('data/boerse-de/fundamentals.json', 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print(len(out), 'Firmen')
