"""Ergänzt data/boerse-de/zusatz.json (Cashflow, Bilanz, Gewinnrechnung aus Jahresabschlüssen, Mio.) um Firmen aus stdin.
Eingabe: {"SYM":{"jahre":[2021,...],"ocf":[..],"capex":[..],"da":[..],"div":[..],"bb":[..],"cash":[..],"debt":[..],
  "umsatz":[..],"brutto":[..],"ebit":[..],"zins":[..],"steuer":[..],"hinweis":".."}}  null = fehlt, Beträge positiv."""
import json, os, sys
P = 'data/boerse-de/zusatz.json'
d = json.load(open(P, encoding='utf-8')) if os.path.exists(P) else {'quelle': 'Jahresabschlüsse (stockanalysis.com), Mio. in Berichtswährung', 'firmen': {}}
new = json.load(sys.stdin)
for sym, f in new.items():
    n = len(f['jahre'])
    for k, v in f.items():
        if isinstance(v, list): assert len(v) == n, (sym, k, len(v), n)
    old = d['firmen'].get(sym, {})
    if old and old.get('jahre') == f['jahre']:
        old.update(f); f = old
    d['firmen'][sym] = f
json.dump(d, open(P, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
print(len(d['firmen']), 'Firmen in zusatz.json')
