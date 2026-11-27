"""Ranglisten fuer den Newsletter (typ: evergreen), erzeugt aus den Hub-Daten (data/kennzahlen.json).

Jede Liste: Top 10 nach einer Kennzahl in einer Region (USA, Europa, einzelne Laender, Japan). Je Firma ein eigener Text mit
Geschaeftsmodell (data/firma-profile.json und data/firma-profile-ranglisten.json), letztem Jahr und fuenf Jahren.
Aufruf: python3 tools/build_ranglisten.py ; danach tools/build_magazin.py (baut /ranglisten/<slug>/ und die Uebersicht).
Indonesien und Brasilien sind ausgeschlossen, ebenso Kleinfirmen (Mindest-Boersenwert je Region).
"""
import datetime, glob, hashlib, json, os, random, re, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_evergreen as E
from build_evergreen import mrd, firma_zelle, tabelle, einmalig, EUROPA, MONATE, ZM

_orig_anzeige = E.anzeige_name
_SUFFIX = re.compile(r"[,\s]+(co\.?,?\s*ltd\.?|ltd\.?|limited|inc\.?|incorporated|corporation|corp\.?|plc|p\.l\.c\.|ag|se|s\.a\.|sa|n\.v\.|nv|asa|ab|aktiebolag|s\.p\.a\.|a/s|company|holdings?|\(publ\)|group)$", re.I)


def anzeige_name(n):
    n = _orig_anzeige(n or "")
    n = re.sub(r"\s+", " ", n.replace("\xa0", " ")).strip()
    n = re.sub(r"\s*/[a-z]{2}/?$", "", n, flags=re.I)
    for _ in range(3):
        m = _SUFFIX.search(n)
        if m and len(n[:m.start()]) >= 2:
            n = n[:m.start()].rstrip(", ")
    return n


E.anzeige_name = anzeige_name


def de(v, n=1):
    return "–" if v is None else E.de(v, n)


ROOT = E.ROOT
os.chdir(ROOT)
HEUTE = datetime.date.today()
MONATE_LANG = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"]
STAND = f"{MONATE_LANG[HEUTE.month - 1]} {HEUTE.year}"
ORDNER = f"content/magazin/9200_{HEUTE.isoformat()}"

LAND = {"US": "den USA", "DE": "Deutschland", "FR": "Frankreich", "GB": "Großbritannien", "CH": "der Schweiz", "NL": "den Niederlanden",
        "SE": "Schweden", "ES": "Spanien", "IT": "Italien", "JP": "Japan", "NO": "Norwegen", "DK": "Dänemark", "FI": "Finnland",
        "BE": "Belgien", "AT": "Österreich", "IE": "Irland", "LU": "Luxemburg", "PT": "Portugal", "KR": "Südkorea", "PL": "Polen", "GR": "Griechenland"}
LAND_N = {"US": "USA", "DE": "Deutschland", "FR": "Frankreich", "GB": "Großbritannien", "CH": "Schweiz", "NL": "Niederlande", "SE": "Schweden",
          "ES": "Spanien", "IT": "Italien", "JP": "Japan", "NO": "Norwegen", "DK": "Dänemark", "FI": "Finnland", "BE": "Belgien", "AT": "Österreich",
          "IE": "Irland", "LU": "Luxemburg", "PT": "Portugal", "KR": "Südkorea", "PL": "Polen", "GR": "Griechenland"}
NORD = {"SE", "NO", "DK", "FI"}
# Region: key -> (Name im Titel, Laender, Mindest-Boersenwert in Euro, Text "aus ...", Gruppe)
REGION = {
    "welt": ("weltweit", EUROPA | {"US", "JP"}, 10e9, "aus den USA, Europa und Japan"),
    "usa": ("USA", {"US"}, 10e9, "aus den USA"),
    "europa": ("Europa", EUROPA, 5e9, "aus Europa"),
    "de": ("Deutschland", {"DE"}, 3e9, "aus Deutschland"),
    "fr": ("Frankreich", {"FR"}, 3e9, "aus Frankreich"),
    "gb": ("Großbritannien", {"GB"}, 3e9, "aus Großbritannien"),
    "ch": ("Schweiz", {"CH"}, 3e9, "aus der Schweiz"),
    "nl": ("Niederlande", {"NL"}, 3e9, "aus den Niederlanden"),
    "se": ("Schweden", {"SE"}, 3e9, "aus Schweden"),
    "es": ("Spanien", {"ES"}, 3e9, "aus Spanien"),
    "it": ("Italien", {"IT"}, 3e9, "aus Italien"),
    "nord": ("Skandinavien", NORD, 3e9, "aus Schweden, Norwegen, Dänemark und Finnland"),
    "jp": ("Japan", {"JP"}, 5e9, "aus Japan"),
}

P = {}
for f in ("data/firma-profile.json", "data/firma-profile-ranglisten.json"):
    if os.path.exists(f):
        for k, v in json.load(open(f, encoding="utf-8")).get("firmen", {}).items():
            if v.get("text"):
                P[k] = v["text"]
BR = json.load(open("data/firmen-branchen.json", encoding="utf-8")).get("firmen", {})
FEHLT = set()


def zm_info(s, r):
    return E._zahlmonate_n(s, r) if hasattr(E, "_zahlmonate_n") else (None, [])


def lade():
    W = json.load(open("data/kennzahlen.json", encoding="utf-8"))["werte"]
    out = {}
    for s, r in W.items():
        if r.get("name") and (r.get("dividende") or 0) > 0 and r.get("land") in (EUROPA | {"US", "JP"}) and (r.get("rendite") or 0) > 0 \
                and (r.get("boersenwert_eur") or 0) > 0 and r.get("kurs_eur"):
            out[s] = r
    return out


def vorzeichen(x):
    return "stieg" if x >= 0 else "sank"


# ---------- Kennzahl-Definitionen ----------
def f_beste(W, ks):
    kand = {s: r for s, r in ks.items() if 0 < r["rendite"] <= 15 and r.get("div_wachstum_5j") is not None and 0 <= r["div_wachstum_5j"] <= 25
            and r.get("fcf_ausschuettung") is not None and 0 < r["fcf_ausschuettung"] <= 100 and E.plausibel(r)}
    if len(kand) < 8:
        return {}, None
    a = E.rang({s: r["rendite"] for s, r in kand.items()}); b = E.rang({s: r["div_wachstum_5j"] for s, r in kand.items()})
    c = E.rang({s: -r["fcf_ausschuettung"] for s, r in kand.items()})
    return {s: 0.35 * a[s] + 0.3 * b[s] + 0.35 * c[s] for s in kand}, kand


def einfach(feld, lo=None, hi=None, extra=None, absteigend=True):
    def f(W, ks):
        kand = {}
        for s, r in ks.items():
            v = r.get(feld)
            if v is None or (lo is not None and v <= lo) or (hi is not None and v > hi):
                continue
            if extra and not extra(r):
                continue
            kand[s] = r
        return {s: (r[feld] if absteigend else -r[feld]) for s, r in kand.items()}, kand
    return f


def f_zahler(W, ks):
    kand = {s: r for s, r in ks.items() if (r.get("dividenden_usd") or 0) > 0 and (r.get("rendite") or 0) <= 15}
    return {s: r["dividenden_usd"] for s, r in kand.items()}, kand


def f_monat(W, ks):
    kand = {s: r for s, r in ks.items() if zm_info(s, r)[0] == 12 and r["rendite"] <= 15}
    return {s: r["boersenwert_eur"] for s, r in kand.items()}, kand


def f_halb(W, ks):
    kand = {}
    for s, r in ks.items():
        n, idx = zm_info(s, r)
        if n == 2 and idx[1] - idx[0] == 6 and r["rendite"] <= 15:
            kand[s] = r
    return {s: r["boersenwert_eur"] for s, r in kand.items()}, kand


def f_quartal(W, ks):
    kand = {}
    for s, r in ks.items():
        n, idx = zm_info(s, r)
        if n == 4 and idx[1] - idx[0] == 3 and r["rendite"] <= 15 and r["rendite"] >= 2:
            kand[s] = r
    return {s: r["rendite"] for s, r in kand.items()}, kand


# Metrik: key -> (Funktion, Titelbaustein, Spalte2-Titel, Wert2, Spalte3-Titel, Wert3)
def pct(feld):
    return lambda r: (de(r[feld]) + " %") if r.get(feld) is not None else "–"
M = {
    "beste": (f_beste, "Beste Dividendenaktien", ("Rendite", pct("rendite")), ("Deckung", lambda r: de(r["fcf_ausschuettung"], 0) + " %")),
    "rendite": (einfach("rendite", lo=3, hi=15, extra=lambda r: (r.get("fcf_ausschuettung") is None or r["fcf_ausschuettung"] <= 100)), "Höchste Dividendenrenditen",
                ("Rendite", pct("rendite")), ("Deckung", lambda r: (de(r["fcf_ausschuettung"], 0) + " %") if r.get("fcf_ausschuettung") is not None else "–")),
    "dwachstum": (einfach("div_wachstum_5j", lo=3, hi=40, extra=lambda r: r["rendite"] <= 15), "Stärkstes Dividendenwachstum", ("Wachstum 5 J.", pct("div_wachstum_5j")), ("Rendite", pct("rendite"))),
    "umsatz5": (einfach("umsatz_wachstum_5j", lo=3, hi=60, extra=lambda r: r["rendite"] <= 15), "Größtes Umsatzwachstum", ("Umsatz 5 J. p. a.", pct("umsatz_wachstum_5j")), ("Rendite", pct("rendite"))),
    "umsatz1": (einfach("umsatz_wachstum", lo=5, hi=80, extra=lambda r: r["rendite"] <= 15), "Umsatzsprung im letzten Jahr", ("Umsatz", pct("umsatz_wachstum")), ("Rendite", pct("rendite"))),
    "gewinn5": (einfach("gewinn_wachstum_5j", lo=5, hi=60, extra=lambda r: r["rendite"] <= 15), "Größtes Gewinnwachstum", ("Gewinn 5 J. p. a.", pct("gewinn_wachstum_5j")), ("Rendite", pct("rendite"))),
    "serie": (einfach("dividendenserie", lo=9), "Längste Dividendenserie", ("Erhöhungen", lambda r: f"{r['dividendenserie']} Jahre"), ("Rendite", pct("rendite"))),
    "kings": (einfach("dividendenserie", lo=49), "Dividend Kings", ("Erhöhungen", lambda r: f"{r['dividendenserie']} Jahre"), ("Rendite", pct("rendite"))),
    "zahler": (f_zahler, "Größte Dividendenzahler", ("Ausschüttung", lambda r: de(r["dividenden_usd"] / 1e9, 1) + " Mrd. $"), ("Rendite", pct("rendite"))),
    "guenstig": (einfach("kgv", lo=3, hi=15, extra=lambda r: r["rendite"] >= 2 and r["rendite"] <= 15, absteigend=False), "Günstige Dividendenaktien", ("KGV", lambda r: de(r["kgv"])), ("Rendite", pct("rendite"))),
    "sicher": (einfach("fcf_ausschuettung", lo=0, hi=60, extra=lambda r: 2.5 <= r["rendite"] <= 15, absteigend=False), "Dividenden mit viel Luft", ("Deckung", lambda r: de(r["fcf_ausschuettung"], 0) + " %"), ("Rendite", pct("rendite"))),
    "marge": (einfach("nettomarge", lo=10, hi=80, extra=lambda r: 2 <= r["rendite"] <= 15), "Hohe Gewinnmargen", ("Nettomarge", pct("nettomarge")), ("Rendite", pct("rendite"))),
    "fcf": (einfach("fcf_rendite", lo=4, hi=30, extra=lambda r: 2 <= r["rendite"] <= 15), "Hohe Cashflow-Rendite", ("FCF-Rendite", pct("fcf_rendite")), ("Rendite", pct("rendite"))),
    "monat": (f_monat, "Monatszahler", ("Zahlung", lambda r: "jeden Monat"), ("Rendite", pct("rendite"))),
    "halb": (f_halb, "Halbjahreszahler", ("Zahlmonate", None), ("Rendite", pct("rendite"))),
    "quartal": (f_quartal, "Quartalszahler mit hoher Rendite", ("Zahlmonate", None), ("Rendite", pct("rendite"))),
    "ueber10": (einfach("rendite", lo=9.99, hi=25), "Dividendenrendite über 10 %", ("Rendite", pct("rendite")), ("Börsenwert", lambda r: mrd(r["boersenwert_eur"]))),
}
# Plan: (Metrik, Region)
PLAN = []
for reg in ["welt", "usa", "europa", "de", "fr", "gb", "ch", "nl", "se", "es", "it", "nord", "jp"]:
    PLAN.append(("beste", reg))
for reg in ["welt", "usa", "europa", "de", "fr", "gb", "ch", "es", "it", "nord", "jp"]:
    PLAN.append(("rendite", reg))
for reg in ["welt", "usa", "europa", "de", "fr", "gb", "ch", "jp"]:
    PLAN.append(("dwachstum", reg))
for reg in ["welt", "usa", "europa", "de", "fr", "gb", "jp"]:
    PLAN.append(("umsatz5", reg))
for reg in ["welt", "usa", "europa", "de", "gb", "jp"]:
    PLAN.append(("umsatz1", reg))
for reg in ["welt", "usa", "europa", "jp"]:
    PLAN.append(("gewinn5", reg))
PLAN += [("serie", "usa"), ("serie", "welt"), ("kings", "usa")]
for reg in ["welt", "usa", "europa", "de", "gb", "jp", "fr"]:
    PLAN.append(("zahler", reg))
for reg in ["welt", "usa", "europa", "de", "gb", "jp"]:
    PLAN.append(("guenstig", reg))
for reg in ["welt", "usa", "europa"]:
    PLAN += [("sicher", reg), ("marge", reg), ("fcf", reg)]
PLAN += [("monat", "usa"), ("halb", "europa"), ("quartal", "usa"), ("quartal", "europa"), ("ueber10", "europa")]

ORT = {"welt": "weltweit", "usa": "USA", "europa": "Europa", "de": "Deutschland", "fr": "Frankreich", "gb": "Großbritannien", "ch": "Schweiz",
       "nl": "Niederlande", "se": "Schweden", "es": "Spanien", "it": "Italien", "nord": "Skandinavien", "jp": "Japan"}


def titel_und_slug(metrik, reg):
    ort = ORT[reg]
    basis = M[metrik][1]
    t = {
        "beste": f"Beste Dividendenaktien {ort}: Die Top 10 für {HEUTE.year}",
        "rendite": f"Höchste Dividendenrenditen {ort}: Die Top 10 mit Deckung",
        "dwachstum": f"Stärkstes Dividendenwachstum {ort}: Die Top 10 der letzten fünf Jahre",
        "umsatz5": f"Größtes Umsatzwachstum {ort}: Top 10 Dividendenaktien",
        "umsatz1": f"Umsatzsprung {ort}: Dividendenaktien mit dem größten Plus im letzten Jahr",
        "gewinn5": f"Größtes Gewinnwachstum {ort}: Top 10 Dividendenaktien über fünf Jahre",
        "serie": f"Dividendenaristokraten {ort}: Die längsten Erhöhungsserien",
        "kings": f"Dividend Kings {ort}: Aktien mit mehr als 50 Jahren Dividendenerhöhung",
        "zahler": f"Größte Dividendenzahler {ort}: Wer am meisten ausschüttet",
        "guenstig": f"Günstige Dividendenaktien {ort}: Niedriges KGV und solide Rendite",
        "sicher": f"Sichere Dividenden {ort}: Aktien mit viel Luft beim Cashflow",
        "marge": f"Dividendenaktien {ort} mit hohen Gewinnmargen: Die Top 10",
        "fcf": f"Hohe Cashflow-Rendite {ort}: Dividendenaktien mit starkem freien Cashflow",
        "monat": "Monatszahler: Dividendenaktien, die jeden Monat zahlen",
        "halb": f"Halbjahreszahler {ort}: Dividendenaktien mit zwei Zahlungen im Jahr",
        "quartal": f"Quartalszahler {ort} mit hoher Rendite: Die Top 10",
        "ueber10": f"Dividendenrendite über 10 % in {ort}: Welche Aktien es gibt",
    }[metrik]
    slug = re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", (t.split(":")[0].lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")))).strip("-")
    slug = slug[:80].strip("-")
    return t, slug


# ---------- Texte je Firma ----------
def profil(s, r):
    if s in P:
        return P[s]
    FEHLT.add(s)
    br = BR.get(s)
    n = anzeige_name(r["name"])
    land = LAND_N.get(r.get("land"), "")
    return f"{n} ({land}) gehört zur Branche {br}." if br else f"{n} ist ein börsennotierter Konzern aus {LAND.get(r.get('land'), land)}."


def rnd(slug, s):
    return random.Random(int(hashlib.md5((slug + s).encode()).hexdigest()[:8], 16))


def satz_metrik(metrik, i, n, r, rg):
    v = {
        "beste": [f"Mit {de(r['rendite'])} % Rendite, {de(r['div_wachstum_5j'])} % Dividendenwachstum pro Jahr und einer Deckung von {de(r['fcf_ausschuettung'], 0)} % durch den freien Cashflow ergibt {n} eine ausgewogene Mischung.",
                  f"Die Rendite liegt bei {de(r['rendite'])} %, die Dividende wuchs über fünf Jahre jährlich um {de(r['div_wachstum_5j'])} %, und der freie Cashflow deckt sie zu {de(r['fcf_ausschuettung'], 0)} %.",
                  f"{n} punktet auf drei Feldern zugleich: {de(r['rendite'])} % Rendite, {de(r['div_wachstum_5j'])} % Dividendenplus im Schnitt und {de(r['fcf_ausschuettung'], 0)} % Cashflow-Deckung."],
        "rendite": [f"Die Dividendenrendite beträgt {de(r['rendite'])} %" + (f", und der freie Cashflow deckt die Ausschüttung zu {de(r['fcf_ausschuettung'], 0)} %." if r.get("fcf_ausschuettung") is not None else "."),
                    f"Mit {de(r['rendite'])} % Rendite gehört {n} zu den ertragsstärksten Werten dieser Liste" + (f", bei einer Cashflow-Deckung von {de(r['fcf_ausschuettung'], 0)} %." if r.get("fcf_ausschuettung") is not None else "."),
                    f"Anleger erhalten aktuell {de(r['rendite'])} % Dividendenrendite" + (f"; der freie Cashflow reicht für {de(r['fcf_ausschuettung'], 0)} % der Ausschüttung." if r.get("fcf_ausschuettung") is not None else ".")],
        "dwachstum": [f"Die Dividende ist in den vergangenen fünf Jahren im Schnitt um {de(r['div_wachstum_5j'])} % pro Jahr gestiegen.",
                      f"Jahr für Jahr hob {n} die Dividende zuletzt im Schnitt um {de(r['div_wachstum_5j'])} % an.",
                      f"Beim Dividendenwachstum liegt {n} mit {de(r['div_wachstum_5j'])} % pro Jahr (Fünfjahresschnitt) vorn."],
        "umsatz5": [f"Der Umsatz wuchs über fünf Jahre im Schnitt um {de(r['umsatz_wachstum_5j'])} % pro Jahr.",
                    f"Mit {de(r['umsatz_wachstum_5j'])} % Umsatzwachstum pro Jahr über fünf Jahre gehört {n} zu den dynamischsten Firmen der Liste.",
                    f"Seit fünf Jahren legt der Umsatz jährlich um durchschnittlich {de(r['umsatz_wachstum_5j'])} % zu."],
        "umsatz1": [f"Der Umsatz legte im letzten Geschäftsjahr um {de(r['umsatz_wachstum'])} % zu.",
                    f"Ein Umsatzplus von {de(r['umsatz_wachstum'])} % machte das Geschäftsjahr {r.get('gj')} zum Sprung nach vorn.",
                    f"Mit {de(r['umsatz_wachstum'])} % mehr Umsatz im Jahresvergleich steht {n} weit oben."],
        "gewinn5": [f"Der Gewinn wuchs über fünf Jahre im Schnitt um {de(r['gewinn_wachstum_5j'])} % pro Jahr.",
                    f"Jährlich {de(r['gewinn_wachstum_5j'])} % mehr Gewinn über fünf Jahre bringen {n} auf diesen Platz.",
                    f"Das Gewinnwachstum von {de(r['gewinn_wachstum_5j'])} % pro Jahr (Fünfjahresschnitt) ist der Grund für die Platzierung."],
        "serie": [f"{n} hat die Dividende {r['dividendenserie']} Jahre in Folge erhöht.",
                  f"Seit {r['dividendenserie']} Jahren ohne Unterbrechung steigt die Dividende.",
                  f"Die Erhöhungsserie ist mit {r['dividendenserie']} Jahren eine der längsten der Liste."],
        "kings": [f"{r['dividendenserie']} Jahre in Folge mit höherer Dividende machen {n} zum Dividend King.",
                  f"Über {r['dividendenserie']} Jahre hinweg wurde die Dividende jedes Jahr angehoben.",
                  f"Mit {r['dividendenserie']} Erhöhungen in Serie gehört {n} zur Spitzengruppe."],
        "zahler": [f"Zuletzt flossen rund {de((r.get('dividenden_usd') or 0) / 1e9, 1)} Mrd. US-Dollar an die Aktionäre.",
                   f"{n} schüttete zuletzt etwa {de((r.get('dividenden_usd') or 0) / 1e9, 1)} Mrd. US-Dollar an Dividenden aus.",
                   f"Die Ausschüttung summiert sich auf rund {de((r.get('dividenden_usd') or 0) / 1e9, 1)} Mrd. US-Dollar im Jahr."],
        "guenstig": [f"Mit einem KGV von {de(r['kgv'])} ist die Aktie niedrig bewertet, die Rendite liegt bei {de(r['rendite'])} %.",
                     f"Das KGV beträgt {de(r['kgv'])}, dazu kommen {de(r['rendite'])} % Dividendenrendite.",
                     f"Ein KGV von {de(r['kgv'])} und {de(r['rendite'])} % Rendite machen {n} zu einem der günstigeren Werte."],
        "sicher": [f"Die Ausschüttung beansprucht nur {de(r['fcf_ausschuettung'], 0)} % des freien Cashflows, die Rendite beträgt {de(r['rendite'])} %.",
                   f"Vom freien Cashflow gehen lediglich {de(r['fcf_ausschuettung'], 0)} % an die Aktionäre, bei {de(r['rendite'])} % Rendite.",
                   f"Mit einer Cashflow-Deckung von {de(r['fcf_ausschuettung'], 0)} % bleibt viel Spielraum für Investitionen und Erhöhungen."],
        "marge": [f"Die Nettomarge liegt bei {de(r['nettomarge'])} %.",
                  f"Von jedem Euro Umsatz bleiben {de(r['nettomarge'])} Cent als Gewinn hängen.",
                  f"Mit {de(r['nettomarge'])} % Nettomarge arbeitet {n} sehr profitabel."],
        "fcf": [f"Die Cashflow-Rendite beträgt {de(r['fcf_rendite'])} %.",
                f"Der freie Cashflow entspricht {de(r['fcf_rendite'])} % des Börsenwerts.",
                f"Gemessen am Börsenwert wirft der freie Cashflow {de(r['fcf_rendite'])} % ab."],
        "monat": [f"{n} zahlt in jedem Monat des Jahres eine Dividende.", f"Die Dividende kommt monatlich auf das Konto.", f"Zwölf Zahlungen im Jahr machen {n} zum Monatszahler."],
        "halb": [f"Die Dividende wird zweimal im Jahr gezahlt ({r.get('zahlmonate')}).", f"{n} zahlt halbjährlich, nämlich im {r.get('zahlmonate')}.", f"Zwei Zahlungen pro Jahr ({r.get('zahlmonate')})."],
        "quartal": [f"Die Dividende kommt vierteljährlich ({r.get('zahlmonate')}), die Rendite liegt bei {de(r['rendite'])} %.", f"{n} zahlt jedes Quartal und kommt auf {de(r['rendite'])} % Rendite.", f"Vier Zahlungen im Jahr ({r.get('zahlmonate')}) bei {de(r['rendite'])} % Rendite."],
        "ueber10": [f"Die Rendite von {de(r['rendite'])} % liegt über der Marke von 10 %.", f"{de(r['rendite'])} % Dividendenrendite sind hier ein Warnsignal und eine Chance zugleich.", f"Mit {de(r['rendite'])} % Rendite steht {n} auf dieser Liste."],
    }[metrik]
    return rg.choice(v)


def satz_jahr(r, n, rg):
    um, gw = r.get("umsatz_wachstum"), r.get("gewinn_wachstum")
    gj = r.get("gj")
    gw = gw if gw is not None and abs(gw) <= 150 else None
    if um is None:
        return None
    if gw is not None:
        v = [f"Im Geschäftsjahr {gj} {vorzeichen(um)} der Umsatz um {de(abs(um))} %, der Gewinn {vorzeichen(gw)} um {de(abs(gw))} %.",
             f"Das letzte Jahr ({gj}) brachte beim Umsatz {'ein Plus' if um >= 0 else 'ein Minus'} von {de(abs(um))} % und beim Gewinn {'ein Plus' if gw >= 0 else 'ein Minus'} von {de(abs(gw))} %.",
             f"{n} steigerte im Geschäftsjahr {gj} den Umsatz um {de(um)} % und den Gewinn um {de(gw)} %." if um >= 0 and gw >= 0 else
             f"Im Geschäftsjahr {gj} lag der Umsatz {de(abs(um))} % {'über' if um >= 0 else 'unter'} und der Gewinn {de(abs(gw))} % {'über' if gw >= 0 else 'unter'} dem Vorjahr."]
    else:
        v = [f"Im Geschäftsjahr {gj} {vorzeichen(um)} der Umsatz um {de(abs(um))} %.",
             f"Der Umsatz lag im letzten Jahr ({gj}) {de(abs(um))} % {'über' if um >= 0 else 'unter'} dem Vorjahr."]
    return rg.choice(v)


def satz_fuenf(r, n, rg, skip=()):
    u5, d5, g5 = r.get("umsatz_wachstum_5j"), r.get("div_wachstum_5j"), r.get("gewinn_wachstum_5j")
    teile = []
    if "u" in skip: u5 = None
    if "g" in skip: g5 = None
    if "d" in skip: d5 = None
    if u5 is not None and abs(u5) <= 80:
        teile.append(("der Umsatz", u5))
    if g5 is not None and abs(g5) <= 80:
        teile.append(("der Gewinn", g5))
    if d5 is not None and abs(d5) <= 80:
        teile.append(("die Dividende", d5))
    if not teile:
        return None
    teile = teile[:3]
    def fr(t, x):
        return f"{t} {'wuchs' if x >= 0 else 'schrumpfte'} um {de(abs(x))} %"
    liste = ", ".join(fr(t, x) for t, x in teile[:-1]) + (" und " if len(teile) > 1 else "") + fr(*teile[-1])
    return rg.choice([f"Über die vergangenen fünf Jahre gerechnet: {liste} pro Jahr.", f"Im Fünfjahresschnitt gilt: {liste} jährlich.",
                      f"Auf fünf Jahre betrachtet gilt: {liste} pro Jahr."])


def satz_bewertung(r, n, rg):
    t = []
    if r.get("kgv") and 0 < r["kgv"] < 200:
        t.append(f"KGV {de(r['kgv'])}")
    t.append(f"Rendite {de(r['rendite'])} %")
    t.append(f"Börsenwert {mrd(r['boersenwert_eur'])}")
    return rg.choice([f"Die Hub-Kennzahlen: {', '.join(t)}.", f"Zur Bewertung: {', '.join(t)}.", f"Im Aktien-Hub stehen {', '.join(t)}."])


class D(dict):
    def __missing__(self, k):
        return None


def firma_block(slug, metrik, i, s, r):
    r = D(r)
    rg = rnd(slug, s)
    n = anzeige_name(r["name"])
    teile = [profil(s, r), satz_metrik(metrik, i, n, r, rg)]
    zw = [x for x in (satz_jahr(r, n, rg), satz_fuenf(r, n, rg, {'umsatz5': 'u', 'gewinn5': 'g', 'dwachstum': 'd', 'beste': 'd'}.get(metrik, ''))) if x]
    if rg.random() < 0.5:
        zw.reverse()
    teile += zw
    if metrik not in ("serie", "kings") and r.get("dividendenserie") and r["dividendenserie"] >= 10 and rg.random() < 0.7:
        teile.append(f"Die Dividende wurde {r['dividendenserie']} Jahre in Folge erhöht.")
    if metrik not in ("rendite", "guenstig", "ueber10", "beste", "quartal") and rg.random() < 0.6:
        teile.append(satz_bewertung(r, n, rg))
    return f"### {i}. {n}\n\n" + " ".join(teile) + "\n\n"


def faq(metrik, reg, ort_text, kriterium, lo):
    ort = ORT[reg]
    q1 = {"monat": "Welche Aktien zahlen jeden Monat Dividende?", "halb": f"Welche Aktien aus {ort} zahlen die Dividende halbjährlich?",
          "serie": "Was sind Dividendenaristokraten?", "kings": "Was sind Dividend Kings?"}.get(metrik, f"Welche sind die besten Dividendenaktien in {ort}?" if metrik == "beste" else f"Was zeigt diese Liste für {ort}?")
    a1 = {"monat": "Monatszahler schütten ihre Dividende zwölfmal im Jahr aus. In den USA gibt es sie vor allem unter Immobilien- und Finanzfirmen, in Europa sind sie selten.",
          "serie": "Dividendenaristokraten sind Firmen, die ihre Dividende viele Jahre in Folge erhöht haben. Die Liste sortiert nach der Länge dieser Serie.",
          "kings": "Dividend Kings sind Firmen, die ihre Dividende mindestens 50 Jahre in Folge erhöht haben."}.get(metrik, f"Die Liste ordnet Dividendenaktien {ort_text} nach {kriterium}. Die Zahlen stammen aus dem Aktien-Hub von Dividenden-Rechner.de und werden regelmäßig neu berechnet.")
    q2 = "Wie wird die Liste berechnet?"
    a2 = f"Berücksichtigt werden Dividendenaktien {ort_text} mit einem Börsenwert ab {de(lo / 1e9, 0)} Mrd. Euro. Gleiche Firmen mit mehreren Börsenplätzen zählen nur einmal. Datengrundlage sind die letzten berichteten Geschäftszahlen und die aktuellen Kurse."
    q3 = "Ist die Liste eine Kaufempfehlung?"
    a3 = "Nein. Die Liste ist eine Auswertung nach festen Regeln. Vor einer Anlageentscheidung gehören Geschäftsmodell, Verschuldung und Branche geprüft."
    return f"## Häufige Fragen\n\n### {q1}\n\n{a1}\n\n### {q2}\n\n{a2}\n\n### {q3}\n\n{a3}\n"


def kriterium_text(metrik):
    return {"beste": "Rendite, Dividendenwachstum und Deckung durch den freien Cashflow", "rendite": "der Dividendenrendite (3 bis 15 Prozent, Deckung höchstens 100 Prozent des freien Cashflows)",
            "dwachstum": "dem jährlichen Dividendenwachstum der letzten fünf Jahre (zwischen 3 und 40 Prozent)", "umsatz5": "dem durchschnittlichen Umsatzwachstum der letzten fünf Jahre",
            "umsatz1": "dem Umsatzwachstum im letzten Geschäftsjahr", "gewinn5": "dem durchschnittlichen Gewinnwachstum der letzten fünf Jahre",
            "serie": "der Zahl der Jahre mit Dividendenerhöhung in Folge", "kings": "der Zahl der Jahre mit Dividendenerhöhung in Folge (mindestens 50)",
            "zahler": "der Summe der zuletzt ausgeschütteten Dividenden", "guenstig": "dem Kurs-Gewinn-Verhältnis (3 bis 15) bei mindestens 2 Prozent Rendite",
            "sicher": "dem Anteil der Ausschüttung am freien Cashflow (höchstens 60 Prozent) bei mindestens 2,5 Prozent Rendite",
            "marge": "der Nettomarge (mindestens 10 Prozent) bei mindestens 2 Prozent Rendite", "fcf": "der Cashflow-Rendite (mindestens 4 Prozent) bei mindestens 2 Prozent Rendite",
            "monat": "dem Börsenwert unter den Firmen mit zwölf Zahlungen im Jahr", "halb": "dem Börsenwert unter den Firmen mit zwei Zahlungen im Abstand von sechs Monaten",
            "quartal": "der Dividendenrendite unter den Firmen mit vierteljährlicher Zahlung", "ueber10": "der Dividendenrendite (mindestens 10 Prozent)"}[metrik]


def intro(metrik, reg, ort_text, lo, n):
    k = kriterium_text(metrik)
    a = {"beste": f"Wer Dividendenaktien {ort_text} sucht, braucht mehr als eine hohe Rendite. Diese Liste kombiniert Rendite, Dividendenwachstum und Cashflow-Deckung zu einer Punktzahl und zeigt die zehn besten Werte.",
         "rendite": f"Hohe Renditen locken, sind aber oft ein Warnsignal. Diese Liste zeigt die zehn Aktien {ort_text} mit den höchsten Dividendenrenditen, deren Ausschüttung aus dem freien Cashflow gedeckt ist.",
         "dwachstum": f"Eine Dividende, die Jahr für Jahr wächst, schlägt auf Dauer oft eine hohe Anfangsrendite. Diese Liste zeigt die Dividendenaktien {ort_text}, die ihre Ausschüttung in den letzten fünf Jahren am stärksten erhöht haben.",
         "umsatz5": f"Dividenden brauchen Wachstum. Diese Liste zeigt die zehn Dividendenaktien {ort_text}, deren Umsatz in den letzten fünf Jahren am stärksten gewachsen ist.",
         "umsatz1": f"Manche Firmen drehen im Jahr kräftig auf. Diese Liste zeigt die Dividendenaktien {ort_text} mit dem größten Umsatzplus im letzten Geschäftsjahr.",
         "gewinn5": f"Wachsende Gewinne tragen wachsende Dividenden. Diese Liste zeigt die Dividendenaktien {ort_text} mit dem stärksten Gewinnwachstum der letzten fünf Jahre.",
         "serie": f"Dividendenaristokraten gelten als Verlässlichkeitsbeweis. Diese Liste zeigt Aktien {ort_text} mit den längsten Serien von Dividendenerhöhungen.",
         "kings": f"Mehr als 50 Jahre steigende Dividenden schaffen nur wenige Firmen. Diese Liste zeigt die Dividend Kings {ort_text}.",
         "zahler": f"Wer zahlt am meisten? Diese Liste zeigt die Konzerne {ort_text}, die zuletzt die höchste Summe an ihre Aktionäre ausgeschüttet haben.",
         "guenstig": f"Niedrig bewertet und trotzdem eine Dividende: Diese Liste zeigt die Aktien {ort_text} mit dem niedrigsten KGV bei solider Rendite.",
         "sicher": f"Eine sichere Dividende erkennt man am Spielraum. Diese Liste zeigt Aktien {ort_text}, die nur einen kleinen Teil ihres freien Cashflows ausschütten.",
         "marge": f"Hohe Gewinnmargen schaffen Spielraum für Dividenden. Diese Liste zeigt die profitabelsten Dividendenaktien {ort_text}.",
         "fcf": f"Der freie Cashflow ist die Quelle jeder Dividende. Diese Liste zeigt Aktien {ort_text} mit der höchsten Cashflow-Rendite.",
         "monat": f"Monatliche Dividenden helfen beim Planen. Diese Liste zeigt Aktien {ort_text}, die in jedem Monat zahlen.",
         "halb": f"Halbjährliche Dividenden sind in Europa verbreitet. Diese Liste zeigt Aktien {ort_text}, die zweimal im Jahr im Abstand von sechs Monaten zahlen.",
         "quartal": f"Vierteljährliche Zahlungen sind in den USA der Standard. Diese Liste zeigt die Quartalszahler {ort_text} mit der höchsten Rendite.",
         "ueber10": f"Eine Rendite von mehr als 10 Prozent ist selten. Diese Liste zeigt die Aktien {ort_text}, die diese Marke erreichen."}[metrik]
    return (f"Stand: {HEUTE.strftime('%d.%m.%Y')}.\n\n{a}\n\n"
            f"Die Rangfolge richtet sich nach {k}. Berücksichtigt werden Aktien {ort_text} mit einem Börsenwert ab {de(lo / 1e9, 0)} Mrd. Euro, Kleinfirmen und Doppellistungen bleiben draußen.\n\n")


def zahlmonate_wert(s, r):
    return r.get("zahlmonate") or ZM.get(s) or "–"


def erzeuge(metrik, reg, W, nr):
    fn, _, c2, c3 = M[metrik]
    name, laender, lo, ort_text = REGION[reg]
    if metrik in ("monat", "ueber10", "halb"):
        lo = 2e9
    ks = {s: r for s, r in W.items() if r["land"] in laender and r["boersenwert_eur"] >= lo}
    score, kand = fn(W, ks)
    if not kand:
        return None
    ok = {s: kand[s] for s in einmalig(W, kand)}
    top = sorted(ok, key=lambda s: -score[s])[:10]
    if len(top) < (3 if metrik == "monat" else 5 if metrik == "ueber10" else 6):
        return None
    t, slug = titel_und_slug(metrik, reg)
    kopf_tab = ["Firma", c2[0], c3[0]]
    zeilen = []
    for i, s in enumerate(top, 1):
        r = ok[s]
        v2 = c2[1](r) if c2[1] else zahlmonate_wert(s, r)
        zeilen.append([firma_zelle(s, r, i), v2, c3[1](r)])
    body = intro(metrik, reg, ort_text, lo, len(top))
    body += "## Die Top " + str(len(top)) + " im Überblick\n\n" + tabelle(zeilen, kopf_tab) + "\n"
    body += "## Die Firmen im Einzelnen\n\n"
    for i, s in enumerate(top, 1):
        body += firma_block(slug, metrik, i, s, ok[s])
    body += faq(metrik, reg, ort_text, kriterium_text(metrik), lo)
    beschr = f"{t.split(':')[0]}: Die Top {len(top)} {ort_text} mit Kennzahlen, Geschäftsmodell und Entwicklung der letzten Jahre. Stand {STAND}."
    beschr = beschr.replace('"', "'")[:300]
    gruppe = {"beste": "Die Besten", "rendite": "Rendite und Sicherheit", "sicher": "Rendite und Sicherheit", "ueber10": "Rendite und Sicherheit", "dwachstum": "Wachstum", "umsatz5": "Wachstum", "umsatz1": "Wachstum",
              "gewinn5": "Wachstum", "serie": "Aristokraten und Kings", "kings": "Aristokraten und Kings", "zahler": "Die Größten", "guenstig": "Günstig und profitabel", "marge": "Günstig und profitabel",
              "fcf": "Günstig und profitabel", "monat": "Zahlrhythmus", "halb": "Zahlrhythmus", "quartal": "Zahlrhythmus"}[metrik]
    kopf = (f'---\ntitle: "{t}"\ndescription: "{beschr}"\ndate: {HEUTE.isoformat()} 09:00\nupdated: {HEUTE.isoformat()}\nauthor: "Kilian Treß"\n'
            f'category: Ratgeber\ntyp: evergreen\nkein_logo: ja\ngruppe: "{gruppe}"\nregion: "{ORT[reg]}"\n---\n')
    return slug, kopf + "\n" + body


def main():
    W = lade()
    # alte Ranglisten (frueherer Lauf) entfernen
    for d in glob.glob("content/magazin/92*_*"):
        shutil.rmtree(d)
    for d in glob.glob("content/magazin/91*_*"):       # alte Evergreens aus tools/build_evergreen.py (typ: evergreen), nichts anderes
        fs = glob.glob(os.path.join(d, "*.md"))
        if fs and all("typ: evergreen" in open(f, encoding="utf-8").read(3000) for f in fs):
            shutil.rmtree(d)
    os.makedirs(ORDNER, exist_ok=True)
    done, slugs = 0, set()
    for metrik, reg in PLAN:
        res = erzeuge(metrik, reg, W, done)
        if not res:
            print("übersprungen:", metrik, reg)
            continue
        slug, text = res
        if slug in slugs:
            print("doppelt:", slug); continue
        slugs.add(slug)
        done += 1
        open(f"{ORDNER}/92{done:02d}_{HEUTE.strftime('%m%d')}-{slug}.md", "w", encoding="utf-8").write(text)
    print(done, "Listen;", len(FEHLT), "Firmen ohne Profil")
    json.dump(sorted(FEHLT), open("/tmp/fehlt.json", "w"))


if __name__ == "__main__":
    main()
