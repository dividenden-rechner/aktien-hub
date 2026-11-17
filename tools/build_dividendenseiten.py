#!/usr/bin/env python3
"""Baut die öffentlichen Dividendenseiten je Firma:  dividende/<slug>/index.html  und die Übersicht  dividende/index.html.

Daten (nur vorhandene, nichts geschätzt):
  data/dividendenseiten.json       Firmenliste (Name, Slug, Typ, Zahlungsrhythmus, ein Satz Einordnung, alte Adressen)
  data/sec/fundamentals.json       Dividende je Aktie, Gewinn je Aktie, Cashflow usw. (SEC, Geschäftsjahre)
  data/kurse/xetra-letzter.json    letzter Schlusskurs in Euro (über data/kurse/isin-zuordnung.json)
  data/wechselkurse-ezb.json       USD je EUR (EZB)
  data/dividenden-termine.json     zuletzt beschlossene Dividende mit Ex-Tag und Zahltag (falls schon erfasst)
  data/magazin.json                eigene News-Artikel zur Firma (Feld sym)

Danach: Sitemap und llms.txt ergänzen, 301-Weiterleitungen in tools/umzug/redirects-entwurf.csv auf die neuen Seiten setzen.
Aufruf:  python3 tools/build_dividendenseiten.py
"""
import csv, datetime, html, json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "https://dividenden-rechner.github.io/aktien-hub/"   # wird beim Live-Bau durch die echte Domain ersetzt
VORLAGE = os.path.join(ROOT, "grundlagen", "dividendenaristokraten", "index.html")
STEUER_US = 0.2555   # 15 % US-Quellensteuer (W-8BEN) + 10 % deutsche Abgeltungsteuer nach Anrechnung + Soli darauf, ohne Kirchensteuer
MONATE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"]
esc = lambda s: html.escape(str(s), quote=True)


def lade(p):
    return json.load(open(os.path.join(ROOT, p), encoding="utf-8"))


def de(x, n=2):
    s = f"{x:,.{n}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def proz(x, n=1, vz=False):
    if 0 < abs(x) < 0.005: n = 2
    s = de(x * 100, n) + " %"
    return ("+" + s if x > 0 else s) if vz else s


def datum(iso):
    d = datetime.date.fromisoformat(iso[:10])
    return f"{d.day}. {MONATE[d.month - 1]} {d.year}"


def gj_label(iso, dez=True):
    """Geschäftsjahr-Beschriftung: Kalenderjahr bei Abschluss im Dezember, sonst z. B. '2025/26'."""
    d = datetime.date.fromisoformat(iso)
    if d.month == 12: return str(d.year)
    if d.month == 1 and d.day <= 10: return str(d.year - 1)   # Abschluss in den ersten Januartagen = Kalenderjahr davor
    return f"{d.year - 1}/{str(d.year)[2:]}"


def betrag(v):
    """Dividendenbetrag: zwei Nachkommastellen, mehr nur wenn nötig (z. B. 0,0125 oder 2,6305)."""
    return de(v) if abs(round(v, 2) - v) < 1e-9 else de(v, 4).rstrip("0").rstrip(",")


def rahmen(tiefe):
    """Kopf und Fuß der Seite aus einer bestehenden Seite übernehmen, damit Menü und Footer überall gleich sind."""
    v = open(VORLAGE, encoding="utf-8").read()
    head_links = re.search(r'(<link rel="icon".*?<link rel="manifest"[^>]*>)', v, re.S).group(1)
    kopf = re.search(r'(<header id="hub-global-header">.*?</header>\s*<script[^>]*navigation\.js[^>]*></script>\s*<script[^>]*logos\.js[^>]*></script>)', v, re.S).group(1)
    fuss = re.search(r'(<footer class="site-footer">.*?</footer>)', v, re.S).group(1)
    kopf = kopf.replace(' aria-current="page"', "")
    pre = "../" * tiefe
    fix = lambda s: s.replace('"../../', '"' + pre)
    return fix(head_links), fix(kopf), fix(fuss)


RHYTHMUS = {12: "monatlich", 4: "vierteljährlich", 2: "halbjährlich", 1: "jährlich"}
RATE = {12: "Monat", 4: "Quartal", 2: "Halbjahr", 1: "Jahr"}


def reihe(k, key, weg):
    return [(d, v) for d, v in k.get(key, []) if d[:4] not in weg and v is not None]


def wert_am(serie, d):
    for dd, v in serie:
        if dd == d:
            return v
    return None


def kennzahlen(f, sec, kurse, iz, usd_je_eur, termine):
    s = sec.get(f["sym"])
    if not s:
        return None
    k, weg = s["k"], set(f.get("weglassen", []))
    dps = reihe(k, "dividende_je_aktie", weg)
    if not dps:
        return None
    # Wer laut Recherche länger erhöht, als unsere Daten zurückreichen, darf in den Daten nicht sinken:
    # einzelne Ausreißer (falsch zugeordnete Jahreswerte) fallen dann heraus.
    # nur der jüngste lückenlose Block an Geschäftsjahren
    for kk in range(len(dps) - 1, 0, -1):
        if int(dps[kk][0][:4]) - int(dps[kk - 1][0][:4]) > 1:
            dps = dps[kk:]; break
    sj = (f.get("serie") or {}).get("jahre")
    if sj and sj >= len(dps) - 1:
        i = 0
        roh = list(dps)
        while i < len(dps) - 1:
            if dps[i + 1][1] < dps[i][1] * 0.995:
                weg_i = i if i == 0 or dps[i + 1][1] >= dps[i - 1][1] else i + 1
                print(f"  {f['sym']}: Wert {dps[weg_i][0][:4]} ({dps[weg_i][1]}) passt nicht zur Erhöhungsserie, ausgelassen")
                dps.pop(weg_i); i = max(i - 1, 0)
            else:
                i += 1
        if len(roh) - len(dps) > 2:   # zu viele Brüche: Daten passen nicht zur Serie, nichts glätten
            print(f"  {f['sym']}: Reihe passt nicht zur Erhöhungsserie, ungeglättet gelassen")
            dps = roh
    dez = s["gj"][5:7] == "12"
    r = {"f": f, "sec_name": s["n"], "gj": s["gj"], "dez": dez, "dps": dps, "cik": s.get("cik", "")}
    letzt_d, letzt = dps[-1]
    r["dps_letzt"], r["gj_letzt"] = letzt, gj_label(letzt_d, dez)
    # Kurs (Euro) und Rendite
    i = iz.get(f["sym"]) or {}
    isin = (i.get("isin") if isinstance(i, dict) else i) or f.get("isin")
    kz = kurse["k"].get(isin) if isin else None
    r["isin"] = isin
    if kz and kz[0]:
        r["kurs_eur"], r["kurs_waehrung"] = kz[0], kz[2]
        r["kurs_usd"] = kz[0] * usd_je_eur if kz[2] == "EUR" else None
    else:
        r["kurs_eur"] = r["kurs_usd"] = None
    # Wachstum
    vals = [v for _, v in dps]
    r["cagr5"] = (vals[-1] / vals[-6]) ** (1 / 5) - 1 if len(vals) >= 6 and vals[-6] > 0 else None
    r["veraenderung"] = vals[-1] / vals[-2] - 1 if len(vals) >= 2 and vals[-2] > 0 else None
    serie = 0
    for a, b in zip(vals[-2::-1], vals[::-1]):
        if b > a * 1.0005:
            serie += 1
        else:
            break
    r["erhoehungen"] = serie
    r["kuerzung"] = any(b < a * 0.97 for a, b in zip(vals, vals[1:]))
    # Ausschüttungsquoten (letztes Geschäftsjahr)
    eps = wert_am(reihe(k, "eps_verw", weg), letzt_d)
    r["eps"] = eps
    r["quote_gewinn"] = letzt / eps if eps and eps > 0 else None
    # Free-Cashflow-Quote als Durchschnitt der letzten drei Geschäftsjahre (einzelne Jahre schwanken stark, z. B. durch Einmalzahlungen)
    gez_s, ocf_s, cap_s = (dict(reihe(k, n, weg)) for n in ("dividenden_gezahlt", "operativer_cf", "capex"))
    jahre = [d for d, _ in dps[-3:] if d in gez_s and d in ocf_s and d in cap_s]
    sg, sf = sum(gez_s[d] for d in jahre), sum(ocf_s[d] - abs(cap_s[d]) for d in jahre)
    r["quote_fcf"] = sg / sf if len(jahre) == 3 and sf > 0 and sg > 0 and f["typ"] != "bdc" else None
    if f["typ"] == "reit":
        gew, abs_, aktien = (wert_am(reihe(k, n, weg), letzt_d) for n in ("gewinn", "abschreibungen", "aktien_verw"))
        ffo = (gew + abs_) / aktien if gew is not None and abs_ and aktien else None
        r["ffo"] = ffo
        r["quote_ffo"] = letzt / ffo if ffo and ffo > 0 else None
    # zuletzt beschlossene Dividende
    reg = [t for t in termine.get(f["sym"], []) if t.get("art") == "regulaer" and t.get("waehrung", "USD") == "USD"]
    reg.sort(key=lambda t: t.get("meldung") or t.get("ex_tag") or "")
    r["termin"] = reg[-1] if reg else None
    # Jahre mit Dividendenerhöhung in Folge (recherchiert), fortgeschrieben über neue Beschlüsse
    se = dict(f.get("serie") or {})
    r["serie"] = se
    r["serie_jahre"] = se.get("jahre")
    if se.get("betrag") and se.get("zuletzt_erhoeht"):
        hoeher = [t for t in reg if (t.get("meldung") or "")[:4].isdigit() and int(t["meldung"][:4]) > se["zuletzt_erhoeht"]
                  and t["betrag"] > se["betrag"] * 1.0005]
        if hoeher:
            r["serie_jahre"] = (se.get("jahre") or 0) + 1 if se.get("jahre") is not None else None
            r["serie_fortgeschrieben"] = hoeher[0]
    # Dividendenrendite (ab 17.11.2026): zuletzt beschlossene REGULAERE Dividende x Zahlungen pro Jahr.
    # Sonder- und Zusatzdividenden zaehlen nicht mit, sie stehen in einer eigenen Zeile. Reihenfolge der Quellen:
    # 1. Beschluss aus der Pressemitteilung (Termine-Agent), 2. recherchierter Betrag je Zahlung (serie.betrag),
    # 3. Ersatz: Dividende des letzten Geschaeftsjahres (kann Sonderzahlungen enthalten, wird so gekennzeichnet).
    heute = datetime.date.today()
    def frisch(t, tage):
        d = t.get("meldung") or t.get("ex_tag") or ""
        try:
            return (heute - datetime.date.fromisoformat(d[:10])).days <= tage
        except ValueError:
            return False
    if r["termin"] and frisch(r["termin"], 400):
        r["reg_betrag"], r["reg_quelle"] = r["termin"]["betrag"], "beschluss"
    elif se.get("betrag"):
        r["reg_betrag"], r["reg_quelle"] = se["betrag"], "recherche"
    else:
        r["reg_betrag"], r["reg_quelle"] = None, None
    r["dps_jahr"] = r["reg_betrag"] * f["rhythmus"] if r["reg_betrag"] else None
    # Sonderdividenden der letzten 12 Monate: aus den Beschluessen, sonst recherchiert (Feld sonder in der Konfiguration)
    sonder = [t for t in termine.get(f["sym"], []) if t.get("art") == "sonder" and t.get("waehrung", "USD") == "USD" and frisch(t, 365)]
    sk = f.get("sonder") or {}
    if sonder:
        r["sonder_jahr"] = sum(t["betrag"] for t in sonder)
        r["sonder_text"] = "laut Beschlüssen der letzten zwölf Monate"
    elif sk.get("betrag_jahr"):
        r["sonder_jahr"], r["sonder_text"] = sk["betrag_jahr"], sk.get("text", "")
    else:
        r["sonder_jahr"], r["sonder_text"] = None, ""
    k_usd = r["kurs_usd"]
    r["rendite_gj"] = letzt / k_usd if k_usd else None
    if r["dps_jahr"] and k_usd:
        r["rendite"], r["rendite_basis"] = r["dps_jahr"] / k_usd, "aktuell"
    elif r["sonder_jahr"] and k_usd and letzt > r["sonder_jahr"]:
        r["rendite"], r["rendite_basis"] = (letzt - r["sonder_jahr"]) / k_usd, "gj_ohne_sonder"
    else:
        r["rendite"], r["rendite_basis"] = r["rendite_gj"], "gj"
    r["rendite_sonder"] = r["sonder_jahr"] / k_usd if r["sonder_jahr"] and k_usd else None
    # Jahresdividende fuer Rechner und Uebersicht (ohne Sonderzahlungen)
    r["dps_basis"] = r["dps_jahr"] or (letzt - r["sonder_jahr"] if r["rendite_basis"] == "gj_ohne_sonder" else letzt)
    return r


def status(jahre):
    if jahre is None: return ""
    if jahre >= 50: return "Dividend King"
    if jahre >= 25: return "Dividendenaristokrat"
    if jahre >= 10: return "10+ Jahre Dividendenwachstum"
    return ""


def jahre_text(j):
    return f"{j} Jahr" if j == 1 else f"{j} Jahre"


def balken(dps, dez):
    """Schlichtes Balkendiagramm (SVG) der Dividende je Aktie pro Geschäftsjahr."""
    n = len(dps); w, h, pad_l, pad_b, pad_t = 720, 260, 8, 28, 22
    bw = (w - pad_l * 2) / n
    mx = max(v for _, v in dps) or 1
    teile = []
    for i, (d, v) in enumerate(dps):
        bh = (h - pad_b - pad_t) * v / mx
        x = pad_l + i * bw + bw * 0.18; y = h - pad_b - bh
        teile.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw * 0.64:.1f}" height="{bh:.1f}" rx="3" fill="#2f9e5b"/>')
        teile.append(f'<text x="{x + bw * 0.32:.1f}" y="{y - 6:.1f}" text-anchor="middle" font-size="12" fill="#14202b">{betrag(v) if v < 0.1 else de(v, 2)}</text>')
        teile.append(f'<text x="{x + bw * 0.32:.1f}" y="{h - 8}" text-anchor="middle" font-size="12" fill="#5d6b78">{esc(gj_label(d, dez))}</text>')
    return (f'<svg viewBox="0 0 {w} {h}" width="100%" role="img" aria-label="Dividende je Aktie in US-Dollar pro Geschäftsjahr" '
            f'style="max-width:{w}px;display:block;margin:10px 0 4px">{"".join(teile)}</svg>')


def news_links(sym, mag, tiefe):
    its = [m for m in mag if (m.get("sym") or "").upper() == sym][:3]
    pre = "../" * tiefe
    return "".join(f'<li><a href="{pre}news/{esc(m["slug"])}/">{esc(m["title"])}</a></li>' for m in its)



def logo_span(sym, name, prefix):
    """Logo einer Firma wie auf der BDC-Liste: zuerst assets/logos/<kuerzel>.png, sonst assets/logos/hub/<KUERZEL>.png,
    fehlt auch das, holt logos.js das Bild ueber den Zwischenserver nach und zeigt sonst einen Buchstaben."""
    k = sym.lower()
    if os.path.exists(os.path.join(ROOT, "assets", "logos", k + ".png")):
        return f'<span class="arlogo"><img src="{prefix}assets/logos/{k}.png" alt="" width="30" height="30" loading="lazy" data-sym="{esc(sym.upper())}" data-ph="{esc((name or sym)[:1].upper())}"></span>'
    up = sym.upper()
    ph = esc((name or sym)[:1].upper())
    return (f'<span class="arlogo"><img src="{prefix}assets/logos/hub/{esc(up)}.png" alt="" width="30" height="30" loading="lazy" '
            f'data-sym="{esc(up)}" data-ph="{ph}"></span>')

SORT_JS = """<script>(function(){function v(td,num){var d=td.getAttribute('data-v');if(d===null)d=td.textContent.trim();if(!num)return d.toLowerCase();var n=parseFloat(d);return isNaN(n)?-Infinity:n}
document.querySelectorAll('table.sortable').forEach(function(t){var hs=t.tHead?t.tHead.rows[0].cells:[];Array.prototype.forEach.call(hs,function(th,i){th.style.cursor='pointer';th.title='Sortieren';th.setAttribute('tabindex','0');var dir=1;
function go(){var b=t.tBodies[0];var rows=Array.prototype.slice.call(b.rows);var num=th.getAttribute('data-num')==='1';rows.sort(function(x,y){var a=v(x.cells[i],num),c=v(y.cells[i],num);return (a>c?1:a<c?-1:0)*dir});rows.forEach(function(r){b.appendChild(r)});dir=-dir}
th.addEventListener('click',go);th.addEventListener('keydown',function(e){if(e.key==='Enter'||e.key===' '){e.preventDefault();go()}})})})})();</script>"""

TAB_CSS = """<style>.ari-tab{table-layout:fixed;width:100%;font-size:14px;border-collapse:collapse;margin:12px 0 8px}
.ari-tab th,.ari-tab td{padding:8px 4px;border-bottom:1px solid #e5e9ee;text-align:center;white-space:nowrap;vertical-align:middle;font-variant-numeric:tabular-nums}
.ari-tab thead th{font-size:12.5px;font-weight:600;color:#5d6b78;background:#f5f8fa;cursor:pointer;white-space:normal;line-height:1.25;vertical-align:bottom}
.ari-tab th.fi,.ari-tab td.fi{text-align:left}
.ari-tab td.fi a{display:flex;align-items:center;gap:7px;min-width:0;text-decoration:none;color:inherit}
.ari-tab td.fi .nm{min-width:0;overflow:hidden;text-overflow:ellipsis}
.ari-tab .arlogo{flex:0 0 30px;width:30px;height:30px;padding:3px;border-radius:6px}
.ari-tab col.c1{width:44%}.ari-tab col.c2,.ari-tab col.c3,.ari-tab col.c4{width:18.6%}
.ari-tab col.c5{width:18.6%}
.ari-hint{font-size:13px;color:#5d6b78;margin:4px 0 0}</style>"""
COLS4 = '<colgroup><col class="c1"><col class="c2"><col class="c3"><col class="c4"></colgroup>'
COLS6 = '<colgroup><col class="c1"><col class="c2"><col class="c3"><col class="c4"><col class="c5"></colgroup>'

PEER_BLOCKS = {}

def peer_block(sym, cfg_by_sym, gruppen):
    """Querverlinkung je Aktie: Aristokratenliste plus bis zu drei Aktien aus derselben Peer-Gruppe."""
    gr = next((g for g in gruppen if sym in g["members"]), None)
    peers = [m for m in (gr["members"] if gr else []) if m != sym and m in cfg_by_sym][:3]
    items = "".join(f'<li><a href="../{cfg_by_sym[m]["slug"]}/" style="display:flex;align-items:center;gap:10px">{logo_span(m, cfg_by_sym[m]["name"], "../../")}{esc(cfg_by_sym[m]["name"])}</a></li>' for m in peers)
    peer_teil = (f'<p>Aus der Gruppe „{esc(gr["name"])}“ lohnt der Blick auf:</p><ul>{items}</ul>' if peers else "")
    return (f'<h2>Vergleich und Einordnung</h2>{peer_teil}'
            f'<p><a href="../aristokraten/">Alle Dividendenaristokraten und Dividend Kings im Vergleich</a></p>')

def seite(r, kopf_links, kopf, fuss, mag, kurs_datum, sec_stand, usd_je_eur, jahr):
    f = r["f"]; name = f["name"]; url = f"dividende/{f['slug']}/"
    rend = proz(r["rendite"]) if r["rendite"] else None
    title = f"{name} Dividende {jahr}: Rendite, Historie und Termine"
    desc_teile = [f"{name} zahlt aufs Jahr gerechnet eine reguläre Dividende von {de(r['dps_jahr'])} US-Dollar je Aktie" if r["dps_jahr"] else
                  f"{name} zahlte im Geschäftsjahr {r['gj_letzt']} eine Dividende von {de(r['dps_letzt'])} US-Dollar je Aktie"]
    if rend: desc_teile.append(f"die Dividendenrendite liegt bei rund {rend}")
    desc = ", ".join(desc_teile) + ". Historie, Wachstum, Ausschüttungsquote, Termine und Rechner."
    rhythmus = RHYTHMUS.get(f["rhythmus"], "regelmäßig")

    # Einleitung: eine kurze, aus den Zahlen gebaute Einordnung
    sj0 = r["serie_jahre"]
    if f.get("satz"):
        einl = f["satz"]
    elif sj0 and sj0 >= 50:
        einl = f"{name} zählt zu den Dividend Kings: Die Dividende steigt seit {sj0} Jahren in Folge."
    elif sj0 and sj0 >= 25:
        einl = f"{name} gehört zu den Dividendenaristokraten und hat die Dividende {sj0} Jahre in Folge erhöht."
    else:
        einl = f"{name} zahlt {rhythmus} eine Dividende."
    s = [esc(einl)]
    if r["veraenderung"] is not None and len(r["dps"]) >= 2:
        if r["veraenderung"] > 0.0005:
            s.append(f"Im Geschäftsjahr {r['gj_letzt']} stieg die Dividende je Aktie um {proz(r['veraenderung'])} auf {de(r['dps_letzt'])} US-Dollar.")
        elif r["veraenderung"] < -0.0005:
            s.append(f"Im Geschäftsjahr {r['gj_letzt']} sank die Dividende je Aktie um {proz(-r['veraenderung'])} auf {de(r['dps_letzt'])} US-Dollar.")
        else:
            s.append(f"Im Geschäftsjahr {r['gj_letzt']} blieb die Dividende mit {de(r['dps_letzt'])} US-Dollar je Aktie unverändert.")
    if r["cagr5"] is not None:
        s.append(f"Über fünf Jahre wuchs sie im Schnitt um {proz(r['cagr5'])} pro Jahr.")
    lead = " ".join(s)

    # Kennzahlen-Tabelle
    zeilen = []
    if rend:
        if r["rendite_basis"] == "aktuell":
            basis = (f"aktuelle reguläre Dividende ({betrag(r['reg_betrag'])} USD × {f['rhythmus']}) zum Kurs von {de(r['kurs_eur'])} €"
                     if f["rhythmus"] > 1 else f"aktuelle reguläre Dividende ({betrag(r['reg_betrag'])} USD) zum Kurs von {de(r['kurs_eur'])} €")
        elif r["rendite_basis"] == "gj_ohne_sonder":
            basis = f"Dividende des Geschäftsjahres {r['gj_letzt']} ohne Sonderzahlungen zum Kurs von {de(r['kurs_eur'])} €"
        else:
            basis = f"Dividende des Geschäftsjahres {r['gj_letzt']} zum Kurs von {de(r['kurs_eur'])} €"
        zeilen.append(("Dividendenrendite", f"{rend}", basis))
    if r["rendite_sonder"]:
        zeilen.append(("Sonderdividenden (12 Monate)", f"{de(r['sonder_jahr'])} USD",
                       f"zusätzlich rund {proz(r['rendite_sonder'])} Rendite, in der Dividendenrendite nicht enthalten" + (f"; {esc(r['sonder_text'])}" if r["sonder_text"] else "")))
    if r["dps_jahr"]:
        zeilen.append(("Reguläre Dividende je Aktie (aufs Jahr gerechnet)", f"{de(r['dps_jahr'])} USD", f"rund {de(r['dps_jahr'] / usd_je_eur)} €"))
    zeilen.append((f"Dividende je Aktie ({r['gj_letzt']})", f"{de(r['dps_letzt'])} USD",
                   f"rund {de(r['dps_letzt'] / usd_je_eur)} €" + (", einschließlich Sonderzahlungen" if r["sonder_jahr"] else "")))
    if r["veraenderung"] is not None:
        zeilen.append(("Veränderung zum Vorjahr", proz(r["veraenderung"], vz=True), ""))
    if r["cagr5"] is not None:
        zeilen.append(("Dividendenwachstum (5 Jahre, pro Jahr)", proz(r["cagr5"], vz=True), ""))
    se, sj = r["serie"], r["serie_jahre"]
    if se:
        wert = jahre_text(sj) if sj is not None else "nie gesenkt"
        if sj == 0: wert = "keine"
        st = status(sj)
        zeilen.append(("Dividendenerhöhungen in Folge" + (f" ({st})" if st else ""), wert, esc(se.get("text", ""))))
    if f["typ"] == "reit" and r.get("quote_ffo"):
        zeilen.append(("Ausschüttungsquote (auf FFO)", proz(r["quote_ffo"], 0), "FFO genähert: Gewinn plus Abschreibungen je Aktie"))
    elif f["typ"] == "bdc" and r["quote_gewinn"]:
        zeilen.append(("Ausschüttungsquote (auf Gewinn je Aktie)", proz(r["quote_gewinn"], 0), "bei BDCs schwankt der Gewinn mit den Bewertungen, wichtiger ist das NII"))
    elif r["quote_gewinn"]:
        zeilen.append(("Ausschüttungsquote (auf Gewinn)", proz(r["quote_gewinn"], 0), ""))
    elif r["eps"] is not None and r["eps"] <= 0:
        zeilen.append(("Ausschüttungsquote (auf Gewinn)", "nicht aussagekräftig", "Verlust im letzten Geschäftsjahr"))
    if r["quote_fcf"] and f["typ"] != "reit":
        if r["quote_fcf"] > 1:
            # Über 100 %: meist verzerrt durch Firmenkäufe, Steuer- oder andere Einmalzahlungen, die den Free Cashflow drücken
            wert = "über 300&nbsp;%*" if r["quote_fcf"] > 3 else proz(r["quote_fcf"], 0) + "*"
            zeilen.append(("Ausschüttungsquote (auf Free Cashflow)", wert,
                           "Durchschnitt der letzten drei Geschäftsjahre<br>* Über 100&nbsp;% deutet oft auf Sondereffekte hin: Zahlungen für zugekaufte Firmen, "
                           "Steuernachzahlungen oder andere Einmalzahlungen drücken den Free Cashflow einzelner Jahre. Die laufende Deckung ist dann meist besser, als die Quote zeigt."))
        else:
            zeilen.append(("Ausschüttungsquote (auf Free Cashflow)", proz(r["quote_fcf"], 0), "Durchschnitt der letzten drei Geschäftsjahre"))
    zeilen.append(("Zahlweise", rhythmus, ""))
    tab = "".join(f'<tr><td>{esc(a)}' + (f'<br><span style="font-size:13px;color:var(--mut)">{c}</span>' if c else "") +
                  f'</td><td class="n" style="white-space:nowrap"><strong>{b}</strong></td></tr>' for a, b, c in zeilen)

    # Termine
    t = r["termin"]
    if t:
        termin_html = ('<div class="tablewrap"><table><thead><tr><th>Beschlossen am</th><th class="n">Betrag</th><th>Ex-Tag</th><th>Zahltag</th></tr></thead><tbody>'
                       f'<tr><td>{datum(t["meldung"]) if t.get("meldung") else "–"}</td><td class="n">{betrag(t["betrag"])} USD</td>'
                       f'<td>{datum(t["ex_tag"]) if t.get("ex_tag") else "–"}</td><td>{datum(t["zahltag"]) if t.get("zahltag") else "–"}</td></tr></tbody></table></div>'
                       '<p class="meta">Wer die Aktie spätestens am Handelstag vor dem Ex-Tag kauft, erhält die Dividende. In den USA sind Ex-Tag und Stichtag seit Mai 2024 identisch.</p>')
    else:
        termin_html = (f'<p>{esc(name)} zahlt {rhythmus}. Die nächste beschlossene Dividende mit Ex-Tag und Zahltag tragen wir hier ein, sobald das Unternehmen sie veröffentlicht.</p>')

    # Historie-Tabelle
    hist_zeilen = []
    for i in range(len(r["dps"]) - 1, -1, -1):
        d, v = r["dps"][i]
        vor = r["dps"][i - 1][1] if i > 0 else None
        hist_zeilen.append(f'<tr><td>{esc(gj_label(d))}</td><td class="n">{betrag(v)}</td>'
                           f'<td class="n">{proz(v / vor - 1, vz=True) if vor else "–"}</td></tr>')
    hist = "".join(hist_zeilen)

    quote_text = ""
    qg, qf = r["quote_gewinn"], r["quote_fcf"]
    if f["typ"] == "normal" and qg and qf:
        if qg > 1 and qf <= 1:
            quote_text = (f'<p>Die Ausschüttungsquote auf den Gewinn liegt über 100&nbsp;%, die auf den Free Cashflow darunter. Der Buchgewinn war zuletzt '
                          f'also niedriger als der erwirtschaftete Cashflow, etwa durch Abschreibungen oder Sondereffekte. Aus dem Cashflow war die Dividende gedeckt.</p>')
        elif qf > 1 and qg <= 1:
            quote_text = (f'<p>Der Gewinn deckt die Dividende, der freie Cashflow der letzten drei Jahre reichte dafür aber nicht ganz. '
                          f'Das kann an hohen Investitionen oder Einmalzahlungen liegen. Dauerhaft muss eine Dividende aus dem Cashflow bezahlt werden.</p>')
        elif qf > 1 and qg > 1:
            quote_text = '<p>Sowohl Gewinn als auch freier Cashflow lagen zuletzt unter der gezahlten Dividende. Die Differenz wurde aus Reserven oder Schulden bezahlt, das ist auf Dauer nicht tragfähig.</p>'
    typ_hinweis = ""
    if f["typ"] == "reit":
        typ_hinweis = f'<p>Bei REITs sagt die Quote auf den Gewinn wenig, weil hohe Abschreibungen den Gewinn drücken. Aussagekräftiger ist die Quote auf FFO, siehe <a href="../../fortgeschrittene/reits-bewerten/">REITs bewerten</a>.</p>'
    elif f["typ"] == "bdc":
        typ_hinweis = f'<p>BDCs müssen den Großteil ihrer Erträge ausschütten. Ob die Dividende gedeckt ist, zeigt der Vergleich mit dem Nettoertrag aus Zinsen (NII), siehe <a href="../../fortgeschrittene/bdcs-bewerten/">BDCs bewerten</a>.</p>'
    if r["sonder_jahr"]:
        typ_hinweis += "<p>Die Jahreswerte in der Historie enthalten neben der regulären Dividende auch die Sonderdividenden. Die Dividendenrendite oben rechnet nur mit der regulären Dividende.</p>"

    news = news_links(f["sym"], mag, 2)
    news_html = f'<h2>Aktuelle Meldungen zu {esc(name)}</h2><ul>{news}</ul>' if news else ""

    kurs_d = datum(kurs_datum) if kurs_datum else ""
    rechner = f'''<h2>Was bringt die {esc(name)}-Aktie im Jahr?</h2>
<div class="calc" id="divcalc" data-dps="{r['dps_basis']}" data-fx="{usd_je_eur}" data-kurs="{r['kurs_eur'] or ''}" data-steuer="{STEUER_US}">
<div class="grid"><div><label for="anz">Anzahl Aktien</label><input id="anz" type="number" min="0" step="1" value="100" inputmode="numeric"></div>
<div><label for="betr">oder Anlagebetrag in Euro <span class="hint">(zum letzten Kurs)</span></label><input id="betr" type="number" min="0" step="100" inputmode="decimal" placeholder="z. B. 5000"></div></div>
<div class="tablewrap"><table><tbody>
<tr><td>Dividende brutto pro Jahr</td><td class="n"><strong id="r-brutto">–</strong></td></tr>
<tr><td>nach Steuern (ca.)</td><td class="n"><strong id="r-netto">–</strong></td></tr>
<tr><td>pro {RATE.get(f["rhythmus"], "Zahlung")} (brutto)</td><td class="n"><strong id="r-rate">–</strong></td></tr>
</tbody></table></div>
<p class="meta">Grundlage: {"aktuelle reguläre Dividende aufs Jahr gerechnet" if r["dps_jahr"] else "Dividende des Geschäftsjahres " + r["gj_letzt"] + (" ohne Sonderzahlungen" if r["rendite_basis"] == "gj_ohne_sonder" else "")} ({de(r['dps_basis'])} USD je Aktie{", ohne Sonderdividenden" if r["sonder_jahr"] else ""}), umgerechnet zum EZB-Kurs ({de(usd_je_eur, 4)} USD je Euro). Nach Steuern: 15&nbsp;% US-Quellensteuer mit W-8BEN plus Abgeltungsteuer und Soli in Deutschland, zusammen rund 25,6&nbsp;%, ohne Kirchensteuer und ohne Sparer-Pauschbetrag.</p>
</div>
<script>(function(){{var c=document.getElementById("divcalc");if(!c)return;var dps=+c.dataset.dps,fx=+c.dataset.fx,k=+c.dataset.kurs,st=+c.dataset.steuer,per={f["rhythmus"]};
var a=document.getElementById("anz"),b=document.getElementById("betr");function e(x){{return x.toLocaleString("de-DE",{{minimumFractionDigits:2,maximumFractionDigits:2}})+"\\u00a0€"}}
function r(){{var n=+a.value||0,g=n*dps/fx;document.getElementById("r-brutto").textContent=e(g);document.getElementById("r-netto").textContent=e(g*(1-st));document.getElementById("r-rate").textContent=e(g/per)}}
a.addEventListener("input",function(){{b.value="";r()}});b.addEventListener("input",function(){{if(k>0){{a.value=Math.floor((+b.value||0)/k)}}r()}});r()}})();</script>'''

    faq = []
    faq.append((f"Wie hoch ist die Dividende von {name}?",
                (f"Die reguläre Dividende liegt aufs Jahr gerechnet bei {de(r['dps_jahr'])} US-Dollar je Aktie" if r["dps_jahr"] else
                 f"Im Geschäftsjahr {r['gj_letzt']} zahlte {name} {de(r['dps_letzt'])} US-Dollar je Aktie")
                + (f", das entspricht beim aktuellen Kurs einer Rendite von rund {rend}." if rend else ".")
                + (f" Dazu kamen in den letzten zwölf Monaten Sonderdividenden von {de(r['sonder_jahr'])} US-Dollar." if r["sonder_jahr"] else "")))
    if t:
        faq.append((f"Wann zahlt {name} die nächste Dividende?",
                    f"Zuletzt wurden {betrag(t['betrag'])} US-Dollar je Aktie beschlossen" + (f", Ex-Tag ist der {datum(t['ex_tag'])}" if t.get("ex_tag") else "") + (f", ausgezahlt wird am {datum(t['zahltag'])}." if t.get("zahltag") else ".")))
    else:
        faq.append((f"Wie oft zahlt {name} Dividende?", f"{name} zahlt die Dividende {rhythmus}."))
    faq.append((f"Wie wird die {name}-Dividende in Deutschland besteuert?",
                "In den USA werden mit dem Formular W-8BEN 15 % Quellensteuer einbehalten. Diese wird auf die deutsche Abgeltungsteuer angerechnet, sodass in Deutschland noch rund 10 % plus Solidaritätszuschlag anfallen."))
    if se and sj:
        faq.insert(1, (f"Seit wie vielen Jahren erhöht {name} die Dividende?",
                       f"{name} hat die Dividende {jahre_text(sj)} in Folge erhöht" + (" und zählt damit zu den Dividend Kings." if sj >= 50 else " und zählt damit zu den Dividendenaristokraten." if sj >= 25 else ".")))
    elif se and sj == 0:
        faq.insert(1, (f"Erhöht {name} die Dividende jedes Jahr?", se.get("text", "")))
    faq_html = "".join(f"<details><summary>{esc(q)}</summary><p>{esc(a)}</p></details>" for q, a in faq)

    ld = [
        {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Start", "item": BASE},
            {"@type": "ListItem", "position": 2, "name": "Dividenden", "item": BASE + "dividende/"},
            {"@type": "ListItem", "position": 3, "name": f"{name} Dividende", "item": BASE + url}]},
        {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]},
    ]
    ld_html = "".join(f'<script type="application/ld+json">{json.dumps(x, ensure_ascii=False)}</script>\n' for x in ld)
    serie_quelle_html = ""
    if se and not se.get("quelle") and se.get("quelle_text"):
        serie_quelle_html = f'<li>Dividendenerhöhungen in Folge: {esc(se["quelle_text"])} (Stand {datum(se["stand"]) if se.get("stand") else "–"})</li>'
    if se and se.get("quelle"):
        dom = re.sub(r"^https?://(www\.)?", "", se["quelle"]).split("/")[0]
        serie_quelle_html = (f'<li>Dividendenerhöhungen in Folge: <a href="{esc(se["quelle"])}" rel="nofollow noopener" target="_blank">{esc(dom)}</a>'
                             f' (Stand {datum(se["stand"]) if se.get("stand") else "–"})</li>')
    heute = datetime.date.today().isoformat()
    logo = logo_span(f["sym"], name, "../../")

    return f'''<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<meta name="robots" content="index,follow,max-snippet:-1,max-image-preview:large">
<link rel="canonical" href="{BASE}{url}">
<meta property="og:type" content="website">
<meta property="og:locale" content="de_DE">
<meta property="og:site_name" content="Dividenden-Rechner Aktien-Hub">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{BASE}{url}">
<meta property="og:image" content="{BASE}assets/og-default.png">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#ffffff">
<link rel="stylesheet" href="../../assets/site.css">
{ld_html}{kopf_links}
</head>
<body>
{kopf}
<main class="wrap"><article>
<nav class="crumbs" aria-label="Brotkrumen"><a href="../../">Start</a> › <a href="../">Dividenden</a> › <span aria-current="page">{esc(name)}</span></nav>
<div class="titlerow" style="gap:12px">{logo}<h1>{esc(name)} Dividende</h1></div>
<p class="meta">Stand: {datum(heute)} · Kurs vom {kurs_d} · Kürzel {esc(f["sym"])}{" · ISIN " + esc(r["isin"]) if r.get("isin") else ""}</p>
<p class="lead">{lead}</p>
<div class="tablewrap"><table><tbody>{tab}</tbody></table></div>
{quote_text}
<h2>Nächste Dividende</h2>
{termin_html}
<h2>Dividendenhistorie</h2>
<p>Dividende je Aktie in US-Dollar pro Geschäftsjahr, wie im Geschäftsbericht ausgewiesen.</p>
{balken(r["dps"], r["dez"])}
<div class="tablewrap"><table><thead><tr><th>Geschäftsjahr</th><th class="n">Dividende je Aktie (USD)</th><th class="n">Veränderung</th></tr></thead><tbody>{hist}</tbody></table></div>
{typ_hinweis}
{rechner}
{news_html}
<h2>Häufige Fragen</h2>
{faq_html}
{PEER_BLOCKS.get(f["sym"], "")}
<aside class="related"><h2>Weiterlesen</h2><ul>
<li><a href="../">Weitere US-Dividendenaktien im Überblick</a></li>
<li><a href="../aristokraten/">Liste: Dividend Kings und Dividendenaristokraten</a></li>
<li><a href="../../grundlagen/dividendenaristokraten/">Was Dividendenaristokraten und Dividend Kings sind</a></li>
<li><a href="../../fortgeschrittene/quellensteuer/usa/">USA: Quellensteuer und W-8BEN</a></li>
<li><a href="../../">Dividendenrechner: Wie wächst dein Depot?</a></li>
</ul></aside>
<details style="margin:18px 0 0"><summary style="font-size:14px;color:var(--accd);cursor:pointer;list-style:none">Quellen</summary>
<ul style="font-size:14px;margin-top:8px">
<li>Dividende je Aktie, Gewinn und Cashflow: Geschäftsberichte bei der SEC (<a href="https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&amp;CIK={r['cik']}&amp;type=10-K" rel="nofollow noopener" target="_blank">EDGAR</a>)</li>
<li>Kurs: Schlusskurs deutscher Börsenplätze vom {kurs_d}, Wechselkurs: EZB-Referenzkurs</li>
{serie_quelle_html}
</ul></details>
<p class="note"><strong>Hinweis:</strong> Diese Seite dient der allgemeinen Information und ist keine Anlageberatung. Die Zahlen stammen aus den Geschäftsberichten (SEC) und Börsenkursen, sie werden täglich aktualisiert. Vergangene Dividenden sind keine Garantie für künftige Zahlungen. Datenstand Fundamentaldaten: {datum(sec_stand)}.</p>
</article></main>
{fuss}
{SORT_JS}
</body>
</html>
''', title, desc, url


def uebersicht(rs, kopf_links, kopf, fuss, jahr):
    zeilen = []
    for r in sorted(rs, key=lambda r: -(r["rendite"] or 0)):
        f = r["f"]
        zeilen.append(f'<tr><td class="fi" data-v="{esc(f["name"])}"><a href="{f["slug"]}/">{logo_span(f["sym"], f["name"], "../")}<span class="nm">{esc(f["name"])}</span></a></td>'
                      f'<td class="n" data-v="{r["rendite"] or ""}">{proz(r["rendite"]) if r["rendite"] else "–"}</td>'
                      f'<td class="n" data-v="{r["dps_basis"]}">{de(r["dps_basis"])}</td>'
                      f'<td class="n" data-v="{r["cagr5"] if r["cagr5"] is not None else ""}">{proz(r["cagr5"], vz=True) if r["cagr5"] is not None else "–"}</td>'
                      f'<td class="n" data-v="{r["serie_jahre"] if r["serie_jahre"] is not None else ""}">{r["serie_jahre"] if r["serie_jahre"] is not None else "–"}</td>'
                      f'<td data-v="{RHYTHMUS.get(f["rhythmus"], "")}">{RHYTHMUS.get(f["rhythmus"], "–")}</td></tr>')
    title = f"US-Dividendenaktien {jahr}: Rendite, Historie und Termine"
    desc = "Dividendenrendite, Dividende je Aktie, Wachstum und Zahlweise bekannter US-Dividendenaktien wie Coca-Cola, Realty Income, PepsiCo und Altria, täglich aktualisiert."
    return f'''<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<meta name="robots" content="index,follow,max-snippet:-1,max-image-preview:large">
<link rel="canonical" href="{BASE}dividende/">
<meta property="og:type" content="website">
<meta property="og:locale" content="de_DE">
<meta property="og:site_name" content="Dividenden-Rechner Aktien-Hub">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{BASE}dividende/">
<meta property="og:image" content="{BASE}assets/og-default.png">
<meta name="theme-color" content="#ffffff">
<link rel="stylesheet" href="../assets/site.css">
{kopf_links}
</head>
<body>
{kopf}
<main class="wrap"><article>
<nav class="crumbs" aria-label="Brotkrumen"><a href="../">Start</a> › <span aria-current="page">Dividenden</span></nav>
<h1>US-Dividendenaktien im Überblick</h1>
<p class="lead">Eine Auswahl der beliebtesten US-Dividendenaktien mit Rendite, letzter Jahresdividende und Wachstum über fünf Jahre. Ein Klick auf den Namen führt zur ausführlichen Seite mit Historie, Terminen und Rechner.</p>
{TAB_CSS}
<div class="tablewrap"><table class="sortable ari-tab">{COLS6}<thead><tr><th class="fi">Aktie</th><th class="n" data-num="1">Rendite</th><th class="n" data-num="1">Dividende je Aktie (USD)</th><th class="n" data-num="1">Wachstum 5 J. p. a.</th><th class="n" data-num="1">Erhöhungen in Folge (Jahre)</th><th>Zahlweise</th></tr></thead><tbody>
{"".join(zeilen)}
</tbody></table></div>
<p>Welche dieser Werte ihre Dividende seit mindestens 25 oder 50 Jahren erhöhen, zeigt die <a href="aristokraten/">Liste der Dividend Kings und Dividendenaristokraten</a>.</p>
<p class="meta">Rendite und Dividende: aktuelle reguläre Dividende aufs Jahr gerechnet, wo noch kein Beschluss vorliegt die Dividende des letzten Geschäftsjahres; jeweils ohne Sonderdividenden, zum letzten Börsenkurs in Euro. Sortiert nach Rendite. Stand: {datum(datetime.date.today().isoformat())}.</p>
<p class="note"><strong>Hinweis:</strong> Diese Übersicht dient der allgemeinen Information und ist keine Anlageberatung. Eine hohe Rendite kann auch ein Warnsignal sein, siehe <a href="../grundlagen/dividendenfalle/">Dividendenfalle erkennen</a>.</p>
</article></main>
{fuss}
{SORT_JS}
</body>
</html>
''', title, desc


def aristokraten(rs, kopf_links, kopf, fuss, jahr):
    """Liste der Werte nach Jahren mit Dividendenerhöhung in Folge (nur recherchierte Zahlen)."""
    gruppen = [("Dividend Kings: 50 Jahre und mehr", 50, 999), ("Dividendenaristokraten: 25 bis 49 Jahre", 25, 49),
               ("Auf dem Weg: 10 bis 24 Jahre", 10, 24)]
    teile = []
    for titel, lo, hi in gruppen:
        g = sorted([r for r in rs if r["serie_jahre"] is not None and lo <= r["serie_jahre"] <= hi], key=lambda r: -r["serie_jahre"])
        if not g: continue
        z = "".join(f'<tr><td class="fi" data-v="{esc(r["f"]["name"])}"><a href="../{r["f"]["slug"]}/">{logo_span(r["f"]["sym"], r["f"]["name"], "../../")}<span class="nm">{esc(r["f"]["name"])}</span></a></td>'
                    f'<td class="n" data-v="{r["serie_jahre"]}"><strong>{r["serie_jahre"]}</strong></td>'
                    f'<td class="n" data-v="{r["rendite"] or ""}">{proz(r["rendite"]) if r["rendite"] else "–"}</td>'
                    f'<td class="n" data-v="{r["cagr5"] if r["cagr5"] is not None else ""}">{proz(r["cagr5"], vz=True) if r["cagr5"] is not None else "–"}</td></tr>'
                    for r in g)
        teile.append(f'<h2>{esc(titel)}</h2><div class="tablewrap"><table class="sortable ari-tab">{COLS4}<thead><tr><th class="fi">Aktie</th><th class="n" data-num="1">Jahre in Folge</th>'
                     f'<th class="n" data-num="1">Rendite</th><th class="n" data-num="1">Wachstum 5 J. p. a.</th></tr></thead><tbody>{z}</tbody></table></div>')
    n_king = sum(1 for r in rs if (r["serie_jahre"] or 0) >= 50); n_ari = sum(1 for r in rs if 25 <= (r["serie_jahre"] or 0) < 50)
    ohne = sorted([r for r in rs if r["serie_jahre"] is not None and r["serie_jahre"] < 10], key=lambda r: -r["serie_jahre"])
    ohne_html = ""
    if ohne:
        ohne_html = ('<h2>Ohne lange Erhöhungsserie</h2><p>Diese Werte zahlen Dividende, haben sie aber nur kurz oder zuletzt gar nicht erhöht: '
                     + ", ".join(f'<a href="../{r["f"]["slug"]}/">{esc(r["f"]["name"])}</a>' for r in ohne) + ".</p>")
    title = f"Dividend Kings und Dividendenaristokraten {jahr}: Liste mit Rendite"
    desc = (f"Welche US-Aktien ihre Dividende seit 25 oder 50 Jahren in Folge erhöhen: Procter & Gamble, Coca-Cola, Johnson & Johnson, PepsiCo und weitere, "
            f"mit Rendite und Dividendenwachstum. Täglich aktualisiert.")
    return f'''<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<meta name="robots" content="index,follow,max-snippet:-1,max-image-preview:large">
<link rel="canonical" href="{BASE}dividende/aristokraten/">
<meta property="og:type" content="website">
<meta property="og:locale" content="de_DE">
<meta property="og:site_name" content="Dividenden-Rechner Aktien-Hub">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{BASE}dividende/aristokraten/">
<meta property="og:image" content="{BASE}assets/og-default.png">
<meta name="theme-color" content="#ffffff">
<link rel="stylesheet" href="../../assets/site.css">
{kopf_links}
</head>
<body>
{kopf}
<main class="wrap"><article>
<nav class="crumbs" aria-label="Brotkrumen"><a href="../../">Start</a> › <a href="../">Dividenden</a> › <span aria-current="page">Dividend Kings und Aristokraten</span></nav>
<h1>Dividend Kings und Dividendenaristokraten</h1>
<p class="lead">Wer seine Dividende über Jahrzehnte jedes Jahr erhöht, hat Rezessionen, Zinswenden und Krisen überstanden, ohne die Ausschüttung anzutasten. Unter den Werten, zu denen wir eigene Dividendenseiten führen, sind derzeit {n_king} Dividend Kings mit mindestens 50 Erhöhungen in Folge und {n_ari} weitere mit mindestens 25 Jahren.</p>
{TAB_CSS}<p class="ari-hint">Eine Auswahl der beliebtesten Dividendenwerte, keine vollständige Liste aller Dividendenaristokraten. Ein Klick auf eine Spalte sortiert die Tabelle.</p>
{"".join(teile)}
{ohne_html}
<p class="meta">Jahre in Folge: recherchiert aus Angaben der Unternehmen und von S&amp;P Dow Jones Indices, fortgeschrieben mit jeder neuen Erhöhung. Rendite: aktuelle reguläre Dividende aufs Jahr gerechnet (sonst die des letzten Geschäftsjahres), ohne Sonderdividenden, zum letzten Börsenkurs in Euro. Die Liste wächst mit jeder neuen Firmenseite. Stand: {datum(datetime.date.today().isoformat())}.</p>
<p>Offiziell sind Dividendenaristokraten Mitglieder des S&amp;P 500 Dividend Aristocrats Index. Dafür zählen neben den 25 Jahren auch Größe und Handelsvolumen. Was hinter den Begriffen steckt und worauf du achten solltest, erklärt der Beitrag <a href="../../grundlagen/dividendenaristokraten/">Dividendenaristokraten, Dividend Kings und Champions</a>.</p>
<p class="note"><strong>Hinweis:</strong> Diese Liste dient der allgemeinen Information und ist keine Anlageberatung. Eine lange Erhöhungsserie ist keine Garantie für künftige Dividenden.</p>
</article></main>
{fuss}
{SORT_JS}
</body>
</html>
''', title, desc


def sitemap_llms(eintraege):
    f = os.path.join(ROOT, "sitemap.xml"); s = open(f, encoding="utf-8").read()
    s = re.sub(r"<url><loc>" + re.escape(BASE) + r"dividende/[^<]*</loc>.*?</url>\n?", "", s)
    heute = datetime.date.today().isoformat()
    add = "".join(f"<url><loc>{BASE}{u}</loc><lastmod>{heute}</lastmod><priority>{'0.8' if u == 'dividende/' else '0.7'}</priority></url>\n" for u, _, _ in eintraege)
    open(f, "w", encoding="utf-8").write(s.replace("</urlset>", add + "</urlset>"))
    f = os.path.join(ROOT, "llms.txt"); s = open(f, encoding="utf-8").read()
    s = re.sub(r"- \[[^\]]*\]\(" + re.escape(BASE) + r"dividende/[^)]*\)[^\n]*\n", "", s)
    add = "".join(f"- [{t}]({BASE}{u}): {d}\n" for u, t, d in eintraege)
    s = s.replace("\n## Hinweis", "\n" + add + "\n## Hinweis", 1) if "\n## Hinweis" in s else s.rstrip("\n") + "\n" + add
    open(f, "w", encoding="utf-8").write(s)


def weiterleitungen(rs):
    """Alte Google-Sites-Adressen der Firmen auf die neuen Dividendenseiten umbiegen."""
    p = os.path.join(ROOT, "tools", "umzug", "redirects-entwurf.csv")
    rows = list(csv.DictReader(open(p, encoding="utf-8")))
    felder = list(rows[0].keys())
    ziel = {a.lower(): f"/dividende/{r['f']['slug']}/" for r in rs for a in r["f"].get("alt", [])}
    for row in rows:
        z = ziel.get(row["alter_pfad"].strip().rstrip("/").lower())
        if z:
            row["neuer_pfad"], row["status"] = z, "301 (Dividendenseite der Firma)"
    nl = "\r\n" if b"\r\n" in open(p, "rb").read(200) else "\n"
    w = csv.DictWriter(open(p, "w", encoding="utf-8", newline=""), fieldnames=felder, lineterminator=nl)
    w.writeheader(); w.writerows(rows)


def main():
    cfg = lade("data/dividendenseiten.json")["firmen"]
    secj = lade("data/sec/fundamentals.json"); sec = secj["firmen"]
    kurse = lade("data/kurse/xetra-letzter.json"); iz = lade("data/kurse/isin-zuordnung.json")
    usd_je_eur = lade("data/wechselkurse-ezb.json")["je_eur"]["USD"]
    termine = lade("data/dividenden-termine.json").get("firmen", {})
    mag = sorted(lade("data/magazin.json").get("items", []), key=lambda m: m.get("date", ""), reverse=True)
    jahr = datetime.date.today().year
    kl1, k1, f1 = rahmen(2); kl0, k0, f0 = rahmen(1)
    rs, eintraege = [], []
    cfg_by_sym = {f["sym"]: f for f in cfg}
    gruppen = lade("data/dividende-peers.json")["gruppen"]
    PEER_BLOCKS.clear()
    for f in cfg:
        PEER_BLOCKS[f["sym"]] = peer_block(f["sym"], cfg_by_sym, gruppen)
    for f in cfg:
        r = kennzahlen(f, sec, kurse, iz, usd_je_eur, termine)
        if not r:
            print("übersprungen (keine Daten):", f["sym"]); continue
        h, t, d, u = *seite(r, kl1, k1, f1, mag, kurse.get("datum"), secj.get("stand", ""), usd_je_eur, jahr),
        os.makedirs(os.path.join(ROOT, u), exist_ok=True)
        open(os.path.join(ROOT, u, "index.html"), "w", encoding="utf-8").write(h)
        rs.append(r); eintraege.append((u, t, d))
    h, t, d = uebersicht(rs, kl0, k0, f0, jahr)
    open(os.path.join(ROOT, "dividende", "index.html"), "w", encoding="utf-8").write(h)
    eintraege.insert(0, ("dividende/", t, d))
    h, t, d = aristokraten(rs, kl1, k1, f1, jahr)
    os.makedirs(os.path.join(ROOT, "dividende", "aristokraten"), exist_ok=True)
    open(os.path.join(ROOT, "dividende", "aristokraten", "index.html"), "w", encoding="utf-8").write(h)
    eintraege.insert(1, ("dividende/aristokraten/", t, d))
    sitemap_llms(eintraege)
    weiterleitungen(rs)
    print(f"{len(rs)} Dividendenseiten gebaut")


if __name__ == "__main__":
    main()
