#!/usr/bin/env python3
"""Einmalige Aufteilung: Startseite behaelt nur den Dividenden-Rechner, alle anderen Rechner bekommen eigene Unterseiten.
Die Skripte (Chart.js, Rechner-Sammlung) liegen danach in assets/. Aufruf einmalig: python3 tools/split_rechner.py"""
import html, os, re
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
L = open("index.html", encoding="utf-8").read().split("\n")
src = "\n".join(L)

SLUG = {"dividenden-vergleich": "dividenden-vergleich", "von-dividenden-leben": "von-dividenden-leben", "rentenluecke": "rentenluecke",
        "rentenstrategie": "rentenstrategie", "reinvestieren": "dividenden-reinvestieren", "altersvorsorgedepot": "altersvorsorgedepot",
        "vorabpauschale": "vorabpauschale-rechner", "etf-rechner": "etf-rechner"}
NAME = {"dividenden-rechner": "Dividenden-Rechner", "dividenden-vergleich": "Dividenden-Vergleich", "von-dividenden-leben": "Von Dividenden leben",
        "rentenluecke": "Rentenlücke füllen", "rentenstrategie": "Rentenstrategie", "reinvestieren": "Dividenden reinvestieren",
        "altersvorsorgedepot": "Altersvorsorge-Depot", "vorabpauschale": "Vorabsteuer bei ETF/Fonds", "etf-rechner": "ETF-Rechner"}
ORDER = list(NAME)

# ---- Skripte auslagern
i_chart = next(i for i, l in enumerate(L) if l.startswith("<script>") and i + 1 < len(L) and L[i + 1].startswith("/*!") and "Chart.js" in L[i + 2])
i_chart_end = next(i for i in range(i_chart, len(L)) if L[i] == "</script>")
i_app = i_chart_end + 1
assert L[i_app] == "<script>" and "Rechner für dividenden-rechner" in L[i_app + 1]
i_app_end = next(i for i in range(i_app, len(L)) if L[i] == "</script>")
i_coll = i_app_end + 1
assert L[i_coll] == "<script>" and "Rechner-Sammlung" in L[i_coll + 1]
i_coll_end = next(i for i in range(i_coll, len(L)) if L[i] == "</script>")
open("assets/chart.umd.js", "w", encoding="utf-8").write("\n".join(L[i_chart + 1:i_chart_end]) + "\n")
open("assets/rechner.js", "w", encoding="utf-8").write("\n".join(L[i_app + 1:i_app_end] + L[i_coll + 1:i_coll_end]) + "\n")
js = open("assets/rechner.js", encoding="utf-8").read()

# ---- Rechner.js: Startlogik pro Seite
a = """    if (!$("calc-menu")) return;
    ORDER.forEach(function (k) {"""
assert a in js
js = js.replace(a, """    var rid = root.RECHNER_ID || "dividenden-rechner";
    var SLUG = %s;
    var h0 = (location.hash || "").replace("#", "");
    if (SLUG[h0] && h0 !== rid) { location.replace((root.RECHNER_BASE || "") + SLUG[h0] + "/"); return; }
    if (!$("t-" + rid)) return;
    ORDER.forEach(function (k) {""" % str(SLUG).replace("'", '"'))
a = """    var h = (location.hash || "").replace("#", "");
    show(ORDER.indexOf(h) > -1 ? h : ORDER[0], false);
    root.addEventListener("hashchange", function () { var x = (location.hash || "").replace("#", ""); if (ORDER.indexOf(x) > -1 && x !== current) show(x, false); });"""
assert a in js
js = js.replace(a, "    show(rid, false);")
open("assets/rechner.js", "w", encoding="utf-8").write(js)

# ---- Bloecke
starts = [i for i, l in enumerate(L) if l.startswith('<div class="calc-wrap" id="t-')]
end_last = next(i for i, l in enumerate(L) if l.startswith('<aside class="note" style="background:#f0fdf4')) - 1
blocks = {}
for n, s in enumerate(starts):
    e = starts[n + 1] - 1 if n + 1 < len(starts) else end_last
    bid = re.match(r'<div class="calc-wrap" id="t-([a-z-]+)"', L[s]).group(1)
    blocks[bid] = L[s:e + 1]
assert list(blocks) == ORDER, list(blocks)

# ---- gemeinsame Teile
i_body = next(i for i, l in enumerate(L) if l.startswith('<body class="tools">'))
head = "\n".join(L[:i_body])
header = "\n".join(L[i_body:i_body + 4])   # body, header, 2 Skripte
assert "navigation.js" in header and "logos.js" in header, header[-200:]
f0 = next(i for i, l in enumerate(L) if l.startswith('<footer class="site-footer">'))
f1 = next(i for i in range(f0, len(L)) if "</footer>" in L[i])
footer = "\n".join(L[f0:f1 + 1])
MENU_CSS = ("<style id=\"menu-links\">.calc-menu a{flex:none;font:inherit;font-size:13px;font-weight:500;padding:6px 0 8px;border-bottom:2px solid transparent;margin-bottom:-1px;color:#8a97a3;text-decoration:none}"
            ".calc-menu a:hover{color:#5b6874}.calc-menu a[aria-current=page]{color:#33414d;font-weight:600;border-bottom-color:#8a97a3}.tool h1{margin:0 0 1.2rem;padding-bottom:10px;border-bottom:2px solid #e5e7eb;color:var(--success);font-size:1.5em;line-height:1.25}</style>")


def menu(cur, up):
    out = []
    for k in ORDER:
        href = (up if k == "dividenden-rechner" else up + SLUG[k] + "/")
        if k == "dividenden-rechner" and up == "":
            href = "./"
        out.append(f'<a href="{href}"' + (' aria-current="page"' if k == cur else "") + f">{NAME[k]}</a>")
    return '<nav class="calc-menu" id="calc-menu" aria-label="Rechner auswählen">' + "".join(out) + "</nav>"


def relink(t, up):
    """interne Links relativ zur Seite: #id -> Unterseite, sonstige relative Links mit Praefix"""
    for k, s in SLUG.items():
        t = t.replace(f'href="#{k}"', f'href="{up}{s}/"')
    t = t.replace('href="#dividenden-rechner"', f'href="{up or "./"}"')
    if up:
        t = re.sub(r'(href|src)="(?!https?:|//|#|mailto:|data:|tel:|\.\./)([^"]*)"', lambda m: f'{m.group(1)}="{up}{m.group(2)}"', t)
        t = t.replace('href=""', f'href="{up}"')
    return t


def meta(h, slug, title, desc):
    url = f"https://dividenden-rechner.github.io/aktien-hub/{slug}/"
    h = re.sub(r"<title>.*?</title>", f"<title>{html.escape(title)}</title>", h)
    h = re.sub(r'(<meta name="description" content=")[^"]*', lambda m: m.group(1) + html.escape(desc, quote=True), h)
    h = re.sub(r'(<link rel="canonical" href=")[^"]*', lambda m: m.group(1) + url, h)
    h = re.sub(r'(<meta property="og:url" content=")[^"]*', lambda m: m.group(1) + url, h)
    h = re.sub(r'(<meta property="og:title" content=")[^"]*', lambda m: m.group(1) + html.escape(title, quote=True), h)
    h = re.sub(r'(<meta property="og:description" content=")[^"]*', lambda m: m.group(1) + html.escape(desc, quote=True), h)
    h = re.sub(r'<script type="application/ld\+json">.*?</script>\n?', "", h, flags=re.S)
    return h


def plain(t):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t))).strip()


# ---- Unterseiten
for bid, slug in SLUG.items():
    blk = "\n".join(blocks[bid])
    blk = blk.replace(' hidden>', '>', 1) if blk.split("\n")[0].endswith(" hidden>") else blk
    h2 = re.search(r'<h2 id="(h-[a-z-]+)">(.*?)</h2>', blk)
    name = plain(h2.group(2))
    blk = blk.replace(h2.group(0), f'<h1 id="{h2.group(1)}">{h2.group(2)}</h1>', 1)
    intro = re.search(r'<p class="intro">(.*?)</p>', blk, re.S)
    desc = plain(intro.group(1))[:300] if intro else name
    if len(desc) > 158:
        desc = desc[:155].rsplit(" ", 1)[0] + " …"
    title = f"{name}: kostenloser Rechner | Dividenden-Rechner"
    up = "../"
    page = (meta(head, slug, title, desc).replace("</head>", MENU_CSS + "\n</head>") + "\n" + header + "\n"
            + '<main class="wrap"><article class="wide">\n'
            + f'<nav class="crumbs" aria-label="Brotkrumen"><a href="">Start</a> › <span aria-current="page">{html.escape(NAME[bid])}</span></nav>\n'
            + menu(bid, up) + "\n<!--calc-start-->\n" + blk + "\n<!--calc-end-->\n<!--av-start--><!--av-end-->\n"
            + '<p class="note"><strong>Hinweis:</strong> Dieser Text dient der allgemeinen Information und ist weder Anlage-, Steuer- noch Rechtsberatung. Alle Ergebnisse sind Szenarien auf Basis deiner Annahmen und keine Prognose.</p>\n'
            + "</article></main>\n" + footer + "\n"
            + '<script src="assets/chart.umd.js"></script>\n'
            + f'<script>window.RECHNER_ID="{bid}";</script>\n<script src="assets/rechner.js"></script>\n</body>\n</html>\n')
    page = relink(page, up)
    os.makedirs(slug, exist_ok=True)
    open(os.path.join(slug, "index.html"), "w", encoding="utf-8").write(page)
    print("Seite:", slug, len(page))

# ---- Startseite: nur Dividenden-Rechner, Menue als Links
S = L[:]
# Bloecke 2..9 entfernen (von hinten)
cut_from = starts[1]
S = S[:cut_from] + S[end_last + 1:]
# Skripte ersetzen: Chart.js + 2 Rechner-Skripte -> externe Dateien
j = next(i for i, l in enumerate(S) if l == "<script>" and i + 1 < len(S) and S[i + 1].startswith("/*!") and "Chart.js" in S[i + 2])
je = j
for _ in range(3):
    je = next(i for i in range(je, len(S)) if S[i] == "</script>") + 1
ext = ['<script src="assets/chart.umd.js"></script>',
       '<script>window.RECHNER_ID="dividenden-rechner";</script>', '<script src="assets/rechner.js"></script>']
S = S[:j] + ext + S[je:]
home = "\n".join(S)
home = re.sub(r'<nav class="calc-menu" id="calc-menu".*?</nav>', lambda m: menu("dividenden-rechner", ""), home, count=1, flags=re.S)
home = home.replace("</head>", MENU_CSS + "\n</head>", 1)
home = home.replace(' hidden>', '>', 1) if '<div class="calc-wrap" id="t-dividenden-rechner" hidden>' in home else home
for k, s in SLUG.items():
    home = home.replace(f'href="#{k}"', f'href="{s}/"')
open("index.html", "w", encoding="utf-8").write(home)
print("Startseite:", len(src), "->", len(home))
