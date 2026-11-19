import json
import os
import sys

import pytest

BASIS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASIS)
sys.path.insert(0, os.path.join(BASIS, "scripts"))
from app import canada, firds  # noqa: E402
from app.common import isin_gueltig, isin_pruefziffer, klasse  # noqa: E402
from sec_cik import zuordnen as sec_zuordnen  # noqa: E402

UNI = os.path.join(BASIS, "data", "universe", "canada")


# ---------- ISIN
@pytest.mark.parametrize("isin", ["CA7800871021", "CA8787422044", "BRPETRACNPR6", "MX01AC100006", "US0378331005"])
def test_isin_gueltig(isin):
    assert isin_gueltig(isin)


@pytest.mark.parametrize("isin", ["CA7800871022", "CA780087102", "", None, "ca7800871021"])
def test_isin_ungueltig(isin):
    assert not isin_gueltig(isin)


def test_pruefziffer():
    assert isin_pruefziffer("CA780087102") == "1"


# ---------- XIC-Bestandsliste
XIC = '''﻿Fund Holdings as of,"Nov 18, 2026"

Ticker,Name,Sector,Asset Class,Market Value,Weight (%),Notional Value,Shares,Price,Location,Exchange,Currency,FX Rate,Market Currency
"RY","ROYAL BANK OF CANADA","Financials","Equity","1","5.10","1","1","1","Canada","Toronto Stock Exchange","CAD","1.00","CAD"
"TECK.B","TECK RESOURCES SUBORDINATE VOTING","Materials","Equity","1","0.50","1","1","1","Canada","Toronto Stock Exchange","CAD","1.00","CAD"
"REI.UN","RIOCAN REAL ESTATE INVESTMENT TRUS","Real Estate","Equity","1","0.10","1","1","1","Canada","Toronto Stock Exchange","CAD","1.00","CAD"
"VALX","VALIENTE RESOURCES","Other","Equity","1","0.00","1","1","1","Canada","TSX Venture Exchange","CAD","1.00","CAD"
"2299955D","CONSTELLATION SOFTWARE INC","IT","Equity","0","0.00","0","1","0","Canada","Toronto Stock Exchange","CAD","1.00","CAD"
"CAD","CAD CASH","Cash","Cash","1","0.1","1","1","1","Canada","-","CAD","1.00","CAD"
'''


def test_parse_xic_stichtag_und_filter():
    stichtag, m, verworfen = canada.parse_xic(XIC)
    assert stichtag == "2026-11-18"
    assert [x["ticker"] for x in m] == ["RY", "TECK.B", "REI.UN"]
    assert {v["ticker"] for v in verworfen} == {"VALX", "2299955D"}   # TSXV-Restbestand und Platzhalter
    assert all(x["waehrung"] == "CAD" for x in m)


def test_gattungen_und_arten():
    assert canada.klasse_aus("TECK.B", "TECK RESOURCES") == "B"
    assert canada.klasse_aus("BN", "BROOKFIELD CLASS A") == "A"
    assert canada.klasse_aus("REI.UN", "RIOCAN REIT") is None
    assert canada.wertpapierart("REI.UN", "RIOCAN REAL ESTATE INVESTMENT TRUST") == "unit_reit"
    assert canada.wertpapierart("BIP.UN", "BROOKFIELD INFRASTRUCTURE PARTNERS") == "unit_trust_or_partnership"
    assert canada.wertpapierart("ATZ", "ARITZIA SUBORDINATE VOTING") == "share_subordinate_voting"
    assert canada.hub_kuerzel("TECK.B") == "TECK-B.TO" and canada.hub_kuerzel("T") == "T.TO"   # T = Telus, nicht AT&T
    assert klasse("Brookfield Corp. Registered Shares Cl.A  o.N.") == "A"


# ---------- FIRDS-Zuordnung
FD = {
    "CA8787422044": {"name": "Teck Resources Ltd. Reg. Shares(Sub Vtg) Cl.B o.N.", "cfi": "ESVUFR", "lei": "L1", "aktiv": True},
    "CA8787421053": {"name": "Teck Resources Ltd. Reg. Shares Cl.A o.N.", "cfi": "ESVUFR", "lei": "L1", "aktiv": True},
    "CA33767E2024": {"name": "FirstService Corp. Registered Shares o.N.", "cfi": "ESVUFR", "lei": "L2", "aktiv": True},
    "BMG348041077": {"name": "First Pacific Co. Ltd. Registered Shares", "cfi": "ESVUFR", "lei": "L3", "aktiv": True},
    "CA11276H1064": {"name": "Brookfield Infrastructure Corp Reg.Exch.Subord.Vot.Shs.A o.N.", "cfi": "ESVUFR", "lei": "L4", "aktiv": True},
    "CA62930A1021": {"name": "NGEx Minerals Ltd. Registered Shares o.N.", "cfi": "ESVUFR", "lei": "L5", "aktiv": True},
    "CA62930A2011": {"name": "NGEx Minerals Ltd. Registered Shares New o.N.", "cfi": "ESVUFR", "lei": "L5", "aktiv": True},
    "CA13645T1003": {"name": "CANADIAN PACIFIC RAILWAY LTD. Registered Shares o.N.", "cfi": "ESVUFR", "lei": "L6", "aktiv": False},
}


def test_gattung_entscheidet():
    assert firds.zuordnen("TECK RESOURCES SUBORDINATE VOTING", "TECK.B", FD)[0] == "CA8787422044"


def test_kein_praefix_fehltreffer():
    assert firds.zuordnen("FIRSTSERVICE SUBORDINATE VOTING", "FSV", FD)[0] == "CA33767E2024"   # nicht First Pacific


def test_units_nie_auf_aktiengesellschaft():
    assert firds.zuordnen("BROOKFIELD INFRASTRUCTURE PARTNERS", "BIP.UN", FD)[0] is None


def test_mehrdeutig_bleibt_leer():
    isin, lei, methode, kand = firds.zuordnen("NGEX MINERALS", "NGEX", FD)
    assert isin is None and methode == "mehrdeutig" and len(kand) == 2


def test_mehrdeutig_mit_deutschem_handel_eindeutig():
    assert firds.zuordnen("NGEX MINERALS", "NGEX", FD, frozenset({"CA62930A2011"}))[0] == "CA62930A2011"


def test_beendete_notierung_nicht_verwendet():
    assert firds.zuordnen("CANADIAN PACIFIC RAILWAY", "CP", FD)[0] is None


# ---------- SEC-CIK
def test_sec_cik_name_entscheidet_nicht_das_kuerzel():
    lst = [{"hub_kuerzel": "RY.TO", "ticker": "RY", "name": "ROYAL BANK OF CANADA"},
           {"hub_kuerzel": "T.TO", "ticker": "T", "name": "TELUS"}]
    sec = [(1000275, "ROYAL BANK OF CANADA", "RY", "NYSE"), (732717, "AT&T INC.", "T", "NYSE"), (868675, "TELUS CORP", "TU", "NYSE")]
    erg, _ = sec_zuordnen(lst, sec)
    assert erg["RY.TO"][0] == 1000275
    assert erg["T.TO"][0] == 868675   # gleiches Kuerzel T bei der SEC ist AT&T, der Name entscheidet


# ---------- erzeugte Daten: Dubletten, Quellen, verified, Datumslogik
def _lade(name):
    p = os.path.join(UNI, name)
    if not os.path.exists(p):
        pytest.skip("Universum noch nicht erzeugt")
    return json.load(open(p, encoding="utf-8"))


def test_keine_dubletten():
    secs, lst, iss = _lade("securities.json"), _lade("listings.json"), _lade("issuers.json")
    isins = [s["isin"] for s in secs if s["isin"]]
    assert len(isins) == len(set(isins))
    assert len({l["listing_id"] for l in lst}) == len(lst)
    assert len({i["issuer_id"] for i in iss}) == len(iss)
    assert len({l["hub_kuerzel"] for l in lst}) == len(lst)


def test_isins_gueltig_und_konsistent():
    secs = {s["security_id"]: s for s in _lade("securities.json")}
    for l in _lade("listings.json"):
        s = secs[l["security_id"]]
        assert l["isin"] == s["isin"]
        assert s["isin"] is None or isin_gueltig(s["isin"])
        if s["isin"] is None:
            assert s["isin_methode"] in ("mehrdeutig", "nicht_gefunden", "kein_name")


def test_nichts_verified_und_review_pending():
    for name in ("issuers.json", "securities.json", "listings.json"):
        for r in _lade(name):
            assert r.get("verified") is False and r.get("human_review") == "pending"


def test_quellen_und_stichtag():
    im = _lade("index_memberships.json")
    assert im["index"]["stichtag"] and len(im["index"]["stichtag"]) == 10
    assert im["index"]["abgerufen"][:10] >= im["index"]["stichtag"]
    for l in _lade("listings.json"):
        assert l["quelle"] and l["abgerufen"] and l["mic"] == "XTSE"
    for m in im["mitglieder"]:
        assert m["stand"] == im["index"]["stichtag"] and m["quelle"]


def test_ohne_isin_im_review():
    rev = {r["listing_id"] for r in _lade("review.json")}
    for s in _lade("securities.json"):
        if not s["isin"]:
            assert s["security_id"].split(":", 1)[1] in rev
