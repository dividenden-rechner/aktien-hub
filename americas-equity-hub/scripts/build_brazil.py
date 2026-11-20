#!/usr/bin/env python3
"""Brasilien aus CVM Dados Abertos (ODbL) -> Universum, Finanzfakten 2010-2025, Hub-Dateien.

Universum: alle Emittenten mit Aktien (ON/PN/Units) im Markt 'Bolsa' laut FCA (valor_mobiliario 2010-2026), auch beendete
Notierungen; Stammdaten aus CAD/FCA geral; LEI ueber GLEIF (CC0) per CNPJ (exakte Kennung, kein Namensabgleich).
ISIN: bleibt leer - die CVM fuehrt keine ISIN, GLEIF liefert fuer brasilianische Aktien keine, die B3 (ISIN-Vergabestelle)
untersagt kommerzielle Nutzung (siehe data/rights/source_license.json).
Finanzen: DFP 2010-2025, Konzern (con), sonst Einzelabschluss (ind); je Wert Datei, Konto, Version, Rohwert, Skala.
Abruf: Crawl-Delay 10 s laut robots.txt der CVM; Rohdateien in data/raw/br (nicht im Repository).
Aufruf: python3 scripts/build_brazil.py [--jahre 2010-2025] [--ohne-gleif] [--nur-cache]"""
import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import zipfile
from datetime import datetime, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
BASIS = os.path.dirname(HIER)
sys.path.insert(0, BASIS)
from app import brazil as br  # noqa: E402
from app import rights  # noqa: E402
from app.common import get  # noqa: E402

ROOT = os.path.dirname(BASIS)
RAW = os.path.join(BASIS, "data", "raw", "br")
UNI = os.path.join(BASIS, "data", "universe", "brazil")
FIN = os.path.join(BASIS, "data", "financials", "brazil")
HUB = os.path.join(ROOT, "data", "americas", "firma")
_letzter_abruf = [0.0]


def laden(pfad_url, name, nur_cache=False):
    """Datei der CVM laden (Crawl-Delay 10 s), lokal zwischenspeichern; vorhandene Dateien werden nicht neu geladen."""
    ziel = os.path.join(RAW, name)
    if os.path.exists(ziel) and os.path.getsize(ziel) > 0:
        return ziel
    if nur_cache:
        return None
    os.makedirs(RAW, exist_ok=True)
    warte = 10 - (time.time() - _letzter_abruf[0])
    if warte > 0:
        time.sleep(warte)
    try:
        daten = get(f"{br.BASIS_URL}/{pfad_url}", timeout=600)
    except Exception as e:  # noqa: BLE001
        print("  nicht ladbar:", pfad_url, str(e)[:80])
        return None
    finally:
        _letzter_abruf[0] = time.time()
    with open(ziel, "wb") as f:
        f.write(daten)
    return ziel


def schreibe(pfad, obj, kompakt=False):
    os.makedirs(os.path.dirname(pfad), exist_ok=True)
    with open(pfad + ".tmp", "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=None if kompakt else 1, separators=(",", ":") if kompakt else None, sort_keys=False)
        f.write("\n")
    os.replace(pfad + ".tmp", pfad)


def ziffern(cnpj):
    return re.sub(r"\D", "", cnpj or "")


# ------------------------------------------------------------------ Universum
def universum(jahre_fca, nur_cache, abruf):
    cad_p = laden("CAD/DADOS/cad_cia_aberta.csv", "cad_cia_aberta.csv", nur_cache)
    cad = {}
    if cad_p:
        for z in br.csv_zeilen(open(cad_p, "rb")):
            cad[ziffern(z["CNPJ_CIA"])] = z
    wp, geral = {}, {}
    for j in jahre_fca:
        p = laden(f"DOC/FCA/DADOS/fca_cia_aberta_{j}.zip", f"fca_cia_aberta_{j}.zip", nur_cache)
        if not p:
            continue
        z = zipfile.ZipFile(p)
        for name in z.namelist():
            if name.startswith(f"fca_cia_aberta_valor_mobiliario_{j}"):
                for r in br.csv_zeilen(z.open(name)):
                    if not br.ist_aktie(r["Valor_Mobiliario"]) or (r.get("Mercado") or "").strip() != "Bolsa":
                        continue
                    kz = (r.get("Codigo_Negociacao") or "").strip().upper()
                    if not re.fullmatch(r"[A-Z][A-Z0-9]{3}\d{1,2}", kz):   # Platzhalter wie 000000 verwerfen
                        continue
                    c = ziffern(r["CNPJ_Companhia"])
                    key = (c, kz)
                    e = wp.setdefault(key, {"cnpj": c, "name": r["Nome_Empresarial"].strip(), "kuerzel": kz,
                                            "valor_mobiliario": r["Valor_Mobiliario"].strip(), "jahre": set(), "zeilen": []})
                    e["jahre"].add(j)
                    e["zeilen"].append((j, r.get("Versao") or "0", r))
            elif name.startswith(f"fca_cia_aberta_geral_{j}"):
                for r in br.csv_zeilen(z.open(name)):
                    geral[ziffern(r["CNPJ_Companhia"])] = r   # spaetere Jahre ueberschreiben fruehere
    issuers, securities, listings = {}, {}, []
    letztes_jahr = max(jahre_fca)
    for (c, kz), e in sorted(wp.items()):
        j, _, r = max(e["zeilen"], key=lambda x: (x[0], int(x[1]) if x[1].isdigit() else 0))
        g = geral.get(c, {})
        k = cad.get(c, {})
        issuers.setdefault(c, {
            "issuer_id": f"BR:CNPJ:{c}", "cnpj": c, "cd_cvm": (k.get("CD_CVM") or g.get("Codigo_CVM") or "").lstrip("0") or None,
            "name": (k.get("DENOM_SOCIAL") or e["name"]).strip(), "name_kurz": (k.get("DENOM_COMERC") or "").strip() or None,
            "sitzland": (g.get("Pais_Origem") or "").strip() or None, "sektor": (k.get("SETOR_ATIV") or g.get("Setor_Atividade") or "").strip() or None,
            "cvm_status": (k.get("SIT") or "").strip() or None, "cvm_status_seit": k.get("DT_INI_SIT") or None,
            "registrierung_beendet": k.get("DT_CANCEL") or None, "lei": None,
            "quellen": [br.QUELLE], "verified": False, "human_review": "pending"})
        gt = br.gattung(kz, e["valor_mobiliario"])
        sec_id = f"BR:CNPJ:{c}:{gt}"
        s = securities.setdefault(sec_id, {"security_id": sec_id, "issuer_id": f"BR:CNPJ:{c}", "isin": None,
                                           "isin_hinweis": "keine Quelle mit Freigabe (CVM ohne ISIN, B3 untersagt kommerzielle Nutzung)",
                                           "gattung": gt, "art": "unit" if gt == "UNIT" else "aktie",
                                           "unit_zusammensetzung": (r.get("Composicao_BDR_Unit") or "").strip() or None,
                                           "quellen": [br.QUELLE], "verified": False, "human_review": "pending"})
        ende = (r.get("Data_Fim_Negociacao") or "").strip() or None
        aktiv = j == letztes_jahr and not ende
        listings.append({"listing_id": f"{kz}@{br.MIC_B3}#{c}", "kuerzel": kz, "mic": br.MIC_B3, "boerse": "B3", "security_id": sec_id,
                         "issuer_id": f"BR:CNPJ:{c}", "segment": (r.get("Segmento") or "").strip() or None,
                         "handel_seit": (r.get("Data_Inicio_Negociacao") or "").strip() or None, "handel_bis": ende,
                         "listung_seit": (r.get("Data_Inicio_Listagem") or "").strip() or None,
                         "status": "aktiv" if aktiv else "beendet_oder_nicht_mehr_gemeldet", "fca_jahre": [min(e["jahre"]), max(e["jahre"])],
                         "handelswaehrung": None, "handelswaehrung_hinweis": "nicht in CVM-Daten angegeben",
                         "quelle": br.QUELLE, "abgerufen": abruf, "verified": False, "human_review": "pending"})
    return issuers, securities, listings, cad


def gleif_lei(issuers, cache_pfad):
    """LEI je CNPJ ueber GLEIF (CC0); Kennung exakt im Format 00.000.000/0000-00."""
    try:
        cache = json.load(open(cache_pfad, encoding="utf-8"))
    except Exception:
        cache = {}
    for c, i in issuers.items():
        if c not in cache:
            fmt = f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}" if len(c) == 14 else c
            try:
                d = json.loads(get("https://api.gleif.org/api/v1/lei-records?" + urllib.parse.urlencode({"filter[entity.registeredAs]": fmt})))["data"]
                cache[c] = [[x["id"], x["attributes"]["entity"]["legalName"]["name"], x["attributes"]["entity"].get("status")] for x in d]
            except Exception:
                continue
            time.sleep(0.5)
        treffer = [t for t in cache.get(c, []) if t[2] == "ACTIVE"] or cache.get(c, [])
        if len(treffer) == 1:
            i["lei"] = treffer[0][0]
            i["lei_quelle"] = "gleif (CNPJ = registeredAs)"
            if "gleif" not in i["quellen"]:
                i["quellen"].append("gleif")
    schreibe(cache_pfad, cache, kompakt=True)


# ------------------------------------------------------------------ Finanzen
DATEIEN = {"DRE": "DRE", "BPA": "BPA", "BPP": "BPP", "DFC": ("DFC_MI", "DFC_MD"), "DMPL": "DMPL"}


def finanzen(jahre_dfp, cnpjs, nur_cache):
    fakten = {}   # cnpj -> list
    for j in jahre_dfp:
        p = laden(f"DOC/DFP/DADOS/dfp_cia_aberta_{j}.zip", f"dfp_cia_aberta_{j}.zip", nur_cache)
        if not p:
            continue
        z = zipfile.ZipFile(p)
        namen = set(z.namelist())
        # je Unternehmen: neueste Version, Exercicio ULTIMO; con bevorzugt, sonst ind
        daten = {}   # (cnpj, basis, typ) -> [zeilen]
        version = {}
        for basis in ("con", "ind"):
            for typ, dat in DATEIEN.items():
                for d in (dat if isinstance(dat, tuple) else (dat,)):
                    n = f"dfp_cia_aberta_{d}_{basis}_{j}.csv"
                    if n not in namen:
                        continue
                    for r in br.csv_zeilen(z.open(n)):
                        c = ziffern(r["CNPJ_CIA"])
                        if c not in cnpjs or r.get("ORDEM_EXERC", "").startswith("PEN"):
                            continue
                        v = int(r.get("VERSAO") or 0)
                        kv = (c, basis)
                        if v < version.get(kv, -1):
                            continue
                        if v > version.get(kv, -1):
                            version[kv] = v
                            for k in [k for k in daten if k[0] == c and k[1] == basis]:
                                del daten[k]
                        daten.setdefault((c, basis, typ), {"datei": n, "zeilen": []})["zeilen"].append(r)
        kap = {}
        n = f"dfp_cia_aberta_composicao_capital_{j}.csv"
        if n in namen:
            for r in br.csv_zeilen(z.open(n)):
                c = ziffern(r["CNPJ_CIA"])
                if c in cnpjs:
                    kap[c] = (r, n)
        for c in sorted({k[0] for k in daten}):
            basis = "con" if any(k[0] == c and k[1] == "con" and k[2] in ("DRE", "BPA") for k in daten) else "ind"
            liste = fakten.setdefault(c, [])

            def neu(kennzahl, wert, einheit, datei, konto, roh=None, skala=None, ende=None, abgeleitet=None):
                f = {"j": j, "ende": ende, "k": kennzahl, "v": wert, "w": "BRL" if einheit != "Stück" else None, "e": einheit,
                     "basis": basis, "datei": datei, "konto": konto, "version": version.get((c, basis)),
                     "quelle": br.QUELLE, "review": "pending"}
                if roh is not None and roh != wert:
                    f["roh"], f["skala"] = roh, skala
                if abgeleitet:
                    f["abgeleitet"] = abgeleitet
                liste.append(f)
                return f

            werte = {}
            for kennzahl, (typ, regel) in br.KENNZAHLEN.items():
                blk = daten.get((c, basis, typ))
                if not blk:
                    continue
                zl = br.waehle(blk["zeilen"], regel)
                if not zl:
                    continue
                w, roh, esc = br.betrag(zl["VL_CONTA"], zl["ESCALA_MOEDA"], zl["CD_CONTA"])
                if w is None or (zl["CD_CONTA"].startswith("3.99") and w == 0):
                    continue
                if kennzahl == "capex":
                    w = abs(w)
                einheit = "BRL je Aktie" if kennzahl in br.JE_AKTIE else "BRL"
                werte[kennzahl] = neu(kennzahl, w, einheit, blk["datei"], f"{zl['CD_CONTA']} {zl['DS_CONTA'].strip()}", roh, esc, zl.get("DT_FIM_EXERC"))
            blk = daten.get((c, basis, "DMPL"))
            if blk:
                aus = br.dmpl_ausschuettungen(blk["zeilen"])
                if "_unklar" in aus:
                    neu("pruefhinweis_dmpl", 1, "Faktor", blk["datei"], aus.pop("_unklar"), ende=blk["zeilen"][0].get("DT_FIM_EXERC"),
                        abgeleitet="Dividenden/JCP nicht ausgewertet (Layout unklar)")
                for art, (w, konten) in aus.items():
                    ende = blk["zeilen"][0].get("DT_FIM_EXERC")
                    werte[art] = neu({"jcp": "jcp", "dividenden": "dividenden", "gemischt": "dividenden_und_jcp_gemischt"}[art], w, "BRL",
                                     blk["datei"], "; ".join(konten), ende=ende)
            ende = next((f["ende"] for f in werte.values() if f.get("ende")), None)
            # abgeleitete Werte (exakte Rechnung, gekennzeichnet)
            if "eigenkapital_gesamt" in werte:
                mi = werte.get("minderheiten", {}).get("v", 0.0)
                neu("eigenkapital", werte["eigenkapital_gesamt"]["v"] - mi, "BRL", werte["eigenkapital_gesamt"]["datei"], "2.03 − Minderheiten",
                    ende=ende, abgeleitet="eigenkapital_gesamt − minderheiten")
            if "finanzschulden_kurz" in werte or "finanzschulden_lang" in werte:
                s = werte.get("finanzschulden_kurz", {}).get("v", 0.0) + werte.get("finanzschulden_lang", {}).get("v", 0.0)
                neu("finanzschulden", s, "BRL", (werte.get("finanzschulden_kurz") or werte.get("finanzschulden_lang"))["datei"],
                    "2.01.x + 2.02.x Empréstimos e Financiamentos", ende=ende, abgeleitet="finanzschulden_kurz + finanzschulden_lang")
            if "operativer_cf" in werte and "capex" in werte:
                neu("free_cashflow", werte["operativer_cf"]["v"] - werte["capex"]["v"], "BRL", werte["operativer_cf"]["datei"], "6.01 − Capex",
                    ende=ende, abgeleitet="operativer_cf − capex")
            if c in kap:
                r, n = kap[c]
                try:
                    ges, tes = int(r["QT_ACAO_TOTAL_CAP_INTEGR"]), int(r["QT_ACAO_TOTAL_TESOURO"] or 0)
                    on, pn = int(r["QT_ACAO_ORDIN_CAP_INTEGR"]), int(r["QT_ACAO_PREF_CAP_INTEGR"])
                except (TypeError, ValueError):
                    ges = None
                if ges:
                    neu("aktien_ausgegeben", ges, "Stück", n, "QT_ACAO_TOTAL_CAP_INTEGR", ende=ende)
                    neu("aktien_ausstehend", ges - tes, "Stück", n, "QT_ACAO_TOTAL_CAP_INTEGR − QT_ACAO_TOTAL_TESOURO", ende=ende,
                        abgeleitet="ausgegeben − eigene Aktien")
                    neu("aktien_on", on, "Stück", n, "QT_ACAO_ORDIN_CAP_INTEGR", ende=ende)
                    neu("aktien_pn", pn, "Stück", n, "QT_ACAO_PREF_CAP_INTEGR", ende=ende)
                    # Pruefung: Gewinn / EPS ~ Aktienzahl? (Aktienzahl teils in Tausend gemeldet) -> nur Hinweis, keine Korrektur
                    g, e = werte.get("gewinn") or werte.get("gewinn_gesamt"), werte.get("eps_on") or werte.get("eps_ohne_gattung")
                    if g and e and e["v"]:
                        q = (g["v"] / e["v"]) / max(ges - tes, 1)
                        if not 0.5 < q < 2:
                            neu("pruefhinweis_aktienzahl", round(q, 3), "Faktor", n, "Gewinn/EPS geteilt durch Aktien ausstehend", ende=ende,
                                abgeleitet="Plausibilitätsprüfung; Abweichung, nicht korrigiert")
        print(f"  DFP {j}: {len({k[0] for k in daten})} Emittenten", flush=True)
    return fakten


# ------------------------------------------------------------------ Hub
HUB_FELDER = {"umsatz": "umsatz", "gewinn": "gewinn", "operatives_ergebnis": "operatives_ergebnis", "bilanzsumme": "bilanzsumme",
              "eigenkapital": "eigenkapital", "operativer_cf": "operativer_cf", "capex": "capex", "finanzschulden_kurz": "schulden_kurz",
              "finanzschulden_lang": "schulden_lang", "eps_on": "eps_verw", "jcp": "jcp_gezahlt"}


def hub_export(issuers, listings, fakten):
    if not rights.publizierbar([br.QUELLE]):
        print("Rechte-Gate: CVM nicht publizierbar - kein Hub-Export")
        return 0
    os.makedirs(HUB, exist_ok=True)
    alt = {f[:-5] for f in os.listdir(HUB) if f.endswith(".SA.json")}
    n = 0
    index_pfad = os.path.join(HUB, "_index.json")
    try:
        index = json.load(open(index_pfad, encoding="utf-8"))
    except Exception:
        index = {}
    index = {k: v for k, v in index.items() if not k.endswith(".SA")}
    for c, i in issuers.items():
        fs = fakten.get(c)
        if not fs:
            continue
        akt = [l for l in listings if l["issuer_id"] == i["issuer_id"] and l["status"] == "aktiv"]
        if not akt:
            continue
        def rang(l):
            m = re.search(r"(\d{1,2})$", l["kuerzel"])
            return {"3": 0, "4": 1, "11": 2}.get(m.group(1) if m else "", 3), l["kuerzel"]
        t = sorted(akt, key=rang)[0]["kuerzel"] + ".SA"
        k = {}
        for f in fs:
            feld = HUB_FELDER.get(f["k"])
            if feld and f.get("ende"):
                k.setdefault(feld, {})[f["ende"]] = f["v"]
        verdacht = {f["j"] for f in fs if f["k"] == "pruefhinweis_aktienzahl"}
        for f in fs:   # Aktienzahl nur, wenn sie zu Gewinn/EPS passt (sonst z. B. in Tausend gemeldet)
            if f["k"] == "aktien_ausstehend" and f["j"] not in verdacht and f.get("ende"):
                k.setdefault("aktien_verw", {})[f["ende"]] = f["v"]
        for f in fs:   # Ersatz, wo die Mutter-Zuordnung bzw. die Gattung fehlt (Banken)
            ers = {"gewinn_gesamt": "gewinn", "eps_ohne_gattung": "eps_verw"}.get(f["k"])
            if ers and f.get("ende"):
                k.setdefault(ers, {}).setdefault(f["ende"], f["v"])
        div = {}
        for f in fs:
            if f["k"] in ("dividenden", "jcp", "dividenden_und_jcp_gemischt") and f.get("ende"):
                div[f["ende"]] = div.get(f["ende"], 0.0) + f["v"]
        if div:
            k["dividenden_gezahlt"] = div
        k = {feld: [[e, r[e]] for e in sorted(r)] for feld, r in k.items() if r}
        enden = sorted({e for r in k.values() for e, _ in r})
        if not enden:
            continue
        fa = {"n": i["name_kurz"] or i["name"], "rechtstraeger": i["name"], "isin": None, "lei": i.get("lei"), "land": "BR",
              "gj": enden[-1], "w": "BRL", "std": "IFRS (CVM DFP)", "quelle": "CVM", "lizenz": "ODbL 1.0 – Quelle: CVM Dados Abertos",
              "kuerzel_b3": [l["kuerzel"] for l in akt], "cnpj": c, "human_review": "pending", "verified": False,
              "hinweis": "Dividenden und JCP getrennt in der CVM-Quelle; dividenden_gezahlt = Dividenden + JCP (brutto, laut DMPL).",
              "k": k}
        schreibe(os.path.join(HUB, f"{t}.json"), fa, kompakt=True)
        alt.discard(t)
        index[t] = [fa["n"], None, "BR", fa["gj"]]
        n += 1
    for t in alt:
        os.remove(os.path.join(HUB, f"{t}.json"))
    schreibe(index_pfad, dict(sorted(index.items())), kompakt=True)
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jahre", default="2010-2025")
    ap.add_argument("--ohne-gleif", action="store_true")
    ap.add_argument("--nur-cache", action="store_true")
    a = ap.parse_args()
    v, b = (int(x) for x in a.jahre.split("-"))
    abruf = datetime.now(timezone.utc).isoformat(timespec="seconds")
    issuers, securities, listings, cad = universum(list(range(v, b + 2)), a.nur_cache, abruf)   # FCA bis b+1 (aktueller Stand)
    if not a.ohne_gleif:
        gleif_lei(issuers, os.path.join(UNI, "gleif_cache.json"))
    fakten = finanzen(list(range(v, b + 1)), set(issuers), a.nur_cache)
    # Ausgabe Universum
    schreibe(os.path.join(UNI, "issuers.json"), list(issuers.values()))
    schreibe(os.path.join(UNI, "securities.json"), sorted(securities.values(), key=lambda s: s["security_id"]))
    schreibe(os.path.join(UNI, "listings.json"), sorted(listings, key=lambda l: l["listing_id"]))
    review = [{"issuer_id": i["issuer_id"], "name": i["name"], "grund": "ohne Finanzdaten (DFP)"} for c, i in issuers.items() if c not in fakten]
    review += [{"security_id": s["security_id"], "grund": "ISIN offen", "aktion": "ISIN aus Quelle mit Freigabe bestätigen"} for s in securities.values()]
    schreibe(os.path.join(UNI, "review.json"), review)
    # Finanzen je Emittent
    os.makedirs(FIN, exist_ok=True)
    for c, fs in fakten.items():
        i = issuers[c]
        schreibe(os.path.join(FIN, f"{c}.json"), {"issuer_id": i["issuer_id"], "name": i["name"], "quelle": br.QUELLE,
                                                  "lizenz": "ODbL 1.0 (CVM Dados Abertos)", "fakten": sorted(fs, key=lambda f: (f["j"], f["k"]))}, kompakt=True)
    n_hub = hub_export(issuers, listings, fakten)
    jahre = {}
    for fs in fakten.values():
        n = len({f["j"] for f in fs if f["k"] in ("gewinn", "gewinn_gesamt")})
        jahre[n] = jahre.get(n, 0) + 1
    summary = {"erstellt": abruf, "quelle": "CVM Dados Abertos (ODbL)", "emittenten": len(issuers),
               "emittenten_aktiv": len({l["issuer_id"] for l in listings if l["status"] == "aktiv"}),
               "wertpapiere": len(securities), "notierungen": len(listings), "notierungen_aktiv": sum(1 for l in listings if l["status"] == "aktiv"),
               "gattungen": {g: sum(1 for s in securities.values() if s["gattung"] == g) for g in sorted({s["gattung"] or "?" for s in securities.values()})},
               "mit_lei": sum(1 for i in issuers.values() if i["lei"]), "mit_isin": 0,
               "mit_finanzdaten": len(fakten), "jahre_mit_gewinn_verteilung": dict(sorted(jahre.items(), reverse=True)),
               "mit_jcp": sum(1 for fs in fakten.values() if any(f["k"] == "jcp" and f["v"] for f in fs)),
               "hub_dateien": n_hub}
    schreibe(os.path.join(UNI, "summary.json"), summary)
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
