"""Evergreen-Artikel für den Newsbereich: Rankings aus den Hub-Daten (data/kennzahlen.json).

Erzeugt Magazin-Beiträge (content/magazin/...) mit dem Datum der letzten Aktualisierung.
Die Listen sind dynamisch: jeder Lauf zieht die aktuellen Werte. Danach tools/build_magazin.py laufen lassen.
"""
import datetime, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
HEUTE = datetime.date.today()
DATUM = HEUTE.strftime("%d.%m.%Y")
AUTOR = "Kilian Treß"
MAGAZIN = "content/magazin"
MONATE = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]


def lade():
    W = json.load(open("data/kennzahlen.json", encoding="utf-8"))["werte"]
    return {s: r for s, r in W.items() if r.get("name") and (r.get("dividende") or 0) > 0}


def plausibel(r):
    """Ausreißer raus: Serie über 60 Jahre, Wachstum über 30 % oder unter -10 % je Jahr, KGV über 60 (Datenfehler, Sonderfälle)."""
    ser = r.get("dividendenserie")
    if ser is not None and ser > 60:
        return False
    w5 = r.get("div_wachstum_5j")
    if w5 is not None and not (-10 <= w5 <= 30):
        return False
    kgv = r.get("kgv")
    if kgv is not None and not (0 < kgv <= 60):
        return False
    return True


def ok(r, *, rmax=15, ausmax=100):
    rend, aus = r.get("rendite"), r.get("ausschuettung")
    if rend is None or not (0 < rend <= rmax):
        return False
    if aus is not None and not (0 < aus <= ausmax):
        return False
    if not plausibel(r):
        return False
    m = r.get("boersenwert_eur") or 0
    return m >= 2e9


def einmalig(W, syms):
    """Gleiche Firma nur einmal (Doppellistungen wie GOOG/GOOGL, ADR und Heimatbörse)."""
    gesehen, out = set(), []
    for s in sorted(syms, key=lambda x: -(W[x].get("boersenwert_eur") or 0)):
        r = W[s]
        schluessel = re.sub(r"[^a-z]", "", (r.get("name") or "").lower())[:14]
        if schluessel in gesehen:
            continue
        gesehen.add(schluessel); out.append(s)
    return out


def anzeige_name(n):
    if n and n == n.upper():
        return " ".join(w.capitalize() if len(w) > 3 else w for w in n.split())
    return n


def rang(werte):
    """Prozentrang 0..1 je Schlüssel (höher ist besser)."""
    s = sorted(werte.items(), key=lambda kv: kv[1])
    n = len(s) - 1 or 1
    return {k: i / n for i, (k, _) in enumerate(s)}


def de(v, n=1):
    return f"{v:,.{n}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def link_name(sym, name):
    name = anzeige_name(name)
    return f"[{name}](/aktien-hub/{sym_slug(sym)}/)" if sym_slug(sym) else name


_SLUGS = None
def sym_slug(sym):
    global _SLUGS
    if _SLUGS is None:
        _SLUGS = json.load(open("data/firmen-slugs.json", encoding="utf-8"))
    return _SLUGS.get(sym)


def kopf(titel, beschr, slug, datei_zeit):
    return (f'---\ntitle: "{titel}"\ndescription: "{beschr}"\ndate: {datei_zeit}\nupdated: {HEUTE.isoformat()}\n'
            f'author: "{AUTOR}"\ncategory: Ratgeber\ntyp: evergreen\nkein_logo: ja\n---\n')


def tabelle(zeilen, kopfzeile):
    out = "| " + " | ".join(kopfzeile) + " |\n|" + "|".join(["---"] * len(kopfzeile)) + "|\n"
    for z in zeilen:
        out += "| " + " | ".join(str(c) for c in z) + " |\n"
    return out


def beste(W):
    kand = {s: r for s, r in W.items() if ok(r, ausmax=80) and r.get("div_wachstum_5j") is not None and 0 <= r["div_wachstum_5j"] <= 25
            and r.get("fcf_ausschuettung") is not None and 0 < r["fcf_ausschuettung"] <= 100 and (r.get("dividendenserie") or 0) >= 5}
    kand = {s: kand[s] for s in einmalig(W, kand)}
    if len(kand) < 10:
        return None
    rend = rang({s: r["rendite"] for s, r in kand.items()})
    wach = rang({s: r["div_wachstum_5j"] for s, r in kand.items()})
    ser = rang({s: (r.get("dividendenserie") or 0) for s, r in kand.items()})
    dek = rang({s: -(r.get("fcf_ausschuettung") if r.get("fcf_ausschuettung") is not None else 100) for s, r in kand.items()})
    score = {s: 0.3 * rend[s] + 0.3 * wach[s] + 0.2 * ser[s] + 0.2 * dek[s] for s in kand}
    top = sorted(kand, key=lambda s: -score[s])[:10]
    zeilen = []
    for i, s in enumerate(top, 1):
        r = kand[s]
        zeilen.append([i, link_name(s, r["name"]), de(r["rendite"]) + " %", de(r["div_wachstum_5j"]) + " %",
                       (de(r["ausschuettung"], 0) + " %") if r.get("ausschuettung") is not None else "–",
                       (de(r["fcf_ausschuettung"], 0) + " %") if r.get("fcf_ausschuettung") is not None else "–",
                       f'{r["dividendenserie"]} Jahre' if r.get("dividendenserie") else "–"])
    body = (
        f"Die Liste aktualisiert sich bei jedem Lauf aus den Daten des Aktien-Hubs. Stand: {DATUM}.\n\n"
        "Wir haben alle Dividendenaktien mit einem Börsenwert ab 2 Mrd. Euro betrachtet, die mindestens fünf Jahre in Folge ihre Dividende erhöht haben und deren Rendite über 0 und höchstens 15 Prozent liegt. "
        "Jede Firma bekommt eine Punktzahl aus vier Kennzahlen: Dividendenrendite (30 %), Dividendenwachstum über fünf Jahre (30 %), Länge der Erhöhungsserie (20 %) und Deckung durch den freien Cashflow (20 %). Je höher die Deckung, desto besser.\n\n"
        + tabelle(zeilen, ["Platz", "Firma", "Rendite", "Dividendenwachstum 5 J.", "Ausschüttungsquote", "Anteil am FCF", "Erhöhungen in Folge"]) +
        "\nEine hohe Rendite allein ist kein Qualitätsmerkmal. Deshalb zählen Wachstum und Deckung genauso. Eine Firma, die ihre Dividende aus Schulden zahlt, fällt in der Punktzahl zurück, auch wenn die Rendite hoch ist.\n\n"
        "Diese Liste ist eine Auswertung nach festen Regeln und keine Kaufempfehlung. Vor einer Entscheidung lohnt der Blick auf das Geschäftsmodell, die Verschuldung und die Branche der Firma.\n"
    )
    return "die-10-besten-dividendenaktien", "Die 10 besten Dividendenaktien", \
           "Die zehn Dividendenaktien mit der besten Mischung aus Rendite, Wachstum, Erhöhungsserie und Deckung. Die Liste wird regelmäßig aus den Daten neu berechnet.", body


def wachstum(W):
    kand = {s: r for s, r in W.items() if ok(r, rmax=50) and r.get("div_wachstum_5j") is not None and 0 < r["div_wachstum_5j"] <= 30 and (r.get("dividendenserie") or 0) >= 3}
    kand = {s: kand[s] for s in einmalig(W, kand)}
    top = sorted(kand, key=lambda s: -kand[s]["div_wachstum_5j"])[:10]
    if len(top) < 10:
        return None
    zeilen = [[i, link_name(s, kand[s]["name"]), de(kand[s]["div_wachstum_5j"]) + " %", de(kand[s]["rendite"]) + " %",
               (de(kand[s]["div_wachstum_10j"]) + " %") if kand[s].get("div_wachstum_10j") is not None else "–"]
              for i, s in enumerate(top, 1)]
    body = (f"Diese Liste zeigt die Firmen, deren Dividende je Aktie in den letzten fünf Jahren am stärksten gewachsen ist. Stand: {DATUM}.\n\n"
            "Berücksichtigt werden Dividendenaktien mit einer Rendite zwischen 0 und 50 Prozent und mindestens drei Erhöhungen in Folge. Die Wachstumsrate ist der jährliche Durchschnitt.\n\n"
            + tabelle(zeilen, ["Platz", "Firma", "Dividendenwachstum 5 J. pro Jahr", "Rendite", "Dividendenwachstum 10 J. pro Jahr"]) +
            "\nHohes Wachstum kommt oft von einem niedrigen Ausgangspunkt. Wer das Wachstum bewertet, sollte zusätzlich prüfen, ob die Dividende aus dem Gewinn oder dem freien Cashflow gedeckt ist.\n\n"
            "Die Liste ist eine Auswertung nach festen Regeln und keine Kaufempfehlung.\n")
    return "dividendenwachstum-die-staerksten-steigerungen", "Dividendenwachstum: Die 10 Firmen mit den stärksten Steigerungen", \
           "Welche Dividendenaktien ihre Ausschüttung in den vergangenen fünf Jahren am stärksten erhöht haben. Die Liste wird aus den Daten neu berechnet.", body


def high_yield(W):
    kand = {s: r for s, r in W.items() if ok(r, rmax=15, ausmax=80) and r["rendite"] >= 5 and (r.get("fcf_ausschuettung") is None or r["fcf_ausschuettung"] <= 100)}
    kand = {s: kand[s] for s in einmalig(W, kand)}
    top = sorted(kand, key=lambda s: -kand[s]["rendite"])[:10]
    if len(top) < 10:
        return None
    zeilen = [[i, link_name(s, kand[s]["name"]), de(kand[s]["rendite"]) + " %",
               (de(kand[s]["ausschuettung"], 0) + " %") if kand[s].get("ausschuettung") is not None else "–",
               (de(kand[s]["fcf_ausschuettung"], 0) + " %") if kand[s].get("fcf_ausschuettung") is not None else "–",
               (de(kand[s]["div_wachstum_5j"]) + " %") if kand[s].get("div_wachstum_5j") is not None else "–"]
              for i, s in enumerate(top, 1)]
    body = (f"Hohe Dividendenrenditen locken, sind aber oft ein Warnsignal. Diese Liste zeigt die zehn Firmen mit der höchsten Rendite, die zugleich eine Ausschüttung unter 80 Prozent des Gewinns und höchstens 100 Prozent des freien Cashflows aufweisen. Stand: {DATUM}.\n\n"
            "Berücksichtigt werden Firmen mit einem Börsenwert ab 2 Mrd. Euro und einer Rendite zwischen 5 und 15 Prozent.\n\n"
            + tabelle(zeilen, ["Platz", "Firma", "Rendite", "Ausschüttungsquote", "Anteil am FCF", "Dividendenwachstum 5 J."]) +
            "\nWer eine hohe Rendite sieht, sollte drei Fragen stellen: Ist die Dividende aus dem Cashflow gedeckt? Wächst das Geschäft? Ist die Rendite hoch, weil der Kurs gefallen ist? Die Spalten helfen bei den ersten beiden Antworten.\n\n"
            "Die Liste ist eine Auswertung nach festen Regeln und keine Kaufempfehlung.\n")
    return "high-yield-hohe-dividendenrenditen-mit-deckung", "High Yield: Hohe Dividendenrenditen mit solider Deckung", \
           "Die zehn Dividendenaktien mit der höchsten Rendite, die ihre Ausschüttung trotzdem aus Gewinn und Cashflow zahlen. Die Liste wird regelmäßig neu berechnet.", body


def monatlich(W):
    res = []
    for s, r in W.items():
        zm = (r.get("zahlmonate") or "").strip()
        if not zm:
            continue
        if zm.lower().startswith("jeden"):
            n = 12
        else:
            n = len({m.strip() for m in zm.split(",") if m.strip() in MONATE})
        if n >= 4 and ok(r, rmax=15):
            res.append((n, s))
    res = [(n, s) for n, s in res if s in einmalig(W, [x for _, x in res])]
    res.sort(key=lambda t: (-t[0], -(W[t[1]].get("boersenwert_eur") or 0)))
    top = res[:10]
    if len(top) < 5:
        return None
    zeilen = [[i, link_name(s, W[s]["name"]), W[s]["zahlmonate"], n, de(W[s]["rendite"]) + " %"] for i, (n, s) in enumerate(top, 1)]
    body = (f"Manche Firmen zahlen ihre Dividende nicht einmal im Jahr, sondern öfter. Diese Liste zeigt Dividendenaktien mit den meisten Zahlmonaten, die wir für sie belegt haben. Stand: {DATUM}.\n\n"
            "Berücksichtigt werden Firmen mit mindestens vier belegten Zahlmonaten und einer Rendite zwischen 0 und 15 Prozent. Monate, die nicht belegt sind, fehlen in der Liste.\n\n"
            + tabelle(zeilen, ["Platz", "Firma", "Zahlmonate", "Anzahl Monate", "Rendite"]) +
            "\nMonatliche Zahlungen helfen beim Planen von Einnahmen, ändern aber nichts an der Qualität der Firma. Der Blick auf Deckung und Wachstum bleibt wichtig.\n\n"
            "Die Liste ist eine Auswertung nach festen Regeln und keine Kaufempfehlung. Die Monate stammen aus Zahlungsterminen der Unternehmen und können sich ändern.\n")
    return "dividende-aktien-mit-vielen-zahlmonaten", "Dividenden im Monatsrhythmus: Aktien mit den meisten Zahlmonaten", \
           "Welche Dividendenaktien über das Jahr verteilt zahlen und wie viele Monate belegt sind. Die Liste wird aus den Zahlterminen neu berechnet.", body


def main():
    W = lade()
    erzeugt = []
    for i, fn in enumerate([beste, wachstum, high_yield, monatlich]):
        ergebnis = fn(W)
        if not ergebnis:
            print("übersprungen (zu wenig Daten):", fn.__name__)
            continue
        slug, titel, beschr, body = ergebnis
        ordner = os.path.join(MAGAZIN, f"910{i+1}_{HEUTE.isoformat()}")
        os.makedirs(ordner, exist_ok=True)
        datei = os.path.join(ordner, f"910{i+1}_{HEUTE.strftime('%m%d')}-{slug}.md")
        ziel = os.path.join(ordner, os.path.basename(datei))
        zeit = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        open(ziel, "w", encoding="utf-8").write(kopf(titel, beschr, slug, zeit) + "\n" + body)
        erzeugt.append(ziel)
    print("\n".join(erzeugt))


if __name__ == "__main__":
    main()
