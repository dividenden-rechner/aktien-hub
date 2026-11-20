"""Rechte-Gate: entscheidet je Zweck anhand von data/rights/source_license.json.
Regel: unknown/restricted/prohibited sind NICHT allowed. Oeffentlicher Export (Hub, Website, API, oeffentliches Repository)
nur, wenn jede beteiligte Quelle fuer dauerhafte_speicherung, oeffentliche_api und kommerzielle_weiterverwendung allowed ist."""
import json
import os

PFAD = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "rights", "source_license.json")
STATUS = ("allowed", "restricted", "unknown", "prohibited")
EXPORT_ZWECKE = ("dauerhafte_speicherung", "oeffentliche_api", "kommerzielle_weiterverwendung")
_CACHE = None


def register(pfad=PFAD):
    global _CACHE
    if _CACHE is None or pfad != PFAD:
        d = json.load(open(pfad, encoding="utf-8"))
        reg = {q["source_id"]: q for q in d["quellen"]}
        for q in reg.values():
            for z in d["zwecke"]:
                if q["rechte"].get(z) not in STATUS:
                    raise ValueError(f"{q['source_id']}: Zweck {z} ohne gueltigen Status")
        if pfad != PFAD:
            return reg
        _CACHE = reg
    return _CACHE


def status(source_id, zweck, reg=None):
    q = (reg or register()).get(source_id)
    if q is None:
        return "unknown"   # unbekannte Quelle: nie erlaubt
    return q["rechte"].get(zweck, "unknown")


def erlaubt(source_ids, zweck, reg=None):
    ids = [source_ids] if isinstance(source_ids, str) else list(source_ids)
    return bool(ids) and all(status(s, zweck, reg) == "allowed" for s in ids)


def publizierbar(source_ids, reg=None):
    """True nur, wenn alle Quellen fuer alle Export-Zwecke ausdruecklich allowed sind."""
    return all(erlaubt(source_ids, z, reg) for z in EXPORT_ZWECKE)


def filtern(datensatz, reg=None):
    """Entfernt aus einem Datensatz {feld: wert, '_quellen': {feld: [source_id,...]}} alle Felder, deren Quellen nicht
    publizierbar sind. Felder ohne Quellenangabe werden ebenfalls entfernt (kein Export ohne Provenienz)."""
    q = datensatz.get("_quellen") or {}
    out = {}
    for k, v in datensatz.items():
        if k == "_quellen":
            continue
        if k in q and publizierbar(q[k], reg):
            out[k] = v
    return out
