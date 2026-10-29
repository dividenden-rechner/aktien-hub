#!/usr/bin/env python3
"""Baut die Wissensartikel (Einführung, Grundlagen, Fortgeschrittene, Über uns) aus Markdown:
content/wissen/<bereich>/<name>.md  ->  <bereich>/<name>/index.html, dazu Karten auf den Übersichtsseiten, Sitemap und llms.txt.
Wird von tools/build_magazin.py automatisch mit aufgerufen. Einzeln:  python3 tools/build_wissen.py
Kopfbereich (zwischen ---): title, description, lead, karte (Text der Übersichtskarte), updated (JJJJ-MM-TT), weiter (Pfade mit Komma, z. B. grundlagen/kgv/, fortgeschrittene/quellensteuer/), reihenfolge (Zahl, optional)."""
import re, os, sys, json, html, glob, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import glossar

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
esc = lambda s: html.escape(str(s), quote=True)
BEREICHE = {"einfuehrung": ("einfuehrung", "Einführung"), "grundlagen": ("grundlagen", "Grundlagen"),
            "fortgeschrittene": ("fortgeschrittene", "Fortgeschrittene"), "ueber-uns": ("", "Über uns")}
MARK = "<!-- wissen-gebaut -->"
HINWEIS = ('<p class="note"><strong>Hinweis:</strong> Dieser Text dient der allgemeinen Information und ist weder Anlage-, Steuer- noch Rechtsberatung. '
           'Kapitalanlagen sind mit Risiken verbunden, bis hin zum Totalverlust. Die Zahlenbeispiele sind frei gewählt und keine Prognose.</p>')

def read(path):
    raw = open(path, encoding="utf-8").read()
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", raw, re.S)
    if not m: raise SystemExit(f"{path}: Kopfbereich zwischen --- fehlt")
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.strip().startswith("#"):
            k, v = line.split(":", 1); meta[k.strip().lower()] = v.strip().strip('"').strip("'")
    for k in ("title", "description", "lead"):
        if not meta.get(k): raise SystemExit(f"{path}: Feld '{k}' fehlt")
    b = os.path.basename(os.path.dirname(path))
    meta["bereich"] = b; meta["slug"] = os.path.splitext(os.path.basename(path))[0]
    meta["url"] = f"{b}/{meta['slug']}/"; meta["body"] = m.group(2).strip()
    meta["upd"] = datetime.datetime.strptime(meta.get("updated") or datetime.date.today().isoformat(), "%Y-%m-%d")
    meta["reihenfolge"] = int(meta.get("reihenfolge") or 50)
    return meta

def title_of(url, pages):
    for p in pages:
        if p["url"] == url: return p["title"]
    return glossar._h1(url) or url

def faq_split(body_html):
    """'Häufige Fragen' mit h3-Fragen -> details-Blöcke + Liste (Frage, Antwort) für das FAQ-Markup."""
    m = re.search(r"<h2[^>]*>\s*Häufige Fragen\s*</h2>(.*)$", body_html, re.S)
    if not m: return body_html, []
    faq = []; out = ""
    for q, a in re.findall(r"<h3[^>]*>(.*?)</h3>\s*(.*?)(?=<h3|$)", m.group(1), re.S):
        qt = re.sub(r"<[^>]+>", "", q).strip(); at = re.sub(r"<[^>]+>", " ", a); at = re.sub(r"\s+", " ", at).strip()
        faq.append((qt, at)); out += f"<details><summary>{esc(qt)}</summary>{a.strip()}</details>\n"
    return body_html[:m.start(1)] + "\n" + out, faq

def build_page(bm, p, pages):
    depth = 2; pre = "../" * depth; url = p["url"]
    nav_key, label = BEREICHE[p["bereich"]]
    body = bm.md_to_html(p["body"], depth)
    body, faq = faq_split(body)
    hits = [h for h in glossar.analyse({}, body) if h["url"] != url]
    body = glossar.verlinke(body, hits, pre)
    words = len(re.sub(r"<[^>]+>", " ", body).split()); mins = max(1, round(words / 200))
    crumbs = (f'<a href="{pre}">Start</a> › ' + (f'<a href="{pre}{p["bereich"]}/">{label}</a> › ' if nav_key else "") + f'<span aria-current="page">{esc(p["title"])}</span>')
    ld = [{"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Start", "item": bm.BASE}] +
            ([{"@type": "ListItem", "position": 2, "name": label, "item": bm.BASE + p["bereich"] + "/"}] if nav_key else []) +
            [{"@type": "ListItem", "position": 3 if nav_key else 2, "name": p["title"], "item": bm.BASE + url}]},
          {"@context": "https://schema.org", "@type": "Article", "headline": p["title"][:110], "description": p["description"], "inLanguage": "de",
           "dateModified": bm.iso(p["upd"]), "mainEntityOfPage": bm.BASE + url, "wordCount": words,
           "author": {"@type": "Organization", "name": bm.CFG["default_author"], "url": bm.BASE + "ueber-uns/"},
           "publisher": {"@type": "Organization", "name": bm.SITE, "logo": {"@type": "ImageObject", "url": bm.BASE + bm.CFG["publisher_logo"]}}}]
    if faq:
        ld.append({"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]})
    extra = "".join('<script type="application/ld+json">%s</script>\n' % json.dumps(x, ensure_ascii=False) for x in ld)
    o = MARK + "\n" + bm.head(depth, p["title"], p["description"], url, "article", bm.BASE + "assets/og-default.png", extra).replace("<!DOCTYPE html>", "<!DOCTYPE html>", 1)
    o = o.replace(MARK + "\n", "", 1)
    o = o.replace("<html lang=\"de\">", "<html lang=\"de\">\n" + MARK, 1)
    o += bm.nav_html(depth, nav_key) + "</nav></div></header>\n"
    o += f'<script src="{pre}assets/navigation.js"></script>\n<script src="{pre}assets/logos.js"></script>\n<main class="wrap"><article>\n'
    o += f'<nav class="crumbs" aria-label="Brotkrumen">{crumbs}</nav>\n<h1>{esc(p["title"])}</h1>\n'
    o += f'<p class="meta">Zuletzt aktualisiert: {bm.de_date(p["upd"])} · {mins} Min. Lesezeit</p>\n<p class="lead">{esc(p["lead"])}</p>\n'
    o += body + "\n"
    weiter = [x.strip() for x in (p.get("weiter") or "").split(",") if x.strip()]
    if weiter:
        o += '<aside class="related"><h2>Weiterlesen</h2><ul>\n' + "\n".join(f'<li><a href="{pre}{w}">{esc(title_of(w, pages))}</a></li>' for w in weiter) + "\n</ul></aside>\n"
    o += (f'<aside class="note" style="background:#f0fdf4;border-left-color:#10b981"><strong>Passende Werkzeuge:</strong> Prüfe Aktien im <a href="{pre}aktien/">Aktien-Hub</a>, '
          f'vergleiche sie im <a href="{pre}aktien/vergleich/">Aktien-Vergleich</a>, filtere mit dem <a href="{pre}screener/">Screener</a> oder rechne mit den <a href="{pre}">Rechnern</a>.</aside>\n')
    o += HINWEIS + "\n</article></main>\n" + bm.footer_html(depth) + "\n</body>\n</html>\n"
    out = os.path.join(ROOT, p["bereich"], p["slug"], "index.html")
    if os.path.exists(out) and MARK not in open(out, encoding="utf-8").read():
        raise SystemExit(f"{out} existiert und wurde nicht aus Markdown gebaut. Anderen Dateinamen wählen oder die Seite zuerst entfernen.")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "w", encoding="utf-8").write(o)

def card(p, pre):
    return f'<a class="card" href="{pre}{p["url"]}"><h3>{esc(p.get("kurztitel") or p["title"])}</h3><p>{esc(p.get("karte") or p["description"])}</p></a>\n'

def patch_index(bereich, pages):
    f = os.path.join(ROOT, bereich, "index.html")
    if not os.path.exists(f): return
    s = open(f, encoding="utf-8").read()
    mine = sorted([p for p in pages if p["bereich"] == bereich], key=lambda p: (p["reihenfolge"], p["title"]))
    cards = "".join(card(p, "../") for p in mine)
    s = re.sub(r"<!-- wissen-neu -->.*?<!-- /wissen-neu -->", "<!-- wissen-neu -->", s, flags=re.S)
    if "<!-- wissen-neu -->" not in s:
        if bereich == "einfuehrung":
            s = s.replace('<aside class="related">', '<h2>Weitere Einsteiger-Themen</h2>\n<div class="cards">\n<!-- wissen-neu -->\n</div>\n\n<aside class="related">', 1)
        else:
            return
    s = s.replace("<!-- wissen-neu -->", "<!-- wissen-neu -->\n" + cards + "<!-- /wissen-neu -->", 1)
    open(f, "w", encoding="utf-8").write(s)

def patch_sitemap_llms(bm, pages):
    f = os.path.join(ROOT, "sitemap.xml"); s = open(f, encoding="utf-8").read()
    for p in pages:
        s = re.sub(r"<url><loc>%s</loc>.*?</url>\n?" % re.escape(bm.BASE + p["url"]), "", s)
    add = "".join(f"<url><loc>{bm.BASE}{p['url']}</loc><lastmod>{p['upd'].date()}</lastmod><priority>0.7</priority></url>\n" for p in pages)
    open(f, "w", encoding="utf-8").write(s.replace("</urlset>", add + "</urlset>"))
    f = os.path.join(ROOT, "llms.txt"); s = open(f, encoding="utf-8").read()
    for p in pages:
        s = re.sub(r"- \[[^\]]*\]\(%s\)[^\n]*\n" % re.escape(bm.BASE + p["url"]), "", s)
    add = "".join(f"- [{p['title']}]({bm.BASE}{p['url']}): {p['description']}\n" for p in pages)
    s = s.replace("\n## Hinweis", "\n" + add + "\n## Hinweis", 1) if "\n## Hinweis" in s else s + "\n" + add
    open(f, "w", encoding="utf-8").write(s)

def run(bm):
    pages = [read(f) for f in sorted(glob.glob(os.path.join(ROOT, "content", "wissen", "*", "*.md"))) if not os.path.basename(f).startswith(("_", "README"))]
    for p in pages: p["url"] = p["url"]
    glossar.reload()                       # Stichworte auch für Seiten, die erst jetzt entstehen
    for p in pages: build_page(bm, p, pages)
    glossar.reload()
    for b in ("einfuehrung", "grundlagen", "fortgeschrittene"): patch_index(b, pages)
    patch_sitemap_llms(bm, pages)
    print(f"{len(pages)} Wissensartikel gebaut")

if __name__ == "__main__":
    import build_magazin as bm
    run(bm)
