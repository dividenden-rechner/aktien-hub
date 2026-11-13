"""Sammelt Fundamentaldaten je Firma ueber die OpenAI-API (Websuche) und legt sie als
Rohstand in data/gpt/<SYMBOL>.json ab. Die Daten gehen NICHT direkt in den Hub, sondern
werden erst geprueft und dann mit bd_store.py / bd_zusatz_store.py uebernommen.
Aufruf: FIRMEN="POST.VI=Oesterreichische Post;EVN.VI=EVN" MODELL=gpt-5.5 python3 tools/gpt_daten.py"""
import json, os, re, sys, time, urllib.request, urllib.error

KEY = os.environ.get("CHAT_API_KEY", "").strip()
MODELL = os.environ.get("MODELL", "").strip() or "gpt-5.5"
ZIEL = os.path.join(os.path.dirname(__file__), "..", "data", "gpt")
R_KEYS = ["umsatz", "ebt", "jahresueberschuss", "dividendenausschuettung", "eigenkapital", "eps",
          "dividende_je_aktie", "aktien_mio", "eigenkapitalrendite_pct"]
Z_KEYS = ["ocf", "capex", "da", "div", "bb", "cash", "debt", "umsatz", "brutto", "ebit", "zins", "steuer"]

AUFTRAG = """Du sammelst Finanzdaten der boersennotierten Firma {name} (Symbol {sym}) aus den Geschaeftsberichten
bzw. der Investor-Relations-Seite der Firma. Nutze die Websuche. Bevorzuge die Geschaeftsberichte und IR-Tabellen der Firma,
erst danach Datenseiten. Nichts schaetzen, nichts erfinden: Was du nicht belegen kannst, ist null.

Alle Betraege in der BERICHTSWAEHRUNG der Firma, in Millionen, positiv (ausser Verluste). Je-Aktie-Werte in Berichtswaehrung.
Geschaeftsjahre 2019 bis 2025 (bei abweichendem Geschaeftsjahr zaehlt das Jahr, in dem es beginnt; im hinweis vermerken).

Antworte NUR mit einem JSON-Objekt, ohne Text davor oder danach, in genau dieser Form:
{{"name": "...", "isin": "...", "waehrung": "EUR", "dividende_waehrung": null,
 "reihen": {{"umsatz": [7 Werte 2019..2025], "ebt": [...], "jahresueberschuss": [...], "dividendenausschuettung": [...],
            "eigenkapital": [...], "eps": [...], "dividende_je_aktie": [...], "aktien_mio": [...], "eigenkapitalrendite_pct": [...]}},
 "zusatz": {{"jahre": [2021, 2022, 2023, 2024, 2025], "ocf": [5 Werte], "capex": [...], "da": [...], "div": [...], "bb": [...],
            "cash": [...], "debt": [...], "umsatz": [...], "brutto": [...], "ebit": [...], "zins": [...], "steuer": [...]}},
 "hinweis": "Besonderheiten, Definitionen, Luecken",
 "quellen": ["URL 1", "URL 2"]}}

Bedeutung: ebt = Ergebnis vor Steuern; jahresueberschuss = Anteil der Aktionaere; dividendenausschuettung = gezahlte Dividendensumme;
eigenkapital = Eigenkapital der Aktionaere zum Jahresende; eps = verwaessert; dividende_je_aktie = fuer das Geschaeftsjahr beschlossen
(ordentlich plus Sonderdividende); aktien_mio = Aktien im Umlauf zum Jahresende; eigenkapitalrendite_pct = Jahresueberschuss / Eigenkapital.
ocf = operativer Cashflow; capex = Investitionen in Sachanlagen und immaterielle Werte; da = Abschreibungen; div = gezahlte Dividenden;
bb = Aktienrueckkaeufe (0 wenn belegt keine); cash = liquide Mittel inkl. kurzfristiger Anlagen; debt = Finanzschulden inkl. Leasing;
brutto = Bruttogewinn; ebit = operatives Ergebnis; zins = Zinsaufwand; steuer = Ertragsteuern.
Banken und Versicherer: umsatz, brutto, ebit, ocf, capex, debt null. Immobilienfirmen: brutto null."""


def frage(sym, name):
    body = {"model": MODELL, "tools": [{"type": "web_search"}],
            "input": AUFTRAG.format(sym=sym, name=name)}
    req = urllib.request.Request("https://api.openai.com/v1/responses", data=json.dumps(body).encode(),
                                 headers={"Authorization": "Bearer " + KEY, "Content-Type": "application/json"})
    try:
        d = json.load(urllib.request.urlopen(req, timeout=900))
    except urllib.error.HTTPError as e:
        return None, "HTTP %s %s" % (e.code, e.read()[:300].decode("utf-8", "replace")), {}
    text = "".join(c.get("text", "") for o in d.get("output", []) if o.get("type") == "message"
                   for c in o.get("content", []) if c.get("type") == "output_text")
    suchen = sum(1 for o in d.get("output", []) if o.get("type") == "web_search_call")
    use = d.get("usage", {})
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None, "kein JSON in der Antwort: " + text[:200], use
    try:
        j = json.loads(m.group(0))
    except Exception as e:
        return None, "JSON fehlerhaft: %s" % e, use
    j["_suchen"] = suchen
    return j, None, use


def pruefe(j):
    f = []
    for k in R_KEYS:
        if len((j.get("reihen") or {}).get(k) or []) != 7:
            f.append("reihen." + k)
    for k in Z_KEYS:
        if len((j.get("zusatz") or {}).get(k) or []) != 5:
            f.append("zusatz." + k)
    return f


def main():
    if not KEY:
        print("CHAT_API_KEY fehlt"); sys.exit(1)
    firmen = [x.split("=", 1) for x in os.environ.get("FIRMEN", "").split(";") if "=" in x]
    os.makedirs(ZIEL, exist_ok=True)
    for sym, name in firmen:
        sym, name = sym.strip(), name.strip()
        t = time.time()
        j, fehler, use = frage(sym, name)
        if fehler:
            print("FEHLER", sym, fehler); continue
        j.update({"symbol": sym, "modell": MODELL, "stand": time.strftime("%Y-%m-%d"), "_fehlt": pruefe(j)})
        json.dump(j, open(os.path.join(ZIEL, sym + ".json"), "w"), ensure_ascii=False, indent=1)
        print("OK", sym, "%ds" % (time.time() - t), "Suchen:", j["_suchen"], "Tokens ein/aus:",
              use.get("input_tokens"), use.get("output_tokens"), "Formfehler:", j["_fehlt"] or "keine")


if __name__ == "__main__":
    main()
