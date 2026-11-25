import re, sys
sys.path.insert(0, "tools")
import idx_fundamentals as F
nam, t = F.bericht("TLKM", 2025)
print("Laenge", len(t) if t else None)
if t:
    print("contexts-tag count", t.count("<xbrli:context"), " xbrli:context id-Beispiel:", re.findall(r'<xbrli:context[^>]*>', t)[:2])
    print("Beispiel fact:", re.findall(r'<idx-cor:SalesAndRevenue[^>]*>[^<]*', t)[:2])
    print("Kontext-Anzahl erkannt:", len(F.kontexte(t)))
    w = F.werte(t)
    print("werte gesamt:", len(w), list(w.items())[:3])
    print("jahreswerte:", {k: v[:2] for k, v in F.jahreswerte(w).items()})
