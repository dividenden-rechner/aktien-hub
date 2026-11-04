#!/usr/bin/env python3
"""Baut die Quellensteuer-Länderseiten aus tools/quellensteuer_laender.py im Muster der Spanien-Seite.
Seiten mit "entwurf": True werden mit noindex gebaut und nicht auf der Übersichtsseite verlinkt.
Aufruf: python3 tools/build_quellensteuer.py [slug ...]"""
import os, re, sys, json, html
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from quellensteuer_laender import LAENDER

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "https://dividenden-rechner.github.io/aktien-hub/"
SHELL = open(os.path.join(ROOT, "fortgeschrittene/quellensteuer/spanien/index.html"), encoding="utf-8").read()
HEUTE = "2026-11-04"
esc = lambda s: html.escape(s, quote=True)
raw = lambda s: s  # Texte enthalten bereits &amp; wo nötig
SATZ = 26.375


def de(x, d=2):
    t = f"{x:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return t


def pct(x):
    t = f"{x:.3f}".rstrip("0").rstrip(".")
    return t.replace(".", ",")


def rechnung(c):
    e, a = c["einbehalt"], c["abkommen"]
    if not e or a is None:
        return ""
    einb = e * 10
    anr = min(e, a) * 10
    erst = max(0.0, (e - a) * 10)
    dt = max(0.0, 1000 * SATZ / 100 - anr)
    netto = 1000 - einb - dt
    rows = [("Einbehalt im Quellenland", f"{de(einb)} €"), ("Davon in Deutschland anrechenbar", f"{de(anr)} €")]
    if erst > 0:
        rows += [("Im Quellenland erstattbar", f"{de(erst)} €"), ("Netto nach allen Steuern, ohne Erstattung", f"{de(netto)} €"), ("Netto nach allen Steuern, mit Erstattung", f"{de(netto + erst)} €")]
    else:
        rows += [("Netto nach allen Steuern", f"{de(netto)} €")]
    tr = "".join(f"<tr><td>{a1}</td><td>{b1}</td></tr>" for a1, b1 in rows)
    zusatz = ""
    if c.get("nur_unfranked"):
        zusatz = " Die Rechnung gilt nur für den unfranked-Anteil einer Dividende; auf den franked-Anteil fällt keine Quellensteuer an."
    return ('<h2 id="rechnung">Beispielrechnung mit 1.000 € Dividende</h2>'
            f'<p>Beispiel mit 1.000 € Brutto-Dividende aus {esc(c.get("aus", c["name"]))}. Annahmen: Abgeltungsteuer 25 % plus Solidaritätszuschlag (zusammen 26,375 %), keine Kirchensteuer, Sparer-Pauschbetrag nicht berücksichtigt. Das ist eine eigene Rechnung, keine amtliche Auskunft.{zusatz}</p>'
            f'<div class="tablewrap"><table><thead><tr><th>Posten</th><th>Betrag</th></tr></thead><tbody>{tr}</tbody></table></div>'
            '<p>Reicht dein Sparer-Pauschbetrag aus, entfällt die deutsche Steuer. Die angerechnete Auslandssteuer geht dann ins Leere, und die erstattbare Differenz ist der einzige Teil, den du zurückholen kannst.</p>')


def deutschland(c):
    e, a = c["einbehalt"], c["abkommen"]
    if not e:
        return ('<h2 id="deutschland">Was passiert in Deutschland?</h2>'
                f'<p>Weil in {esc(c.get("aus", c["name"]).replace("aus ",""))} nichts einbehalten wird, gibt es in Deutschland nichts anzurechnen. Die Dividende ist wie andere Kapitalerträge steuerpflichtig, die Abgeltungsteuer zieht deine Bank ein, sofern dein Sparer-Pauschbetrag nicht reicht.</p>')
    return ('<h2 id="deutschland">Was passiert in Deutschland?</h2>'
            '<p>Deutschland rechnet ausländische Quellensteuer auf die Abgeltungsteuer an, aber höchstens mit dem Satz des Doppelbesteuerungsabkommens. '
            + (f'Bei Dividenden aus {esc(c.get("aus", c["name"]))} sind das {pct(min(e, a))} der einbehaltenen {pct(e)} Prozentpunkte.' if a is not None else f'Bei Dividenden aus {esc(c.get("aus", c["name"]))} haben wir den Abkommenssatz nicht belegt.')
            + '</p><p>Was darüber hinaus einbehalten wurde, ist in Deutschland nicht anrechenbar und muss im Quellenland zurückgefordert werden. '
              'Nicht angerechnete, aber anrechenbare Beträge trägst du in der Anlage KAP ein. Die Zeilennummern ändern sich von Jahr zu Jahr; prüfe sie im aktuellen Formular. Das Finanzamt verlangt dafür die Steuerbescheinigung im Original.</p>')


def main_html(c, by_slug):
    toc = [("kurz", "Kurzantwort und Steckbrief")] + [(i, t) for i, t, _ in c["sections"]]
    if c["einbehalt"] and c["abkommen"] is not None:
        toc.append(("rechnung", "Beispielrechnung mit 1.000 € Dividende"))
    toc += [("deutschland", "Was passiert in Deutschland?"), ("faq", "Häufige Fragen"), ("quellen", "Quellen und Stand")]
    toc_h = '<nav class="toc" aria-label="Inhalt"><strong>Inhalt</strong><ul>' + "".join(f'<li><a href="#{i}">{t}</a></li>' for i, t in toc) + "</ul></nav>"
    rows = "".join(f"<tr><td>{a}</td><td>{b}</td></tr>" for a, b in c["rows"])
    entwurf = ""
    if c.get("entwurf"):
        pr = c.get("pruefen") or []
        pr_h = (" Offen: " + "; ".join(pr) + ".") if pr else ""
        entwurf = f'<p class="note"><strong>Entwurf (Stand {HEUTE[8:]}.{HEUTE[5:7]}.{HEUTE[:4]}):</strong> Diese Seite ist noch nicht freigegeben und nicht verlinkt. Alle Angaben sind aus den unten genannten Quellen; was dort nicht stand, ist im Text als nicht belegt gekennzeichnet.{pr_h}</p>'
    secs = "".join(f'<h2 id="{i}">{t}</h2>\n{b}\n' for i, t, b in c["sections"])
    faq = "".join(f"<h3>{esc(q)}</h3>\n<p>{a}</p>\n" for q, a in c["faq"])
    qu = "".join(f'<li><a href="{u}" rel="noopener nofollow">{t}</a></li>' for t, u in c["quellen"])
    rel = [("../../../fortgeschrittene/quellensteuer/", "Quellensteuer: Überblick und Länderübersicht"), ("../../../fortgeschrittene/quellensteuer/rueckerstattung/", "Rückerstattung beantragen"), ("../../../grundlagen/dividendenbesteuerung/", "Besteuerung von Dividenden")]
    for r in c.get("related", []):
        if r in by_slug:
            rel.append((f"../../../fortgeschrittene/quellensteuer/{r}/", by_slug[r]["titel"]))
        else:
            rel.append((f"../../../fortgeschrittene/quellensteuer/{r}/", r.capitalize() + ": Quellensteuer"))
    rel_h = "".join(f'<li><a href="{h}">{t}</a></li>\n' for h, t in rel)
    return (f'<main class="wrap"><article>\n<nav class="crumbs" aria-label="Brotkrumen"><a href="../../../">Start</a> › <a href="../../../fortgeschrittene/">Fortgeschrittene</a> › <a href="../../../fortgeschrittene/quellensteuer/">Quellensteuer</a> › <span aria-current="page">{esc(c["name"])}</span></nav>\n'
            f'<h1>{esc(c["titel"])}</h1>\n<p class="lead">{c["lead"]}</p>\n{entwurf}{toc_h}<h2 id="kurz">Kurzantwort und Steckbrief</h2>\n<p><strong>Kurz gesagt:</strong> {c["kurz"]}</p>\n'
            f'<div class="tablewrap"><table><thead><tr><th>Merkmal</th><th>Angabe</th></tr></thead><tbody>{rows}</tbody></table></div>\n{secs}{rechnung(c)}\n{deutschland(c)}\n'
            f'<h2 id="faq">Häufige Fragen</h2>\n{faq}<h2 id="quellen">Quellen und Stand</h2>\n<p>Stand der Recherche: November 2026. Wo eine Angabe nur aus älteren oder inoffiziellen Quellen stammt, steht das im Text. Prüfe Sätze, Formulare, Adressen und Fristen vor einem Antrag bei der Behörde.</p>\n<ul>{qu}</ul>\n\n'
            f'<aside class="related"><h2>Weiterlesen</h2><ul>\n{rel_h}</ul></aside>\n'
            '<aside class="note" style="background:#f0fdf4;border-left-color:#10b981"><strong>Passende Werkzeuge:</strong> Prüfe Aktien im <a href="../../../aktien-hub/">Aktien-Hub</a>, filtere mit dem <a href="../../../screener/">Screener</a> oder verfolge Dividenden und Termine in deinem <a href="../../../depot/">Depot</a>.</aside>\n'
            '<p class="note"><strong>Hinweis:</strong> Dieser Text dient der allgemeinen Information und ist weder Anlage-, Steuer- noch Rechtsberatung. Formulare, Fristen und Steuersätze ändern sich; prüfe sie vor einem Antrag bei der jeweiligen Steuerbehörde oder einer Steuerberatung.</p>\n</article>')


def page(c, by_slug):
    url = f"{BASE}fortgeschrittene/quellensteuer/{c['slug']}/"
    s = SHELL
    s = re.sub(r"<title>.*?</title>", lambda m: f"<title>{esc(c['meta_title'])}</title>", s, count=1, flags=re.S)
    s = re.sub(r'<meta name="description" content="[^"]*">', lambda m: f'<meta name="description" content="{esc(c["description"])}">', s, count=1)
    s = re.sub(r'<link rel="canonical" href="[^"]*">', lambda m: f'<link rel="canonical" href="{url}">', s, count=1)
    s = re.sub(r'<meta property="og:title" content="[^"]*">', lambda m: f'<meta property="og:title" content="{esc(c["meta_title"])}">', s, count=1)
    s = re.sub(r'<meta property="og:description" content="[^"]*">', lambda m: f'<meta property="og:description" content="{esc(c["description"])}">', s, count=1)
    s = re.sub(r'<meta property="og:url" content="[^"]*">', lambda m: f'<meta property="og:url" content="{url}">', s, count=1)
    if c.get("entwurf"):
        s = re.sub(r'<meta name="robots" content="[^"]*">', '<meta name="robots" content="noindex,nofollow">', s, count=1)
    bc = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Start", "item": BASE},
        {"@type": "ListItem", "position": 2, "name": "Fortgeschrittene", "item": BASE + "fortgeschrittene/"},
        {"@type": "ListItem", "position": 3, "name": "Quellensteuer", "item": BASE + "fortgeschrittene/quellensteuer/"},
        {"@type": "ListItem", "position": 4, "name": c["name"], "item": url}]}
    art = {"@context": "https://schema.org", "@type": "Article", "headline": c["titel"], "description": c["description"], "inLanguage": "de", "datePublished": HEUTE, "dateModified": HEUTE, "mainEntityOfPage": url, "publisher": {"@type": "Organization", "name": "Dividenden-Rechner Aktien-Hub"}}
    strip = lambda t: re.sub(r"<[^>]+>", "", html.unescape(t))
    fq = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": strip(a)}} for q, a in c["faq"]]}
    ld = "".join(f'<script type="application/ld+json">{json.dumps(x, ensure_ascii=False)}</script>\n' for x in (bc, art, fq))
    s = re.sub(r'(<script type="application/ld\+json">.*?</script>\n){3}', lambda m: ld, s, count=1, flags=re.S)
    s = re.sub(r'<main class="wrap"><article>.*?</article>', lambda m: main_html(c, by_slug), s, count=1, flags=re.S)
    return s


def main():
    by_slug = {c["slug"]: c for c in LAENDER}
    wahl = set(sys.argv[1:])
    for c in LAENDER:
        if wahl and c["slug"] not in wahl:
            continue
        d = os.path.join(ROOT, "fortgeschrittene", "quellensteuer", c["slug"])
        os.makedirs(d, exist_ok=True)
        open(os.path.join(d, "index.html"), "w", encoding="utf-8").write(page(c, by_slug))
        print("gebaut:", c["slug"])


if __name__ == "__main__":
    main()
