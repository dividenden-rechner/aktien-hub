"""Dividendenseiten für alle dividendenzahlenden Firmen (aktien-hub/<slug>/dividende/).

Die Werte kommen aus data/kennzahlen.json. Die kuratierten Seiten aus build_dividendenseiten.py
(dividendenseiten.json) bleiben unangetastet. Jede Seite zeigt die vorhandenen Kennzahlen und unten
ein Akkordeon mit Fragen und Antworten, die aus den Daten gebaut werden (auch als FAQPage-Markup).
Fehlt ein Wert, erscheint dazu keine Frage.
"""
import json, os, re, sys
from html import escape as esc

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_dividendenseiten as B

ROOT, BASE = B.ROOT, B.BASE
VORLAGE = os.path.join(ROOT, "aktien-hub", "altria", "dividende", "index.html")
KURS_WAEHRUNG_HINWEIS = {"USD": "US-Dollar", "EUR": "Euro", "GBP": "britische Pfund", "CHF": "Schweizer Franken", "JPY": "Yen", "SEK": "schwedische Kronen", "CAD": "kanadische Dollar", "AUD": "australische Dollar", "HKD": "Hongkong-Dollar", "KRW": "südkoreanische Won", "DKK": "dänische Kronen", "NOK": "norwegische Kronen", "SGD": "Singapur-Dollar", "TWD": "neue Taiwan-Dollar", "BRL": "brasilianische Real"}


def lade(p):
    with open(os.path.join(ROOT, p), encoding="utf-8") as fh:
        return json.load(fh)


def zahl(v, n=2):
    return B.de(v, n) if v is not None else None


def pct(v, n=1):
    return B.de(v, n) + " %" if v is not None else None


def gueltig(v, obergrenze):
    return v is not None and abs(v) <= obergrenze


def vorlage_teile():
    """Kopf (Head) und Fuß aus einer bestehenden Dividendenseite übernehmen."""
    s = open(VORLAGE, encoding="utf-8").read()
    head = s[:s.find("<body>")]
    head = re.sub(r"<script type=\"application/ld\+json\">.*?</script>\n?", "", head, flags=re.S)
    head = re.sub(r"<script[^>]*>.*?</script>\n?", "", head, flags=re.S)
    fuss = s[s.find("<footer"):]
    kopf = s[s.find("<body>") + 6:s.find("<main")]
    return head, kopf, fuss


def seite(sym, r, slug, name, faq_extra, head_vorlage, kopf, fuss):
    waehrung = r.get("waehrung") or "USD"
    einheit = KURS_WAEHRUNG_HINWEIS.get(waehrung, waehrung)
    div = r.get("dividende")
    rend = r.get("rendite")
    url = f"aktien-hub/{slug}/dividende/"
    title = f"{name} Dividende: Rendite, Historie und Fragen | Aktien-Hub"
    desc_teile = []
    if div is not None:
        desc_teile.append(f"{name} zahlt aufs Jahr gerechnet {zahl(div)} {waehrung} je Aktie")
    if rend is not None:
        desc_teile.append(f"Rendite rund {pct(rend)}")
    desc = (": ".join([desc_teile[0]]) if desc_teile else f"{name} Dividende") + (", " + ", ".join(desc_teile[1:]) if len(desc_teile) > 1 else "") + ". Zahlweise, Ausschüttung und Kennzahlen im Überblick."
    desc = desc[:300]

    kopfzeilen = []
    if r.get("isin"):
        kopfzeilen.append(f"ISIN {r['isin']}")
    if r.get("wkn"):
        kopfzeilen.append(f"WKN {r['wkn']}")
    kopfzeilen.append(f"Kürzel {sym}")

    zeilen = []
    if div is not None:
        zeilen.append(("Dividende je Aktie (letztes Jahr)", f"{zahl(div)} {waehrung}", ""))
    if rend is not None:
        zeilen.append(("Dividendenrendite", pct(rend), "Dividende im Verhältnis zum aktuellen Kurs"))
    if r.get("zahlweise"):
        zeilen.append(("Zahlweise", r["zahlweise"], ""))
    if r.get("zahlmonate"):
        zeilen.append(("Zahlmonate", r["zahlmonate"], ""))
    if gueltig(r.get("ausschuettung"), 1000):
        zeilen.append(("Ausschüttungsquote am Gewinn", pct(r["ausschuettung"], 0), ""))
    if gueltig(r.get("fcf_ausschuettung"), 1000):
        zeilen.append(("Anteil am freien Cashflow", pct(r["fcf_ausschuettung"], 0), ""))
    if gueltig(r.get("div_wachstum_5j"), 500):
        zeilen.append(("Dividendenwachstum 5 Jahre (pro Jahr)", pct(r["div_wachstum_5j"]), ""))
    if gueltig(r.get("div_wachstum_10j"), 500):
        zeilen.append(("Dividendenwachstum 10 Jahre (pro Jahr)", pct(r["div_wachstum_10j"]), ""))
    if r.get("dividendenserie"):
        zeilen.append(("Dividendenerhöhungen in Folge", f"{r['dividendenserie']} Jahre", ""))
    if gueltig(r.get("kgv"), 500) and r.get("kgv") > 0:
        zeilen.append(("KGV", zahl(r["kgv"], 1), "Kurs im Verhältnis zum Gewinn je Aktie"))

    tabelle = "".join(f'<tr><td>{esc(a)}{(" <span class=\"hint\">" + esc(c) + "</span>") if c else ""}</td><td class="n">{esc(b)}</td></tr>' for a, b, c in zeilen)
    tabelle = f'<div class="tablewrap"><table><tbody>{tabelle}</tbody></table></div>' if tabelle else ""

    faq = []
    if div is not None:
        faq.append((f"Wie hoch ist die Dividende von {name}?",
                    f"Aufs Jahr gerechnet zahlt {name} {zahl(div)} {waehrung} je Aktie" + (f", das entspricht einer Rendite von rund {pct(rend)}." if rend is not None else ".")
                    + ("" if waehrung == "USD" else f" Der Betrag ist in {einheit} angegeben.")))
    # faq_dynamisch erwartet die Rendite als Anteil (0,058 statt 5,8)
    r_faq = dict(r, rendite=(r.get('rendite') / 100) if r.get('rendite') is not None else None)
    faq += B.faq_dynamisch(r_faq, name)
    faq += faq_extra
    faq_html = "".join(f"<details><summary>{esc(q)}</summary><p>{esc(a)}</p></details>" for q, a in faq)

    ld = [
        {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Start", "item": BASE},
            {"@type": "ListItem", "position": 2, "name": "Aktien-Hub", "item": BASE + "aktien-hub/"},
            {"@type": "ListItem", "position": 3, "name": f"{name} Dividende", "item": BASE + url}]},
        {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]},
    ]
    ld_html = "".join(f'<script type="application/ld+json">{json.dumps(x, ensure_ascii=False)}</script>\n' for x in ld)

    head = head_vorlage
    head = re.sub(r"<title>.*?</title>", lambda m: f"<title>{esc(title)}</title>", head, flags=re.S)
    head = re.sub(r'<meta name="description" content="[^"]*">', lambda m: f'<meta name="description" content="{esc(desc)}">', head)
    head = re.sub(r'<link rel="canonical" href="[^"]*">', lambda m: f'<link rel="canonical" href="{BASE}{url}">', head)
    head = re.sub(r'(<meta property="og:title" content=")[^"]*"', lambda m: m.group(1) + esc(title) + '"', head)
    head = re.sub(r'(<meta property="og:description" content=")[^"]*"', lambda m: m.group(1) + esc(desc) + '"', head)
    head = re.sub(r'(<meta property="og:url" content=")[^"]*"', lambda m: m.group(1) + BASE + url + '"', head)
    head = re.sub(r'<meta property="og:image" content="[^"]*">', lambda m: '<meta property="og:image" content="' + BASE + 'assets/og-default.png">', head)

    main = f'''<main class="wrap"><article>
<nav class="crumbs" aria-label="Brotkrumen"><a href="../../../">Start</a> › <a href="../../../aktien-hub/">Aktien-Hub</a> › <a href="../">{esc(name)}</a> › <span aria-current="page">Dividende</span></nav>
<div class="titlerow"><h1>{esc(name)} Dividende</h1></div>
<p class="meta">{esc(" · ".join(kopfzeilen))}</p>
<p class="lead">{esc(desc.split(". Zahlweise")[0])}.</p>
{tabelle}
<p><a href="../">Zur Aktienseite von {esc(name)}</a> · <a href="../../../dividende/">Alle Dividenden im Überblick</a> · <a href="../../../dividende/aristokraten/">Dividendenaristokraten</a></p>
<h2>Fragen und Antworten</h2>
<div class="faq">{faq_html}</div>
</article></main>
'''
    return f'{head}{ld_html}</head>\n<body>{kopf}{main}{fuss}'


def main():
    werte = lade("data/kennzahlen.json")["werte"]
    slugs = lade("data/firmen-slugs.json")
    wkn = {}
    try:
        wkn = lade("data/kurse/wkn.json").get("k", {})
    except Exception:
        pass
    kuratiert = {f["sym"] for f in lade("data/dividendenseiten.json")["firmen"]}
    lean_namen = {f["sym"]: f["name"] for f in lade("data/firmen-lean.json")["firmen"]} if os.path.exists(os.path.join(ROOT, "data", "firmen-lean.json")) else {}
    head, kopf, fuss = vorlage_teile()
    n = 0
    gebaut = []
    for sym, r in werte.items():
        if sym in kuratiert or not r.get("name") or not (r.get("dividende") or 0) > 0:
            continue
        slug = slugs.get(sym)
        if not slug or not os.path.isdir(os.path.join(ROOT, "aktien-hub", slug)):
            continue
        if not (r.get("rendite") or 0) > 0 and not os.path.exists(os.path.join(ROOT, "aktien-hub", slug, "dividende", "index.html")):
            continue  # neue Seiten nur mit Rendite > 0 (sonst keine sinnvolle Dividendenseite)
        r = dict(r)
        r["wkn"] = wkn.get(r.get("isin") or "")
        if sym in lean_namen:
            r["name"] = lean_namen[sym]  # Schreibweise aus der Firmenliste (in kennzahlen teils GROSSGESCHRIEBEN)
        if not r.get("zahlmonate"):
            pass
        html_ = seite(sym, r, slug, r["name"], [], head, kopf, fuss)
        ziel = os.path.join(ROOT, "aktien-hub", slug, "dividende")
        os.makedirs(ziel, exist_ok=True)
        with open(os.path.join(ziel, "index.html"), "w", encoding="utf-8") as fh:
            fh.write(html_)
        gebaut.append(f"aktien-hub/{slug}/dividende/")
        n += 1
    print("Dividendenseiten gebaut:", n)
    sitemap_aufraeumen(gebaut)


def sitemap_aufraeumen(gebaut):
    """Sitemap: jede URL nur einmal, neue Dividendenseiten eintragen (die Datei hatte sich bei jedem Lauf vervielfacht)."""
    import datetime
    f = os.path.join(ROOT, "sitemap.xml")
    s = open(f, encoding="utf-8").read()
    bloecke = re.findall(r"<url>.*?</url>\n?", s, flags=re.S)
    kopf = s[:s.find("<url>")] if "<url>" in s else s
    gesehen, neu = set(), []
    for b in bloecke:
        m = re.search(r"<loc>([^<]*)</loc>", b)
        if not m or m.group(1) in gesehen:
            continue
        gesehen.add(m.group(1)); neu.append(b if b.endswith("\n") else b + "\n")
    heute = datetime.date.today().isoformat()
    for u in gebaut:
        loc = B.BASE + u
        if loc not in gesehen:
            neu.append(f"<url><loc>{loc}</loc><lastmod>{heute}</lastmod><priority>0.6</priority></url>\n")
            gesehen.add(loc)
    open(f, "w", encoding="utf-8").write(kopf + "".join(neu) + "</urlset>\n")


if __name__ == "__main__":
    main()
