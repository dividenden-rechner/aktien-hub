"""Gemeinsame Hilfen: HTTP mit Wiederholung, ISIN-Pruefung, Namensnormalisierung."""
import re
import time
import unicodedata
import urllib.error
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (dividenden-rechner.de Datensammlung)"}


def get(url, timeout=120, versuche=4, headers=None):
    for v in range(versuche):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={**UA, **(headers or {})}), timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and v < versuche - 1:
                time.sleep(10 * (v + 1)); continue
            raise
        except (urllib.error.URLError, TimeoutError):
            if v < versuche - 1:
                time.sleep(10 * (v + 1)); continue
            raise


def isin_pruefziffer(basis):
    """ISO 6166: Buchstaben -> Zahlen (A=10 ... Z=35), dann Luhn ueber die Ziffernfolge."""
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
    return bool(isin) and bool(re.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}\d", isin)) and isin_pruefziffer(isin[:11]) == isin[11]


FUELL = {"THE", "INC", "INCORPORATED", "CORP", "CORPORATION", "CO", "COMPANY", "LTD", "LIMITED", "LTEE", "LTÉE", "PLC", "SA",
         "SAB", "DE", "CV", "AND", "&", "HOLDINGS", "HOLDING", "GROUP", "TRUST", "FUND", "LP", "L", "P", "ULC", "NV",
         "CLASS", "CL", "A", "B", "C", "SUBORDINATE", "SUB", "VOTING", "VTG", "NON", "MULTIPLE", "SHARES", "SHS", "SHARE",
         "COMMON", "COM", "ORD", "ORDINARY", "UNITS", "UNIT", "NPV", "NEW", "REGISTERED", "REG", "VARIABLE", "PARTNERSHIP",
         "SUBORD", "VTG", "VOT", "O", "N", "ON", "CD", "EXCH", "INC", "CO", "CORP"}


def tokens(name):
    """Name -> Menge bedeutungstragender Woerter (ohne Rechtsform, Gattung, Satzzeichen, Akzente)."""
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().upper()
    s = re.sub(r"[^A-Z0-9]+", " ", s)
    return {w for w in s.split() if w not in FUELL and len(w) > 1 and not re.fullmatch(r"\d+", w)}


def klasse(text):
    """Gattungsbuchstabe aus Ticker ('TECK.B') oder Namen ('CLASS B', 'CL B'); sonst None."""
    m = re.search(r"\.([A-Z])$", text or "")
    if m:
        return m.group(1)
    m = re.search(r"\b(?:CLASS|CL)\.?\s*([A-Z])\b", (text or "").upper())
    return m.group(1) if m else None


def wort_passt(a, b):
    """Gleiches Wort oder Abkuerzung: eines ist Praefix des anderen, mindestens 4 Buchstaben (INTL ~ INTERNATIONAL nicht,
    aber FINL/FINANCIAL ueber FIN... nein: nur echte Praefixe wie RESTAURANT/RESTAURANTS, PREC/PRECIOUS, DEVEL/DEVELOPMENT)."""
    if a == b:
        return True
    k, l = sorted((a, b), key=len)
    return len(k) >= 4 and l.startswith(k)


ABK = {"INTL": "INTERNATIONAL", "FINL": "FINANCIAL", "HLDGS": "HOLDINGS", "CDN": "CANADIAN", "RES": "RESOURCES",
       "RL": "REAL", "INVT": "INVESTMENT", "INVS": "INVESTMENT", "PPTYS": "PROPERTIES", "EXPLORAT": "EXPLORATION",
       "COMMUNIC": "COMMUNICATIONS", "TECHNOLOG": "TECHNOLOGIES", "CONS": "CONSOLIDATED"}


def norm_tokens(name):
    return {ABK.get(w, w) for w in tokens(name)}


def enthalten(ziel, menge):
    """Jedes Wort aus ziel hat ein passendes Wort (gleich oder Praefix) in menge."""
    return all(any(wort_passt(z, m) for m in menge) for z in ziel)
