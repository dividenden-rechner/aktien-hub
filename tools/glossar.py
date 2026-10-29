"""Automatische Verlinkung vom Magazin auf die Erklaerartikel (Grundlagen / Fortgeschrittene) und zurueck.
Konfiguration: tools/glossar.json. Wird von build_magazin.py benutzt."""
import re, os, json, html

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
esc = lambda s: html.escape(str(s), quote=True)
SKIP = ("a", "h1", "h2", "h3", "h4", "h5", "h6", "code", "pre", "figcaption", "summary", "th", "td", "em", "script", "style", "button")
MAX_INLINE = 6          # so viele Textlinks hoechstens je Artikel
MAX_BOX = 5             # so viele Eintraege hoechstens im Kasten

def _h1(path):
    try:
        s = open(os.path.join(ROOT, path, "index.html"), encoding="utf-8").read()
        m = re.search(r"<h1[^>]*>(.*?)</h1>", s, re.S)
        return html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip() if m else None
    except OSError:
        return None

def load():
    cfg = json.load(open(os.path.join(ROOT, "tools", "glossar.json"), encoding="utf-8"))
    entries = []
    for e in cfg["entries"]:
        if not os.path.exists(os.path.join(ROOT, e["url"], "index.html")):
            continue                                   # Seite gibt es (noch) nicht: ueberspringen
        e = dict(e); e["title"] = _h1(e["url"]) or e["grund"]
        pats = []
        for t in sorted(e["terms"], key=len, reverse=True):
            flags = 0 if (len(t) <= 4 and t.upper() == t) else re.I
            pats.append(re.compile(r"(?<![\w/-])" + re.escape(t) + r"(?:s|n|en|e)?(?![\wÄÖÜäöüß-])", flags))
        e["pats"] = pats
        entries.append(e)
    laender = {}
    for k, v in cfg["laender"].items():
        url = f"fortgeschrittene/quellensteuer/{k}/"
        if os.path.exists(os.path.join(ROOT, url, "index.html")):
            laender[k] = dict(v, url=url, title=_h1(url) or f"{v['name']}: Quellensteuer")
    return entries, laender

ENTRIES, LAENDER = load()

def reload():
    global ENTRIES, LAENDER
    ENTRIES, LAENDER = load()

def _text(body):
    return html.unescape(re.sub(r"<[^>]+>", " ", body))

def land_fuer(post, text):
    """Land fuer die Quellensteuer-Seite: erst Boersenkuerzel (.CO = Daenemark), dann Landesname nahe 'Quellensteuer'."""
    sym = (post.get("logo_symbol") or "").upper()
    for k, v in LAENDER.items():
        if any(sym.endswith(s) for s in v["suffix"]):
            return k
    for m in re.finditer(r"Quellensteuer", text):
        fenster = text[max(0, m.start() - 150): m.end() + 150]
        for k, v in LAENDER.items():
            if any(re.search(r"(?<!\w)" + re.escape(n), fenster) for n in v["namen"]):
                return k
    return None

def analyse(post, body_html):
    """Gibt die Treffer zurueck: Liste von dicts {id,url,title,grund,count} nach Wichtigkeit."""
    text = _text(body_html); hits = []
    for e in ENTRIES:
        n = sum(len(p.findall(text)) for p in e["pats"])
        if n: hits.append({"id": e["id"], "url": e["url"], "title": e["title"], "grund": e["grund"], "count": n, "pats": e["pats"]})
    ids = {h["id"] for h in hits}
    # Bedingung: Quellensteuer + erkanntes Land -> Laenderseite (z. B. Daenemark: Quellensteuer zurueckholen)
    if "qst" in ids:
        k = land_fuer(post, text)
        if k:
            v = LAENDER[k]
            hits = [h for h in hits if h["id"] != "qst"]
            hits.insert(0, {"id": "qst-" + k, "url": v["url"], "title": v["title"], "grund": f"So holst du die {v['name']}-Quellensteuer zurück (und alles Grundsätzliche zur Quellensteuer)", "count": 99, "bedingt": True,
                            "pats": [p for e in ENTRIES if e["id"] == "qst" for p in e["pats"]]})
    # Bedingung: hohe Ausschuettungsquote (ab 75 %) -> Warnsignale
    m = re.search(r"(?:Ausschüttungsquote|Payout[ -]Ratio)[^.]{0,90}?(\d{1,3}(?:,\d+)?)\s?(?:%|Prozent)", text)
    if m:
        try: wert = float(m.group(1).replace(",", "."))
        except ValueError: wert = 0
        if wert >= 75:
            for e in ENTRIES:
                if e["id"] == "falle" and not any(h["id"] == "falle" for h in hits):
                    hits.append({"id": "falle", "url": e["url"], "title": e["title"], "grund": f"Eine Ausschüttungsquote von {m.group(1)} % kann ein Warnsignal sein", "count": 1, "bedingt": True, "pats": []})
    hits.sort(key=lambda h: -h["count"])
    return hits

def verlinke(body_html, hits, pre):
    """Verlinkt die erste Textstelle je Treffer (nur in Fliesstext: nicht in Ueberschriften, Tabellen, Links, Bildzeilen)."""
    todo = [h for h in hits if h["pats"]][:MAX_INLINE]
    parts = re.split(r"(<[^>]+>)", body_html); stack = []; done = set()
    for i, seg in enumerate(parts):
        if seg.startswith("<"):
            m = re.match(r"<(/?)([a-zA-Z0-9]+)", seg)
            if m and not seg.endswith("/>"):
                tag = m.group(2).lower()
                if tag in SKIP:
                    if m.group(1): 
                        if tag in stack: stack.reverse(); stack.remove(tag); stack.reverse()
                    else: stack.append(tag)
            continue
        if stack or not seg.strip():
            continue
        cand = []
        for h in todo:
            if h["id"] in done: continue
            for p in h["pats"]:
                m = p.search(seg)
                if m: cand.append((m.start(), m.end(), h, m.group(0))); break
        cand.sort(key=lambda c: c[0]); last = -1; ok = []
        for c in cand:                                     # ueberlappende Treffer auslassen
            if c[0] >= last: ok.append(c); last = c[1]
        for a, b, h, txt in reversed(ok):
            seg = seg[:a] + f'<a class="glossar-link" href="{pre}{h["url"]}" title="{esc(h["title"])}">{txt}</a>' + seg[b:]
            done.add(h["id"])
        parts[i] = seg
    return "".join(parts)

def box(hits, pre):
    if not hits: return ""
    items = "\n".join(f'<li><a href="{pre}{h["url"]}">{esc(h["title"])}</a> {('<span class="glossar-grund">' + esc(h["grund"]) + '</span>') if h.get("bedingt") else ""}</li>' for h in hits[:MAX_BOX])
    return f'<aside class="related glossar"><h2>Hintergrund zum Thema</h2><ul>\n{items}\n</ul></aside>\n'

def patch_erklaerseiten(posts):
    """Auf den Erklaerseiten: Kasten 'Aktuell in den News' mit bis zu 3 neuesten Artikeln, die das Thema behandeln."""
    pro_seite = {}
    for p in posts:
        for h in p.get("glossar_hits", []):
            pro_seite.setdefault(h["url"], []).append(p)
    urls = {e["url"] for e in ENTRIES} | {v["url"] for v in LAENDER.values()}
    for url in sorted(urls):
        f = os.path.join(ROOT, url, "index.html")
        if not os.path.exists(f): continue
        s = open(f, encoding="utf-8").read()
        s = re.sub(r"<!-- mag-artikel -->.*?<!-- /mag-artikel -->\n?", "", s, flags=re.S)
        arts = pro_seite.get(url, [])[:3]
        if arts:
            pre = "../" * (url.strip("/").count("/") + 1)
            blk = ('<!-- mag-artikel -->\n<aside class="related glossar"><h2>Aktuell in den News</h2><ul>\n' +
                   "\n".join(f'<li><a href="{pre}magazin/{x["slug"]}/">{esc(x["title"])}</a></li>' for x in arts) + '\n</ul></aside>\n<!-- /mag-artikel -->\n')
            m = re.search(r'<p class="note"><strong>Hinweis:', s)
            if not m: continue
            s = s[:m.start()] + blk + s[m.start():]
        open(f, "w", encoding="utf-8").write(s)
