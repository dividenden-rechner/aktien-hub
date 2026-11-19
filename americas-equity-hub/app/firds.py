"""ESMA FIRDS (amtliches EU-Instrumentenregister): ISIN, voller Name, CFI-Code und LEI fuer Instrumente eines Landes,
die an EU-Handelsplaetzen gehandelt werden. Dient zur ISIN-/LEI-Zuordnung nordamerikanischer Aktien."""
import json
import re
import urllib.parse

from .common import enthalten, get, isin_gueltig, klasse, norm_tokens, wort_passt

URL = "https://registers.esma.europa.eu/solr/esma_registers_firds/select"


def laden(praefixe=("CA",), cfi=("ES*", "CI*", "EU*", "CE*")):
    """{isin: {name, cfi, lei, mics:set, aktiv:bool}} fuer alle ISINs mit den Praefixen und CFI-Gruppen."""
    out = {}
    for p in praefixe:
        q = f"isin:{p}* AND (" + " OR ".join(f"gnr_cfi_code:{c}" for c in cfi) + ")"
        start = 0
        while True:
            params = {"q": q, "rows": 10000, "start": start, "wt": "json", "sort": "id asc",
                      "fl": "isin,gnr_full_name,gnr_cfi_code,lei,mic,mrkt_trdng_trmination_date"}
            d = json.loads(get(URL + "?" + urllib.parse.urlencode(params), timeout=180))["response"]
            for x in d["docs"]:
                i = x.get("isin")
                if not isin_gueltig(i):
                    continue
                e = out.setdefault(i, {"name": x.get("gnr_full_name"), "cfi": x.get("gnr_cfi_code"), "lei": x.get("lei"),
                                       "mics": set(), "aktiv": False})
                e["mics"].add(x.get("mic"))
                e["aktiv"] |= not x.get("mrkt_trdng_trmination_date")
                if not e["lei"] and x.get("lei"):
                    e["lei"] = x["lei"]
            start += len(d["docs"])
            if not d["docs"] or start >= d["numFound"]:
                break
    return out


def zuordnen(name, ticker, firds, de_gehandelt=frozenset()):
    """Name/Ticker eines Indexmitglieds -> (isin, lei, methode, kandidaten). Angenommen wird nur ein eindeutiger
    Treffer: alle bedeutungstragenden Woerter des Namens kommen im FIRDS-Namen vor, gleiche Gattung (Klasse A/B), aktive
    Aktie. Mehrere ISINs: Vorrang fuer in Deutschland gehandelte; bleibt es mehrdeutig, bleibt die ISIN leer."""
    ziel = norm_tokens(name)
    abgeschnitten = len(name or "") >= 33
    if abgeschnitten and len(ziel) > 1:   # ETF-Namen sind nach ~34 Zeichen abgeschnitten: letztes Wort unsicher
        letztes = (norm_tokens((name or "").rsplit(" ", 1)[-1]) or {None}).pop()
        ziel.discard(letztes)
    kl = klasse(ticker) or klasse(name)
    if not ziel:
        return None, None, "kein_name", []
    kand, ausdruecklich = [], []
    for isin, e in firds.items():
        if not e["aktiv"] or not (e["cfi"] or "").startswith(("ES", "CI", "EU", "CE")):
            continue
        tk = norm_tokens(e["name"])
        # beide Richtungen: jedes Wort hier hat ein Gegenstueck dort; bei abgeschnittenem Namen darf dort eins uebrig sein
        rest = [w for w in tk if not any(wort_passt(w, z) for z in ziel)]
        if not enthalten(ziel, tk) or len(rest) > (1 if abgeschnitten else 0):
            continue
        if ticker.endswith(".UN") and not re.search(r"UNIT|L\.?P\.?\b|TRUST|REIT|FUND|PARTNERS", (e["name"] or "").upper()):
            continue   # Units (Trust/Partnership/REIT) nie einer Aktiengesellschaft gleichen Namens zuordnen
        fk = klasse(e["name"])
        if kl and fk and kl != fk:
            continue
        kand.append(isin)
        if kl and fk == kl:
            ausdruecklich.append(isin)
    if len(set(ausdruecklich)) == 1:   # eine ISIN nennt genau die Gattung des Tickers
        kand = ausdruecklich
    if len(set(kand)) > 1 and de_gehandelt:
        de = [i for i in kand if i in de_gehandelt]
        if de:
            kand = de
    kand = sorted(set(kand))
    if len(kand) == 1:
        return kand[0], firds[kand[0]].get("lei"), "esma_firds_name_eindeutig", kand
    return None, None, ("mehrdeutig" if kand else "nicht_gefunden"), kand
