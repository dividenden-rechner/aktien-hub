#!/usr/bin/env python3
"""Asien-Jahreszahlen fuer den Aktien-Hub: data/asien/fundamentals.json im Format von data/esef/fundamentals.json.

Quellen (nur bereits gepruefte, in asia-equity-hub/ abgelegte Werte):
  - asia-equity-hub/reports/history/history_2024_2025.json (GJ 2024/2025 aus den Konzernabschluessen 2025)
  - asia-equity-hub/reports/history/ten_year_merged.json (GJ 2010-2025 aus den Zehnjahresuebersichten mehrerer
    Berichte; neuester Bericht gewinnt; als nicht vergleichbar markierte Jahre, z. B. CKH-Vorgaenger 2010-2015, werden
    NICHT uebernommen)
GJ 2024/2025 aus dem Abschluss haben Vorrang vor der Zehnjahresuebersicht. Werte werden auf ganze
Waehrungseinheiten umgerechnet (Mio./Tsd. -> Einheiten, US-Cent -> USD), wie bei SEC- und ESEF-Daten.
Alle Werte: maschinell extrahiert, menschliche Pruefung ausstehend.
Aufruf: python3 tools/build_asien_fundamentals.py
"""
import json, os, datetime
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AH = os.path.join(ROOT, "asia-equity-hub", "reports", "history")
SCALE = {"million": 1e6, "thousand": 1e3, "units": 1, "cents": 0.01, "billion": 1e9}
# Hub-Feld -> moegliche Quellfelder (erstes vorhandenes gewinnt)
MAP = {
    "umsatz": ["revenue"], "gewinn": ["net_income_attributable"], "eps_ber": ["eps_basic"],
    "eigenkapital": ["equity_attributable"], "bilanzsumme": ["total_assets"], "liquide_mittel": ["cash"],
    "operativer_cf": ["operating_cash_flow"], "capex": ["capex"], "operatives_ergebnis": ["operating_profit"],
    "dividenden_gezahlt": ["dividends_paid_to_shareholders"],
    "dividende_je_aktie": ["dividend_per_share_usd_cents", "dividend_per_share", "dividend_per_share_ten_year"],
    "aktien_verw": ["shares_outstanding", "shares_in_issue", "diluted_weighted_shares"],
    "zinsaufwand": ["finance_costs"], "abschreibungen": ["depreciation_amortisation"],
    "schulden_kurz": ["current_borrowings"], "schulden_lang": ["non_current_borrowings"],
    "bruttogewinn": ["gross_profit"],
    "umlaufvermoegen": ["current_assets"], "kurzfr_verbindl": ["current_liabilities"],
    "verbindlichkeiten": ["total_liabilities"],
}
# In Deutschland gehandelte ISIN je Asien-Firma (Kurs fuer tools/kennzahlen.py); BYD: H-Aktie (A-Aktie in DE nicht handelbar)
ISIN = {"0001.HK": "KYG217651051", "0019.HK": "HK0019000162", "0142.HK": "BMG348041077",
        "D05.SI": "SG1L01001701", "002594.SZ": "CNE100000296"}
LAND = {"HK": "HK", "SI": "SG", "SZ": "CN", "SS": "CN"}


def wert(f):
    v = f.get("value")
    if v is None:
        return None
    return round(float(v) * SCALE.get(f.get("unit"), 1), 6)


def abgeleitet(reihen, roh):
    """Exakte Rechnungen aus Berichtswerten desselben Jahres (keine Schaetzung); nur wo das Ziel noch fehlt."""
    for y, r in roh.items():
        def setze(hub, v):
            if v is not None and y not in reihen.get(hub, {}):
                reihen.setdefault(hub, {})[y] = round(v, 6)
        if "profit_before_tax" in r and "net_profit" in r:
            setze("steuern", r["profit_before_tax"] - r["net_profit"])           # Steuern = Gewinn vor Steuern - Jahresueberschuss
        if "depreciation_ppe" in r and "amortisation_intangibles" in r:
            setze("abschreibungen", r["depreciation_ppe"] + r["amortisation_intangibles"])
        if "revenue" in r and "cost_of_sales" in r:
            setze("bruttogewinn", r["revenue"] - abs(r["cost_of_sales"]))
        if "non_current_borrowings" in r and "bonds_payable" in r:
            reihen.setdefault("schulden_lang", {})[y] = round(r["non_current_borrowings"] + r["bonds_payable"], 6)


def bauen():
    hist = json.load(open(os.path.join(AH, "history_2024_2025.json"), encoding="utf-8"))["companies"]
    merged_path = os.path.join(AH, "ten_year_merged.json")
    if not os.path.exists(merged_path):
        merged_path = os.path.join(AH, "ten_year_2016_2025.json")
    ten = {i["symbol"]: i for i in json.load(open(merged_path, encoding="utf-8"))["issuers"]}
    firmen = {}
    for c in hist:
        sym = c["symbol"]
        years = c["years"]
        any_year = next(iter(years.values()))
        cur = any_year["currency"]
        reihen = {}
        # 1) Zehnjahresuebersicht
        for f in (ten.get(sym) or {}).get("facts", []):
            if f.get("comparable") is False:
                continue  # z. B. Vorgaengergesellschaft vor einer Reorganisation
            for hub, src in MAP.items():
                if f["field"] in src and f.get("currency") in (cur, None) and f.get("value") is not None:
                    if hub == "dividende_je_aktie" and sym == "0142.HK" and f["field"] != "dividend_per_share_usd_cents":
                        continue  # First Pacific: Ausschuettung je Aktie in HK-Cent bzw. inkl. Sonderausschuettung -> nur USD-Werte aus dem Abschluss
                    reihen.setdefault(hub, {})[f["fiscal_year"]] = wert(f)
        # 2) Abschluss 2024/2025 (Vorrang)
        for y, block in years.items():
            facts = {f["field"]: f for f in block["facts"]}
            for hub, src in MAP.items():
                for s in src:
                    f = facts.get(s)
                    if f and f.get("value") is not None and (f.get("currency") in (cur, None) or s == "dividend_per_share_usd_cents"):
                        reihen.setdefault(hub, {})[int(y)] = wert(f)
                        break
        roh = {}
        for f in (ten.get(sym) or {}).get("facts", []):
            if f.get("comparable") is not False and f.get("value") is not None:
                roh.setdefault(f["fiscal_year"], {})[f["field"]] = wert(f)
        for y, block in years.items():
            for f in block["facts"]:
                if f.get("value") is not None:
                    roh.setdefault(int(y), {})[f["field"]] = wert(f)
        abgeleitet(reihen, roh)
        k = {hub: [[f"{jahr}-12-31", v] for jahr, v in sorted(r.items()) if v is not None] for hub, r in reihen.items()}
        firmen[sym] = {"n": c.get("company") or sym, "isin": ISIN.get(sym), "land": LAND.get(sym.rsplit(".", 1)[1]), "w": cur,
                       "gj": f"{max(int(y) for y in years)}-12-31", "quelle": "Geschäftsbericht (PDF)",
                       "quelle_url": any_year.get("source_url"), "status": "maschinell extrahiert, menschliche Prüfung ausstehend",
                       "k": {kk: vv for kk, vv in k.items() if vv}}
    return {"stand": datetime.date.today().isoformat(),
            "quelle": "Geschäftsberichte (PDF) via asia-equity-hub, maschinell extrahiert", "firmen": firmen}


if __name__ == "__main__":
    res = bauen()
    os.makedirs(os.path.join(ROOT, "data", "asien"), exist_ok=True)
    json.dump(res, open(os.path.join(ROOT, "data", "asien", "fundamentals.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for s, f in res["firmen"].items():
        print(s, f["n"], f["w"], {k: len(v) for k, v in f["k"].items()})
