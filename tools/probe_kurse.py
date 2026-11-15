"""Prueft, welche kostenlosen Quellen aus GitHub Actions Japan- und Korea-Kurse liefern."""
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}
TESTS = {
    "stooq 7203.jp": "https://stooq.com/q/l/?s=7203.jp&f=sd2t2ohlcv&h&e=csv",
    "stooq 005930.kr": "https://stooq.com/q/l/?s=005930.kr&f=sd2t2ohlcv&h&e=csv",
    "yahoo query2 7203.T": "https://query2.finance.yahoo.com/v8/finance/chart/7203.T?range=5d&interval=1d",
    "yahoo 005930.KS": "https://query1.finance.yahoo.com/v8/finance/chart/005930.KS?range=5d&interval=1d",
}
for name, url in TESTS.items():
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read(400).decode("utf-8", "replace").replace("\n", " | ")
        print(f"{name}: OK {body[:300]}")
    except Exception as e:
        print(f"{name}: FEHLER {type(e).__name__} {e}")
