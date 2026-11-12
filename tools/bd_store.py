"""Legt boerse.de-Reihen 2019-2025 in data/de/boerse-de-reihen.json ab. Aufruf: bd_store.py (liest BATCH aus stdin als JSON)."""
import json, sys, os
P = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), '..', 'data', 'de', 'boerse-de-reihen.json')
JAHRE = [2019, 2020, 2021, 2022, 2023, 2024, 2025]
KEYS = ['umsatz','ebt','jahresueberschuss','dividendenausschuettung','eigenkapital','eps','dividende_je_aktie','aktien_mio','eigenkapitalrendite_pct']
d = json.load(open(P)) if os.path.exists(P) else {"quelle":"boerse.de Fundamentalanalyse (je Firma, Seite 'fundamental-analyse')","stand":"2026-11-12","einheit":"Mio € (je Aktie in €; aktien_mio in Mio. Stück)","jahre":JAHRE,"hinweis":"Jahresüberschuss meist Anteil der Aktionäre, kann je Firma von Pressemitteilungen abweichen. Umsatz bei Banken/Versicherern von boerse.de nicht geführt (null). Nicht geprüft gegen Geschäftsberichte.","firmen":{}}
batch = json.load(sys.stdin)
for sym, v in batch.items():
    name = v.pop('name'); isin = v.pop('isin')
    row = {'name': name, 'isin': isin}
    for k in KEYS:
        s = v[k]
        assert len(s) == 7, (sym, k, s)
        row[k] = s
    d['firmen'][sym] = row
json.dump(d, open(P, 'w'), ensure_ascii=False, indent=0)
print(len(d['firmen']), 'Firmen')
