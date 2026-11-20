#!/usr/bin/env python3
"""ISIN fuer die Japan- und Korea-Firmen des Asien-Universums (asia-equity-hub/reports/universe/identity_map.json),
damit der Kurs aus den Tagesdateien der Deutschen Boerse gefunden wird.

Japan: GLEIF (offizielles LEI-Register; LEI -> ISIN stammt von den nationalen Vergabestellen ueber ANNA).
  Suche nach dem japanischen Firmennamen aus der EDINET-Liste (exakt, Land JP), sonst nach dem englischen Namen.
  Unter den ISINs des Rechtstraegers nur Stammaktien: JP3 + 5-stellige Emittentennummer + 000 + Pruefziffer
  (Anleihen tragen andere Endungen). Mehrere Treffer: die in Deutschland gehandelte.
Korea: Stammaktien-ISIN nach dem Aufbau der koreanischen Vergabestelle: KR7 + 6-stelliger Boersencode + 00 + Pruefziffer.
  Koreanische Stammaktien werden in Deutschland praktisch nicht gehandelt; der Kurs fehlt dann (wird so vermerkt).
Ausgabe: data/asien/isin.json {ticker: {isin, methode, lei?, in_de_gehandelt}}; nur Kandidaten, human_review: pending.
Aufruf: python3 tools/asien_isin.py
"""
import glob, json, os, re, time, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = {"User-Agent": "dividenden-rechner.de Datensammlung"}
JP_AKTIE = re.compile(r"^JP3\d{5}000\d$")


def pruefziffer(basis):
    """ISIN-Pruefziffer (ISO 6166): Buchstaben -> Zahlen (A=10 ... Z=35), dann Luhn."""
    ziffern = "".join(str(int(c, 36)) for c in basis)
    summe = 0
    for i, c in enumerate(reversed(ziffern)):
        d = int(c)
        if i % 2 == 0:
            d *= 2
            if d > 9:
                d -= 9
        summe += d
    return str((10 - summe % 10) % 10)


def isin_gueltig(isin):
    return bool(re.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}\d", isin)) and pruefziffer(isin[:11]) == isin[11]


def get(url):
    for v in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return json.loads(r.read())
        except Exception:
            if v == 3:
                raise
            time.sleep(10 * (v + 1))


def gehandelt():
    """Alle ISINs aus den Tagesdateien der Deutschen Boerse (Xetra, Tradegate, Frankfurt)."""
    isins = set((json.load(open(os.path.join(ROOT, "data/kurse/xetra-letzter.json"))) or {}).get("k", {}))
    for platz in ("xetra", "tradegate", "frankfurt"):
        dateien = sorted(glob.glob(os.path.join(ROOT, "data", "kurse", platz, "*.json")))
        for p in dateien[-3:]:
            isins |= set(json.load(open(p)).get("k", {}))
    return isins


def norm(n):
    n = (n or "").upper().replace("株式会社", "").replace("（株）", "")
    n = re.sub(r"\b(CORPORATION|CORP|COMPANY|CO|LTD|LIMITED|INC|HOLDINGS?|KABUSHIKI KAISHA|K\.?K)\b\.?", " ", n)
    return re.sub(r"[^0-9A-Z\u3040-\u30ff\u4e00-\u9fff]+", "", n)


def gleif_jp(namen, de):
    """Volltextsuche (Land JP); angenommen wird nur ein Rechtstraeger, dessen offizieller oder weiterer Name nach
    Normalisierung (ohne 株式会社, Corporation, Co., Ltd. usw.) genau einem unserer Namen entspricht."""
    ziel = {norm(n) for n in namen if n and norm(n)}
    for name in [n for n in namen if n]:
        such = re.sub(r"(株式会社|CORPORATION|CO\.,? ?LTD\.?|INC\.?)", " ", name, flags=re.I).strip()
        j = get("https://api.gleif.org/api/v1/lei-records?" + urllib.parse.urlencode(
            {"filter[fulltext]": such, "filter[entity.legalAddress.country]": "JP", "page[size]": 10}))
        time.sleep(1)
        for d in j.get("data", []):
            ent = d["attributes"]["entity"]
            alle = [ent["legalName"]["name"]] + [o.get("name") for o in ent.get("otherNames") or []] + \
                   [o.get("name") for o in ent.get("transliteratedOtherNames") or []]
            if not ziel & {norm(n) for n in alle if n}:
                continue
            lei = d["id"]
            kand, seite = [], 1
            while seite < 10:
                r = get(f"https://api.gleif.org/api/v1/lei-records/{lei}/isins?page[size]=200&page[number]={seite}")
                kand += [x["attributes"]["isin"] for x in r.get("data", []) if x["attributes"]["isin"].startswith("JP3")]
                if seite >= ((r.get("meta") or {}).get("pagination") or {}).get("lastPage", 1):
                    break
                seite += 1
                time.sleep(1)
            time.sleep(1)
            aktien = sorted({k for k in kand if JP_AKTIE.match(k) and isin_gueltig(k)}, key=lambda k: (k not in de, k))
            if aktien:
                return {"isin": aktien[0], "lei": lei, "methode": "gleif_lei_isin", "gleif_name": ent["legalName"]["name"],
                        "weitere": aktien[1:] or None}
            # nur Anleihen gemeldet: Emittentennummer (Stellen 4-8) -> Stammaktie JP3 + Nummer + 000 + Pruefziffer;
            # angenommen nur, wenn genau diese ISIN in den Handelsdateien der Deutschen Boerse vorkommt
            abgeleitet = sorted({"JP3" + k[3:8] + "000" + pruefziffer("JP3" + k[3:8] + "000") for k in kand if re.match(r"^JP3\d{5}", k)})
            treffer = [k for k in abgeleitet if k in de]
            if len(treffer) == 1:
                return {"isin": treffer[0], "lei": lei, "methode": "jp_isin_aufbau_aus_gleif_emittentennummer_in_de_gehandelt",
                        "gleif_name": ent["legalName"]["name"]}
            return {"lei": lei, "methode": "gleif_lei_ohne_aktien_isin", "gleif_name": ent["legalName"]["name"]}
    return None


def main():
    ident = json.load(open(os.path.join(ROOT, "asia-equity-hub/reports/universe/identity_map.json"), encoding="utf-8"))["entries"]
    pfad = os.path.join(ROOT, "data", "asien", "isin.json")
    alt = json.load(open(pfad, encoding="utf-8")) if os.path.exists(pfad) else {}
    de = gehandelt()
    out = {}
    for e in ident:
        t, st = e.get("ticker"), e.get("status")
        if not t or st not in ("confirmed_official_list",):
            continue
        if e["market"] == "Südkorea" and re.fullmatch(r"\d{6}", e.get("exchange_code") or ""):
            basis = "KR7" + e["exchange_code"] + "00"
            isin = basis + pruefziffer(basis)
            out[t] = {"isin": isin, "methode": "kr_isin_aufbau_stammaktie", "in_de_gehandelt": isin in de, "human_review": "pending"}
        elif e["market"] == "Japan":
            if alt.get(t, {}).get("lei"):   # schon gefunden: nicht erneut suchen
                out[t] = dict(alt[t], in_de_gehandelt=alt[t].get("isin") in de)
                continue
            try:
                r = gleif_jp([e.get("official_name_local"), e.get("official_name")], de)
            except Exception as ex:  # noqa: BLE001
                print(t, "GLEIF-Fehler", str(ex)[:80])
                r = None
            if r:
                r = {k: v for k, v in r.items() if v}
                r.update(in_de_gehandelt=r.get("isin") in de, human_review="pending")
                out[t] = r
            print(t, (r or {}).get("isin"), (r or {}).get("in_de_gehandelt"), flush=True)
    os.makedirs(os.path.dirname(pfad), exist_ok=True)
    json.dump(dict(sorted(out.items())), open(pfad, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    jp = [v for k, v in out.items() if k.endswith(".T") and v.get("isin")]
    print(f"Japan: {len(jp)} ISINs, davon in Deutschland gehandelt {sum(v['in_de_gehandelt'] for v in jp)}; "
          f"Korea: {len(out) - len(jp)} ISINs, gehandelt {sum(v['in_de_gehandelt'] for k, v in out.items() if not k.endswith('.T'))}")


if __name__ == "__main__":
    main()
