"""Evergreen-Artikel für den Newsbereich: Rankings aus den Hub-Daten (data/kennzahlen.json).

Erzeugt Magazin-Beiträge (content/magazin/...) mit dem Datum der letzten Aktualisierung.
Die Listen sind dynamisch: jeder Lauf zieht die aktuellen Werte und das eigene Meldungsarchiv
(data/magazin.json). Danach tools/build_magazin.py laufen lassen.
Indonesische Firmen sind in allen Listen ausgeschlossen.
"""
import datetime, json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
HEUTE = datetime.date.today()
DATUM = HEUTE.strftime("%d.%m.%Y")
AUTOR = "Kilian Treß"
MAGAZIN = "content/magazin"
MONATE = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]
EUROPA = {"DE", "FR", "NL", "GB", "CH", "IT", "ES", "SE", "NO", "DK", "BE", "FI", "IE", "AT", "LU", "PT"}
ASIEN = {"JP", "KR"}
AUSGESCHLOSSEN_LAND = {"ID"}
ZM = (json.load(open("data/zahlmonate.json", encoding="utf-8")).get("firmen") or {})
ARCHIV_PFAD = "data/magazin.json"
EVERGREEN_SLUGS = {"die-10-besten-dividendenaktien", "die-10-besten-dividendenaktien-europa",
                   "dividendenwachstum-die-staerksten-steigerungen",
                   "high-yield-hohe-dividendenrenditen-mit-deckung", "dividende-aktien-mit-vielen-zahlmonaten"}


def lade():
    W = json.load(open("data/kennzahlen.json", encoding="utf-8"))["werte"]
    return {s: r for s, r in W.items()
            if r.get("name") and (r.get("dividende") or 0) > 0 and r.get("land") not in AUSGESCHLOSSEN_LAND}


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
    return (r.get("boersenwert_eur") or 0) >= 2e9


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


_SLUGS = None
def sym_slug(sym):
    global _SLUGS
    if _SLUGS is None:
        _SLUGS = json.load(open("data/firmen-slugs.json", encoding="utf-8"))
    return _SLUGS.get(sym)


def link_name(sym, name):
    name = anzeige_name(name)
    return f"[{name}](/aktien-hub/{sym_slug(sym)}/)" if sym_slug(sym) else name


def logo(sym, name):
    """Firmenlogo wie auf der BDC-Liste; von der Artikelseite aus (news/<slug>/) liegt assets/ zwei Ebenen höher."""
    k = sym.lower()
    if os.path.exists(os.path.join(ROOT, "assets", "logos", k + ".png")):
        src = f"../../assets/logos/{k}.png"
    else:
        src = f"../../assets/logos/hub/{sym.upper()}.png"
    ph = ((name or sym)[:1] or "?").upper()
    return f'<span class="arlogo"><img src="{src}" alt="" width="30" height="30" loading="lazy" data-sym="{sym.upper()}" data-ph="{ph}"></span>'


def kopf(titel, beschr, slug, datei_zeit):
    return (f'---\ntitle: "{titel}"\ndescription: "{beschr}"\ndate: {datei_zeit}\nupdated: {HEUTE.isoformat()}\n'
            f'author: "{AUTOR}"\ncategory: Ratgeber\ntyp: evergreen\nkein_logo: ja\n---\n')


def lade_archiv():
    """Eigenes Meldungsarchiv je Firma (data/magazin.json, Feld sym). Evergreen-Artikel selbst zählen nicht."""
    try:
        items = json.load(open(ARCHIV_PFAD, encoding="utf-8")).get("items", [])
    except (OSError, ValueError):
        return {}
    out = {}
    for it in items:
        sym = it.get("sym")
        if not sym or it.get("slug") in EVERGREEN_SLUGS:
            continue
        out.setdefault(sym, []).append(it)
    for sym in out:
        out[sym].sort(key=lambda x: x.get("date", ""), reverse=True)
    return out


ARCHIV = lade_archiv()


def archiv_zeilen(sym, n=2):
    zeilen = []
    for it in ARCHIV.get(sym, [])[:n]:
        try:
            datum = datetime.date.fromisoformat(it.get("date", "")[:10]).strftime("%d.%m.%Y")
        except ValueError:
            datum = ""
        zeilen.append(f"- {datum}: [{it.get('title', '')}](/news/{it.get('slug')}/)")
    return zeilen


def archiv_absatz(syms, n=5):
    """Abschnitt unter einer Liste: die jüngsten eigenen Meldungen zu Firmen der Liste."""
    eintraege = []
    for s in syms:
        for it in ARCHIV.get(s, [])[:1]:
            eintraege.append((it.get("date", ""), it))
    eintraege.sort(key=lambda t: t[0], reverse=True)
    if not eintraege:
        return ""
    zeilen = [f"- [{it.get('title', '')}](/news/{it.get('slug')}/)" for _, it in eintraege[:n]]
    return "\n## Zuletzt bei uns\n\nZu Firmen dieser Liste haben wir zuletzt berichtet:\n\n" + "\n".join(zeilen) + "\n\n"


def karte(platz, s, r, kz, warum):
    """Eine Firma als Karte: Logo, Name, Kennzahlen, Kurs, Begründung und Archiv. Lesbar auf dem Handy, ohne Tabelle."""
    kz_zeile = " · ".join(kz)
    kurs = f"Kurs: {de(r['kurs_eur'], 2)} €" if r.get("kurs_eur") is not None else ""
    teile = [f"## {platz}. {logo(s, r['name'])} {link_name(s, r['name'])}", kz_zeile]
    if kurs:
        teile.append(kurs)
    if warum:
        teile.append(warum)
    arch = archiv_zeilen(s)
    if arch:
        teile.append("**Zuletzt bei uns:**\n\n" + "\n".join(arch))
    return "\n\n".join(teile) + "\n\n"


def tief(wert, text):
    return f"{text} {de(wert)} %" if wert is not None else None


def kz_basis(r):
    kz = [f"**Rendite {de(r['rendite'])} %**"]
    if r.get("div_wachstum_5j") is not None:
        kz.append(f"Dividendenwachstum 5 J. {de(r['div_wachstum_5j'])} % pro Jahr")
    if r.get("ausschuettung") is not None:
        kz.append(f"Ausschüttung {de(r['ausschuettung'], 0)} % des Gewinns")
    if r.get("fcf_ausschuettung") is not None:
        kz.append(f"{de(r['fcf_ausschuettung'], 0)} % des freien Cashflows")
    if r.get("dividendenserie"):
        kz.append(f"{r['dividendenserie']} Jahre Erhöhungen in Folge")
    return kz


def kopfzeilen(titel_text):
    return f"Stand: {DATUM}.\n\n{titel_text}\n\n"


def beste(W, europa=False):
    kand = {s: r for s, r in W.items() if ok(r, ausmax=80) and r.get("div_wachstum_5j") is not None and 0 <= r["div_wachstum_5j"] <= 25
            and r.get("fcf_ausschuettung") is not None and 0 < r["fcf_ausschuettung"] <= 100 and (r.get("dividendenserie") or 0) >= 5
            and (not europa or r.get("land") in EUROPA)}
    kand = {s: kand[s] for s in einmalig(W, kand)}
    if len(kand) < 10:
        return None
    faktoren = {
        "Rendite": rang({s: r["rendite"] for s, r in kand.items()}),
        "Wachstum": rang({s: r["div_wachstum_5j"] for s, r in kand.items()}),
        "Erhöhungsserie": rang({s: (r.get("dividendenserie") or 0) for s, r in kand.items()}),
        "Deckung": rang({s: -(r.get("fcf_ausschuettung") if r.get("fcf_ausschuettung") is not None else 100) for s, r in kand.items()}),
    }
    gewicht = {"Rendite": 0.3, "Wachstum": 0.3, "Erhöhungsserie": 0.2, "Deckung": 0.2}
    score = {s: sum(gewicht[f] * faktoren[f][s] for f in faktoren) for s in kand}
    top = sorted(kand, key=lambda s: -score[s])[:10]
    karten = []
    for i, s in enumerate(top, 1):
        r = kand[s]
        staerken = sorted(faktoren, key=lambda f: -faktoren[f][s])[:2]
        warum = f"Stark bei {staerken[0].lower()} und {staerken[1].lower()} (Punktzahl {de(score[s] * 100, 0)} von 100)."
        karten.append(karte(i, s, r, kz_basis(r), warum))
    body = (kopfzeilen(
        ("Betrachtet werden europäische Dividendenaktien" if europa else "Betrachtet werden Dividendenaktien weltweit")
        + " mit einem Börsenwert ab 2 Mrd. Euro, die mindestens fünf Jahre in Folge ihre Dividende erhöht haben und deren Rendite über 0 und höchstens 15 Prozent liegt. "
        "Jede Firma bekommt eine Punktzahl aus vier Kennzahlen: Rendite (30 %), Dividendenwachstum über fünf Jahre (30 %), Länge der Erhöhungsserie (20 %) und Deckung durch den freien Cashflow (20 %).")
        + "".join(karten)
        + archiv_absatz(top)
        + "## Wie die Liste entsteht\n\n"
          "Eine hohe Rendite allein ist kein Qualitätsmerkmal. Deshalb zählen Wachstum und Deckung genauso. Eine Firma, die ihre Dividende aus Schulden zahlt, fällt in der Punktzahl zurück, auch wenn die Rendite hoch ist.\n\n"
          "Diese Liste ist eine Auswertung nach festen Regeln und keine Kaufempfehlung. Vor einer Entscheidung lohnt der Blick auf das Geschäftsmodell, die Verschuldung und die Branche der Firma.\n")
    if europa:
        return "die-10-besten-dividendenaktien-europa", "Die 10 besten Dividendenaktien Europas", \
               "Die zehn europäischen Dividendenaktien mit der besten Mischung aus Rendite, Wachstum, Erhöhungsserie und Deckung. Die Liste wird regelmäßig aus den Daten neu berechnet.", body
    return "die-10-besten-dividendenaktien", "Die 10 besten Dividendenaktien", \
           "Die zehn Dividendenaktien mit der besten Mischung aus Rendite, Wachstum, Erhöhungsserie und Deckung. Die Liste wird regelmäßig aus den Daten neu berechnet.", body


def wachstum(W):
    kand = {s: r for s, r in W.items() if ok(r, rmax=50) and r.get("div_wachstum_5j") is not None and 0 < r["div_wachstum_5j"] <= 30 and (r.get("dividendenserie") or 0) >= 3}
    kand = {s: kand[s] for s in einmalig(W, kand)}
    top = sorted(kand, key=lambda s: -kand[s]["div_wachstum_5j"])[:10]
    if len(top) < 10:
        return None
    karten = []
    for i, s in enumerate(top, 1):
        r = kand[s]
        kz = [f"**Dividendenwachstum 5 J. {de(r['div_wachstum_5j'])} % pro Jahr**", f"Rendite {de(r['rendite'])} %"]
        if r.get("div_wachstum_10j") is not None:
            kz.append(f"10 J. {de(r['div_wachstum_10j'])} % pro Jahr")
        warum = f"Erhöhungen in Folge: {r['dividendenserie']} Jahre." if r.get("dividendenserie") else ""
        karten.append(karte(i, s, r, kz, warum))
    body = (kopfzeilen("Diese Liste zeigt die Firmen, deren Dividende je Aktie in den letzten fünf Jahren am stärksten gewachsen ist. "
                       "Berücksichtigt werden Dividendenaktien mit einer Rendite zwischen 0 und 50 Prozent und mindestens drei Erhöhungen in Folge. Die Wachstumsrate ist der jährliche Durchschnitt.")
            + "".join(karten)
            + archiv_absatz(top)
            + "## Einordnung\n\nHohes Wachstum kommt oft von einem niedrigen Ausgangspunkt. Wer das Wachstum bewertet, sollte zusätzlich prüfen, ob die Dividende aus dem Gewinn oder dem freien Cashflow gedeckt ist.\n\n"
              "Die Liste ist eine Auswertung nach festen Regeln und keine Kaufempfehlung.\n")
    return "dividendenwachstum-die-staerksten-steigerungen", "Dividendenwachstum: Die 10 Firmen mit den stärksten Steigerungen", \
           "Welche Dividendenaktien ihre Ausschüttung in den vergangenen fünf Jahren am stärksten erhöht haben. Die Liste wird aus den Daten neu berechnet.", body


def high_yield(W):
    """Großfirmen ab 5 Mrd. Euro, Rendite 5 bis 15 %, Ausschüttung höchstens 100 % des freien Cashflows.
    Die Gewinnquote wird nicht begrenzt: bei REITs, BDCs und Firmen mit schwachem Jahresgewinn ist sie irreführend.
    Auswahl je Gebiet nach Punkten: halb Rendite, halb Deckung. Ziel: 7 USA, 2 Europa, 1 Asien."""
    basis = {s: r for s, r in W.items() if ok(r, rmax=15, ausmax=10_000) and r["rendite"] >= 5
             and (r.get("fcf_ausschuettung") is None or r["fcf_ausschuettung"] <= 100)
             and (r.get("boersenwert_eur") or 0) >= 5e9}
    basis = {s: basis[s] for s in einmalig(W, basis)}
    if not basis:
        return None
    rend = rang({s: r["rendite"] for s, r in basis.items()})
    dek = rang({s: -(r["fcf_ausschuettung"] if r.get("fcf_ausschuettung") is not None else 75) for s, r in basis.items()})
    punkte = {s: 0.5 * rend[s] + 0.5 * dek[s] for s in basis}

    def waehle(laender, n):
        pool = [s for s in basis if basis[s].get("land") in laender]
        return sorted(pool, key=lambda s: -punkte[s])[:n]

    top = waehle({"US"}, 7) + waehle(EUROPA, 2) + waehle(ASIEN, 1)
    if len(top) < 10:
        return None
    top = sorted(top, key=lambda s: -basis[s]["rendite"])
    karten = []
    for i, s in enumerate(top, 1):
        r = basis[s]
        kz = [f"**Rendite {de(r['rendite'])} %**"]
        if r.get("fcf_ausschuettung") is not None:
            kz.append(f"{de(r['fcf_ausschuettung'], 0)} % des freien Cashflows")
        if r.get("div_wachstum_5j") is not None:
            kz.append(f"Dividendenwachstum 5 J. {de(r['div_wachstum_5j'])} %")
        warum = "Die Ausschüttung ist vom freien Cashflow gedeckt." if r.get("fcf_ausschuettung") is not None and r["fcf_ausschuettung"] < 100 else ""
        karten.append(karte(i, s, r, kz, warum))
    body = (kopfzeilen("Hohe Dividendenrenditen locken, sind aber oft ein Warnsignal. Diese Liste zeigt zehn Großfirmen mit hoher Rendite, deren Ausschüttung aus dem freien Cashflow gedeckt ist: sieben aus den USA, zwei aus Europa und eine aus Asien. "
                       "Berücksichtigt werden Firmen mit einem Börsenwert ab 5 Mrd. Euro und einer Rendite zwischen 5 und 15 Prozent.")
            + "".join(karten)
            + archiv_absatz(top)
            + "## Drei Fragen vor dem Kauf\n\nWer eine hohe Rendite sieht, sollte drei Fragen stellen: Ist die Dividende aus dem Cashflow gedeckt? Wächst das Geschäft? Ist die Rendite hoch, weil der Kurs gefallen ist?\n\n"
              "Die Liste ist eine Auswertung nach festen Regeln und keine Kaufempfehlung.\n")
    return "high-yield-hohe-dividendenrenditen-mit-deckung", "High Yield: Hohe Dividendenrenditen mit solider Deckung", \
           "Die zehn Großfirmen mit der höchsten Rendite, die ihre Ausschüttung aus dem freien Cashflow zahlen. Die Liste wird regelmäßig neu berechnet.", body


def monatlich(W):
    res = []
    for s, r in W.items():
        zm = (r.get("zahlmonate") or ZM.get(s) or "").strip()
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
    karten = []
    for i, (n, s) in enumerate(top, 1):
        r = W[s]
        zm = r.get("zahlmonate") or ZM.get(s)
        kz = [f"**{n} Zahlmonate**", f"Rendite {de(r['rendite'])} %"]
        karten.append(karte(i, s, r, kz, f"Zahlmonate: {zm}."))
    body = (kopfzeilen("Manche Firmen zahlen ihre Dividende nicht einmal im Jahr, sondern öfter. Diese Liste zeigt Dividendenaktien mit den meisten Zahlmonaten, die wir für sie belegt haben. "
                       "Berücksichtigt werden Firmen mit mindestens vier belegten Zahlmonaten und einer Rendite zwischen 0 und 15 Prozent. Monate, die nicht belegt sind, fehlen in der Liste.")
            + "".join(karten)
            + archiv_absatz([s for _, s in top])
            + "## Einordnung\n\nMonatliche Zahlungen helfen beim Planen von Einnahmen, ändern aber nichts an der Qualität der Firma. Der Blick auf Deckung und Wachstum bleibt wichtig.\n\n"
              "Die Liste ist eine Auswertung nach festen Regeln und keine Kaufempfehlung. Die Monate stammen aus Zahlungsterminen der Unternehmen und können sich ändern.\n")
    return "dividende-aktien-mit-vielen-zahlmonaten", "Dividenden im Monatsrhythmus: Aktien mit den meisten Zahlmonaten", \
           "Welche Dividendenaktien über das Jahr verteilt zahlen und wie viele Monate belegt sind. Die Liste wird aus den Zahlterminen neu berechnet.", body


def main():
    W = lade()
    erzeugt = []
    plan = [("1", beste), ("2", wachstum), ("3", high_yield), ("4", monatlich), ("5", lambda w: beste(w, europa=True))]
    for nummer, fn in plan:
        ergebnis = fn(W)
        if not ergebnis:
            print("übersprungen (zu wenig Daten):", nummer)
            continue
        slug, titel, beschr, body = ergebnis
        ordner = os.path.join(MAGAZIN, f"910{nummer}_{HEUTE.isoformat()}")
        os.makedirs(ordner, exist_ok=True)
        datei = os.path.join(ordner, f"910{nummer}_{HEUTE.strftime('%m%d')}-{slug}.md")
        zeit = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        open(datei, "w", encoding="utf-8").write(kopf(titel, beschr, slug, zeit) + "\n" + body)
        erzeugt.append(datei)
    print("\n".join(erzeugt))


if __name__ == "__main__":
    main()
