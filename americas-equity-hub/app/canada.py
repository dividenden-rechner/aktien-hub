"""Kanada: Mitglieder des S&P/TSX Composite aus der veroeffentlichten Bestandsliste des iShares S&P/TSX Capped
Composite Index ETF (XIC). Die offizielle S&P-Mitgliederliste ist lizenzpflichtig (spglobal.com: HTTP 403);
der ETF bildet den Index nach und veroeffentlicht taeglich seine Bestaende. Quelle und Stichtag werden vermerkt."""
import csv
import io
import re
from datetime import datetime

XIC_URL = ("https://www.blackrock.com/ca/investors/en/products/239837/ishares-sptsx-capped-composite-index-etf/"
           "1464253357814.ajax?fileType=csv&fileName=XIC_holdings&dataType=fund")
INDEX_ID = "SPTSX_COMPOSITE"
INDEX_NAME = "S&P/TSX Composite"
MIC_TSX = "XTSE"


def parse_xic(text):
    """CSV-Text -> (stichtag 'JJJJ-MM-TT', [mitglieder]). Nur Aktien (Asset Class 'Equity') mit Boerse TSX;
    Platzhalter ohne gueltiges TSX-Kuerzel (z. B. '2299955D') werden verworfen und gezaehlt."""
    text = text.lstrip("﻿").replace("\r", "")
    zeilen = text.split("\n")
    m = re.match(r'Fund Holdings as of,"([^"]+)"', zeilen[0])
    stichtag = datetime.strptime(m.group(1), "%b %d, %Y").date().isoformat() if m else None
    kopf = next(i for i, z in enumerate(zeilen) if z.startswith("Ticker,"))
    mitglieder, verworfen = [], []
    for r in csv.DictReader(io.StringIO("\n".join(zeilen[kopf:]))):
        if (r.get("Asset Class") or "").strip() != "Equity":
            continue
        t = (r.get("Ticker") or "").strip().upper()
        if not re.fullmatch(r"[A-Z]{1,5}(\.[A-Z]{1,2})?", t):
            verworfen.append({"ticker": t, "name": r.get("Name"), "grund": "kein_gueltiges_kuerzel (Platzhalter)"})
            continue
        if r.get("Exchange") != "Toronto Stock Exchange":
            verworfen.append({"ticker": t, "name": r.get("Name"), "grund": f"nicht TSX ({r.get('Exchange')}), Restbestand des ETF"})
            continue
        mitglieder.append({"ticker": t, "name": (r.get("Name") or "").strip(), "sektor": (r.get("Sector") or "").strip(),
                           "waehrung": (r.get("Currency") or "").strip() or None,
                           "gewicht_prozent": _zahl(r.get("Weight (%)")), "sitz_laut_etf": (r.get("Location") or "").strip() or None})
    return stichtag, mitglieder, verworfen


def _zahl(s):
    try:
        return float(str(s).replace(",", ""))
    except (TypeError, ValueError):
        return None


def wertpapierart(ticker, name):
    """Grobe Art nach Kuerzel/Name: Units (Trusts, Partnerships, REITs: Endung .UN) oder Aktie; Gattung getrennt."""
    n = (name or "").upper()
    if ticker.endswith(".UN"):
        return "unit_reit" if "REIT" in n or "REAL ESTATE" in n else "unit_trust_or_partnership"
    if "SUBORDINATE" in n or "SUB VTG" in n:
        return "share_subordinate_voting"
    if "NON VOTING" in n or "NON-VOTING" in n or "NON VTG" in n:
        return "share_non_voting"
    return "share"


def hub_kuerzel(ticker):
    """Kuerzel im Hub: TSX-Kuerzel mit Endung .TO, Gattung mit Bindestrich (TECK.B -> TECK-B.TO), damit es keine
    Verwechslung mit US-Kuerzeln gibt (T = Telus, nicht AT&T)."""
    return ticker.replace(".", "-") + ".TO"


def klasse_aus(ticker, name):
    """Gattung: Buchstabe aus dem Kuerzel (TECK.B -> B), sonst aus dem Namen ('CLASS A'); Units/Trusts ohne Klasse."""
    from .common import klasse
    if ticker.endswith(".UN"):
        return None
    return klasse(ticker) or klasse(name)
