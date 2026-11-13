"""Wandelt data/<land>/boerse-de-reihen.json (boerse.de, Mio.) in das SEC/ESEF-Format um:
data/boerse-de/fundamentals.json. Der Aktien-Hub liest die Datei als dritte Quelle (füllt Lücken)."""
import json, os
M = 1e6
MAP = {'umsatz':('umsatz',M),'jahresueberschuss':('gewinn',M),'eps':('eps_verw',1),'dividende_je_aktie':('dividende_je_aktie',1),
       'dividendenausschuettung':('dividenden_gezahlt',M),'aktien_mio':('aktien_verw',M),'eigenkapital':('eigenkapital',M),
       'ebt':('ergebnis_vor_steuer',M),'eigenkapitalrendite_pct':('eigenkapitalrendite',1)}
LAND = {'DE':'DE','PA':'FR','AS':'NL','L':'GB','SW':'CH','MC':'ES','MI':'IT','ST':'SE','OL':'NO','CO':'DK','HE':'FI','BR':'BE','VI':'AT','LS':'PT','IR':'IE','T':'JP','HK':'HK','SI':'SG','TA':'IL','AT':'GR','AX':'AU'}
out = {}
for land in ('de','fr','uk','ch','es','it','nl','se','no','dk','fi','be','at','pt','ie','jp','hk','sg','il','gr','au'):
    p = f'data/{land}/boerse-de-reihen.json'
    if not os.path.exists(p): continue
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
        if f.get('dividende_waehrung') and f['dividende_waehrung'] != e['w']: e['dps_w'] = f['dividende_waehrung']   # Dividende in anderer Waehrung als der Bericht
        out[sym] = e
# Zusatz aus Jahresabschlüssen (Cashflow, Bilanz, Gewinnrechnung): data/boerse-de/zusatz.json, hat Vorrang je Jahr
ZMAP = {'ocf':'operativer_cf','capex':'capex','da':'abschreibungen','div':'dividenden_gezahlt','bb':'aktienrueckkauf','cash':'liquide_mittel',
        'debt':'schulden_lang','umsatz':'umsatz','brutto':'bruttogewinn','ebit':'operatives_ergebnis','zins':'zinsaufwand','steuer':'steuern'}
zp = 'data/boerse-de/zusatz.json'
if os.path.exists(zp):
    for sym, z in json.load(open(zp, encoding='utf-8'))['firmen'].items():
        e = out.get(sym)
        if not e: continue
        for src, dst in ZMAP.items():
            if src not in z: continue
            alt = {d: v for d, v in e['k'].get(dst, [])}
            for j, v in zip(z['jahre'], z[src]):
                if v is not None: alt[f'{j}-12-31'] = round(v*M, 4)
            if alt: e['k'][dst] = sorted([d, v] for d, v in alt.items())
        if z.get('hinweis'): e['hinweis'] = (e.get('hinweis', '') + ' ' + z['hinweis']).strip()
        e['quelle'] = 'boerse.de, Cashflow und Bilanz: Jahresabschlüsse'
os.makedirs('data/boerse-de', exist_ok=True)
json.dump({'stand': __import__('datetime').date.today().isoformat(), 'quelle': 'boerse.de Fundamentalanalyse', 'firmen': out},
          open('data/boerse-de/fundamentals.json', 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print(len(out), 'Firmen')
