#!/usr/bin/env python3
"""Aktualisiert die vier Kachel-Vorschauen auf der Startseite mit echten Zahlen (FMP, Lauf im Workflow kacheln.yml).
Aussehen wie auf den echten Seiten; fehlt eine Zahl, bleibt die Kachel unveraendert (nichts wird erfunden)."""
import os, re, sys, json, datetime
sys.path.insert(0, os.path.dirname(__file__))
import ir_agent as ia
import fetch_logos as fl

F = 'font-family="Inter,system-ui,sans-serif"'
HUB = ("JNJ", "Johnson & Johnson")                       # Aktien-Hub: Free Cashflow
SCREENER = [("JPM", "JPMorgan"), ("BAC", "Bank of America"), ("WFC", "Wells Fargo")]
DEPOT = [("MSFT", "Microsoft", 40), ("MCD", "McDonald's", 35), ("PG", "Procter & Gamble", 25)]   # Beispiel-Gewichte
EARN_GRUPPEN = [[("MSFT", "AAPL", "GOOGL", "AMZN", "META", "NVDA")], [("PFE", "LLY", "MRK", "BMY", "ABBV", "JNJ")],
                [("PEP", "KO", "PG", "MDLZ", "KDP", "CL")], [("XOM", "CVX", "COP", "OXY")], [("JPM", "BAC", "C", "WFC", "GS", "MS")]]


def de(v, n=1): return f"{v:,.{n}f}".replace(",", "X").replace(".", ",").replace("X", ".")
def logo(sym):
    k = sym.lower().replace(".", "-"); p = f"assets/logos/{k}.png"
    if not os.path.exists(p):
        png = fl.from_fmp(sym)
        if not png: return None
        os.makedirs("assets/logos", exist_ok=True); open(p, "wb").write(png)
    return k
def img(k, x, y, w=16): return f'<image href="assets/logos/{k}.png" x="{x}" y="{y}" width="{w}" height="{w}" preserveAspectRatio="xMidYMid meet"/>'
def svg(body, h=96): return f'<svg viewBox="0 0 200 {h}" width="100%" height="{h}" aria-hidden="true" {F}>{body}</svg>'
def num(d, *keys):
    for k in keys:
        v = d.get(k)
        if isinstance(v, (int, float)): return v
    return None


def kachel_hub():
    cf = ia.fmp_get("cash-flow-statement", symbol=HUB[0], period="annual", limit=5)
    if not cf or len(cf) < 5: return None
    cf = sorted(cf, key=lambda x: x["date"])[-5:]
    v = [num(x, "freeCashFlow") for x in cf]
    if any(a is None for a in v) or min(v) <= 0 or v[-2] <= 0: return None
    k = logo(HUB[0]);
    if not k: return None
    mx = max(v); g = (v[-1] / v[-2] - 1) * 100
    s = img(k, 4, 1, 17) + f'<text x="26" y="14" font-size="11" font-weight="700" fill="#2f6fdb">{de(v[-1]/1e9)} Mrd. USD</text>'
    s += f'<text x="{26+len(de(v[-1]/1e9)+" Mrd. USD")*5.6+6:.0f}" y="14" font-size="9" font-weight="700" fill="{"#1f9d55" if g>=0 else "#d64545"}">{"+" if g>=0 else "−"}{abs(g):.0f} %</text>'
    for i, (x, val) in enumerate(zip(cf, v)):
        h = max(6, round(58 * val / mx)); xx = 8 + i * 36; last = i == 4
        s += f'<rect x="{xx}" y="{82-h}" width="26" height="{h}" rx="2" fill="{"#2f6fdb" if last else "#cddcf8"}"/>'
        s += f'<text x="{xx+13}" y="93" font-size="7.5" text-anchor="middle" fill="#5d6b78"{" font-weight=\"700\"" if last else ""}>{x.get("fiscalYear") or x.get("calendarYear") or x["date"][:4]}</text>'
    return s + '<line x1="4" x2="196" y1="82" y2="82" stroke="#dfe5ea"/>'


def kachel_screener():
    rows = []
    for sym, name in SCREENER:
        r = ia.fmp_get("ratios-ttm", symbol=sym)
        r = r[0] if isinstance(r, list) and r else None
        if not r: return None
        y = num(r, "dividendYieldTTM"); pe = num(r, "priceToEarningsRatioTTM", "peRatioTTM"); po = num(r, "dividendPayoutRatioTTM")
        k = logo(sym)
        if None in (y, pe, po) or not k: return None
        rows.append((sym, k, y * 100, pe, po * 100))
    s = '<rect x="2" y="2" width="196" height="18" rx="4" fill="#f0f8f3"/>'
    for t, x, a in (("Aktie", 8, "start"), ("Rendite", 118, "end"), ("KGV", 156, "end"), ("Quote", 192, "end")):
        s += f'<text x="{x}" y="14" font-size="8.5" font-weight="700" fill="#5d6b78" text-anchor="{a}">{t}</text>'
    for i, (sym, k, y, pe, po) in enumerate(rows):
        t = 24 + i * 22
        s += img(k, 6, t) + f'<text x="28" y="{t+12}" font-size="9.5" font-weight="700" fill="#14202b">{sym}</text>'
        s += f'<text x="118" y="{t+12}" font-size="9.5" font-weight="700" fill="#1a7a45" text-anchor="end">{de(y)} %</text><text x="156" y="{t+12}" font-size="9.5" fill="#14202b" text-anchor="end">{de(pe)}</text><text x="192" y="{t+12}" font-size="9.5" fill="#14202b" text-anchor="end">{po:.0f} %</text>'
        if i < 2: s += f'<line x1="2" x2="198" y1="{t+18}" y2="{t+18}" stroke="#eef1f4"/>'
    return s


def kachel_depot():
    cols = ["#2f6fdb", "#1596a8", "#1f9d55"]; s = '<text x="6" y="12" font-size="10" font-weight="700" fill="#14202b">Verteilung</text>'
    x = 6
    for (sym, n, p), c in zip(DEPOT, cols):
        w = round(188 * p / 100); s += f'<rect x="{x}" y="18" width="{w}" height="9" fill="{c}"/>'; x += w
    for i, (sym, n, p) in enumerate(DEPOT):
        k = logo(sym)
        if not k: return None
        y = 36 + i * 19
        s += img(k, 6, y) + f'<text x="28" y="{y+11}" font-size="9.5" fill="#14202b">{n}</text><text x="194" y="{y+11}" font-size="9.5" font-weight="700" text-anchor="end" fill="#14202b">{p} %</text>'
    return s


def kachel_earnings():
    heute = datetime.date.today()
    cal = ia.fmp_get("earnings-calendar", **{"from": (heute - datetime.timedelta(days=3)).isoformat(), "to": (heute + datetime.timedelta(days=14)).isoformat()})
    if not cal: return None
    best = []
    for grp in EARN_GRUPPEN:
        got = {}
        for x in cal:
            if x.get("symbol") in grp[0] and x.get("date") and x["symbol"] not in got: got[x["symbol"]] = x
        c = sorted(got.values(), key=lambda x: x["date"])
        if len(c) > len(best) or (len(c) == len(best) and c and best and c[0]["date"] > best[0]["date"]): best = c
    best = [x for x in best if num(x, "epsEstimated") is not None][:3]
    if len(best) < 3: return None
    s = ""; WT = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
    for i, x in enumerate(best):
        k = logo(x["symbol"]); d = datetime.date.fromisoformat(x["date"][:10]); y = 2 + i * 32
        if not k: return None
        ist = num(x, "epsActual", "eps")
        s += f'<rect x="2" y="{y}" width="196" height="26" rx="6" fill="#fff" stroke="#dfe5ea"/>' + img(k, 8, y + 5)
        s += f'<text x="30" y="{y+11}" font-size="7.5" fill="#5d6b78">{WT[d.weekday()]}, {d.strftime("%d.%m.")}</text><text x="30" y="{y+21}" font-size="10" font-weight="700" fill="#14202b">{x["symbol"]}</text>'
        s += f'<text x="190" y="{y+11}" font-size="7.5" fill="#5d6b78" text-anchor="end">Schätzung {de(x["epsEstimated"], 2)}</text>'
        s += f'<text x="190" y="{y+21}" font-size="10" font-weight="700" fill="{"#1f9d55" if ist is not None and ist >= x["epsEstimated"] else ("#d64545" if ist is not None else "#5d6b78")}" text-anchor="end">{de(ist, 2)+" $" if ist is not None else "–"}</text>'
    return s


def main():
    s = open("index.html", encoding="utf-8").read(); n = 0
    for href, fn in (("aktien", kachel_hub), ("screener", kachel_screener), ("earnings", kachel_earnings)):
        try: body = fn()
        except Exception as e: print(href, "Fehler:", type(e).__name__, e); body = None
        if not body: print(href, ": keine Daten, bleibt unveraendert"); continue
        pat = re.compile(r'(<a class="tile" href="%s/"><div class="pv">).*?(</div>)' % href, re.S)
        s2 = pat.sub(lambda m: m.group(1) + svg(body) + m.group(2), s, count=1)
        if s2 != s: n += 1; s = s2; print(href, ": aktualisiert")
    open("index.html", "w", encoding="utf-8").write(s); print(n, "Kacheln aktualisiert")

if __name__ == "__main__": main()
