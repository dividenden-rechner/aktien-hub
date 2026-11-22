#!/usr/bin/env python3
"""Sieben-Punkte-Check: bewertet die Aktien aus data/sieben-punkte-liste.json
mit festen Regeln (je 0 bis 3 Punkte, höchstens 21) aus data/kennzahlen.json
und schreibt die Rangliste nach fortgeschrittene/aktien-checkliste/index.html
sowie die Werte nach data/sieben-punkte.json.

Neue Aktie: Eintrag in data/sieben-punkte-liste.json ergänzen (ticker, datum, seite, optional video).
"""
import json, html, datetime, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

# (Schlüssel, Titel, Kennzahl, Einheit, Schwellen für 3/2/1 Punkte, höher_ist_besser)
KRIT = [
    ("umsatz", "Umsatzwachstum", "umsatz_wachstum_5j", "% p. a. (5 J.)", (8, 4, 0), True),
    ("gewinn", "Gewinnwachstum", "gewinn_wachstum_5j", "% p. a. (5 J.)", (10, 5, 0), True),
    ("rendite", "Dividendenrendite", "rendite", "%", (4, 2.5, 1), True),
    ("divwachstum", "Dividendenwachstum", "div_wachstum_5j", "% p. a. (5 J.)", (10, 5, 0), True),
    ("deckung", "Ausschüttung vom freien Cashflow", "fcf_ausschuettung", "%", (50, 70, 90), False),
    ("schulden", "Nettoschulden zum EBITDA", "nettoschulden_ebitda", "×", (1, 2, 3), False),
    ("bewertung", "Rendite des freien Cashflows", "fcf_rendite", "%", (6, 4, 2), True),
]
# REITs: FFO statt freiem Cashflow
REIT_ERSATZ = {"deckung": "ffo_ausschuettung"}


def punkte(wert, schw, hoch, key):
    if wert is None:
        return None
    a, b, c = schw
    if hoch:
        # Wachstum: 0 Punkte nur bei Rückgang (Wert unter 0); Rendite: unter der untersten Schwelle 0
        if wert >= a: return 3
        if wert >= b: return 2
        if wert >= c: return 1
        return 0
    if key == "deckung" and wert <= 0:
        return 0  # negativer freier Cashflow
    if key == "schulden" and wert < 0:
        return 3  # Nettocash
    if key == "deckung":
        if wert <= a: return 3
        if wert <= b: return 2
        if wert <= c: return 1
        return 0
    if wert < a: return 3
    if wert < b: return 2
    if wert < c: return 1
    return 0


def fmt(v, einheit):
    if v is None:
        return "–"
    s = f"{v:.1f}".replace(".", ",")
    return s + ("×" if einheit == "×" else " %")


def bewerte(t, k, reit=False):
    out = {}
    for key, titel, feld, einheit, schw, hoch in KRIT:
        f = REIT_ERSATZ.get(key, feld) if reit else feld
        w = k.get(f)
        out[key] = {"wert": w, "punkte": punkte(w, schw, hoch, key), "feld": f}
    return out


def main():
    liste = json.load(open("data/sieben-punkte-liste.json", encoding="utf-8"))["aktien"]
    K = json.load(open("data/kennzahlen.json", encoding="utf-8"))
    W = K["werte"]
    zeilen = []
    for e in liste:
        t = e["ticker"]
        k = W.get(t)
        if not k:
            print("Keine Kennzahlen für", t); continue
        b = bewerte(t, k, e.get("reit", False))
        summe = sum(x["punkte"] or 0 for x in b.values())
        zeilen.append({"ticker": t, "name": e.get("name") or k.get("name"), "datum": e["datum"], "seite": e.get("seite"),
                       "video": e.get("video"), "summe": summe, "kriterien": b, "kurs_eur": k.get("kurs_eur"), "stand": k.get("datum")})
    zeilen.sort(key=lambda z: (-z["summe"], z["name"]))
    json.dump({"stand": K.get("stand"), "aktien": zeilen}, open("data/sieben-punkte.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    schreibe_seite(zeilen, K.get("stand"))
    print(len(zeilen), "Aktien bewertet")


def d_de(iso):
    try:
        return datetime.date.fromisoformat(iso[:10]).strftime("%d.%m.%Y")
    except Exception:
        return iso or ""


def schreibe_seite(zeilen, stand):
    E = html.escape
    rows = []
    for i, z in enumerate(zeilen, 1):
        t = z["ticker"]
        name = E(z["name"])
        link = f'<a href="../../{E(z["seite"])}">{name}</a>' if z.get("seite") else name
        logo = f'<img src="../../assets/logos/hub/{E(t)}.png" alt="" width="26" height="26" loading="lazy" data-sym="{E(t)}" data-ph="{E(name[:1])}">'
        tds = []
        for key, titel, feld, einheit, schw, hoch in KRIT:
            c = z["kriterien"][key]
            p = c["punkte"]
            tds.append(f'<td data-v="{p if p is not None else -1}"><b>{p if p is not None else "–"}</b><small>{fmt(c["wert"], einheit)}</small></td>')
        video = f' · <a href="{E(z["video"])}" rel="noopener" target="_blank">Video</a>' if z.get("video") else ""
        rows.append(f'<tr><td data-v="{i}">{i}</td><td class="n" data-v="{name}"><div>{logo}<span>{link}<small>{E(t)} · geprüft {d_de(z["datum"])}{video}</small></span></div></td>'
                    f'<td class="s" data-v="{z["summe"]}"><b>{z["summe"]}</b><small>von 21</small></td>{"".join(tds)}</tr>')
    kopf = "".join(f'<th data-k="{j+3}">{E(titel)}</th>' for j, (_, titel, *_r) in enumerate(KRIT))
    regeln = []
    for key, titel, feld, einheit, schw, hoch in KRIT:
        a, b, c = schw
        u = "×" if einheit == "×" else " %"
        n = lambda x: f"{x:g}".replace(".", ",") + u
        if key in ("umsatz", "gewinn", "divwachstum"):
            r = (f"ab {n(a)}", f"{n(b)} bis {n(a)}", f"0 bis {n(b)}", "Rückgang bzw. Kürzung")
        elif key == "deckung":
            r = (f"bis {n(a)}", f"{n(a)} bis {n(b)}", f"{n(b)} bis {n(c)}", f"über {n(c)} oder negativer Cashflow")
        elif key == "schulden":
            r = (f"unter {n(a)}", f"{n(a)} bis {n(b)}", f"{n(b)} bis {n(c)}", f"über {n(c)}")
        else:
            r = (f"ab {n(a)}", f"{n(b)} bis {n(a)}", f"{n(c)} bis {n(b)}", f"unter {n(c)}")
        regeln.append(f"<tr><td>{E(titel)}</td><td>{r[0]}</td><td>{r[1]}</td><td>{r[2]}</td><td>{r[3]}</td></tr>")
    titel = "Fortgeschrittene Aktien-Checkliste: Der Sieben-Punkte-Check"
    beschr = "Rangliste der Dividendenaktien aus unserem Sieben-Punkte-Check: Umsatz- und Gewinnwachstum, Dividendenrendite, Dividendenwachstum, Deckung durch den freien Cashflow, Schulden und Bewertung, je 0 bis 3 Punkte."
    url = "https://dividenden-rechner.github.io/aktien-hub/fortgeschrittene/aktien-checkliste/"
    heute = datetime.date.today().strftime("%d.%m.%Y")
    seite = f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{E(titel)}</title>
<meta name="description" content="{E(beschr)}">
<meta name="robots" content="index,follow,max-snippet:-1,max-image-preview:large">
<link rel="canonical" href="{url}">
<meta property="og:type" content="article">
<meta property="og:locale" content="de_DE">
<meta property="og:site_name" content="Dividenden-Rechner Aktien-Hub">
<meta property="og:title" content="{E(titel)}">
<meta property="og:description" content="{E(beschr)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="https://dividenden-rechner.github.io/aktien-hub/assets/og-default.png">
<meta name="theme-color" content="#ffffff">
<link rel="stylesheet" href="../../assets/site.css">
<link rel="icon" href="../../favicon.ico" sizes="any">
<link rel="icon" type="image/png" sizes="32x32" href="../../assets/favicon-32.png">
<link rel="apple-touch-icon" href="../../assets/apple-touch-icon.png">
<link rel="stylesheet" href="../../assets/navigation.css?v=20261025a">
<link rel="manifest" href="../../manifest.webmanifest">
<style>
.rk-wrap{{overflow-x:auto;margin:1.2rem 0;border-top:1px solid #dfe5ea}}
table.rk{{width:100%;border-collapse:collapse;font-size:.92rem;min-width:860px}}
table.rk th{{text-align:left;font-weight:600;font-size:.78rem;color:#5d6b78;padding:.55rem .45rem;border-bottom:1px solid #dfe5ea;cursor:pointer;white-space:nowrap;user-select:none}}
table.rk th.on::after{{content:" ▾"}} table.rk th.on.asc::after{{content:" ▴"}}
table.rk td{{padding:.6rem .45rem;border-bottom:1px solid #eef1f4;vertical-align:middle}}
table.rk td b{{display:block;font-size:1rem}} table.rk td small{{display:block;color:#5d6b78;font-size:.76rem}}
table.rk td.n{{min-width:200px}} table.rk td.n div{{display:flex;gap:.6rem;align-items:center;text-align:left}} table.rk td.n img{{border-radius:4px;flex:none}}
table.rk td.s b{{font-size:1.2rem;color:#2f9e5b}}
table.rg{{width:100%;border-collapse:collapse;font-size:.88rem;margin:1rem 0}} table.rg th,table.rg td{{text-align:left;padding:.45rem .4rem;border-bottom:1px solid #eef1f4}} table.rg td+td{{white-space:nowrap}} table.rg th{{color:#5d6b78;font-weight:600;font-size:.78rem}}
.rg-wrap{{overflow-x:auto}}
</style>
</head>
<body>
<header id="hub-global-header"><div class="hub-nav-inner"><a class="hub-brand" href="../../"><img class="hub-logo" src="../../assets/logo-72.png" alt="" width="36" height="36"> <span class="hub-brand-name">Dividenden-Rechner <span>Aktien-Hub</span></span></a><nav class="hub-links" aria-label="Hauptmenü"><a href="../../">Rechner</a><a href="../../aktien-hub/">Aktien</a><a href="../../dividende/">Dividenden</a><a href="../../depot/">Depot</a><a href="../../news/">News</a><a href="../../screener/">Screener</a><a href="../../einfuehrung/">Einführung</a><a href="../../grundlagen/">Grundlagen</a><a href="../../fortgeschrittene/" aria-current="page">Fortgeschrittene</a><a class="hub-nl" href="../../#newsletter">Newsletter</a></nav></div></header>
<script src="../../assets/navigation.js"></script>
<script src="../../assets/logos.js"></script>
<main class="wrap"><article>
<nav class="crumbs" aria-label="Brotkrumen"><a href="../../">Start</a> › <a href="../../fortgeschrittene/">Fortgeschrittene</a> › <span aria-current="page">Aktien-Checkliste</span></nav>
<h1>{E(titel)}</h1>
<p class="meta">Zuletzt aktualisiert: {heute} · Kennzahlen täglich aus dem Aktien-Hub</p>
<p class="lead">Sieben Fragen, je 0 bis 3 Punkte, höchstens 21. Jede Aktie, die wir im Sieben-Punkte-Check besprechen, landet in dieser Rangliste. Die Punkte rechnen sich aus den aktuellen Kennzahlen des Aktien-Hubs und können sich mit neuen Quartalszahlen oder Kursen ändern.</p>
<div class="rk-wrap"><table class="rk" id="rk"><thead><tr><th data-k="0">Platz</th><th data-k="1">Aktie</th><th data-k="2" class="on">Punkte</th>{kopf}</tr></thead><tbody>
{"".join(rows)}
</tbody></table></div>
<p class="meta">Auf eine Spaltenüberschrift tippen, um zu sortieren. Unter den Punkten steht jeweils der zugrunde liegende Wert.</p>
<h2>So vergeben wir die Punkte</h2>
<p>Die Regeln sind für alle Aktien gleich, damit die Rangliste vergleichbar bleibt. Bei REITs nehmen wir für die Deckung die FFO statt des freien Cashflows. Banken und Versicherungen bewerten wir mit diesem Raster nicht, weil Schulden dort Teil des Geschäfts sind.</p>
<div class="rg-wrap"><table class="rg"><thead><tr><th>Kriterium</th><th>3 Punkte</th><th>2 Punkte</th><th>1 Punkt</th><th>0 Punkte</th></tr></thead><tbody>
{"".join(regeln)}
</tbody></table></div>
<p>Wachstumswerte sind jährliche Durchschnitte über fünf Geschäftsjahre. Die Dividendenrendite bezieht sich auf die aktuelle Jahresdividende und den letzten Xetra-Kurs. Mehr zu den einzelnen Kennzahlen steht in unserer <a href="../dividendenaktie-pruefen/">Checkliste für zehn Minuten</a> und bei den <a href="../kennzahlen-nach-branche/">Kennzahlen nach Branche</a>.</p>
<p class="meta">Die Punkte ordnen Zahlen nach festen Regeln ein. Sie sind keine Kaufempfehlung und keine Anlageberatung.</p>
</article></main>
<footer class="site-footer"><div class="wrap">
<div class="cols">
<a href="../../">Rechner</a><a href="../../aktien-hub/">Aktien</a><a href="../../depot/">Depot</a><a href="../../screener/">Screener</a><a href="../../einfuehrung/">Einführung</a><a href="../../grundlagen/">Grundlagen</a><a href="../../fortgeschrittene/">Fortgeschrittene</a>
<a href="../../ueber-uns/">Über uns</a><a href="../../impressum/">Impressum</a><a href="https://www.instagram.com/dividenden.rechner" rel="noopener nofollow me" target="_blank">Instagram</a><a href="../../datenschutz/">Datenschutz</a>
</div>
<p>Alle Inhalte dienen der allgemeinen Information und sind keine Anlage-, Steuer- oder Rechtsberatung. Kapitalanlagen sind mit Risiken verbunden.</p>
</div></footer>
<script>
(function(){{var t=document.getElementById("rk");if(!t)return;var hs=t.querySelectorAll("th"),cur=2,asc=false;
function sort(k){{if(k===cur)asc=!asc;else{{cur=k;asc=(k<=1);}}var b=t.tBodies[0],r=[].slice.call(b.rows);
r.sort(function(x,y){{var a=x.cells[k].getAttribute("data-v"),c=y.cells[k].getAttribute("data-v"),na=parseFloat(a),nc=parseFloat(c);
var v=(!isNaN(na)&&!isNaN(nc))?na-nc:String(a).localeCompare(String(c),"de");return asc?v:-v;}});r.forEach(function(e){{b.appendChild(e)}});
hs.forEach(function(h,i){{h.classList.toggle("on",i===k);h.classList.toggle("asc",i===k&&asc)}});}}
hs.forEach(function(h,i){{h.addEventListener("click",function(){{sort(i)}})}});}})();
</script>
</body>
</html>
"""
    os.makedirs("fortgeschrittene/aktien-checkliste", exist_ok=True)
    open("fortgeschrittene/aktien-checkliste/index.html", "w", encoding="utf-8").write(seite)


if __name__ == "__main__":
    main()
