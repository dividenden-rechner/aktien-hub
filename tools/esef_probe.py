#!/usr/bin/env python3
"""PROBE (11.11.2026): Wie gut decken die ESEF-Jahresberichte bei filings.xbrl.org die wichtigsten europaeischen Dividendenwerte ab?
Sucht je Firma die neueste Einreichung, laedt deren xBRL-JSON und prueft, ob Umsatz, Gewinn, Gewinn je Aktie, Dividenden,
operativer Cashflow, Investitionen und Eigenkapital vorhanden sind. Schreibt data/esef-probe.md. Aendert sonst nichts."""
import json, re, time, urllib.error, urllib.parse, urllib.request

UA = {"User-Agent": "dividenden-rechner.de Datenpruefung (https://www.dividenden-rechner.de/impressum/)"}
FIRMEN = [  # (Anzeigename, Suchbegriff im Firmennamen)
 ("Allianz", "allianz se"), ("Münchener Rück", "münchener rück"), ("BASF", "basf se"), ("Siemens", "siemens aktiengesellschaft"),
 ("Deutsche Telekom", "deutsche telekom"), ("Mercedes-Benz", "mercedes-benz group"), ("BMW", "bayerische motoren werke"),
 ("Volkswagen", "volkswagen aktiengesellschaft"), ("SAP", "sap se"), ("Deutsche Post / DHL", "deutsche post"), ("E.ON", "e.on se"),
 ("RWE", "rwe aktiengesellschaft"), ("Bayer", "bayer aktiengesellschaft"), ("Henkel", "henkel ag"), ("Hannover Rück", "hannover rück"),
 ("Deutsche Börse", "deutsche börse"), ("Infineon", "infineon"), ("adidas", "adidas"), ("Fresenius", "fresenius se"),
 ("Heidelberg Materials", "heidelberg materials"), ("Vonovia", "vonovia"), ("Commerzbank", "commerzbank"), ("Deutsche Bank", "deutsche bank ag"),
 ("Porsche SE", "porsche automobil holding"), ("Daimler Truck", "daimler truck"), ("Siemens Energy", "siemens energy"),
 ("TotalEnergies", "totalenergies"), ("LVMH", "lvmh"), ("Sanofi", "sanofi"), ("L'Oréal", "l'oréal"), ("AXA", "axa"), ("BNP Paribas", "bnp paribas"),
 ("Schneider Electric", "schneider electric"), ("Vinci", "vinci"), ("Danone", "danone"), ("Air Liquide", "air liquide"),
 ("Enel", "enel"), ("Eni", "eni s.p.a"), ("Intesa Sanpaolo", "intesa sanpaolo"), ("Generali", "assicurazioni generali"), ("UniCredit", "unicredit"),
 ("Iberdrola", "iberdrola"), ("Banco Santander", "banco santander"), ("BBVA", "banco bilbao"), ("Telefónica", "telefónica"),
 ("ASML", "asml holding"), ("ING", "ing groep"), ("Ahold Delhaize", "ahold delhaize"), ("Wolters Kluwer", "wolters kluwer"),
 ("Anheuser-Busch InBev", "anheuser-busch inbev"), ("Nordea", "nordea"), ("Novo Nordisk", "novo nordisk"), ("Kone", "kone"),
 ("Nokia", "nokia"), ("Unilever", "unilever"), ("Shell", "shell plc"), ("BP", "bp p.l.c"), ("HSBC", "hsbc holdings"),
 ("British American Tobacco", "british american tobacco"), ("GSK", "gsk plc"), ("Legal & General", "legal & general"),
 ("Nestlé", "nestlé"), ("Novartis", "novartis"), ("Roche", "roche holding"), ("Zurich Insurance", "zurich insurance"), ("Swiss Re", "swiss re")]
KENN = {"Umsatz": ["Revenue", "RevenueFromContractsWithCustomers"], "Gewinn": ["ProfitLoss", "ProfitLossAttributableToOwnersOfParent"],
        "Gewinn je Aktie": ["BasicEarningsLossPerShare", "DilutedEarningsLossPerShare"],
        "Dividende": ["DividendsPaid", "DividendsPaidClassifiedAsFinancingActivities", "DividendsRecognisedAsDistributionsToOwnersOfParent"],
        "Operativer Cashflow": ["CashFlowsFromUsedInOperatingActivities"],
        "Investitionen": ["PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities", "PurchaseOfPropertyPlantAndEquipment"],
        "Eigenkapital": ["Equity", "EquityAttributableToOwnersOfParent"]}


def get(url):
    for v in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 429 and v < 3:
                time.sleep(60 * (v + 1)); continue   # Drosselung abwarten
            raise


def main():
    zeilen, gesamt = [], {k: 0 for k in KENN}
    for name, such in FIRMEN:
        kurz = such.split()[0]
        flt = json.dumps([{"or": [{"name": "entity.name", "op": "ilike", "val": f"%{such}%"}, {"name": "entity.name", "op": "ilike", "val": f"{kurz}%"}]}])
        try:
            j = get("https://filings.xbrl.org/api/filings?include=entity&sort=-period_end&page[size]=5&filter=" + urllib.parse.quote(flt))
        except Exception as e:
            zeilen.append(f"| {name} | Fehler: {str(e)[:60]} | | | |"); continue
        data = j.get("data", [])
        if not data:
            zeilen.append(f"| {name} | – | nicht gefunden | | |"); continue
        a = data[0]["attributes"]
        jahr, jurl = a.get("period_end", ""), a.get("json_url")
        da = []
        if jurl:
            try:
                x = get("https://filings.xbrl.org" + jurl if jurl.startswith("/") else jurl)
                namen = {str(f.get("dimensions", {}).get("concept", "")).split(":")[-1] for f in (x.get("facts") or {}).values()}
                for k, tags in KENN.items():
                    if any(t in namen for t in tags):
                        da.append(k); gesamt[k] += 1
            except Exception as e:
                da = [f"JSON-Fehler {str(e)[:40]}"]
        fehlt = [k for k in KENN if k not in da]
        zeilen.append(f"| {name} | {jahr} | {'ja' if jurl else 'nein'} | {len([d for d in da if d in KENN])} von {len(KENN)} | {', '.join(fehlt) or '–'} |")
        time.sleep(8)
    md = ["# Probe: ESEF-Berichte (filings.xbrl.org) für europäische Dividendenwerte", "",
          f"{len(FIRMEN)} Firmen geprüft. Je Kennzahl vorhanden: " + ", ".join(f"{k} {v}" for k, v in gesamt.items()), "",
          "| Firma | Letztes Berichtsjahr | xBRL-JSON | Kennzahlen | fehlt |", "|---|---|---|---|---|"] + zeilen
    open("data/esef-probe.md", "w").write("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
