"""Firmenliste für den Jahreswert-Vergleich auf aktien-hub/vergleich/ (data/vergleich-index.json).

Aufgenommen werden Firmen mit Jahreswerten (sec.k), mindestens zwei Geschäftsjahre in einer Kennzahl.
Die Jahreswerte selbst lädt die Seite je Firma aus data/firma-ansicht/<sym>.json.
"""
import glob, json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ANZ = os.path.join(ROOT, "data", "firma-ansicht")


def main():
    out = []
    for f in sorted(glob.glob(os.path.join(ANZ, "*.json"))):
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        sec = d.get("sec") or {}
        k = sec.get("k") or {}
        jahre = {key for key, pts in k.items() if len({str(p[0])[:4] for p in pts if p and p[1] is not None}) >= 2}
        if not jahre:
            continue
        out.append({"sym": os.path.basename(f)[:-5], "n": sec.get("n") or os.path.basename(f)[:-5],
                    "w": sec.get("w") or "", "k": sorted(jahre)})
    json.dump({"firmen": out}, open(os.path.join(ROOT, "data", "vergleich-index.json"), "w", encoding="utf-8"), ensure_ascii=False)
    print("Firmen:", len(out))


if __name__ == "__main__":
    main()
