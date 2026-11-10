#!/usr/bin/env python3
"""Einmal-Test der Ausweichanbieter: Groq (Schreiben) und Tavily (Recherche). Schreibt nichts ins Repository."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ir_agent as ia
print("GROQ_API_KEY gesetzt:", bool(os.environ.get("GROQ_API_KEY", "").strip()))
schema = {"type": "OBJECT", "required": ["titel", "kurz"], "properties": {"titel": {"type": "STRING"}, "kurz": {"type": "STRING"}}}
text = ("Schreibe eine Ueberschrift (max. 90 Zeichen) und eine Kurzmeldung (2 Saetze, Deutsch, sachlich) zu folgender Meldung: "
        "Japan Tobacco meldet, dass Russland am 5. und 6. November alle russischen Gesellschaften des Konzerns unter vorlaeufige Verwaltung gestellt hat. "
        "Russland steht fuer rund 10 % des Umsatzes und rund 25 % des bereinigten operativen Gewinns. Die Aktie fiel zwei Tage in Folge um das Tageslimit.")
out = ia.groq_generate([{"text": text}], schema)
print("Groq-Ergebnis:", out)
t, src = ia.tavily_ground("Recherchiere mit der Websuche Hintergrund fuer einen Artikel über Japan Tobacco (2914.T), Dokument: Mitteilung Russland,")
print("Tavily-Treffer:", len(src))
print(t[:1200])

import json, urllib.request
try:
    req = urllib.request.Request("https://api.groq.com/openai/v1/models", headers={"Authorization": "Bearer " + os.environ.get("GROQ_API_KEY", "").strip(), "User-Agent": "dividenden-rechner-ir/1.0"})
    d = json.load(urllib.request.urlopen(req, timeout=60))
    print("Groq-Modelle:", sorted((m.get("id"), m.get("context_window")) for m in d.get("data", []) if m.get("active", True)))
except Exception as e:
    print("Modellliste-Problem ->", e)
