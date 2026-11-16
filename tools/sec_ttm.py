#!/usr/bin/env python3
"""Quartale nach Geschaeftsjahr und TTM (letzte vier Quartale) je US-Firma.

Liest data/sec/quartal.json (10-Q, Q1 bis Q3) und data/sec/fundamentals.json (Jahreswerte aus 10-K).
Das vierte Quartal ergibt sich als Jahreswert minus Summe der drei Quartale desselben Geschaeftsjahrs.
Schreibt data/sec/ttm.json: je Firma Quartale mit Geschaeftsjahr-Nummer und TTM-Summen.
Bricht die Reihe (fehlendes oder ungleich langes Quartal), bleibt der TTM-Wert leer."""
import json, datetime

METRIKEN = ["umsatz", "gewinn", "eps_verw", "dividende_je_aktie"]   # Cashflow-Posten folgen unten aus kumulierten Werten
TAGE_QUARTAL = (80, 100)


def d(s):
    return datetime.date.fromisoformat(s)


def konsekutiv(datums):
    return all(TAGE_QUARTAL[0] <= (datums[i + 1] - datums[i]).days <= TAGE_QUARTAL[1] for i in range(len(datums) - 1))


def q4_ableiten(quartale, jahreswerte):
    """quartale: [[end, wert, fp, fy]] sortiert; jahreswerte: [[end, wert]] je 10-K"""
    neu = []
    for ej, A in jahreswerte:
        if A is None:
            continue
        E = d(ej)
        innen = [x for x in quartale if E - datetime.timedelta(days=330) < d(x[0]) < E - datetime.timedelta(days=60)]
        if len(innen) != 3 or any(x[2] not in ("Q1", "Q2", "Q3") for x in innen):
            continue
        ds = [d(x[0]) for x in innen]
        if not konsekutiv(ds) or not (60 <= (E - ds[-1]).days <= 120):
            continue
        neu.append([ej, round(A - sum(x[1] for x in innen), 4), "Q4", innen[-1][3]])
    return neu


def ttm(quartale):
    """Summe der letzten vier aufeinanderfolgenden Quartale; None, wenn keine lueckenlose Reihe."""
    if len(quartale) < 4:
        return None
    letzte = quartale[-4:]
    if not konsekutiv([d(x[0]) for x in letzte]):
        return None
    return round(sum(x[1] for x in letzte), 4)


def quartale_aus_kumuliert(eintraege):
    """eintraege: [start, end, dauer_monate, wert] kumuliert seit Geschaeftsjahresbeginn (3, 6, 9, 12 Monate).
    Die Vorperiode ist die Meldung mit drei Monaten weniger und einem Enddatum etwa ein Quartal frueher.
    Die Startdaten schwanken zwischen Meldungen (52/53-Wochen-Jahre), daher wird ueber die Enddaten verkettet."""
    werte = {}
    for _s, e, m, w in eintraege:
        werte[(m, d(e))] = w
    out = {}
    for (m, ende), w in werte.items():
        if m == 3:
            q = w
        else:
            vorher = [v for (mm, ee), v in werte.items() if mm == m - 3 and 60 <= (ende - ee).days <= 120]
            if not vorher:
                continue
            q = w - vorher[0]
        out[ende] = [ende.isoformat(), round(q, 4), "Q%d" % (m // 3), None]
    return [out[k] for k in sorted(out)]


KUM_METRIKEN = {"ocf": "operativer_cf", "capex": "capex", "div": "dividenden_gezahlt"}


def main():
    q = json.load(open("data/sec/quartal.json", encoding="utf-8"))["firmen"]
    f = json.load(open("data/sec/fundamentals.json", encoding="utf-8"))["firmen"]
    ausgabe = {}
    for t, qd in q.items():
        jahr = f.get(t, {}).get("k", {})
        quartale_neu, werte = {}, {}
        for m in METRIKEN:
            liste = sorted(qd.get("quartale", {}).get(m, []), key=lambda x: x[0])
            alle = sorted(liste + q4_ableiten(liste, jahr.get(m, [])), key=lambda x: x[0])[-8:]
            quartale_neu[m] = alle
            aktuell = bool(alle) and (datetime.date.today() - d(alle[-1][0])).days <= 200
            werte[m] = ttm(alle) if aktuell else None   # veraltete Reihen (z. B. 2010) bekommen keine TTM-Werte
        kum = qd.get("kumuliert", {})
        for quelle, m in KUM_METRIKEN.items():
            alle = quartale_aus_kumuliert(kum.get(quelle, []))[-8:]
            quartale_neu[m] = alle
            aktuell = bool(alle) and (datetime.date.today() - d(alle[-1][0])).days <= 200
            werte[m] = ttm(alle) if aktuell else None
        if werte.get("operativer_cf") is not None and werte.get("capex") is not None:
            werte["fcf"] = round(werte["operativer_cf"] - abs(werte["capex"]), 4)
            if werte.get("dividenden_gezahlt") is not None and werte["fcf"] > 0:
                werte["ausschuettung_fcf"] = round(abs(werte["dividenden_gezahlt"]) / werte["fcf"] * 100, 1)
        if not any(quartale_neu.values()):
            continue
        letzte = quartale_neu["umsatz"][-1] if quartale_neu["umsatz"] else None
        ausgabe[t] = {"n": qd.get("n", ""), "letztes_quartal": letzte[0] if letzte else None,
                      "geschaeftsjahr_nr": letzte[2] if letzte else None, "geschaeftsjahr": letzte[3] if letzte else None,
                      "ttm": werte, "quartale": quartale_neu}
    json.dump({"stand": datetime.date.today().isoformat(), "quelle": "SEC EDGAR (10-Q, 10-K), Q4 abgeleitet",
               "firmen": ausgabe}, open("data/sec/ttm.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(len(ausgabe), "Firmen mit TTM geschrieben")


if __name__ == "__main__":
    main()
