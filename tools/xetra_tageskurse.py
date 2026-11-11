#!/usr/bin/env python3
"""Xetra-Tageskurse aus den kostenlosen, 15 Minuten verzoegerten MiFID-Daten der Deutschen Boerse (ab 11.11.2026).
Die Boerse stellt je Handelstag eine Tagesdatei mit allen Xetra-Abschluessen bereit (DETR-posttrade-daily-JJJJ-MM-TT.json.gz),
die nur rund einen Tag online bleibt. Dieses Skript holt alle noch verfuegbaren Tagesdateien, verdichtet sie je ISIN zu
Eroeffnung, Hoch, Tief, Schluss, Stueckzahl und Anzahl Abschluesse und legt sie unter data/kurse/xetra/JJJJ-MM-TT.json ab.
Eine Historie entsteht also erst ab dem Starttag. Nutzung: kostenlos, solange die Daten nicht kommerzialisiert werden
(Market Data Policy der Deutschen Boerse, Art. 13 MiFIR); Datennutzungserklaerung beachten."""
import gzip, io, json, os, re, sys, urllib.request

UA = {"User-Agent": "Mozilla/5.0 (dividenden-rechner.de Tageskurse)"}
LISTE = "https://mfs.deutsche-boerse.com/api/DETR-posttrade"
DOWN = "https://mfs.deutsche-boerse.com/api/download/"
ZIEL = "data/kurse/xetra"


def hole(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=300) as r:
        return r.read()


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
            if z.get("venueOfExecution", "XETA") != "XETA":
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
    os.makedirs(ZIEL, exist_ok=True)
    liste = json.loads(hole(LISTE))
    tage = sorted({m.group(1) for f in liste.get("CurrentFiles", [])
                   for m in [re.match(r"DETR-posttrade-daily-(\d{4}-\d{2}-\d{2})\.json\.gz$", f)] if m})
    print("Tagesdateien online:", tage)
    neu = 0
    for tag in tage:
        pfad = f"{ZIEL}/{tag}.json"
        if os.path.exists(pfad):
            continue
        k = verdichten(hole(f"{DOWN}DETR-posttrade-daily-{tag}.json.gz"))
        if len(k) < 500:
            print(tag, "zu wenige Werte, uebersprungen:", len(k)); continue
        json.dump({"datum": tag, "quelle": "Deutsche Börse, Xetra Post-Trade (MiFID II, 15 Min. verzögert)",
                   "felder": ["eroeffnung", "hoch", "tief", "schluss", "stueck", "abschluesse", "waehrung"], "k": k},
                  open(pfad, "w"), separators=(",", ":"))
        neu += 1
        print(tag, len(k), "ISINs")
    # Letzter Stand fuer schnelle Abfragen
    vorhanden = sorted(f for f in os.listdir(ZIEL) if re.fullmatch(r"\d{4}-\d{2}-\d{2}\.json", f))
    if vorhanden:
        letzt = json.load(open(f"{ZIEL}/{vorhanden[-1]}"))
        vor = json.load(open(f"{ZIEL}/{vorhanden[-2]}")) if len(vorhanden) > 1 else None
        out = {"datum": letzt["datum"], "vortag": vor["datum"] if vor else None, "quelle": letzt["quelle"],
               "felder": ["schluss", "veraenderung_proz", "waehrung"], "k": {}}
        for i, v in letzt["k"].items():
            alt = vor["k"].get(i) if vor else None
            out["k"][i] = [v[3], round((v[3] / alt[3] - 1) * 100, 2) if alt and alt[3] else None, v[6]]
        json.dump(out, open("data/kurse/xetra-letzter.json", "w"), separators=(",", ":"))
    print("neu:", neu)


if __name__ == "__main__":
    main()
