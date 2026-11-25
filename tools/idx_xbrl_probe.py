"""Probe: laedt die XBRL-Instanz eines IDX-Jahresberichts (BBCA 2025) und listet die Kennzahl-Namen."""
import collections, io, json, re, urllib.request, zipfile

UA = {"User-Agent": "Mozilla/5.0 (dividenden-rechner.de Datensammlung)", "Accept": "application/json"}
API = "https://www.idx.id/primary/ListedCompany/GetFinancialReport?indexFrom=0&pageSize=12&year={j}&reportType=rdf&periode=audit&kodeEmiten={k}&SortColumn=KodeEmiten&SortOrder=asc"

def get(u):
    return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60).read()

d = json.loads(get(API.format(j=2025, k="BBCA")))
anh = d["Results"][0]["Attachments"]
zipdatei = next(a for a in anh if a["File_Name"] in ("instance.zip", "inlineXBRL.zip"))
pfad = "https://www.idx.id" + zipdatei["File_Path"]
print("Datei:", zipdatei["File_Name"], pfad[:140])
import subprocess
print(subprocess.run(["curl","-s","-L","-m","60","-A",UA["User-Agent"],"-H","Referer: https://www.idx.id/","-o","/tmp/x.zip","-w","HTTP %{http_code} %{size_download}\n",pfad],capture_output=True,text=True).stdout)
print(subprocess.run(["head","-c","200","/tmp/x.zip"],capture_output=True,text=True).stdout)
z = zipfile.ZipFile("/tmp/x.zip")
print("Inhalt:", z.namelist()[:20])
inst = next((n for n in z.namelist() if n.endswith((".xbrl", ".xml", ".html", ".xhtml"))), z.namelist()[0])
txt = z.read(inst).decode("utf-8", "replace")
print("Instanz:", inst, len(txt))
namen = collections.Counter(re.findall(r"<([a-zA-Z][\w.-]*:[\w.-]+)[\s>]", txt))
print("Anzahl verschiedener Konzepte:", len(namen))
for n, c in namen.most_common(400):
    if not n.startswith(("xbrli:", "link:", "xlink:", "xbrldi:", "iso4217:")):
        print(c, n)
