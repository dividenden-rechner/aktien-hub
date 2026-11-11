#!/usr/bin/env python3
"""Zuordnung Ticker -> ISIN fuer die Firmen aus data/sec/fundamentals.json (ab 11.11.2026).
Quelle: offizielle Liste aller auf Xetra handelbaren Instrumente der Deutschen Boerse (t7-xetr-allTradableInstruments.csv).
Erster Weg: OpenFIGI (offene Wertpapierkennungen von Bloomberg, kostenlos) liefert zu jeder US-ISIN den US-Ticker.
Zweiter Weg fuer den Rest (v. a. Auslandsfirmen): Abgleich ueber den Firmennamen, nur bei sehr hoher Uebereinstimmung. Feste Zuordnungen in data/kurse/isin-fest.json gehen immer vor. Schreibt data/kurse/isin-zuordnung.json
und data/kurse/isin-zuordnung.md (unsichere Treffer zum Pruefen)."""
import csv, difflib, io, json, os, re, time, urllib.request

URL = "https://www.cashmarket.deutsche-boerse.com/resource/blob/1528/ef73eef09b2e8353e17090956eee878b/data/t7-xetr-allTradableInstruments.csv"
UA = {"User-Agent": "Mozilla/5.0 (dividenden-rechner.de ISIN-Zuordnung)"}
WEG = set("""INC INCORPORATED CORP CORPORATION CO COMPANY COS LTD LIMITED PLC NV N V SE AG SA S A AB ASA OYJ SPA S P A
HOLDINGS HOLDING HLDGS GROUP GRP THE TRUST LP L P REIT CL CLASS A B C REG REGISTERED SHS SHARES SHARE NAM AKT AKTIE
ON O N DL EO SF DK LS NK CD YN ADR ADS SP SPONS SPONSORED NEW DE INTERNATIONAL INTL TECHNOLOGIES TECHNOLOGY""".split())
LAND = {"US-GAAP": "US"}


def norm(n):
    n = str(n).upper().replace("&", " ").replace("+", " ")
    n = re.sub(r"\b(DL|EO|SF|LS|DK|NK|YN|CD)[\- ]?[\d,\.]+", " ", n)   # Nennwerte wie DL-,01
    n = re.sub(r"[^A-Z0-9 ]", " ", n)
    return " ".join(t for t in n.split() if t not in WEG and not t.isdigit())


TYPEN = {}


def main():
    import datetime
    try:
        alt = json.load(open("data/kurse/isin-zuordnung.json"))
        st = alt.get("_stand", "2000-01-01")
        if not os.environ.get("ZUORDNUNG_NEU") and (datetime.date.today() - datetime.date.fromisoformat(st)).days < 7:
            print("Zuordnung vom", st, "noch aktuell"); return
    except Exception:
        pass
    raw = urllib.request.urlopen(urllib.request.Request(URL, headers=UA), timeout=120).read().decode("utf-8-sig", "replace")
    zeilen = raw.splitlines()
    kopf = next(i for i, z in enumerate(zeilen) if "ISIN" in z and ";" in z)
    rd = list(csv.DictReader(io.StringIO("\n".join(zeilen[kopf:])), delimiter=";"))
    spalten = list(rd[0].keys()) if rd else []
    sp_name = next((s for s in spalten if s.strip().lower() in ("instrument", "instrument name", "name")), None) or spalten[2]
    sp_typ = next((s for s in spalten if "type" in s.lower() or "typ" in s.lower()), None)
    sp_mn = next((s for s in spalten if "mnemonic" in s.lower()), None)
    gehandelt = {}
    try:
        gehandelt = json.load(open("data/kurse/xetra-letzter.json"))["k"]
    except Exception:
        pass
    inst = []
    for r in rd:
        isin = (r.get("ISIN") or "").strip()
        if not re.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}\d", isin):
            continue
        typ = (r.get(sp_typ) or "").strip() if sp_typ else ""
        TYPEN[typ] = TYPEN.get(typ, 0) + 1
        grp = (r.get("Product Assignment Group Description") or "").upper()
        if any(x in grp for x in ("ETF", "ETP", "ETC", "ETN", "FUND", "BOND", "ANLEIHE")):
            continue
        inst.append({"isin": isin, "name": r.get(sp_name, "").strip(), "n": norm(r.get(sp_name, "")),
                     "mn": (r.get(sp_mn) or "").strip() if sp_mn else "", "typ": typ})
    fest = {}
    try:
        fest = json.load(open("data/kurse/isin-fest.json"))
    except Exception:
        pass
    firmen = json.load(open("data/sec/fundamentals.json"))["firmen"]
    # 1) OpenFIGI: US-ISIN -> US-Ticker (bis 10 Abfragen je Anfrage, ohne Schluessel 25 Anfragen pro Minute)
    figi = {}
    us = [i for i in inst if i["isin"].startswith("US")]
    bekannt = {i["isin"] for i in us}
    # Auch US-Werte, die nur bei Tradegate oder in Frankfurt gehandelt werden (nicht in der Xetra-Liste)
    us += [{"isin": x, "name": "", "n": "", "mn": "", "typ": ""} for x in gehandelt if x.startswith("US") and x not in bekannt]
    for a in range(0, len(us), 10):
        teil = us[a:a + 10]
        body = json.dumps([{"idType": "ID_ISIN", "idValue": i["isin"], "exchCode": "US"} for i in teil]).encode()
        for versuch in range(4):
            try:
                req = urllib.request.Request("https://api.openfigi.com/v3/mapping", data=body,
                                             headers={"Content-Type": "application/json", **UA})
                res = json.loads(urllib.request.urlopen(req, timeout=60).read()); break
            except Exception as e:
                res = None; time.sleep(15 if "429" in str(e) else 3)
        for i, r in zip(teil, res or []):
            for d in (r or {}).get("data", []) or []:
                tk = str(d.get("ticker", "")).upper().replace("/", "-").replace(" ", "-")
                if tk:
                    figi.setdefault(tk, []).append(i)
                    break
        time.sleep(2.5)
    def bester(lst):   # bei mehreren Xetra-Zeilen derselben Aktie: die mit den meisten Abschluessen
        return max(lst, key=lambda i: (i["isin"] in gehandelt, i["isin"].startswith("US")))
    out, unsicher, fehlt = {}, [], []
    for t, f in sorted(firmen.items()):
        if t in fest:
            out[t] = {"isin": fest[t], "quelle": "fest"}; continue
        # Auslandsfirmen (Bericht nicht in Dollar): lieber die Heimataktie per Namensabgleich als das US-Zertifikat (ADR)
        heimat = f.get("w") != "USD"
        if t in figi and not heimat:
            i = bester(figi[t])
            out[t] = {"isin": i["isin"], "xetra": i["name"], "kuerzel": i["mn"], "quelle": "openfigi"}; continue
        # 2) Namensabgleich fuer den Rest, nur Nicht-US-ISINs (US-Firmen hat OpenFIGI abgedeckt)
        sn = norm(f["n"])
        best = None
        for i in inst:
            if not i["n"] or i["isin"].startswith("US"):
                continue
            st, it = set(sn.split()), set(i["n"].split())
            s_ = max(difflib.SequenceMatcher(None, sn, i["n"]).ratio(), len(st & it) / len(st | it) if st and it else 0)
            if i["isin"] in gehandelt:
                s_ += 0.03
            if best is None or s_ > best[0]:
                best = (s_, i)
        if (not best or best[0] < 0.9) and t in figi:
            i = bester(figi[t])
            out[t] = {"isin": i["isin"], "xetra": i["name"], "kuerzel": i["mn"], "quelle": "openfigi"}; continue
        if best and best[0] >= 0.9:
            out[t] = {"isin": best[1]["isin"], "xetra": best[1]["name"], "kuerzel": best[1]["mn"], "quelle": "name", "treffer": round(best[0], 2)}
            unsicher.append(f"{t} ({f['n']}) → {best[1]['name']} {best[1]['isin']} ({best[0]:.2f})")
        else:
            fehlt.append(f"{t} ({f['n']})" + (f": bester Kandidat {best[1]['name']} {best[1]['isin']} ({best[0]:.2f})" if best else ""))
    os.makedirs("data/kurse", exist_ok=True)
    import datetime
    out["_stand"] = datetime.date.today().isoformat()
    json.dump(out, open("data/kurse/isin-zuordnung.json", "w"), ensure_ascii=False, indent=0)
    md = ["# ISIN-Zuordnung (Xetra-Instrumentenliste)", "",
          f"Spalten der Liste: {len(spalten)}", f"Instrumente nach Filter: {len(inst)}",
          f"Zugeordnet: **{len(out) - 1}** von {len(firmen)}. Unsicher (zum Prüfen): {len(unsicher)}. Ohne Treffer: {len(fehlt)}.",
          "", "Korrekturen als {\"TICKER\": \"ISIN\"} in data/kurse/isin-fest.json eintragen.", "",
          "## Über den Namen zugeordnet (bitte prüfen)", ""] + [f"- {x}" for x in unsicher] + ["", "## Ohne Treffer", ""] + [f"- {x}" for x in fehlt]
    open("data/kurse/isin-zuordnung.md", "w").write("\n".join(md) + "\n")
    print("\n".join(md[:8]))


if __name__ == "__main__":
    main()
