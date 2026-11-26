"""Schlanke Firmenseiten (aktien-hub/<slug>/) für Firmen ohne eigene Seite.

Gezeigt wird nur, was die Daten hergeben (data/firmen-lean.json). Fehlt ein Wert, erscheint dazu
weder Zeile noch Frage. Dazu kommt ein kurzer Text zu Geschäft und Geschäftsmodell (data/firma-profile.json).
Das Akkordeon (FAQ) enthält nur Fragen, die aus den vorhandenen Daten beantwortbar sind; als FAQPage-Markup.
Ist eine Dividendenseite vorhanden, wird sie verlinkt.
"""
import datetime, json, os, re, sys
from html import escape as esc

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_dividendenseiten as B
import build_dividende_alle as DA

ROOT, BASE = B.ROOT, B.BASE
LAND = {"US": "den USA", "GB": "Großbritannien", "DE": "Deutschland", "FR": "Frankreich", "IT": "Italien", "ES": "Spanien",
        "SE": "Schweden", "NO": "Norwegen", "DK": "Dänemark", "FI": "Finnland", "NL": "den Niederlanden", "BE": "Belgien",
        "AT": "Österreich", "CH": "der Schweiz", "IE": "Irland", "LU": "Luxemburg", "PT": "Portugal", "GR": "Griechenland",
        "KR": "Südkorea", "JP": "Japan", "CN": "China", "HK": "Hongkong", "SG": "Singapur", "CY": "Zypern", "JE": "Jersey",
        "GG": "Guernsey", "CA": "Kanada", "AU": "Australien", "HR": "Kroatien", "SI": "Slowenien", "HU": "Ungarn"}


def lade(p):
    with open(os.path.join(ROOT, p), encoding="utf-8") as fh:
        return json.load(fh)


def betrag(v, w):
    if v is None:
        return None
    if abs(v) >= 1e9:
        return f"{B.de(v / 1e9, 2)} Mrd. {w}"
    if abs(v) >= 1e6:
        return f"{B.de(v / 1e6, 1)} Mio. {w}"
    return f"{B.de(v, 0)} {w}"


def land_name(c):
    return LAND.get(c, c)


def fragen(f, name, profil, dividende_url):
    """Nur Fragen, die aus den vorhandenen Daten beantwortbar sind."""
    out = [(f"Was macht {name}?", profil)]
    if f.get("land"):
        out.append((f"Woher stammt {name}?",
                    f"{name} ist im Land {land_name(f['land'])} ansässig bzw. dort registriert." +
                    (f" Die Aktie lässt sich über {f['boerse']} handeln." if f.get("boerse") else "")))
    if f.get("umsatz") is not None and f.get("umsatz") > 0:
        out.append((f"Wie hoch ist der Umsatz von {name}?",
                    f"Der zuletzt verfügbare Umsatz von {name} liegt bei {betrag(f['umsatz'], f.get('waehrung') or '')}."))
    if f.get("gewinn") is not None:
        g = f["gewinn"]
        if g >= 0:
            antwort = f"Zuletzt wies {name} einen Gewinn von {betrag(g, f.get('waehrung') or '')} aus."
        else:
            antwort = f"Zuletzt wies {name} einen Verlust von {betrag(-g, f.get('waehrung') or '')} aus."
        out.append((f"Macht {name} Gewinn oder Verlust?", antwort))
    if f.get("kgv") is not None and 0 < f["kgv"] < 500:
        out.append((f"Wie hoch ist das KGV von {name}?",
                    f"Das Kurs-Gewinn-Verhältnis (KGV) von {name} liegt bei {B.de(f['kgv'], 1)}. Es zeigt, "
                    f"wie viele Jahresgewinne der Kurs je Aktie abdeckt."))
    if f.get("div") and f["div"] > 0 and f.get("rend") and f["rend"] > 0:
        out.append((f"Zahlt {name} eine Dividende?",
                    f"Ja. Die letzte Dividende je Aktie lag bei {B.de(f['div'], 2)} {f.get('waehrung') or ''}, "
                    f"das entspricht einer Rendite von rund {B.de(f['rend'], 2)} %. Details stehen auf der "
                    f"Dividendenseite von {name}."))
    elif f.get("div") and f["div"] > 0:
        out.append((f"Zahlt {name} eine Dividende?",
                    f"Die letzte Dividende je Aktie lag bei {B.de(f['div'], 2)} {f.get('waehrung') or ''}."))
    return out


def seite(f, profil, dividende_url, head, kopf, fuss):
    sym, name, slug = f["sym"], f["name"], f["slug"]
    url = f"aktien-hub/{slug}/"
    w = f.get("waehrung") or ""
    title = f"{name} Aktie: Geschäft, Kennzahlen und Fragen | Aktien-Hub"
    desc = (profil.split(". ")[0].rstrip(".") + ". Kennzahlen und Fragen zur Aktie im Überblick.")[:300]
    kopfz = []
    if f.get("isin"):
        kopfz.append(f"ISIN {f['isin']}")
    kopfz.append(f"Kürzel {sym}")
    if f.get("land"):
        kopfz.append(f"Land {land_name(f['land'])}")

    zeilen = []
    if f.get("boerse"):
        zeilen.append(("Handelsplatz", f["boerse"], ""))
    if f.get("sektor"):
        zeilen.append(("Sektor", f["sektor"], ""))
    if w:
        zeilen.append(("Währung", w, ""))
    if f.get("umsatz") is not None and f["umsatz"] > 0:
        zeilen.append(("Umsatz (letztes Jahr)", betrag(f["umsatz"], w), ""))
    if f.get("gewinn") is not None:
        zeilen.append(("Gewinn (letztes Jahr)", betrag(f["gewinn"], w), ""))
    if f.get("kgv") is not None and 0 < f["kgv"] < 500:
        zeilen.append(("KGV", B.de(f["kgv"], 1), "Kurs im Verhältnis zum Gewinn je Aktie"))
    if f.get("div") and f["div"] > 0:
        zeilen.append(("Dividende je Aktie (letztes Jahr)", f"{B.de(f['div'], 2)} {w}", ""))
    if f.get("rend") and f["rend"] > 0:
        zeilen.append(("Dividendenrendite", B.de(f["rend"], 2) + " %", ""))
    tabelle = "".join(f'<tr><td>{esc(a)}{(" <span class=\"hint\">" + esc(c) + "</span>") if c else ""}</td><td class="n">{esc(b)}</td></tr>' for a, b, c in zeilen)
    tabelle = f'<div class="tablewrap"><table><tbody>{tabelle}</tbody></table></div>' if tabelle else ""

    faq = fragen(f, name, profil, dividende_url)
    faq_html = "".join(f"<details><summary>{esc(q)}</summary><p>{esc(a)}</p></details>" for q, a in faq)
    link_div = f'<p><a class="btn alt" href="dividende/">Zum Dividendenprofil →</a></p>' if dividende_url else ""

    ld = [
        {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Start", "item": BASE},
            {"@type": "ListItem", "position": 2, "name": "Aktien-Hub", "item": BASE + "aktien-hub/"},
            {"@type": "ListItem", "position": 3, "name": name, "item": BASE + url}]},
        {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]},
    ]
    ld_html = "".join(f'<script type="application/ld+json">{json.dumps(x, ensure_ascii=False)}</script>\n' for x in ld)

    h = head
    h = re.sub(r"<title>.*?</title>", lambda m: f"<title>{esc(title)}</title>", h, flags=re.S)
    h = re.sub(r'<meta name="description" content="[^"]*">', lambda m: f'<meta name="description" content="{esc(desc)}">', h)
    h = re.sub(r'<link rel="canonical" href="[^"]*">', lambda m: f'<link rel="canonical" href="{BASE}{url}">', h)
    h = re.sub(r'(<meta property="og:title" content=")[^"]*"', lambda m: m.group(1) + esc(title) + '"', h)
    h = re.sub(r'(<meta property="og:description" content=")[^"]*"', lambda m: m.group(1) + esc(desc) + '"', h)
    h = re.sub(r'(<meta property="og:url" content=")[^"]*"', lambda m: m.group(1) + BASE + url + '"', h)
    h = h.replace("<title>", "<!-- schlanke-firmenseite -->\n<title>", 1)

    main = f'''<main class="wrap"><article>
<nav class="crumbs" aria-label="Brotkrumen"><a href="../../">Start</a> › <a href="../">Aktien-Hub</a> › <span aria-current="page">{esc(name)}</span></nav>
<div class="titlerow"><h1>{esc(name)} Aktie</h1></div>
<p class="meta">{esc(" · ".join(kopfz))}</p>
<p class="lead">{esc(profil)}</p>
{tabelle}
{link_div}
<h2>Fragen und Antworten</h2>
<div class="faq">{faq_html}</div>
<p class="note"><strong>Hinweis:</strong> Diese Seite dient der allgemeinen Information und ist keine Anlageberatung. Angaben aus Börsenkursen und Geschäftsberichten, ohne Gewähr.</p>
</article></main>
'''
    return f'{h}{ld_html}</head>\n<body>{kopf}{main}{fuss}', url


def vorlage():
    s = open(os.path.join(ROOT, "aktien-hub", "altria", "index.html"), encoding="utf-8").read()
    head = s[:s.find("<body>")]
    head = re.sub(r"<script[^>]*>.*?</script>\n?", "", head, flags=re.S)
    head = re.sub(r'<link rel="stylesheet" href="\.\./\.\./assets/firma-ansicht[^>]*>\n?', "", head)
    kopf = s[s.find("<body>") + 6:s.find("<main")]
    kopf = re.sub(r"<script[^>]*>.*?</script>\n?", lambda m: m.group(0) if "navigation" in m.group(0) or "logos" in m.group(0) else "", kopf, flags=re.S)
    fuss = s[s.find("<footer"):]
    return head, kopf, fuss


def main():
    lean = lade("data/firmen-lean.json")["firmen"]
    prof = lade("data/firma-profile.json")["firmen"]
    DA.main()  # Dividendenseiten zuerst, damit die Firmenseite den Link richtig setzt
    head, kopf, fuss = vorlage()
    gebaut = []
    for f in lean:
        p = prof.get(f["sym"], {}).get("text")
        if not p or not f.get("slug"):
            continue
        ziel = os.path.join(ROOT, "aktien-hub", f["slug"])
        idx = os.path.join(ziel, "index.html")
        if os.path.exists(idx) and "schlanke-firmenseite" not in open(idx, encoding="utf-8").read(400):
            print("übersprungen (bestehende Seite):", f["slug"])
            continue
        div_ok = os.path.exists(os.path.join(ziel, "dividende", "index.html"))
        html_, url = seite(f, p, "dividende/" if div_ok else None, head, kopf, fuss)
        os.makedirs(ziel, exist_ok=True)
        open(idx, "w", encoding="utf-8").write(html_)
        gebaut.append(url)
    print("Firmenseiten (schlank) gebaut:", len(gebaut))
    dividenden = [f"aktien-hub/{f['slug']}/dividende/" for f in lean
                  if os.path.exists(os.path.join(ROOT, "aktien-hub", f["slug"], "dividende", "index.html"))]
    DA.sitemap_aufraeumen(gebaut + dividenden)


if __name__ == "__main__":
    main()
