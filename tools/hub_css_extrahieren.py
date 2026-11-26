"""Zieht die Ansicht-Styles aus aktien-hub/index.html in assets/firma-ansicht.css (alles unter #hub)."""
import re
raw=open('aktien-hub/index.html').read().split('\n')[9:219]
raw=re.sub(r'</?style>','','\n'.join(raw))
def split_rules(s):
    out=[];i=0;n=len(s)
    while i<n:
        j=s.find('{',i)
        if j<0:break
        k=j;d=0
        while k<n:
            if s[k]=='{':d+=1
            elif s[k]=='}':
                d-=1
                if d==0:break
            k+=1
        out.append((s[i:j].strip(),s[j+1:k]));i=k+1
    return out
SKIP=re.compile(r'^(body|main|html|:root|\.top|#sug|\.sr|\.tiles|\.tile|\.scr[a-z]*|\.subnav.*|#scrchips.*|#hub-global-header.*|\.hub-.*)(?![a-z-])')
def prefix(sel):
    return ','.join(p.strip() if p.strip().startswith('#hub') else '#hub '+p.strip() for p in sel.split(','))
out=[];vars_=''
for sel,body in split_rules(raw):
    if sel.startswith('@media'):
        inner=[prefix(s2)+'{'+b2+'}' for s2,b2 in split_rules(body) if not SKIP.match(s2.split(',')[0].strip())]
        if inner:out.append(sel+'{'+''.join(inner)+'}')
        continue
    if sel==':root':vars_=body;continue
    if SKIP.match(sel.split(',')[0].strip()):continue
    out.append(prefix(sel)+'{'+body+'}')
open('assets/firma-ansicht.css','w').write('#hub{'+vars_+'}\n'+'\n'.join(out)+'\n')
