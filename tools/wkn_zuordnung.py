#!/usr/bin/env python3
"""WKN je ISIN (ab 17.11.2026) aus den kostenlosen Listen "All tradable instruments" der Deutschen Börse
(Xetra und Börse Frankfurt, CSV mit Semikolon, Spalten u. a. ISIN und WKN). US-Werte stehen meist nur in der Frankfurter Liste.
Schreibt data/kurse/wkn.json ({"stand", "quelle", "k": {ISIN: WKN}}), nur für ISINs, die wir kennen
(data/kurse/isin-zuordnung.json, data/dividendenseiten.json). Die Adressen der CSV-Dateien wechseln gelegentlich,
deshalb werden zuerst die festen Kurzadressen und danach die Downloadseiten nach CSV-Links durchsucht."""
import csv, io, json, re, sys, urllib.request
from datetime import date

UA = {"User-Agent": "Mozilla/5.0 (dividenden-rechner.de WKN-Zuordnung)"}
FEST = ["https://www.xetra.com/xetra-en/allTradableInstruments.csv",
        "http://xetra.com/xetra-en/allTradableInstruments.csv"]
SEITEN = ["https://www.cashmarket.deutsche-boerse.com/cash-en/trading/Tradable-Instruments-Xetra",
          "https://www.cashmarket.deutsche-boerse.com/cash-de/handel/Handelbare-Instrumente-Xetra",
          "https://www.xetra.com/xetra-en/instruments/instruments",
          "https://www.cashmarket.deutsche-boerse.com/cash-en/trading/Tradable-Instruments-Xetra/boersefrankfurt"]


def hole(url, timeout=180):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read()


def csv_links():
    links = []
    for s in SEITEN:
        try:
            h = hole(s, 60).decode("utf-8", "replace")
        except Exception as e:
            print("Seite nicht ladbar:", s, e); continue
        for m in re.finditer(r'href="([^"]+?\.csv)"', h, re.I):
            u = m.group(1)
            if not re.search(r"tradable|handelbar|instrument", u, re.I):
                continue
            if u.startswith("/"):
                u = re.match(r"https?://[^/]+", s).group(0) + u
            if u not in links:
                links.append(u)
    return links


def lies(raw, gesucht, out):
    text = raw.decode("utf-8-sig", "replace")
    zeilen = text.splitlines()
    # Kopfzeile suchen (vor der Tabelle stehen oft Titel und Datum)
    for i, z in enumerate(zeilen[:20]):
        if "ISIN" in z and "WKN" in z:
            break
    else:
        return 0
    n = 0
    for row in csv.DictReader(io.StringIO("\n".join(zeilen[i:])), delimiter=";"):
        isin, wkn = (row.get("ISIN") or "").strip(), (row.get("WKN") or "").strip()
        if isin in gesucht and re.fullmatch(r"[A-Z0-9]{6}", wkn) and isin not in out:
            out[isin] = wkn; n += 1
    return n


def main():
    iz = json.load(open("data/kurse/isin-zuordnung.json", encoding="utf-8"))
    gesucht = {(v.get("isin") if isinstance(v, dict) else v) for v in iz.values()}
    for f in json.load(open("data/dividendenseiten.json", encoding="utf-8"))["firmen"]:
        if f.get("isin"): gesucht.add(f["isin"])
    gesucht.discard(None)
    try:
        alt = json.load(open("data/kurse/wkn.json", encoding="utf-8")).get("k", {})
    except Exception:
        alt = {}
    out, quellen = {}, []
    for u in FEST + csv_links():
        try:
            raw = hole(u)
        except Exception as e:
            print("nicht ladbar:", u, e); continue
        n = lies(raw, gesucht, out)
        print(u, "->", n, "WKN")
        if n: quellen.append(u)
    # Deutsche ISINs: WKN steckt in der ISIN (DE000 + WKN + Prüfziffer)
    for isin in gesucht:
        if isin.startswith("DE000") and isin not in out:
            out[isin] = isin[5:11]
    if len(out) < len(alt) * 0.8:
        print("Deutlich weniger WKN als bisher, alte Datei bleibt:", len(out), "statt", len(alt)); sys.exit(0)
    alt.update(out)
    json.dump({"stand": date.today().isoformat(), "quelle": "Deutsche Börse, All tradable instruments (Xetra/Börse Frankfurt)",
               "k": dict(sorted(alt.items()))}, open("data/kurse/wkn.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(len(alt), "WKN gespeichert, gesucht", len(gesucht))


if __name__ == "__main__":
    main()
