#!/usr/bin/env python3
"""Firmenseiten fuer alle Dividendenzahler aus data/kennzahlen.json (nur vorhandene Werte, nichts geschaetzt).
Wird am Ende von build_dividendenseiten.main() aufgerufen. Die 117 handgepflegten Seiten bleiben unveraendert.
Erzeugt: dividende/<slug>/, dividende/firmen/ (A-Z), dividende/sektor/<s>/, dividende/land/<cc>/, data/firmenseiten.json (Sym -> Slug)."""
import datetime, json, math, os, re, html as _h
import build_dividendenseiten as B

ROOT, BASE = B.ROOT, B.BASE
esc = B.esc if hasattr(B, "esc") else (lambda s: _h.escape(str(s), quote=True))
RESERVIERT = {"aristokraten", "firmen", "sektor", "land"}
SEKTOR = {"Industrials": "Industrie", "Financial Services": "Finanzen", "Healthcare": "Gesundheit", "Technology": "Technologie",
          "Utilities": "Versorger", "Consumer Cyclical": "Zyklischer Konsum", "Consumer Defensive": "Basiskonsum",
          "Basic Materials": "Grundstoffe", "Real Estate": "Immobilien", "Energy": "Energie", "Communication Services": "Kommunikation", "BDC": "BDCs"}
LAND = {"US": "USA", "JP": "Japan", "GB": "Großbritannien", "SE": "Schweden", "FR": "Frankreich", "CA": "Kanada", "KR": "Südkorea", "NL": "Niederlande",
        "DE": "Deutschland", "CH": "Schweiz", "AT": "Österreich", "IT": "Italien", "ES": "Spanien", "DK": "Dänemark", "NO": "Norwegen", "FI": "Finnland",
        "BE": "Belgien", "IE": "Irland", "PT": "Portugal", "AU": "Australien", "HK": "Hongkong", "SG": "Singapur", "TW": "Taiwan", "CN": "China",
        "IN": "Indien", "BR": "Brasilien", "MX": "Mexiko", "ZA": "Südafrika", "LU": "Luxemburg", "PL": "Polen", "TH": "Thailand", "MY": "Malaysia",
        "ID": "Indonesien", "CL": "Chile", "CO": "Kolumbien", "PE": "Peru", "AR": "Argentinien", "GR": "Griechenland", "NZ": "Neuseeland", "IL": "Israel"}
SUFFIX = r"\b(inc|incorporated|corp|corporation|ltd|limited|plc|se|ag|sa|nv|co|company|spa|oyj|ab|asa|as|a/s|kgaa|llc|lp|the)\b\.?"
WAEHR = {"USD": "US-Dollar", "EUR": "Euro", "GBP": "Pfund", "GBp": "Pence", "JPY": "Yen", "SEK": "Schwedische Kronen", "CHF": "Franken", "CAD": "Kanadische Dollar",
         "KRW": "Won", "DKK": "Dänische Kronen", "NOK": "Norwegische Kronen", "AUD": "Australische Dollar", "HKD": "HK-Dollar", "TWD": "Taiwan-Dollar"}


NAMEN = {"hp inc.": "HP Inc.", "bhp group limited": "BHP Group", "mol magyar olaj- és gáziparai nyilvánosan működő részvénytársaság": "MOL",
         "mol magyar olaj- és gáziparai nyilvánosan müködö részvénytársaság": "MOL"}


def sauber(n):
    n = _sauber(n)
    if n.upper().startswith("MOL MAGYAR"): return "MOL"
    return NAMEN.get(n.lower(), n)


def _sauber(n):
    n = re.sub(r"\s+", " ", (n or "").strip())
    n = re.sub(r"\s*/[A-Za-z]{2,3}/?$", "", n)      # Zusatz wie "/DE" (US-Bundesstaat) weg
    if n.isupper() and re.search(r"\b(INC|CORP|CORPORATION|LTD|CO|COMPANY|PLC|LLC|LP|TRUST|HOLDINGS|BANCORP|FINANCIAL|GROUP)\b", n):
        n = n.title()
        n = re.sub(r"\b(Of|And|The|For)\b", lambda m: m.group(1).lower(), n)
        n = re.sub(r"\b(Inc|Corp|Ltd|Plc|Llc|Lp|Se|Ag|Sa|Nv|Co|Spa|Ab|Asa)\b", lambda m: m.group(1) if m.group(1) in ("Inc", "Corp", "Ltd", "Plc", "Co") else m.group(1).upper(), n)
    return n.strip(" ,")


def slugify(n):
    s = n.lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss").replace("&", " und ")
    s = re.sub(r"[^\x00-\x7f]", "", s)
    s = re.sub(SUFFIX, " ", s)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:60].strip("-")


def bw(v):
    """Boersenwert in Euro. Bei Yen, Won, Taiwan-Dollar usw. (Wechselkurs ueber 20 je Euro) liegt der Wert in den Daten in Landeswaehrung und wird durch den Kurs geteilt."""
    x, fx = v.get("boersenwert_eur"), v.get("fx") or 1
    if not x: return None
    return x / fx if fx > 20 else x


def zahl(x, n=1):
    return B.de(x, n)


def mrd(usd_eur):
    if usd_eur is None: return "–"
    if usd_eur >= 1e9: return B.de(usd_eur / 1e9, 1) + " Mrd."
    return B.de(usd_eur / 1e6, 0) + " Mio."


def lade_firmen(vorhanden_sym):
    w = B.lade("data/kennzahlen.json")["werte"]
    try:
        bran = B.lade("data/branchen.json").get("branchen", {})
    except Exception:
        bran = {}
    kand = {}
    for t, v in w.items():
        if t in vorhanden_sym or not v.get("name") or not (v.get("dividende") or 0) > 0 or not v.get("kurs_eur"):
            continue
        if (v.get("rendite") or 0) <= 0 or v["rendite"] > 30:
            continue
        key = v.get("isin") or t
        if key in kand and (kand[key][1].get("umsatz_usd") or 0) >= (v.get("umsatz_usd") or 0):
            continue
        kand[key] = (t, v)
    firmen, namen = [], {}
    for t, v in sorted((x for x in kand.values()), key=lambda x: -(x[1].get("umsatz_usd") or 0)):
        nm = sauber(v["name"])
        if nm.lower() in namen:      # gleiche Firma an zweiter Boerse
            continue
        namen[nm.lower()] = 1
        sek = SEKTOR.get(v.get("sektor") or "", "") or SEKTOR.get(bran.get(t, ""), "") or (bran.get(t) if isinstance(bran.get(t), str) else "")
        _, anzahl = reihen_fuer(t)
        if anzahl == 0:
            continue            # keine Jahreszahlen: vorerst außen vor
        firmen.append({"sym": t, "name": nm, "v": v, "sektor": sek, "land": v.get("land") or "", "teil": anzahl < 8})
    return firmen


def vergeben(firmen, reserviert):
    benutzt = set(reserviert) | RESERVIERT
    for f in firmen:
        s = slugify(f["name"]) or f["sym"].lower()
        if s in reserviert:       # gleiche Firma wie eine handgepflegte Seite (z. B. zweite Boersennotierung)
            f["skip"] = True; continue
        if s in benutzt:
            s = f"{s}-{re.sub(r'[^a-z0-9]+', '-', f['sym'].lower()).strip('-')}"
        benutzt.add(s); f["slug"] = s


_GRUPPEN = None

def gruppe_fuer(sym):
    """Erste Peer-Gruppe aus data/dividende-peers.json, in der der Ticker steht (sonst None)."""
    global _GRUPPEN
    if _GRUPPEN is None:
        try:
            _GRUPPEN = json.load(open(os.path.join(B.ROOT, "data", "dividende-peers.json"), encoding="utf-8"))["gruppen"]
        except Exception:
            _GRUPPEN = []
    return next((g for g in _GRUPPEN if sym in g["members"]), None)


def peers_fuer(f, alle, nach_sektor, nach_land):
    gr = gruppe_fuer(f["sym"])
    if gr:
        mit = [g for g in alle if g["sym"] in gr["members"] and g["sym"] != f["sym"]]
        if mit:
            return mit[:5], "GRUPPE:" + gr["name"]
    mc = f["v"].get("umsatz_usd") or 0
    pool = [g for g in nach_sektor.get((f["sektor"], f["land"]), []) if g is not f] if f["sektor"] else []
    art = f"{f['sektor']} aus {LAND.get(f['land'], f['land'])}" if pool else ""
    if len(pool) < 3 and f["sektor"]:
        pool = [g for g in nach_sektor.get((f["sektor"], None), []) if g is not f]
        art = f"{f['sektor']} (weltweit)"
    if len(pool) < 3:
        pool = [g for g in nach_land.get(f["land"], []) if g is not f]
        art = f"ähnlich große Dividendenwerte aus {LAND.get(f['land'], f['land'])}"
    if not pool: return [], ""
    if mc:
        pool = sorted(pool, key=lambda g: abs(math.log((g["v"].get("umsatz_usd") or mc) / mc)))
    return pool[:5], art


_QUELLEN = None

def datenquellen():
    """Jahreszahlen je Firma: SEC zuerst, dann ESEF, Börse Deutschland, Asien (gleicher Aufbau: firmen[sym]['k'])."""
    global _QUELLEN
    if _QUELLEN is None:
        _QUELLEN = []
        for pfad in ["sec/fundamentals.json", "esef/fundamentals.json", "boerse-de/fundamentals.json", "asien/fundamentals.json"]:
            try:
                _QUELLEN.append(json.load(open(os.path.join(B.ROOT, "data", pfad), encoding="utf-8")).get("firmen", {}))
            except Exception:
                _QUELLEN.append({})
    return _QUELLEN


def reihen_fuer(sym):
    """Jahreswerte der Firma aus der ersten Quelle, die sie hat. Gibt (k, Anzahl Kennzahlen) zurück."""
    for q in datenquellen():
        if sym in q and (q[sym].get("k") or {}):
            k = {name: {d[:4]: val for d, val in reihe if val is not None} for name, reihe in q[sym]["k"].items()}
            return k, len([x for x in k.values() if x])
    return {}, 0


_PROG = None
PROG_REIHEN = {"Umsatz": "umsatz", "Free Cashflow": "fcf", "Dividende je Aktie": "dividende_je_aktie",
               "Gewinn je Aktie": "eps", "Operative Marge": "operative_marge"}


def prognose_fuer(sym, v, k):
    """Unternehmensprognosen fürs Folgejahr (Mitte der Spanne), nur in der Berichtswährung und nur für das Jahr direkt nach dem letzten Istwert."""
    global _PROG
    if _PROG is None:
        try:
            _PROG = json.load(open(os.path.join(B.ROOT, "data", "prognosen.json"), encoding="utf-8")).get("firmen", {})
        except Exception:
            _PROG = {}
    jahre = [int(j) for n in ("umsatz", "gewinn", "eps_verw") for j in k.get(n, {})]
    if not jahre or sym not in _PROG:
        return None
    jahr = max(jahre) + 1
    waehr = v.get("waehrung") or ""
    out = {}
    for x in _PROG[sym].get("prognosen", []):
        if str(x.get("geschaeftsjahr")) != str(jahr) or x.get("von") is None or x.get("bis") is None:
            continue
        mitte = (x["von"] + x["bis"]) / 2
        kz = x["kennzahl"]
        if kz == "umsatz" and x.get("einheit") == waehr:
            out["umsatz"] = mitte / 1e9
        elif kz == "fcf" and x.get("einheit") == waehr:
            out["fcf"] = mitte / 1e9
        elif kz == "dividende_je_aktie" and x.get("einheit") == waehr:
            out["dividende_je_aktie"] = round(mitte, 3)
        elif kz in ("eps_bereinigt", "eps_gaap") and x.get("einheit") == waehr and "eps" not in out:
            out["eps"] = round(mitte, 3)
        elif kz == "operative_marge_proz":
            out["operative_marge"] = round(mitte, 1)
    if not out:
        return None
    return {"jahr": jahr, "werte": out}


def diagramm_daten(k, prog=None):
    """Die Diagramm-Reihen für eine Firma (nur Reihen mit mindestens drei Jahren)."""
    def r(n):
        return k.get(n, {})
    jahre = sorted({j for n in ["umsatz", "gewinn", "operativer_cf", "capex", "dividende_je_aktie", "eps_verw", "dividenden_gezahlt", "aktienrueckkauf", "eigenkapital", "schulden_lang"] for j in r(n)})[-10:]
    def reihe(d, teiler=1e9):
        return [round(d[j] / teiler, 3) if d.get(j) is not None else None for j in jahre]
    fcf = {j: r("operativer_cf")[j] - r("capex")[j] for j in jahre if j in r("operativer_cf") and j in r("capex")}
    quote = {j: round(r("dividende_je_aktie")[j] / r("eps_verw")[j] * 100, 1) for j in jahre
             if j in r("dividende_je_aktie") and j in r("eps_verw") and r("eps_verw")[j]}
    quote = {j: v for j, v in quote.items() if 0 < v < 200}
    def quotient(a, b, skal=1.0):
        return [round(r(a)[j] / r(b)[j] * skal, 2) if r(a).get(j) is not None and r(b).get(j) else None for j in jahre]
    zinsdeckung = quotient("operatives_ergebnis", "zinsaufwand")
    op_marge = quotient("operatives_ergebnis", "umsatz", 100)
    netto_marge = quotient("gewinn", "umsatz", 100)
    charts = [
        ("Gewinnfluss: vom Umsatz zum Gewinn", "bar", "Mrd.", [("Umsatz", reihe(r("umsatz")), "#9fd3b2"), ("Bruttogewinn", reihe(r("bruttogewinn")), "#4a9aa6"), ("Operatives Ergebnis", reihe(r("operatives_ergebnis")), "#2f7d4f"), ("Nettogewinn", reihe(r("gewinn")), "#1d4d33")]),
        ("Operativer Cashflow und Free Cashflow", "bar", "Mrd.", [("Operativer Cashflow", reihe(r("operativer_cf")), "#4a9aa6"), ("Free Cashflow", reihe(fcf), "#2f7d4f")]),
        ("Mittelverwendung: Investitionen, Dividende, Rückkäufe", "bar", "Mrd.", [("Investitionen (Capex)", reihe(r("capex")), "#c0392b"), ("Dividendensumme", reihe(r("dividenden_gezahlt")), "#2f7d4f"), ("Aktienrückkäufe", reihe(r("aktienrueckkauf")), "#9fd3b2")]),
        ("Dividende je Aktie", "bar", "", [("Dividende je Aktie", [round(x, 3) if x is not None else None for x in [r("dividende_je_aktie").get(j) for j in jahre]], "#2f7d4f")]),
        ("Gewinn je Aktie (verwässert)", "line", "", [("Gewinn je Aktie", [r("eps_verw").get(j) for j in jahre], "#2f7d4f")]),
        ("Ausschüttungsquote", "bar", "%", [("Ausschüttungsquote", [quote.get(j) for j in jahre], "#9fd3b2")]),
        ("Margen: operativ und netto", "line", "%", [("Operative Marge", op_marge, "#4a9aa6"), ("Nettomarge", netto_marge, "#2f7d4f")]),
        ("Zinslast: Zinsaufwand", "bar", "Mrd.", [("Zinsaufwand", reihe(r("zinsaufwand")), "#c0392b")]),
        ("Zinsdeckung (operatives Ergebnis durch Zinsaufwand)", "line", "x", [("Zinsdeckung", zinsdeckung, "#2f7d4f")]),
        ("Eigenkapital, Liquidität und langfristige Schulden", "bar", "Mrd.", [("Eigenkapital", reihe(r("eigenkapital")), "#4a9aa6"), ("Liquide Mittel", reihe(r("liquide_mittel")), "#9fd3b2"), ("Langfristige Schulden", reihe(r("schulden_lang")), "#c0392b")]),
    ]
    out = []
    for titel, typ, einheit, reihen in charts:
        if any(sum(1 for x in vals if x is not None) >= 3 for _, vals, _ in reihen):
            cj, cr, hat = list(jahre), [], False
            for n, vals, c in reihen:
                wert = None
                if prog and PROG_REIHEN.get(n) in prog["werte"]:
                    wert = prog["werte"][PROG_REIHEN[n]]
                if wert is not None:
                    hat = True
                cr.append({"name": n, "werte": list(vals) + [None], "farbe": c, "prog": wert})
            if hat:
                cj = jahre + [str(prog["jahr"])]
                for r_ in cr:
                    if r_["prog"] is not None:
                        r_["werte"][-1] = r_.pop("prog")
                    else:
                        r_.pop("prog")
            else:
                cr = [{"name": r_["name"], "werte": r_["werte"][:-1], "farbe": r_["farbe"]} for r_ in cr]
                cj = jahre
            out.append({"titel": titel, "typ": typ, "einheit": einheit, "jahre": cj, "prognose": hat,
                        "reihen": cr})
    return out


_DIV = None


def dividende_fuer(f):
    """Dividendenteil wie auf den handkuratierten Seiten: nächste Dividende, Historie und Rechner. Nur für Firmen mit SEC-Dividendenhistorie."""
    global _DIV
    if _DIV is None:
        _DIV = (B.lade("data/kurse/xetra-letzter.json"), B.lade("data/kurse/isin-zuordnung.json"),
                B.lade("data/wechselkurse-ezb.json")["je_eur"]["USD"], B.lade("data/dividenden-termine.json").get("firmen", {}))
    (kurse, iz, usd, termine) = _DIV
    sym = f["sym"]
    if sym not in datenquellen()[0]:
        return ""
    reg = [t for t in termine.get(sym, []) if t.get("art") == "regulaer"]
    n = len(reg)
    rhythmus = 12 if n >= 10 else 4 if n >= 3 else 2 if n == 2 else 1 if n == 1 else 4
    cfg = {"sym": sym, "name": f["name"], "slug": f["slug"], "typ": "normal", "rhythmus": rhythmus,
           "satz": "", "alt": [], "serie": {}, "weglassen": []}
    r = B.kennzahlen(cfg, datenquellen()[0], kurse, iz, usd, termine)
    if not r or not r.get("dps"):
        return ""
    return B.dividende_teile(r, f["name"], usd)


def diagramme_html(sym, k, prog=None):
    daten = diagramm_daten(k, prog)
    if not daten:
        return ""
    cfg = json.dumps(daten, ensure_ascii=False).replace("</", "<\\/")
    kacheln = "".join(f'<div class="fbox"><h3>{esc(c["titel"])}</h3><canvas id="fc{i}" height="180" aria-label="{esc(c["titel"])}"></canvas></div>' for i, c in enumerate(daten))
    hinweis = " Graue Balken und gestrichelte Linien zeigen die Prognose des Unternehmens fürs Folgejahr (Mitte der Spanne)." if any(c.get("prognose") for c in daten) else ""
    return (f'<h2>Finanzen im Überblick</h2><p class="meta">Jahreswerte in USD bzw. Landeswährung. Quelle: Jahresberichte.{hinweis}</p>{kacheln}'
            f'<script type="application/json" id="fin-daten">{cfg}</script>'
            '<script src="../../assets/chart.umd.js" defer></script><script src="../../assets/firma-diagramme.js" defer></script>')


def zeile(f, prefix, wert=True):
    v = f["v"]
    def c(x, fmt, vz=False):
        return f'<td class="n" data-v="{x if x is not None else ""}">{fmt(x) if x is not None else "–"}</td>'
    return (f'<tr><td class="fi" data-v="{esc(f["name"])}"><a href="/aktienhub/{f["slug"]}/">{B.logo_span(f["sym"], f["name"], prefix + "../../")}<span class="nm">{esc(f["name"])}</span></a></td>'
            + c(v.get("rendite"), lambda x: B.de(x, 2) + " %") + c(v.get("kgv"), lambda x: B.de(x, 1))
            + c(v.get("ausschuettung"), lambda x: B.de(x, 0) + " %") + "</tr>")


def kopf_tabelle(zeilen, spalten="Aktie"):
    return (B.TAB_CSS + '<div class="tablewrap"><table class="sortable ari-tab">' + B.COLS4 + f'<thead><tr><th class="fi">{spalten}</th><th class="n" data-num="1">Rendite</th>'
            '<th class="n" data-num="1">KGV</th><th class="n" data-num="1" title="Ausschüttungsquote">Quote</th></tr></thead><tbody>'
            + "".join(zeilen) + '</tbody></table></div>')


def seitenrahmen(title, desc, url, h1, crumbs, body, kl, k, fu, tiefe, ld=""):
    pre = "../" * tiefe
    return f'''<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<meta name="robots" content="index,follow,max-snippet:-1,max-image-preview:large">
<link rel="canonical" href="{BASE}{url}">
<meta property="og:type" content="article">
<meta property="og:locale" content="de_DE">
<meta property="og:site_name" content="Dividenden-Rechner Aktien-Hub">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{BASE}{url}">
<meta property="og:image" content="{BASE}assets/og-default.png">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#ffffff">
<link rel="stylesheet" href="{pre}assets/site.css">
{ld}{kl}
</head>
<body>
{k}
<main class="wrap"><article>
<nav class="crumbs" aria-label="Brotkrumen">{crumbs}</nav>
{h1}
{body}
<p class="note"><strong>Hinweis:</strong> Diese Seite dient der allgemeinen Information und ist keine Anlageberatung. Zahlen aus Börsenkursen und Geschäftsberichten, ohne Gewähr.</p>
</article></main>
{fu}
{B.SORT_JS}
</body>
</html>
'''


def firmenseite(f, peers, art, news, kl, k, fu, stand):
    v, name, sym = f["v"], f["name"], f["sym"]
    url = f"aktienhub/{f['slug']}/"
    wkn = B.WKN.get(v.get("isin") or "")
    land = LAND.get(f["land"], f["land"])
    wae = v.get("waehrung") or ""
    rend = v.get("rendite")
    title = f"{name} Aktie: Dividende, Kennzahlen, KGV | Aktien-Hub"
    teile = [f"{name} Aktie: {B.de(rend, 2)} % Dividendenrendite"]
    if v.get("kgv"): teile.append(f"KGV {B.de(v['kgv'], 1)}")
    if v.get("ausschuettung"): teile.append(f"Ausschüttungsquote {B.de(v['ausschuettung'], 0)} %")
    desc = ", ".join(teile) + ". Kennzahlen, Vergleich mit ähnlichen Aktien und News."
    kennung = ", ".join(x for x in (f"ISIN {v['isin']}" if v.get("isin") else "", f"WKN {wkn}" if wkn else "") if x)
    heim = f"aus {land}" if land else ""
    lead = (f"{esc(name)} ist ein börsennotiertes Unternehmen {esc(heim)}" + (f" im Bereich {esc(f['sektor'])}" if f["sektor"] else "") + ". "
            f"Die Aktie schloss am {B.datum(v['datum'])} bei {B.de(v['kurs_eur'])} € ({esc(v.get('boerse') or 'Börse')}). "
            f"Die Dividendenrendite liegt bei {B.de(rend, 2)} %")
    if v.get("dividende"): lead += f", die Dividende je Aktie bei {B.betrag(v['dividende'])} {esc(WAEHR.get(wae, wae))}"
    lead += "."
    zl = []
    def z(label, wert, hinweis=""):
        if wert: zl.append(f'<tr><th scope="row">{label}</th><td class="n" style="white-space:nowrap">{wert}' + (f'<br><small style="color:#5d6b78;white-space:normal">{hinweis}</small>' if hinweis else "") + '</td></tr>')
    p = lambda x, n=1: (B.de(x, n) + " %") if x is not None else None
    n_ = lambda x, n=1: B.de(x, n) if x is not None else None
    z("Kurs", f"{B.de(v['kurs_eur'])} €", f"{esc(v.get('boerse') or '')}, {B.datum(v['datum'])}")
    z("Börsenwert", (mrd(bw(v)) + " €") if bw(v) else None)
    z("Dividendenrendite", p(rend, 2))
    z("Dividende je Aktie", (B.betrag(v["dividende"]) + " " + wae) if v.get("dividende") else None, (f"Geschäftsjahr {esc(v['gj'])}" if v.get("gj") else ""))
    z("Ausschüttungsquote (Gewinn)", p(v.get("ausschuettung"), 0))
    z("Dividendenwachstum 5 Jahre p. a.", p(v.get("div_wachstum_5j")))
    z("Dividendenwachstum 10 Jahre p. a.", p(v.get("div_wachstum_10j")))
    z("KGV", n_(v.get("kgv"))); fw = (v.get("prognose") or {})
    z("Forward KGV", n_((fw or {}).get("kgv_forward")), (f"auf Basis des erwarteten Gewinns {esc(str(fw.get('eps_jahr') or ''))}" if fw.get("kgv_forward") else ""))
    z("KBV", n_(v.get("kbv"))); z("KUV", n_(v.get("kuv")))
    z("KCV", n_(v.get("kcv"))); z("KFCF", n_(v.get("kfcf")))
    z("EV/EBITDA", n_(v.get("ev_ebitda"))); z("PEG", n_(v.get("peg"), 2))
    z("ROIC", p(v.get("roic"))); z("Operative Marge", p(v.get("operative_marge")))
    z("Zinsdeckung", (B.de(v["zinsdeckung"], 1) + " x") if v.get("zinsdeckung") is not None else None)
    z("Nettoschulden zu EBITDA", n_(v.get("nettoschulden_ebitda"), 1))
    z("Umsatzwachstum 5 Jahre p. a.", p(v.get("umsatz_wachstum_5j"))); z("Gewinnwachstum 5 Jahre p. a.", p(v.get("gewinn_wachstum_5j")))
    z("Free-Cashflow-Rendite", p(v.get("fcf_rendite")))
    z("Nettomarge", p(v.get("nettomarge"))); z("Eigenkapitalrendite", p(v.get("roe")))
    z("Umsatz", (mrd(v.get("umsatz_usd")) + " USD") if v.get("umsatz_usd") else None, "in US-Dollar umgerechnet")
    z("Gewinn", (mrd(v.get("gewinn_usd")) + " USD") if v.get("gewinn_usd") else None, "in US-Dollar umgerechnet")
    z("Nettoschulden", (mrd(v.get("nettoschulden_usd")) + " USD") if v.get("nettoschulden_usd") not in (None, 0) else None)
    tab = f'<div class="tablewrap"><table><thead><tr><th>Kennzahl</th><th class="n">Wert</th></tr></thead><tbody>{"".join(zl)}</tbody></table></div>'

    peer_html = ""
    fin_html = diagramme_html(sym, reihen_fuer(sym)[0], prognose_fuer(sym, v, reihen_fuer(sym)[0]))
    div_html = dividende_fuer(f)
    if v.get("ausschuettung") is not None:
        q = v["ausschuettung"]
        satz = (f"Die Dividende ist mit {B.de(q, 0)} % des Gewinns gedeckt." if q < 100
                else f"Die Dividende übersteigt mit {B.de(q, 0)} % den Gewinn und ist damit nicht aus dem Gewinn gedeckt.")
        fin_html = f'<p>{satz}</p>' + fin_html
    teil_html = ('<p class="note" style="font-size:13px">Daten unvollständig, noch auf der Suche.</p>' if f.get("teil") else "")
    if peers:
        zeilen = [zeile(f, "")] + [zeile(g, "") for g in peers]
        if art.startswith("GRUPPE:"):
            peer_html = (f'<h2>Vergleich mit ähnlichen Aktien</h2><p>Vergleichbare Werte aus der Gruppe „{esc(art[7:])}“.</p>' + kopf_tabelle(zeilen))
        else:
            peer_html = (f'<h2>Vergleich mit ähnlichen Aktien</h2><p>Gegenübergestellt sind {len(peers)} Dividendenwerte aus der Gruppe „{esc(art)}“ mit ähnlichem Umsatz. '
                         f'Die Auswahl entsteht automatisch aus Sektor, Land und Größe.</p>' + kopf_tabelle(zeilen))
        peer_html += '<p><a href="../../aktien-hub/vergleich/">Kennzahlen aller Firmen im Vergleich</a></p>'
    news_html = ""
    if news:
        news_html = "<h2>Aktuelle Artikel</h2><ul>" + "".join(f'<li><a href="../../news/{esc(m["slug"])}/">{esc(m["title"])}</a> <span class="meta">({B.datum(m["date"])})</span></li>' for m in news[:6]) + "</ul>"
    faq = [(f"Wie hoch ist die Dividendenrendite der {name}-Aktie?", f"Die Dividendenrendite liegt bei {B.de(rend, 2)} % (Kurs {B.de(v['kurs_eur'])} € am {B.datum(v['datum'])}).")]
    if v.get("dividende"):
        faq.append((f"Wie hoch ist die Dividende je Aktie bei {name}?", f"Zuletzt {B.betrag(v['dividende'])} {WAEHR.get(wae, wae)} je Aktie {('(Geschäftsjahr ' + v['gj'] + ')') if v.get('gj') else ''}."))
    if kennung:
        faq.append((f"Welche WKN und ISIN hat {name}?", f"{kennung}. Börsenkürzel: {sym}."))
    faq_html = "".join(f"<details><summary>{esc(q)}</summary><p>{esc(a)}</p></details>" for q, a in faq)
    ld = [{"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
              {"@type": "ListItem", "position": 1, "name": "Start", "item": BASE}, {"@type": "ListItem", "position": 2, "name": "Dividenden", "item": BASE + "dividende/"},
              {"@type": "ListItem", "position": 3, "name": f"{name} Aktie", "item": BASE + url}]},
          {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]}]
    ld_html = "".join(f'<script type="application/ld+json">{json.dumps(x, ensure_ascii=False)}</script>\n' for x in ld)
    sk = (f'<a href="/dividende/sektor/{SEKTOR_SLUG[f["sektor"]]}/">{esc(f["sektor"])}</a>' if f["sektor"] in SEKTOR_SLUG else "")
    weiter = (f'<aside class="related"><h2>Weiterlesen</h2><ul><li><a href="/dividende/firmen/">Alle Firmen von A bis Z</a></li>'
              + (f'<li><a href="/dividende/land/{f["land"].lower()}/">Dividendenaktien aus {esc(land)}</a></li>' if f["land"] in LAND_MIT_SEITE else "")
              + (f"<li>Sektor: {sk}</li>" if sk else "")
              + '<li><a href="/dividende/aristokraten/">Dividend Kings und Dividendenaristokraten</a></li><li><a href="../../">Dividendenrechner</a></li></ul></aside>')
    nur_test = (f'<div data-nur-test="1" id="fmp-box" data-sym="{esc(sym)}"></div>'
                f'<p data-nur-test="1">Nur Testseite: <a href="../../aktien-hub/?s={esc(sym)}">{esc(name)} im Aktien-Hub</a> (DCF, Analysten, Live-Kurs)</p>'
                '<script src="../../assets/firma-fmp.js" defer></script>')
    body = (f'<p class="meta">Stand: {B.datum(stand)} · Kürzel {esc(sym)}{(" · " + esc(kennung)) if kennung else ""}</p><p class="lead">{lead}</p>{tab}'
            f'{fin_html}{div_html}{nur_test}{peer_html}{news_html}<h2>Häufige Fragen</h2>{faq_html}{teil_html}{weiter}'
            f'<p class="meta">Quellen: Börsenkurse deutscher Handelsplätze, Geschäftsberichte der Unternehmen und Behörden (SEC, ESEF, Börsenaufsichten), Wechselkurse der EZB. Alle Werte stehen so in den Daten; fehlende Werte sind weggelassen.</p>')
    h1 = f'<div class="titlerow" style="gap:12px">{B.logo_span(sym, name, "../../")}<h1>{esc(name)} Aktie</h1></div>'
    crumbs = f'<a href="../../">Start</a> › <a href="/dividende/">Dividenden</a> › <span aria-current="page">{esc(name)}</span>'
    return seitenrahmen(title, desc, url, h1, crumbs, body, kl, k, fu, 2, ld_html), title, desc, url


SEKTOR_SLUG, LAND_MIT_SEITE = {}, set()


def listenseite(titel, desc, url, h1, intro, firmen_, kl, k, fu, tiefe):
    body = f'<p class="lead">{intro}</p>' + kopf_tabelle([zeile(f, "../" * (tiefe - 1)) for f in sorted(firmen_, key=lambda f: f["name"].lower())])
    return body, titel, desc, url


def bauen(vorhanden, reserviert_slugs, news_by_sym, kl2, k2, f2, stand):
    """Rueckgabe: Liste (url, titel, beschreibung) aller neuen Seiten."""
    global SEKTOR_SLUG, LAND_MIT_SEITE
    firmen = lade_firmen(vorhanden)
    vergeben(firmen, reserviert_slugs)
    firmen = [f for f in firmen if not f.get("skip")]
    kl3, k3, f3 = kl2, k2, f2
    nach_sektor, nach_land = {}, {}
    for f in firmen:
        nach_sektor.setdefault((f["sektor"], f["land"]), []).append(f)
        nach_sektor.setdefault((f["sektor"], None), []).append(f)
        nach_land.setdefault(f["land"], []).append(f)
    SEKTOR_SLUG = {s: B_slug(s) for s in {f["sektor"] for f in firmen if f["sektor"]}}
    LAND_MIT_SEITE = {c for c, l in nach_land.items() if len(l) >= 5 and c}
    eintraege = []
    for f in firmen:
        peers, art = peers_fuer(f, firmen, nach_sektor, nach_land)
        sym_n = re.sub(r"\.NE$", "", f["sym"])
        h, t, d, u = firmenseite(f, peers, art, news_by_sym.get(sym_n, []), kl2, k2, f2, stand)
        os.makedirs(os.path.join(ROOT, u), exist_ok=True)
        open(os.path.join(ROOT, u, "index.html"), "w", encoding="utf-8").write(h)
        eintraege.append((u, t, d))
    # Zuordnung Börsenkürzel -> Firmenseite, damit der Aktien-Hub auf die Seite verlinken kann
    slugs = {f["sym"].upper(): f["slug"] for f in firmen}
    slugs.update({k.replace(".", "-"): v for k, v in list(slugs.items())})
    json.dump(slugs, open(os.path.join(ROOT, "data", "firmen-slugs.json"), "w", encoding="utf-8"), ensure_ascii=False, sort_keys=True)
    # Listen
    def schreibe(url, titel, desc, h1, intro, liste, tiefe, crumb):
        body, _, _, _ = listenseite(titel, desc, url, h1, intro, liste, kl2, k2, f2, tiefe)
        pre = "../" * tiefe
        kl, k, fu = (B.rahmen(tiefe))
        crumbs = f'<a href="{pre}">Start</a> › <a href="{pre}dividende/">Dividenden</a> › <span aria-current="page">{crumb}</span>'
        seite = seitenrahmen(titel, desc, url, f"<h1>{h1}</h1>", crumbs, body, kl, k, fu, tiefe)
        os.makedirs(os.path.join(ROOT, url), exist_ok=True)
        open(os.path.join(ROOT, url, "index.html"), "w", encoding="utf-8").write(seite)
        eintraege.append((url, titel, desc))
    buchst = {}
    for f in firmen:
        b = f["name"][:1].upper(); b = b if b.isalpha() and b.isascii() else "0"
        buchst.setdefault(b, []).append(f)
    # A-Z Uebersicht
    nav = "".join(f'<a href="{("0-9" if b == "0" else b.lower())}/" style="padding:6px 10px;border:1px solid #dfe3e8;border-radius:6px;margin:0 6px 6px 0;display:inline-block">{"0–9" if b == "0" else b}</a>' for b in sorted(buchst))
    sek = "".join(f'<li><a href="/dividende/sektor/{s}/">{esc(n)}</a></li>' for n, s in sorted(SEKTOR_SLUG.items()))
    lan = "".join(f'<li><a href="/dividende/land/{c.lower()}/">{esc(LAND[c] if c in LAND else c)}</a> ({len(nach_land[c])})</li>' for c in sorted(LAND_MIT_SEITE, key=lambda c: -len(nach_land[c])))
    body = (f'<p class="lead">{len(firmen)} weitere Dividendenaktien mit Kennzahlen: Rendite, KGV, Ausschüttungsquote und Vergleich mit ähnlichen Werten.</p>'
            f'<p>{nav}</p><h2>Nach Sektor</h2><ul>{sek}</ul><h2>Nach Land</h2><ul>{lan}</ul>')
    kl, k, fu = B.rahmen(3)
    t, d = "Dividendenaktien von A bis Z: Firmen, Sektoren, Länder | Aktien-Hub", f"Dividendenaktien mit Kennzahlen von A bis Z, nach Sektor und Land. {len(firmen)} Firmen mit Rendite, KGV und Peer-Vergleich."
    seite = seitenrahmen(t, d, "dividende/firmen/", "<h1>Dividendenaktien von A bis Z</h1>",
                         '<a href="../../">Start</a> › <a href="../">Dividenden</a> › <span aria-current="page">Firmen A–Z</span>', body, *B.rahmen(2), 2)
    os.makedirs(os.path.join(ROOT, "dividende", "firmen"), exist_ok=True)
    open(os.path.join(ROOT, "dividende", "firmen", "index.html"), "w", encoding="utf-8").write(seite)
    eintraege.append(("dividende/firmen/", t, d))
    for b, l in buchst.items():
        sl = "0-9" if b == "0" else b.lower()
        schreibe(f"dividende/firmen/{sl}/", f"Dividendenaktien mit {'Zahl' if b == '0' else 'Buchstabe ' + b}: Rendite und Kennzahlen | Aktien-Hub",
                 f"{len(l)} Dividendenaktien ({'0–9' if b == '0' else b}) mit Rendite, KGV und Ausschüttungsquote.", f"Dividendenaktien {'0–9' if b == '0' else b}",
                 f"{len(l)} Firmen, sortierbar nach Rendite, KGV und Ausschüttung.", l, 3, f'<a href="../">Firmen A–Z</a> › {"0–9" if b == "0" else b}')
    for s, sl in SEKTOR_SLUG.items():
        l = [f for f in firmen if f["sektor"] == s]
        schreibe(f"dividende/sektor/{sl}/", f"Dividendenaktien {s}: Rendite und Kennzahlen | Aktien-Hub", f"{len(l)} Dividendenaktien aus dem Sektor {s} mit Rendite, KGV und Ausschüttungsquote.",
                 f"Dividendenaktien: {s}", f"{len(l)} Firmen aus dem Bereich {esc(s)}.", l, 3, esc(s))
    for c in LAND_MIT_SEITE:
        l = nach_land[c]; n = LAND.get(c, c)
        schreibe(f"dividende/land/{c.lower()}/", f"Dividendenaktien aus {n}: Rendite und Kennzahlen | Aktien-Hub", f"{len(l)} Dividendenaktien aus {n} mit Rendite, KGV und Ausschüttungsquote.",
                 f"Dividendenaktien aus {n}", f"{len(l)} Firmen aus {esc(n)}.", l, 3, esc(n))
    json.dump({"firmen": [{"sym": f["sym"], "name": f["name"], "slug": f["slug"]} for f in firmen]},
              open(os.path.join(ROOT, "data", "firmenseiten.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    import shutil
    gueltig = {f["slug"] for f in firmen} | set(reserviert_slugs) | RESERVIERT
    for n in os.listdir(os.path.join(ROOT, "dividende")):      # Seiten von Firmen, die es nicht mehr gibt, entfernen
        d = os.path.join(ROOT, "dividende", n)
        if os.path.isdir(d) and n not in gueltig and os.path.exists(os.path.join(d, "index.html")):
            shutil.rmtree(d)
    print(f"{len(firmen)} Firmenseiten, {len(eintraege) - len(firmen)} Listenseiten gebaut")
    return eintraege


def B_slug(s):
    return slugify(s) or "sonstige"
