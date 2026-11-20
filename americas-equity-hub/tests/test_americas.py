import json
import os
import sys

import pytest

BASIS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(BASIS)
sys.path.insert(0, BASIS)
sys.path.insert(0, os.path.join(BASIS, "scripts"))
from app import brazil as br  # noqa: E402
from app import rights  # noqa: E402
from app.common import isin_gueltig, isin_pruefziffer  # noqa: E402
import build_sec_universe as su  # noqa: E402
import export_hub  # noqa: E402

UNI = os.path.join(BASIS, "data", "universe")


# ================================================================ ISIN
@pytest.mark.parametrize("isin", ["CA7800871021", "CA8787422044", "BRPETRACNPR6", "MX01AC100006", "US0378331005"])
def test_isin_gueltig(isin):
    assert isin_gueltig(isin)


@pytest.mark.parametrize("isin", ["CA7800871022", "CA780087102", "", None, "ca7800871021"])
def test_isin_ungueltig(isin):
    assert not isin_gueltig(isin)


def test_pruefziffer():
    assert isin_pruefziffer("CA780087102") == "1"


# ================================================================ Rechte-Gate
def test_register_vollstaendig_und_gueltig():
    reg = rights.register()
    d = json.load(open(rights.PFAD, encoding="utf-8"))
    for q in reg.values():
        assert set(q["rechte"]) == set(d["zwecke"])
        assert q["agb_url"] is None or q["agb_url"].startswith("https://")
        assert q["abgerufen"] and q["beleg"]


@pytest.mark.parametrize("quelle,erwartet", [("cvm_dados_abertos", True), ("sec_edgar", True), ("gleif", True),
                                             ("b3_website", False), ("tmx_website", False), ("blackrock_ishares_holdings", False),
                                             ("bmv_website", False), ("biva_website", False), ("cnbv", False), ("spdji", False),
                                             ("sedar_plus", False), ("esma_firds", False), ("gibt_es_nicht", False)])
def test_publizierbar(quelle, erwartet):
    assert rights.publizierbar([quelle]) is erwartet


def test_unknown_ist_nicht_allowed(tmp_path):
    reg = {"x": {"source_id": "x", "rechte": {z: "allowed" for z in rights.EXPORT_ZWECKE}}}
    assert rights.publizierbar(["x"], reg)
    reg["x"]["rechte"]["oeffentliche_api"] = "unknown"
    assert not rights.publizierbar(["x"], reg)
    reg["x"]["rechte"]["oeffentliche_api"] = "restricted"
    assert not rights.publizierbar(["x"], reg)


def test_gemischte_quellen_nur_wenn_alle_erlaubt():
    assert rights.publizierbar(["sec_edgar", "gleif"])
    assert not rights.publizierbar(["sec_edgar", "b3_website"])
    assert not rights.publizierbar([])


def test_filtern_entfernt_gesperrte_und_quellenlose_felder():
    d = {"umsatz": 1, "isin": "BRPETRACNPR6", "kurs": 30.0, "ohne": 5,
         "_quellen": {"umsatz": ["cvm_dados_abertos"], "isin": ["b3_website"], "kurs": ["b3_website"]}}
    assert rights.filtern(d) == {"umsatz": 1}


def test_hub_export_gibt_keine_gesperrte_isin_aus():
    f = {"n": "X", "gj": "2025-12-31", "k": {"umsatz": [["2025-12-31", 1.0]]}}
    i = {"cik": 1, "lei": "LEI1"}
    gesperrt = export_hub.firma_datensatz(f, i, {"isin": "CA0000000000", "quellen": ["esma_firds"]}, "CA")
    assert "isin" not in gesperrt and gesperrt["k"] == f["k"] and gesperrt["lei"] == "LEI1"
    frei = export_hub.firma_datensatz(f, i, {"isin": "CA7800871021", "quellen": ["gleif"]}, "CA")
    assert frei["isin"] == "CA7800871021"


def test_veroeffentlichte_hubdateien_ohne_gesperrte_quellen():
    ordner = os.path.join(ROOT, "data", "americas", "firma")
    if not os.path.isdir(ordner):
        pytest.skip("keine Hub-Dateien")
    for fn in os.listdir(ordner):
        assert not fn.endswith(".TO.json"), "Altlast aus BlackRock-Proxy"
        if fn.startswith("_") or not fn.endswith(".json"):
            continue
        d = json.load(open(os.path.join(ordner, fn), encoding="utf-8"))
        assert d.get("verified") is False and d.get("human_review") == "pending"
        assert d.get("quelle") in ("SEC", "CVM")
        if d["land"] == "BR":
            assert d.get("isin") is None   # keine freigegebene ISIN-Quelle fuer Brasilien


# ================================================================ Brasilien
def test_gattung():
    assert br.gattung("PETR4", "Ações Preferenciais") == "PN"
    assert br.gattung("PETR3", "Ações Ordinárias") == "ON"
    assert br.gattung("USIM5", "Ações Preferenciais") == "PNA"
    assert br.gattung("TAEE11", "Units") == "UNIT"
    assert br.gattung("BBAS3", "") == "ON"
    assert br.gattung("XXXX4", "Ações Ordinárias") == "ON"   # CVM-Angabe geht vor


def test_einheiten_eps_nie_skaliert():
    assert br.betrag("497549000.0", "MIL", "3.01")[0] == 497549000000.0
    assert br.betrag("8.54", "MIL", "3.99.01.01")[0] == 8.54
    assert br.betrag("12.5", "UNIDADE", "3.01")[0] == 12.5
    assert br.betrag("", "MIL", "3.01")[0] is None


def _z(konto, ds, wert, spalte=None, escala="MIL"):
    z = {"CD_CONTA": konto, "DS_CONTA": ds, "VL_CONTA": wert, "ESCALA_MOEDA": escala}
    if spalte:
        z["COLUNA_DF"] = spalte
    return z


def test_kennzahl_auswahl_bank_und_industrie():
    dre = [_z("3.01", "Receita de Venda de Bens e/ou Serviços", "100"), _z("3.11", "Lucro/Prejuízo Consolidado do Período", "10"),
           _z("3.11.01", "Atribuído a Sócios da Empresa Controladora", "9")]
    assert br.waehle(dre, br.KENNZAHLEN["umsatz"][1])["VL_CONTA"] == "100"
    assert br.waehle(dre, br.KENNZAHLEN["gewinn"][1])["VL_CONTA"] == "9"
    bank = [_z("3.01", "Receitas de Intermediação Financeira", "300"), _z("3.11", "Lucro ou Prejuízo Líquido Consolidado do Período", "16")]
    assert br.waehle(bank, br.KENNZAHLEN["umsatz"][1]) is None   # Bankertraege sind kein Umsatz
    assert br.waehle(bank, br.KENNZAHLEN["erloes_3_01_sonstige"][1])["VL_CONTA"] == "300"
    assert br.waehle(bank, br.KENNZAHLEN["gewinn_gesamt"][1])["VL_CONTA"] == "16"


def test_dividenden_und_jcp_getrennt():
    pl = "Patrimônio Líquido"
    dmpl = [_z("5.04.06", "Dividendos", "-20000", pl), _z("5.04.07", "Juros sobre Capital Próprio", "-13704", pl),
            _z("5.04.08", "Dividendos e Juros sobre Capital Próprio Intercalares", "-15489", pl),
            _z("5.04.11", "Dividendos prescritos", "828", pl), _z("5.04.06", "Dividendos", "-99999", "Reservas de Lucro"),
            _z("5.05.01", "Lucro Líquido do Período", "50000", pl)]
    a = br.dmpl_ausschuettungen(dmpl)
    assert a["dividenden"][0] == 20000 * 1000
    assert a["jcp"][0] == 13704 * 1000
    assert a["gemischt"][0] == 15489 * 1000     # nicht geraten, wie es sich aufteilt
    assert set(a) == {"dividenden", "jcp", "gemischt"}   # verfallene Dividenden und andere Spalten nicht gezaehlt


def test_dmpl_ersatzspalte_konzern():
    a = br.dmpl_ausschuettungen([_z("5.04.06", "Dividendos", "-5", "Patrimônio Líquido Consolidado")])
    assert a["dividenden"][0] == 5000


def _lade(land, name):
    p = os.path.join(UNI, land, name)
    if not os.path.exists(p):
        pytest.skip(f"{land}/{name} nicht erzeugt")
    return json.load(open(p, encoding="utf-8"))


def test_brasilien_keine_dubletten_und_trennung():
    iss, secs, lst = _lade("brazil", "issuers.json"), _lade("brazil", "securities.json"), _lade("brazil", "listings.json")
    assert len({i["issuer_id"] for i in iss}) == len(iss)
    assert len({s["security_id"] for s in secs}) == len(secs)
    assert len({l["listing_id"] for l in lst}) == len(lst)
    ids = {i["issuer_id"] for i in iss}
    sids = {s["security_id"] for s in secs}
    assert all(s["issuer_id"] in ids for s in secs) and all(l["security_id"] in sids for l in lst)
    assert all(l["mic"] == "BVMF" and l["kuerzel"][0].isalpha() for l in lst)
    assert all(s["isin"] is None for s in secs)
    assert all(s["gattung"] in ("ON", "PN", "PNA", "PNB", "PNC", "PND", "UNIT") for s in secs)


def test_brasilien_fakten_provenienz_und_perioden():
    ordner = os.path.join(BASIS, "data", "financials", "brazil")
    if not os.path.isdir(ordner):
        pytest.skip("keine Finanzdaten")
    dateien = sorted(os.listdir(ordner))[:80]
    for fn in dateien:
        d = json.load(open(os.path.join(ordner, fn), encoding="utf-8"))
        for f in d["fakten"]:
            assert f["quelle"] == "cvm_dados_abertos" and f["datei"].startswith("dfp_cia_aberta_") and f["konto"]
            assert f["review"] == "pending" and 2010 <= f["j"] <= 2025
            assert f["e"] in ("BRL", "BRL je Aktie", "Stück", "Faktor")
            if f.get("ende"):
                assert f["ende"][:4] in (str(f["j"]), str(f["j"] + 1)), (fn, f)
            if f["k"] in ("eps_on", "eps_pn", "eps_verw_on", "eps_ohne_gattung"):
                assert f["e"] == "BRL je Aktie" and "roh" not in f   # je Aktie nie skaliert


# ================================================================ Kanada / Mexiko (SEC + GLEIF)
def test_aktien_isin_filter():
    assert su.aktien_isin(["CA7800871021", "CA780087AB12"], "CA")[0] == "CA7800871021"   # Anleihe (alphanumerische Emission) raus
    assert su.aktien_isin(["CA7800871021", "CA7800872011"], "CA")[0] is None             # mehrdeutig bleibt leer
    assert su.aktien_isin(["MX01AC100006", "MX91AC000002"], "MX")[0] == "MX01AC100006"
    assert su.aktien_isin([], "CA")[1] == "keine_aktien_isin_bei_gleif"


def test_landcodes():
    assert "A6" in su.LAND_CODES["CA"] and "O5" in su.LAND_CODES["MX"] and "O5" not in su.LAND_CODES["CA"]


@pytest.mark.parametrize("land", ["canada", "mexico"])
def test_sec_universum_struktur(land):
    iss, secs, lst = _lade(land, "issuers.json"), _lade(land, "securities.json"), _lade(land, "listings.json")
    assert len({i["issuer_id"] for i in iss}) == len(iss)
    isins = [s["isin"] for s in secs if s["isin"]]
    assert len(isins) == len(set(isins)) and all(isin_gueltig(i) for i in isins)
    assert all(i["verified"] is False and i["human_review"] == "pending" for i in iss)
    assert all(l["quelle"] == "sec_edgar" and l["abgerufen"] for l in lst)
    assert all(not l["mic"] or l["mic"] in su.MIC.values() for l in lst)


def test_dmpl_bankenlayout_nicht_raten():
    zeilen = [_z("5.04.07", "Juros sobre Capital Próprio", "0", "Patrimônio Líquido"),
              _z("5.04.07", "Juros sobre Capital Próprio", "-2883979", "Patrimônio Líquido Consolidado"),
              _z("5.04.07", "Juros sobre Capital Próprio", "-8103085", "")]
    a = br.dmpl_ausschuettungen(zeilen)
    assert "_unklar" in a and "jcp" not in a


def test_dmpl_rueckbuchung_keine_ausschuettung():
    assert br.dmpl_ausschuettungen([_z("5.04.06", "Dividendos", "54318", "Patrimônio Líquido")]) == {}
