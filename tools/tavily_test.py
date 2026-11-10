#!/usr/bin/env python3
"""Einmal-Test der Tavily-Suche (Secret TAVILY_API_KEY). Gibt Treffer mit Quelle aus, schreibt nichts ins Repository."""
import json, os, sys, urllib.request
key = os.environ.get("TAVILY_API_KEY", "").strip()
if not key:
    sys.exit("Das GitHub-Secret TAVILY_API_KEY fehlt.")
frage = os.environ.get("FRAGE") or "Japan Tobacco Russland vorläufige Verwaltung Aktie"
body = {"query": frage, "topic": "news", "search_depth": "basic", "max_results": 6, "days": 7, "include_answer": True}
req = urllib.request.Request("https://api.tavily.com/search", data=json.dumps(body).encode(),
                             headers={"Content-Type": "application/json", "Authorization": "Bearer " + key})
with urllib.request.urlopen(req, timeout=60) as r:
    d = json.loads(r.read().decode())
print("Frage:", frage)
print("Antwort:", (d.get("answer") or "")[:800])
for t in d.get("results", []):
    print("-", t.get("title"), "|", t.get("url"), "|", (t.get("published_date") or "")[:10])
    print("   ", (t.get("content") or "")[:220].replace("\n", " "))
print("Verbrauch:", d.get("usage") or d.get("response_time"))
