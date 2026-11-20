"""Brasilien aus CVM Dados Abertos (ODbL): Emittenten (CAD), Wertpapiere/Notierungen (FCA valor_mobiliario),
Jahresabschluesse (DFP). Alle Werte mit Referenz auf Datei, Konto (CD_CONTA/DS_CONTA), Version und Stichtag.

Einheiten: Betraege mit ESCALA_MOEDA 'MIL' werden mit 1000 multipliziert (Rohwert und Skala bleiben gespeichert);
Gewinn je Aktie (Konten 3.99.x) ist Real je Aktie und wird NIE skaliert, obwohl die Zeile 'MIL' traegt.
Dividenden und Juros sobre Capital Proprio (JCP) kommen getrennt aus der DMPL (5.04.xx, Spalte 'Patrimonio Liquido')."""
import csv
import io
import re

QUELLE = "cvm_dados_abertos"
BASIS_URL = "https://dados.cvm.gov.br/dados/CIA_ABERTA"
MIC_B3 = "BVMF"   # ISO 10383: B3 S.A. - Brasil, Bolsa, Balcao

# Gattung aus dem Handelskuerzel (B3-Konvention: 3 = ON, 4 = PN, 5 = PNA, 6 = PNB, 7 = PNC, 8 = PND, 11 = Unit)
GATTUNG = {"3": "ON", "4": "PN", "5": "PNA", "6": "PNB", "7": "PNC", "8": "PND", "11": "UNIT"}


def csv_zeilen(datei_obj):
    return csv.DictReader(io.TextIOWrapper(datei_obj, encoding="latin-1"), delimiter=";")


def gattung(kuerzel, valor_mobiliario=""):
    """ON/PN/PNA/.../UNIT aus Kuerzel; widerspricht die CVM-Angabe (Ordinarias/Preferenciais/Units), gilt die CVM-Angabe."""
    m = re.fullmatch(r"[A-Z0-9]{4}(\d{1,2})", (kuerzel or "").strip().upper())
    aus_kuerzel = GATTUNG.get(m.group(1)) if m else None
    vm = (valor_mobiliario or "").lower()
    if "units" in vm:
        return "UNIT"
    if "ordin" in vm:
        return "ON"
    if "prefer" in vm:
        return aus_kuerzel if aus_kuerzel and aus_kuerzel.startswith("PN") else "PN"
    return aus_kuerzel


def ist_aktie(valor_mobiliario):
    vm = (valor_mobiliario or "").lower()
    return vm.startswith("ações ordinárias") or vm.startswith("ações preferenciais") or vm == "units"


def betrag(vl, escala, konto):
    """VL_CONTA -> (wert_normiert, rohwert, skala). 3.99.x (je Aktie) nie skalieren."""
    try:
        roh = float(vl)
    except (TypeError, ValueError):
        return None, None, escala
    if konto.startswith("3.99"):
        return roh, roh, "UNIDADE (je Aktie, nicht skaliert)"
    return (roh * 1000.0 if escala == "MIL" else roh), roh, escala


# Kennzahlen: (Datei-Kuerzel, Regel). Regel: Konto exakt + Pflichttext im DS_CONTA, oder Regex auf DS_CONTA unter Praefix
KENNZAHLEN = {
    "umsatz": ("DRE", {"konto": "3.01", "ds": r"Receita de Venda"}),
    "erloes_3_01_sonstige": ("DRE", {"konto": "3.01", "ds_nicht": r"Receita de Venda"}),   # Banken/Versicherer: keine Umsatzerloese
    "operatives_ergebnis": ("DRE", {"konto": "3.05", "ds": r"Resultado Antes do Resultado Financeiro"}),
    "gewinn_gesamt": ("DRE", {"praefix": "3.", "ds": r"^Lucro ?(/|ou) ?Preju[íi]zo (L[íi]quido )?(Consolidado )?do Per[íi]odo$", "tiefe": 2}),
    "gewinn": ("DRE", {"praefix": "3.", "ds": r"Atribu[íi]do a S[óo]cios da Empresa Controladora", "tiefe": 3}),
    "eps_on": ("DRE", {"konto": "3.99.01.01"}),
    "eps_pn": ("DRE", {"konto": "3.99.01.02"}),
    "eps_verw_on": ("DRE", {"konto": "3.99.02.01"}),
    "eps_ohne_gattung": ("DRE", {"konto": "3.99"}),   # manche Banken melden den Gewinn je Aktie nur in 3.99
    "bilanzsumme": ("BPA", {"konto": "1", "ds": r"Ativo Total"}),
    "eigenkapital_gesamt": ("BPP", {"konto": "2.03", "ds": r"Patrim[ôo]nio L[íi]quido"}),
    "minderheiten": ("BPP", {"praefix": "2.03.", "ds": r"N[ãa]o Controladores", "tiefe": 3}),
    "finanzschulden_kurz": ("BPP", {"praefix": "2.01.", "ds": r"^Empr[ée]stimos e Financiamentos$", "tiefe": 3}),
    "finanzschulden_lang": ("BPP", {"praefix": "2.02.", "ds": r"^Empr[ée]stimos e Financiamentos$", "tiefe": 3}),
    "operativer_cf": ("DFC", {"konto": "6.01"}),
    "capex": ("DFC", {"praefix": "6.02.", "ds": r"(Aquisi[çc][ãa]o|Aquisi[çc][õo]es|Compra|Adi[çc][õo]es|Investimentos?) (de |do |dos |em |no |ao )?(ativo )?(imobilizado|Imobilizado)"}),
}
JE_AKTIE = {"eps_on", "eps_pn", "eps_verw_on", "eps_ohne_gattung"}


def tiefe(konto):
    return konto.count(".") + 1


def waehle(zeilen, regel):
    """Aus den Zeilen eines Unternehmens/Jahres die passende Kontozeile (erste in Kontoreihenfolge)."""
    for z in sorted(zeilen, key=lambda z: [int(x) if x.isdigit() else 0 for x in z["CD_CONTA"].split(".")]):
        k, ds = z["CD_CONTA"], z["DS_CONTA"].strip()
        if "konto" in regel and k != regel["konto"]:
            continue
        if "praefix" in regel and (not k.startswith(regel["praefix"]) or ("tiefe" in regel and tiefe(k) != regel["tiefe"])):
            continue
        if "ds" in regel and not re.search(regel["ds"], ds, re.I):
            continue
        if "ds_nicht" in regel and re.search(regel["ds_nicht"], ds, re.I):
            continue
        return z
    return None


def dmpl_ausschuettungen(zeilen):
    """DMPL-Zeilen eines Unternehmens/Jahres -> {'dividenden'|'jcp'|'gemischt': (wert, [konten])}. 'gemischt' = eine Zeile
    nennt Dividenden und JCP zusammen (keine Aufteilung moeglich, wird nicht geraten).
    Nur Konten 5.04.xx (Transaktionen mit Gesellschaftern), Spalte 'Patrimonio Liquido' (Anteil der Aktionaere der Mutter),
    sonst 'Patrimonio Liquido Consolidado'. Vorzeichen: Ausschuettung negativ in der DMPL -> positiver Betrag."""
    out = {}
    ausschuettung = [z for z in zeilen if re.fullmatch(r"5\.04\.\d+", z["CD_CONTA"]) and re.search(r"Dividendo|Juros sobre", z["DS_CONTA"], re.I)]
    namenlos = [z for z in ausschuettung if not (z.get("COLUNA_DF") or "").strip() and (betrag(z["VL_CONTA"], z["ESCALA_MOEDA"], z["CD_CONTA"])[0] or 0)]
    if namenlos:   # Betraege in einer Spalte ohne Bezeichnung: Spalten verschoben (z. B. Bankenlayout) -> nicht raten
        return {"_unklar": "DMPL: Ausschüttungsbeträge in Spalte ohne Bezeichnung (Spalten verschoben) - nicht ausgewertet"}
    for spalte in ("Patrimônio Líquido", "Patrimônio Líquido Consolidado"):
        for z in zeilen:
            if z.get("COLUNA_DF", "").strip() != spalte or not re.fullmatch(r"5\.04\.\d+", z["CD_CONTA"]):
                continue
            ds = z["DS_CONTA"].strip()
            if re.search(r"prescrit|propost|adicionais", ds, re.I):
                continue   # verfallene oder nur vorgeschlagene Dividenden sind keine Ausschuettung des Jahres
            ist_jcp = bool(re.search(r"Juros sobre (o )?Capital Pr[óo]prio|JCP", ds, re.I))
            ist_div = bool(re.search(r"Dividendo", ds, re.I))
            art = "gemischt" if ist_jcp and ist_div else "jcp" if ist_jcp else "dividenden" if ist_div else None
            if not art:
                continue
            w, roh, esc = betrag(z["VL_CONTA"], z["ESCALA_MOEDA"], z["CD_CONTA"])
            if w is None:
                continue
            alt = out.get(art)
            out[art] = ((alt[0] if alt else 0.0) + (-w), (alt[1] if alt else []) + [z["CD_CONTA"] + " " + ds])
        if out:
            break
    return {k: v for k, v in out.items() if v[0] > 0}   # Netto-Rueckbuchungen sind keine Ausschuettung des Jahres
