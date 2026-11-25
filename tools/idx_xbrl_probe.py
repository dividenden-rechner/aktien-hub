"""Probe: laedt die XBRL-Instanz eines IDX-Jahresberichts (BBCA 2025) und listet die Kennzahl-Namen."""
import collections, io, json, re, urllib.request, zipfile

UA = {"User-Agent": "Mozilla/5.0 (dividenden-rechner.de Datensammlung)", "Accept": "application/json"}
API = "https://www.idx.id/primary/ListedCompany/GetFinancialReport?indexFrom=0&pageSize=12&year={j}&reportType=rdf&periode=audit&kodeEmiten={k}&SortColumn=KodeEmiten&SortOrder=asc"

def get(u):
    return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60).read()

d = json.loads(get(API.format(j=2025, k="BBCA")))
anh = d["Results"][0]["Attachments"]
zipdatei = next(a for a in anh if a["File_Name"] == "instance.zip")
import urllib.parse
pfad = "https://www.idx.id" + urllib.parse.quote(zipdatei["File_Path"], safe="/:")
print("Datei:", zipdatei["File_Name"], pfad[:140])
import subprocess
print(subprocess.run(["curl","-s","-L","-m","60","-A",UA["User-Agent"],"-H","Referer: https://www.idx.id/","-o","/tmp/x.zip","-w","HTTP %{http_code} %{size_download}\n",pfad],capture_output=True,text=True).stdout)
z = zipfile.ZipFile("/tmp/x.zip")
print("Inhalt:", z.namelist()[:20])
import re as _re
for n in z.namelist():
    if n.lower().endswith((".xbrl", ".xml")):
        t = z.read(n).decode("utf-8", "replace")
        print("Datei in ZIP:", n, len(t))
        konz = collections.Counter(_re.findall(r"<([a-zA-Z][\w.-]*:[\w.-]+)[\s>]", t))
        print("Konzepte gesamt:", len(konz))
        for k2, c in konz.most_common(260):
            if not k2.startswith(("xbrli:", "link:", "xlink:", "xbrldi:", "iso4217:", "xsi:")):
                print(c, k2)
        break
else:
    print("Keine XBRL-Datei im ZIP:", z.namelist()[:30])
