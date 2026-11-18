#!/usr/bin/env python3
"""ESEF-Jahreszahlen fuer ALLE Emittenten des Europa-Universums (europe-equity-hub/data/universe), nicht nur die feste
Liste in esef_fundamentals.py. Quelle: filings.xbrl.org (ESEF-Jahresfinanzberichte, offiziell eingereicht, kostenlos).

Auswahl: Emittent mit LEI, Sitz in EU/EWR/GB/JE/GG/IM (die Schweiz berichtet nicht nach ESEF), mindestens eine aktive
Notierung. Firmen, die schon ueber SEC oder die feste ESEF-Liste kommen, werden uebersprungen.
Reihenfolge: noch nie geprueft zuerst, Firmen mit deutschem Boersenkurs zuerst (dort lassen sich KGV usw. rechnen).
Erneute Pruefung: mit Berichten nach 7 Tagen, ohne Berichte nach 30 Tagen.

Speicher (nur bei neuen Berichten neu geschrieben, damit das Repository nicht waechst):
  data/esef/universum/<LEI>.json   {"lei","name","berichte":{json_url:{"ende","roh"}}}
  data/esef/universum/_status.json {LEI: [geprueft, anzahl_berichte]}
Ausgabe (gleiches Format wie data/esef/fundamentals.json, eine Datei je Firma, der Hub laedt sie erst beim Aufruf):
  data/esef/firma/<KUERZEL>.json und data/esef/firma/_index.json {KUERZEL: [name, isin, land, gj]}
  data/esef-universum-abdeckung.md
Keine Werte werden erfunden oder als geprueft markiert: alles stammt maschinell aus den eingereichten Berichten.
Aufruf: python3 tools/esef_universum.py [--max-minuten 50] [--limit N]
"""
import argparse, concurrent.futures as cf, datetime, glob, json, os, sys, time, urllib.parse

sys.path.insert(0, os.path.dirname(__file__))
import esef_fundamentals as ef  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UNI = os.path.join(ROOT, "europe-equity-hub", "data", "universe")
SP = os.path.join(ROOT, "data", "esef", "universum")
OUT = os.path.join(ROOT, "data", "esef", "firma")
LAENDER = set("AT BE BG HR CY CZ DK EE FI FR DE GR HU IE IT LV LT LU MT NL PL PT RO SK SI ES SE IS LI NO GB JE GG IM".split())
SUFFIX = {"XPAR": ".PA", "ALXP": ".PA", "XAMS": ".AS", "XBRU": ".BR", "XLIS": ".LS", "XMSM": ".IR", "MTAA": ".MI", "EXGM": ".MI",
          "XMAD": ".MC", "MABX": ".MC", "XSTO": ".ST", "XNGM": ".ST", "XHEL": ".HE", "XCSE": ".CO", "XOSL": ".OL", "XICE": ".IC",
          "XETA": ".DE", "XETB": ".DE", "XLON": ".L", "AIMX": ".L", "XWAR": ".WA", "XNCO": ".WA", "WBAH": ".VI", "XATH": ".AT"}
ERNEUT_MIT, ERNEUT_OHNE = 7, 30


def lade(p, leer=None):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return leer


def schreibe(p, obj, kompakt=True):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":") if kompakt else None, indent=None if kompakt else 1)
    os.replace(tmp, p)


def vorhandene():
    """Kuerzel und ISINs, die schon ueber SEC oder die feste ESEF-Liste kommen; boerse.de-Kuerzel je ISIN."""
    kuerzel, isins, bd = set(), set(), {}
    for p in ("data/sec/fundamentals.json", "data/esef/fundamentals.json", "data/asien/fundamentals.json"):
        for t, f in (lade(os.path.join(ROOT, p), {}) or {}).get("firmen", {}).items():
            kuerzel.add(t.upper())
            if f.get("isin"):
                isins.add(f["isin"])
    for t, f in (lade(os.path.join(ROOT, "data/boerse-de/fundamentals.json"), {}) or {}).get("firmen", {}).items():
        if f.get("isin"):
            bd[f["isin"]] = t
    leis = {v[0] for v in (lade(os.path.join(ROOT, "data/esef/speicher.json"), {}) or {}).get("lei", {}).values() if v}
    return kuerzel, isins, bd, leis


def auswahl(kurse):
    """Emittenten des Universums -> Liste von Firmen-Dicts (lei, name, land, isin, kuerzel, kurs)."""
    iss = lade(os.path.join(UNI, "issuers.json"), [])
    secs = {s["isin"]: s for s in lade(os.path.join(UNI, "securities.json"), [])}
    lst = {}
    for l in lade(os.path.join(UNI, "listings.json"), []):
        if l.get("listing_status") != "terminated":
            lst.setdefault(l["isin"], []).append(l)
    kuerzel_da, isins_da, bd, leis_da = vorhandene()
    vergeben = set(kuerzel_da) | set(bd.values())
    firmen = []
    for i in sorted(iss, key=lambda x: x.get("lei") or ""):
        lei, land = i.get("lei"), (i.get("legal_jurisdiction") or "")[:2]
        if not lei or land not in LAENDER or lei in leis_da:
            continue
        aktiv = [x for x in i.get("isins", []) if secs.get(x, {}).get("active_listing_count", 0) > 0]
        if not aktiv or any(x in isins_da for x in i.get("isins", [])):
            continue
        aktiv.sort(key=lambda x: (x not in kurse, x[:2] != land, x))
        isin = aktiv[0]
        t = bd.get(isin)   # boerse.de-Firma: gleiches Kuerzel, ESEF ergaenzt dort Cashflow und Bilanz
        if not t:
            ls = sorted((l for l in lst.get(isin, []) if l.get("ticker") and l["mic"] in SUFFIX),
                        key=lambda l: (l.get("venue_country") != land, l["mic"] in ("XETB", "XETA"), l["mic"]))
            for l in ls:
                kand = l["ticker"].strip().upper().replace(" ", "-") + SUFFIX[l["mic"]]
                if kand not in vergeben:
                    t = kand
                    break
        if not t:
            t = isin
        vergeben.add(t)
        firmen.append({"lei": lei, "name": i.get("legal_name") or i.get("name") or lei, "land": land, "isin": isin,
                       "kuerzel": t, "kurs": isin in kurse})
    return firmen


def faellig(status, lei, heute):
    s = status.get(lei)
    if not s:
        return True
    tage = (datetime.date.fromisoformat(heute) - datetime.date.fromisoformat(s[0])).days
    return tage >= (ERNEUT_MIT if s[1] else ERNEUT_OHNE)


def holen(f):
    """Neue Berichte eines Emittenten laden (Netzwerk). Gibt (lei, speicher, anzahl, fehler) zurueck."""
    lei = f["lei"]
    p = os.path.join(SP, f"{lei}.json")
    sp = lade(p) or {"lei": lei, "name": f["name"], "berichte": {}}
    neu = 0
    try:
        for b in ef.berichte(lei):
            schl = b["json_url"]
            if schl in sp["berichte"]:
                continue
            url = ef.BASIS + schl if schl.startswith("/") else schl
            x = ef.get(urllib.parse.quote(url, safe=":/%?=&"))   # Dateinamen mit Leerzeichen
            sp["berichte"][schl] = {"ende": b["period_end"], "roh": ef.auslesen(x)}
            neu += 1
            time.sleep(1.5)
    except Exception as e:  # noqa: BLE001
        return lei, sp, neu, str(e)[:120]
    return lei, sp, neu, None


def plausibel(fa):
    """Einheitenfehler in den eingereichten Daten abfangen (z. B. Cent statt Euro getaggt): je Aktie gemeldete Werte, die um
    mehr als Faktor 20 von Gesamtbetrag / Aktienzahl abweichen, werden entfernt (nicht umgerechnet) und vermerkt; bei der
    Dividende tritt dann der nachgerechnete Wert an die Stelle."""
    k, hin = fa["k"], []
    av = dict(k.get("aktien_verw", []))
    for feld, gesamt, ersatz in (("dividende_je_aktie", "dividenden_gezahlt", "dividende_je_aktie_ber"), ("eps_verw", "gewinn", "eps_ber")):
        reihe, ges, ers = dict(k.get(feld, [])), dict(k.get(gesamt, [])), dict(k.get(ersatz, []))
        for e, v in list(reihe.items()):
            if not (av.get(e) and ges.get(e) and v):
                continue
            q = v / (ges[e] / av[e])
            if q > 20 or (0 < q < 0.05):
                del reihe[e]
                hin.append(f"{feld} {e[:4]}: gemeldet {v}, passt nicht zu {gesamt}/Aktienzahl, entfernt")
                if ges[e] > 0:
                    ers[e] = round(ges[e] / av[e], 4)
        if reihe:
            k[feld] = [[e, reihe[e]] for e in sorted(reihe)]
        else:
            k.pop(feld, None)
        if ers:
            k[ersatz] = [[e, ers[e]] for e in sorted(ers)]
    if hin:
        fa["pruefhinweise"] = hin
    return fa


def bauen(firmen):
    """Alle gespeicherten Berichte -> eine Datei je Firma und Index (ohne Netzwerk)."""
    os.makedirs(OUT, exist_ok=True)
    index, zeilen, alt = {}, [], {os.path.basename(p)[:-5] for p in glob.glob(os.path.join(OUT, "*.json"))} - {"_index"}
    for f in firmen:
        sp = lade(os.path.join(SP, f"{f['lei']}.json"))
        if not sp or not sp.get("berichte"):
            continue
        bs = [{"lei": f["lei"], "ende": b["ende"], "roh": b["roh"]} for b in sp["berichte"].values()]
        fa, info = ef.firma_bauen(f["name"], sp.get("name") or f["name"], f["lei"], f["isin"], f["land"], "", bs)
        if not fa:
            zeilen.append((f, None, info))
            continue
        fa = plausibel(fa)
        fa["quelle"] = "ESEF"
        fa["universum"] = True
        fa["human_review"] = "pending"
        t = f["kuerzel"]
        if lade(os.path.join(OUT, f"{t}.json")) != fa:
            schreibe(os.path.join(OUT, f"{t}.json"), fa)
        alt.discard(t)
        index[t] = [fa["n"], f["isin"], f["land"], fa["gj"]]
        zeilen.append((f, fa, info))
    for t in alt:   # Kuerzel geaendert oder Firma nicht mehr im Universum
        os.remove(os.path.join(OUT, f"{t}.json"))
    schreibe(os.path.join(OUT, "_index.json"), dict(sorted(index.items())))
    return index, zeilen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-minuten", type=float, default=50)
    ap.add_argument("--limit", type=int, default=0, help="hoechstens so viele Emittenten abrufen (0 = ohne Grenze)")
    ap.add_argument("--nur-bauen", action="store_true", help="nichts abrufen, nur aus dem Speicher bauen")
    ap.add_argument("--threads", type=int, default=3)
    a = ap.parse_args()
    start, heute = time.time(), datetime.date.today().isoformat()
    kurse = (lade(os.path.join(ROOT, "data/kurse/xetra-letzter.json"), {}) or {}).get("k", {})
    firmen = auswahl(kurse)
    status = lade(os.path.join(SP, "_status.json"), {}) or {}
    offen = [f for f in firmen if faellig(status, f["lei"], heute)]
    offen.sort(key=lambda f: (f["lei"] in status, not f["kurs"], (status.get(f["lei"]) or [""])[0]))
    if a.limit:
        offen = offen[:a.limit]
    fehler, geladen, neu_ges = [], 0, 0
    if not a.nur_bauen and offen:
        with cf.ThreadPoolExecutor(a.threads) as ex:
            laufend, it = set(), iter(offen)
            def nachschub():
                while len(laufend) < a.threads and time.time() - start < a.max_minuten * 60:
                    f = next(it, None)
                    if f is None:
                        return
                    laufend.add(ex.submit(holen, f))
            nachschub()
            while laufend:
                fertig, _ = cf.wait(laufend, return_when=cf.FIRST_COMPLETED)
                for fu in fertig:
                    laufend.discard(fu)
                    lei, sp, neu, err = fu.result()
                    if neu:
                        schreibe(os.path.join(SP, f"{lei}.json"), sp)
                    if err:
                        fehler.append(f"{lei}: {err}")
                    else:
                        status[lei] = [heute, len(sp["berichte"])]
                    geladen += 1
                    neu_ges += neu
                    if geladen % 25 == 0:
                        schreibe(os.path.join(SP, "_status.json"), dict(sorted(status.items())))
                        print(f"  {geladen} Emittenten geprüft, {neu_ges} neue Berichte, {int(time.time() - start)} s", flush=True)
                nachschub()
        schreibe(os.path.join(SP, "_status.json"), dict(sorted(status.items())))
    index, zeilen = bauen(firmen)
    # Abdeckung
    geprueft = sum(1 for f in firmen if f["lei"] in status)
    mit_ber = sum(1 for f in firmen if (status.get(f["lei"]) or [0, 0])[1])
    mit_kurs = sum(1 for f in firmen if f["kuerzel"] in index and f["kurs"])
    jahre = {}
    for f, fa, info in zeilen:
        if fa:
            jahre[info["jahre"]] = jahre.get(info["jahre"], 0) + 1
    md = [f"# ESEF-Jahreszahlen: ganzes Europa-Universum (Stand {heute})", "",
          "Quelle: filings.xbrl.org (eingereichte ESEF-Jahresfinanzberichte). Maschinell ausgelesen, ungeprüft (human_review: pending).", "",
          f"- Emittenten in der Auswahl (LEI, Sitz EU/EWR/GB, aktive Notierung, nicht schon über SEC/feste Liste): **{len(firmen)}**",
          f"- davon geprüft: **{geprueft}**, offen: **{len(firmen) - geprueft}**",
          f"- mit ESEF-Berichten: **{mit_ber}**",
          f"- mit Jahreszahlen im Hub: **{len(index)}**, davon mit deutschem Börsenkurs (KGV, Rendite usw. rechenbar): **{mit_kurs}**",
          f"- in diesem Lauf: {geladen} Emittenten abgerufen, {neu_ges} neue Berichte, {len(fehler)} Fehler", "",
          "ESEF gibt es erst ab Geschäftsjahr 2020 (teils 2021); ältere Jahre stehen nur in PDF-Berichten.", "",
          "| Zeitraum | Firmen |", "|---|---|"] + [f"| {k} | {v} |" for k, v in sorted(jahre.items(), key=lambda x: -x[1])[:15]]
    if fehler:
        md += ["", "## Fehler (nächster Lauf versucht es erneut)", ""] + [f"- {x}" for x in fehler[:50]]
    open(os.path.join(ROOT, "data", "esef-universum-abdeckung.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
    print("\n".join(md[4:11]))


if __name__ == "__main__":
    main()
