#!/usr/bin/env python3
"""Zuordnung Ticker -> ISIN fuer die Firmen aus data/sec/fundamentals.json (ab 11.11.2026).
Quelle: offizielle Liste aller auf Xetra handelbaren Instrumente der Deutschen Boerse (t7-xetr-allTradableInstruments.csv).
Abgleich ueber den Firmennamen (SEC-Name gegen Xetra-Name), bevorzugt US-ISINs fuer US-Firmen und Werte, die zuletzt
gehandelt wurden. Feste Zuordnungen in data/kurse/isin-fest.json gehen immer vor. Schreibt data/kurse/isin-zuordnung.json
und data/kurse/isin-zuordnung.md (unsichere Treffer zum Pruefen)."""
import csv, difflib, io, json, os, re, urllib.request

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
    out, unsicher, fehlt = {}, [], []
    for t, f in sorted(firmen.items()):
        if t in fest:
            out[t] = {"isin": fest[t], "quelle": "fest"}; continue
        sn = norm(f["n"])
        best = None
        for i in inst:
            if not i["n"]:
                continue
            s = difflib.SequenceMatcher(None, sn, i["n"]).ratio()
            st, it = set(sn.split()), set(i["n"].split())
            if st and it:
                s = max(s, len(st & it) / len(st | it))
            if f.get("std") == "US-GAAP" and f.get("w") == "USD":
                s += 0.08 if i["isin"].startswith("US") else -0.15
            if i["isin"] in gehandelt:
                s += 0.05
            if best is None or s > best[0]:
                best = (s, i)
        if not best or best[0] < 0.62:
            fehlt.append(f"{t} ({f['n']})" + (f": bester Kandidat {best[1]['name']} {best[1]['isin']} ({best[0]:.2f})" if best else ""))
            continue
        s, i = best
        out[t] = {"isin": i["isin"], "xetra": i["name"], "kuerzel": i["mn"], "treffer": round(s, 2)}
        if s < 0.85:
            unsicher.append(f"{t} ({f['n']}) → {i['name']} {i['isin']} ({s:.2f})")
    os.makedirs("data/kurse", exist_ok=True)
    json.dump(out, open("data/kurse/isin-zuordnung.json", "w"), ensure_ascii=False, indent=0)
    md = ["# ISIN-Zuordnung (Xetra-Instrumentenliste)", "",
          f"Spalten der Liste: {len(spalten)}", f"Instrumente nach Filter: {len(inst)}",
          f"Zugeordnet: **{len(out)}** von {len(firmen)}. Unsicher (zum Prüfen): {len(unsicher)}. Ohne Treffer: {len(fehlt)}.",
          "", "Korrekturen als {\"TICKER\": \"ISIN\"} in data/kurse/isin-fest.json eintragen.", "",
          "## Unsicher", ""] + [f"- {x}" for x in unsicher] + ["", "## Ohne Treffer", ""] + [f"- {x}" for x in fehlt]
    open("data/kurse/isin-zuordnung.md", "w").write("\n".join(md) + "\n")
    print("\n".join(md[:8]))


if __name__ == "__main__":
    main()
