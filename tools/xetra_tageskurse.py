#!/usr/bin/env python3
"""Xetra-Tageskurse aus den kostenlosen, 15 Minuten verzoegerten MiFID-Daten der Deutschen Boerse (ab 11.11.2026).
Die Boerse stellt je Handelstag eine Tagesdatei mit allen Xetra-Abschluessen bereit (DETR-posttrade-daily-JJJJ-MM-TT.json.gz),
die nur rund einen Tag online bleibt. Dieses Skript holt alle noch verfuegbaren Tagesdateien, verdichtet sie je ISIN zu
Eroeffnung, Hoch, Tief, Schluss, Stueckzahl und Anzahl Abschluesse und legt sie unter data/kurse/xetra/JJJJ-MM-TT.json ab.
Eine Historie entsteht also erst ab dem Starttag. Nutzung: kostenlos, solange die Daten nicht kommerzialisiert werden
(Market Data Policy der Deutschen Boerse, Art. 13 MiFIR); Datennutzungserklaerung beachten."""
import gzip, io, json, os, re, sys, urllib.request

UA = {"User-Agent": "Mozilla/5.0 (dividenden-rechner.de Tageskurse)"}
DOWN = "https://mfs.deutsche-boerse.com/api/download/"
# Handelsplaetze in der Reihenfolge, in der ihr Kurs bevorzugt wird (Xetra zuerst; viele US-Werte gibt es nur bei Tradegate/Frankfurt)
PLAETZE = [("DETR", "xetra", "Xetra"), ("DGAT", "tradegate", "Tradegate"), ("DFRA", "frankfurt", "Börse Frankfurt")]


def hole(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=300) as r:
        return r.read()


VEN = {}


def verdichten(raw):
    k = {}
    with gzip.open(io.BytesIO(raw), "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip().rstrip(",")
            if not line.startswith("{"):
                continue
            try:
                z = json.loads(line)
            except Exception:
                continue
            isin, p, q, t = z.get("instrumentIdentificationCode"), z.get("price"), z.get("quantity") or 0, z.get("tradingDateAndTime", "")
            if not isin or not isinstance(p, (int, float)) or p <= 0 or z.get("priceNotation", "MONE") != "MONE":
                continue
            # Nur Abschluesse im Xetra-Orderbuch fuer den Kurs; ausserboersliche Meldungen (falls vorhanden) zaehlen nicht
            ven = str(z.get("venueOfExecution", ""))
            if "OFF" in ven or ven in ("SINT", "XXXX"):
                VEN[ven] = VEN.get(ven, 0) + 1
                continue
            e = k.get(isin)
            if e is None:
                k[isin] = [t, p, p, p, t, p, q, 1, z.get("priceCurrency", "EUR")]
            else:
                if t < e[0]: e[0], e[1] = t, p
                if p > e[2]: e[2] = p
                if p < e[3]: e[3] = p
                if t >= e[4]: e[4], e[5] = t, p
                e[6] += q; e[7] += 1
    # [Eroeffnung, Hoch, Tief, Schluss, Stueck, Abschluesse, Waehrung]
    return {i: [e[1], e[2], e[3], e[5], round(e[6], 4), e[7], e[8]] for i, e in sorted(k.items())}


def main():
    for code, ordner, name in PLAETZE:
        ziel = f"data/kurse/{ordner}"
        os.makedirs(ziel, exist_ok=True)
        try:
            liste = json.loads(hole(f"https://mfs.deutsche-boerse.com/api/{code}-posttrade"))
        except Exception as e:
            print(name, "Liste nicht ladbar:", e); continue
        tage = sorted({m.group(1) for f in liste.get("CurrentFiles", [])
                       for m in [re.match(rf"{code}-posttrade-daily-(\d{{4}}-\d{{2}}-\d{{2}})\.json\.gz$", f)] if m})
        print(name, "Tagesdateien online:", tage)
        for tag in tage:
            pfad = f"{ziel}/{tag}.json"
            if os.path.exists(pfad):
                continue
            try:
                k = verdichten(hole(f"{DOWN}{code}-posttrade-daily-{tag}.json.gz"))
            except Exception as e:
                print(name, tag, "Fehler:", e); continue
            if len(k) < 200:
                print(name, tag, "zu wenige Werte, uebersprungen:", len(k)); continue
            json.dump({"datum": tag, "quelle": f"Deutsche Börse, {name} Post-Trade (MiFID II, 15 Min. verzögert)",
                       "felder": ["eroeffnung", "hoch", "tief", "schluss", "stueck", "abschluesse", "waehrung"], "k": k},
                      open(pfad, "w"), separators=(",", ":"))
            print(name, tag, len(k), "ISINs")
    # Letzter Stand je ISIN: neuester Handelstag, bevorzugter Handelsplatz
    tage_alle = sorted({f[:10] for _, o, _ in PLAETZE if os.path.isdir(f"data/kurse/{o}")
                        for f in os.listdir(f"data/kurse/{o}") if re.fullmatch(r"\d{4}-\d{2}-\d{2}\.json", f)})
    if not tage_alle:
        return
    def lade(o, tag):
        p = f"data/kurse/{o}/{tag}.json"
        return json.load(open(p))["k"] if os.path.exists(p) else {}
    letzt = tage_alle[-1]; vor = tage_alle[-2] if len(tage_alle) > 1 else None
    out = {"datum": letzt, "vortag": vor, "quelle": "Deutsche Börse (Xetra, Tradegate, Börse Frankfurt), MiFID II, 15 Min. verzögert",
           "felder": ["schluss", "veraenderung_proz", "waehrung", "boerse"], "k": {}}
    for code, o, name in reversed(PLAETZE):   # bevorzugter Platz zuletzt, ueberschreibt
        heute, gestern = lade(o, letzt), (lade(o, vor) if vor else {})
        for i, v in heute.items():
            alt = gestern.get(i)
            out["k"][i] = [v[3], round((v[3] / alt[3] - 1) * 100, 2) if alt and alt[3] else None, v[6], code]
    json.dump(out, open("data/kurse/xetra-letzter.json", "w"), separators=(",", ":"))
    print("Letzter Stand", letzt, len(out["k"]), "ISINs; uebersprungene Plaetze:", VEN)


if __name__ == "__main__":
    main()
