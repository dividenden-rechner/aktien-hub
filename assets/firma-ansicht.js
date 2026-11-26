/* Firmenansicht (gemeinsam für Aktien-Hub-Suche und Firmenseiten)
   Steckbrief, Kennzahlen, Diagramme, Unternehmensmeldungen. Läuft ohne FMP: nur eigene Daten (SEC, ESEF, Deutsche Börse, Asien).
   FA_ROOT zeigt auf das Wurzelverzeichnis der Seite ("../" im Hub, "../../" auf Firmenseiten). */
let FA_NUR_EIGEN;
const FA_ROOT = (typeof window!=="undefined" && window.FA_ROOT) || "../";
const $ = id => document.getElementById(id);
const logo = s => `https://images.financialmodelingprep.com/symbol/${encodeURIComponent(s)}.png`;
const img = (s,web,nm) => { const d = web ? String(web).replace(/^https?:\/\/(www\.)?/, "").split("/")[0] : ""; return window.HubLogos ? HubLogos.img("logo", s, d, nm || s) : `<img class="logo" src="${logo(s)}" alt="" onerror="this.style.visibility='hidden'">`; };
const esc = s => String(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));

const one = a => Array.isArray(a)?(a[0]||{}):(a||{});
/* ===== SEC-Fundamentaldaten (US-Behördendaten, data/sec/fundamentals.json, wöchentlich aktualisiert) =====
   Jahreswerte aus den 10-K/20-F-Berichten. Sie haben Vorrang vor FMP; FMP füllt nur Felder, die die SEC nicht liefert
   (z. B. Bruttogewinn, operatives Ergebnis). Bilanz: FMP zuerst, weil „Schulden gesamt“ dort auch kurzfristige Schulden enthält. */
let SECP=null;
function secLoad(){const v=Math.floor(Date.now()/864e5),j=u=>fetch(u+"?v="+v).then(r=>r.ok?r.json():null).catch(()=>null);
  return SECP||(SECP=Promise.all([j(FA_ROOT+"data/sec/fundamentals.json"),j(FA_ROOT+"data/esef/fundamentals.json"),j(FA_ROOT+"data/boerse-de/fundamentals.json"),j(FA_ROOT+"data/asien/fundamentals.json"),j(FA_ROOT+"data/sec/vorab.json")]).then(([s,e,b,a,vb])=>{
    if(!s&&!e&&!b&&!a)return null;s=s||{firmen:{}};if(e&&e.firmen)for(const t in e.firmen)if(!s.firmen[t])s.firmen[t]=e.firmen[t];
    /* Asien (Geschäftsberichte HK/SG/CN, asia-equity-hub): nur Firmen, die noch nicht vorhanden sind */
    if(a&&a.firmen)for(const t in a.firmen)if(!s.firmen[t])s.firmen[t]=a.firmen[t];
    /* boerse.de (2019 bis 2025): neue Firmen komplett, vorhandene nur um fehlende Reihen und Jahre ergänzt */
    if(b&&b.firmen)for(const t in b.firmen){const bf=b.firmen[t],o=s.firmen[t];if(!o){s.firmen[t]=bf;continue}
      o.k=o.k||{};for(const k in bf.k){const have=new Set((o.k[k]||[]).map(([d])=>secJahr(d)));const add=bf.k[k].filter(([d])=>!have.has(secJahr(d)));if(add.length)o.k[k]=(o.k[k]||[]).concat(add).sort((x,y)=>x[0]<y[0]?-1:1)}}
    /* Vorab-Zahlen aus Ergebnismeldungen (data/sec/vorab.json): neues Geschäftsjahr, bis der SEC-Jahresbericht da ist; vorhandene Jahre bleiben unberührt */
    if(vb&&vb.firmen)for(const t in vb.firmen){const v=vb.firmen[t],o=s.firmen[t];if(!o||!v.gj||!v.k||(v.w&&o.w&&v.w!==o.w))continue;const y=secJahr(v.gj);let n=0;o.k=o.k||{};
      for(const k in v.k){if(v.k[k]==null||(o.k[k]||[]).some(([d])=>secJahr(d)===y))continue;o.k[k]=(o.k[k]||[]).concat([[v.gj,v.k[k]]]).sort((x,z)=>x[0]<z[0]?-1:1);n++}
      if(n&&!o.quelle)o.quelle="SEC+vorab:"+y+"|"+new Date(v.meldung).toLocaleDateString("de-DE")}
    return s}))}
let KZP=null;
function kzLoad(){const v=Math.floor(Date.now()/36e5),j=u=>fetch(u+"?v="+v).then(r=>r.ok?r.json():null).catch(()=>null);
  /* Asien-Kennzahlen (Kurs Deutsche Börse + Geschäftsbericht) ergänzen nur fehlende Firmen */
  return KZP||(KZP=Promise.all([j(FA_ROOT+"data/kennzahlen.json"),j(FA_ROOT+"data/asien/kennzahlen.json")]).then(([a,b])=>{
    if(!a&&!b)return null;a=a||{werte:{}};if(b&&b.werte)for(const t in b.werte)if(!a.werte[t])a.werte[t]=b.werte[t];return a}))}
/* Eigene Kennzahlen: Schlusskurs (Deutsche Börse, verzögert) + SEC-Jahreszahlen + EZB-Kurse; Tabelle im Stil des Steckbriefs */
function kzTabelle(K){
  if(!K)return "";
  const pc=(v,d=1)=>v==null?"–":num(v,d)+" %",x=(v,d=1)=>v==null?"–":num(v,d),xx=(v,d=1)=>v==null?"–":num(v,d)+"×";
  const verlust=K.eps!=null&&K.eps<=0;
  const kgv=K.kgv!=null?x(K.kgv):verlust?'<span class="neg">negativ</span>':"–";
  const reit=K.sektor==="Real Estate";
  const B=[
   ["Bewertung",[["KGV",kgv,verlust?"Verlust im letzten Geschäftsjahr, KGV nicht sinnvoll":"Kurs / Gewinn je Aktie"],...(K.prognose&&K.prognose.kgv_forward!=null?[["Forward-KGV",x(K.prognose.kgv_forward),"Kurs / erwarteter Gewinn je Aktie für "+esc(K.prognose.eps_jahr)]]:[]),["KBV",x(K.kbv,2),"Börsenwert / Eigenkapital"],["KUV",x(K.kuv,2),"Börsenwert / Umsatz"],
     ["Kurs / Cashflow",x(K.kcv),"Börsenwert / operativer Cashflow"],["Kurs / freier Cashflow",x(K.kfcf),"Börsenwert / freier Cashflow"],["EV / EBITDA",x(K.ev_ebitda),"Unternehmenswert / EBITDA"],
     ["EV / Umsatz",x(K.ev_umsatz,2),"Unternehmenswert / Umsatz"],["PEG",x(K.peg,2),"KGV / Gewinnwachstum je Aktie (5 J.)"],["FCF-Rendite",pc(K.fcf_rendite,2),"Freier Cashflow / Börsenwert"]]],
   ["Dividende",[["Dividendenrendite",K.dividende_basis==="ausgesetzt"?"ausgesetzt":pc(K.rendite,2),K.dividende_basis==="ausgesetzt"?esc(K.dividende_hinweis||"keine laufende Dividende"):""],
     ["Dividende je Aktie",K.dividende==null?"–":x(K.dividende,2)+" "+esc(K.waehrung),K.dividende_basis==="ausgesetzt"?"":(K.dividende_basis==="aktuell"?"pro Jahr, aufs Jahr gerechnet":"Geschäftsjahr")+(K.dividende_berechnet?" (nachgerechnet)":"")],
     ["Zahlweise",K.zahlweise?esc(K.zahlweise):"–",K.zahlmonate&&K.zahlmonate.length?"Zahlmonate: "+esc(K.zahlmonate.join(", ")):"Monate offen"],
     ...(K.dividende_sonder?[["Sonderdividenden (12 Monate)",x(K.dividende_sonder,2)+" "+esc(K.waehrung),`zusätzlich ${pc(K.rendite_sonder,2)} Rendite, in der Dividendenrendite nicht enthalten`]]:[]),
     ["Ausschüttungsquote",verlust&&K.dividende?'<span class="neg">über Gewinn</span>':pc(K.ausschuettung,0),"Dividende / Gewinn je Aktie"],["Ausschüttung / freier Cashflow",pc(K.fcf_ausschuettung,0)+(K.fcf_ausschuettung>100?"*":""),"Gezahlte Dividenden / freier Cashflow"+(K.fcf_ausschuettung>100?"<br>* Über 100 % deutet oft auf Sondereffekte hin, etwa Zahlungen für zugekaufte Firmen, Steuernachzahlungen oder andere Einmalzahlungen.":"")],
     ["Dividendenwachstum",`1 Jahr: ${pc(K.div_wachstum_1j)}<br>5 Jahre: ${pc(K.div_wachstum_5j)}<br>10 Jahre: ${pc(K.div_wachstum_10j)}`,"pro Jahr"],
     ["Erhöhungen in Folge",K.dividendenserie==null?"–":K.dividendenserie>=99?"9+ Jahre":K.dividendenserie+" Jahre","innerhalb der letzten zehn Jahre"]]],
   ["Profitabilität",[["Bruttomarge",pc(K.bruttomarge),"Bruttogewinn / Umsatz"],["Operative Marge",pc(K.operative_marge),"Operatives Ergebnis / Umsatz"+(K.ebit_berechnet?" (nachgerechnet)":"")],
     ["EBITDA-Marge",pc(K.ebitda_marge),"EBITDA / Umsatz"],["Nettomarge",pc(K.nettomarge),"Nettogewinn / Umsatz"],["Eigenkapitalrendite (ROE)",pc(K.roe),"Nettogewinn / Eigenkapital"],
     ["ROCE",pc(K.roce),"Ergebnis / eingesetztes Kapital"],["ROIC",pc(K.roic),"Operatives Ergebnis nach 21 % Steuern / (Schulden + Eigenkapital)"]]],
   ["Bilanz",[["Nettoschulden / EBITDA",K.nettoschulden_ebitda!=null&&K.nettoschulden_ebitda<0?"Netto-Cash":xx(K.nettoschulden_ebitda),"In wie vielen Jahren das EBITDA die Nettoschulden tilgen würde"],
     ["Zinsdeckung",xx(K.zinsdeckung),"Operatives Ergebnis / Zinsaufwand"],["Schulden / Eigenkapital",x(K.schulden_ek,2),"Langfristige Schulden / Eigenkapital"],
     ["Current Ratio",x(K.current_ratio,2),"Umlaufvermögen / kurzfristige Verbindlichkeiten"]]],
   ["Wachstum",[["Umsatz",`letztes Jahr: ${pc(K.umsatz_wachstum)}<br>pro Jahr, 5 Jahre: ${pc(K.umsatz_wachstum_5j)}`,""],["Gewinn",`letztes Jahr: ${pc(K.gewinn_wachstum)}<br>pro Jahr, 5 Jahre: ${pc(K.gewinn_wachstum_5j)}`,""],
     ["Gewinn je Aktie",pc(K.eps_wachstum),"letztes Jahr"],["Freier Cashflow",pc(K.fcf_wachstum),"letztes Jahr"]]],
   ["Qualität",[["Piotroski-Score",K.piotroski==null?"–":K.piotroski+" von 9","Neun Prüfungen zu Gewinn, Cashflow, Schulden und Effizienz; ab 7 gilt als stark"+(K.piotroski==null?"":`<span class="zb"><span class="zbg segs"><i class="fill" style="width:${Math.min(100,Math.max(0,K.piotroski/9*100))}%"></i></span><small><span>0</span><span>9</span></small></span>`)],
     ["Altman-Z",x(K.altman_z,2),"Insolvenzrisiko-Kennzahl; über 3 gilt als sicher, unter 1,8 als gefährdet (nicht für Banken)"+(K.altman_z==null?"":`<span class="zb"><span class="zbg"><i class="mk" style="left:${Math.min(100,Math.max(0,K.altman_z/6*100))}%"></i></span><small><span>0</span><span>1,8</span><span>3</span><span>6+</span></small></span>`)]]]];
  const F=K.prognose;
  if(F){const R=[];
    if(F.eps_wachstum_erwartet!=null)R.push(["Erwartetes Gewinnwachstum",pc(F.eps_wachstum_erwartet),"Mitte der Prognose gegenüber dem letzten Geschäftsjahr"]);
    if(F.umsatz_wachstum_erwartet!=null)R.push(["Erwartetes Umsatzwachstum",pc(F.umsatz_wachstum_erwartet),"Umsatzprognose für "+esc(F.umsatz_jahr)+" gegenüber dem letzten Geschäftsjahr"]);
    else if(F.umsatz_wachstum_von!=null)R.push(["Erwartetes Umsatzwachstum",F.umsatz_wachstum_von===F.umsatz_wachstum_bis?pc(F.umsatz_wachstum_von):`${num(F.umsatz_wachstum_von,1)} bis ${num(F.umsatz_wachstum_bis,1)} %`,"Prognose für "+esc(F.umsatz_jahr)]);
    if(F.rendite_erwartet!=null)R.push(["Erwartete Dividendenrendite",pc(F.rendite_erwartet,2),`Angekündigte Dividende ${x(F.dividende_erwartet,2)} ${esc(K.waehrung)} für ${esc(F.dividende_jahr)}`]);
    if(R.length)B.splice(1,0,[`Ausblick des Unternehmens`,R.concat([["Quelle",`<a href="${esc(F.quelle)}" target="_blank" rel="noopener">Ergebnismeldung</a>`,"vom "+new Date(F.datum).toLocaleDateString("de-DE")+"; eigene Prognose des Unternehmens, keine Analystenschätzung"]])]);}
  const D=K.bdc;
  if(D){B.splice(0,B.length);B.push(["BDC (Quartal bis "+new Date(D.quartal).toLocaleDateString("de-DE")+")",[
    ["NAV je Aktie",x(D.nav,2)+" USD",D.nav_1j!=null?"Veränderung zum Vorjahresquartal "+(D.nav_1j>0?"+":"")+num(D.nav_1j,1)+" %":"Nettovermögenswert laut Quartalsmeldung"],
    ["Kurs/NAV",x(D.kurs_nav,2),D.kurs_nav!=null?(D.kurs_nav<1?"Abschlag von "+num((1-D.kurs_nav)*100,0)+" % auf den NAV":"Aufschlag von "+num((D.kurs_nav-1)*100,0)+" % auf den NAV"):""],
    ["NII je Aktie",x(D.nii,2)+" USD","Nettoanlageergebnis im Quartal (bereinigt, falls angegeben)"],
    ["NII-Rendite",pc(D.nii_rendite,2),"NII × 4 / Kurs"],
    ["Dividende je Quartal",x(D.dividende_regulaer,2)+" USD"+(D.dividende_zusatz?" + "+x(D.dividende_zusatz,2)+" Zusatz":""),"zuletzt beschlossen"],
    ["Dividendenrendite",pc(D.rendite,2)+(D.rendite_inkl_zusatz&&D.rendite_inkl_zusatz!==D.rendite?" ("+pc(D.rendite_inkl_zusatz,2)+" mit Zusatz)":""),"regulär × 4 / Kurs"],
    ["Dividendendeckung",pc(D.deckung,0),"NII / regulärer Dividende; unter 100 % wird die Dividende nicht verdient"],
    ["Non-Accruals",pc(D.non_accrual,1),"Notleidende Kredite in % vom Portfolio (Fair Value)"],
    ["Verschuldung (netto)",xx(D.verschuldung,2),"Schulden / Eigenkapital"],
    ["Portfolio",D.portfolio_mio?num(D.portfolio_mio/1000,2)+" Mrd. USD":"–","Fair Value der Investments"],
    ["Quelle",D.quelle?`<a href="${esc(D.quelle)}" target="_blank" rel="noopener">Quartalsmeldung</a>`:"–","Kurs: Deutsche Börse, verzögert, mit EZB-Kurs in USD umgerechnet"]]])}
  if(reit)B.push(["REIT",[["FFO je Aktie",x(K.ffo_je_aktie,2)+" "+esc(K.waehrung),"Nettogewinn plus Abschreibungen je Aktie (Näherung)"],["Kurs/FFO",x(K.kurs_ffo),"Bei REITs aussagekräftiger als das KGV"],["FFO-Ausschüttungsquote",pc(K.ffo_ausschuettung,0),"Gezahlte Dividenden / FFO"]]]);
  /* Jede Kategorie als eigene Karte, abwechselnd hellgrün und weiß, mit Abstand (auf dem Desktop nebeneinander) */
  const karten=B.map(([t,R],i)=>`<section class="kzk ${i%2?"kzk-weiss":"kzk-gruen"}"><h3>${t}</h3><table><tbody>${R.map(r=>`<tr><td class="k">${r[0]}</td><td class="v">${r[1]}</td><td class="d">${r[2]}</td></tr>`).join("")}</tbody></table></section>`).join("");
  let chart="";
  if(D&&D.verlauf&&D.verlauf.length>1){const V=D.verlauf.slice(-12),W=740,H=220,l=46,r=46,t=16,b=28,iw=W-l-r,ih=H-t-b,n=V.length;
    const navs=V.map(v=>v[1]).filter(v=>v),nmin=Math.min(...navs)*.97,nmax=Math.max(...navs)*1.02,bmax=Math.max(...V.map(v=>Math.max(v[2]||0,v[3]||0)))*1.15||1;
    const X=i=>l+iw*(i+.5)/n,YN=v=>t+ih*(1-(v-nmin)/((nmax-nmin)||1)),YB=v=>t+ih*(1-v/bmax),bw=Math.min(16,iw/n/3);
    let g=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="NAV, NII und Dividende je Quartal">`;
    V.forEach((v,i)=>{if(v[2])g+=`<rect x="${X(i)-bw-1}" y="${YB(v[2])}" width="${bw}" height="${t+ih-YB(v[2])}" fill="#15803d" opacity=".85"><title>${v[0]} NII ${num(v[2],2)}</title></rect>`;if(v[3])g+=`<rect x="${X(i)+1}" y="${YB(v[3])}" width="${bw}" height="${t+ih-YB(v[3])}" fill="#8cc63f" opacity=".9"><title>${v[0]} Dividende ${num(v[3],2)}</title></rect>`;
      g+=`<text x="${X(i)}" y="${H-8}" text-anchor="middle" font-size="11" fill="#5d6b78">${"Q"+(Math.floor((+v[0].slice(5,7)-1)/3)+1)+" ’"+v[0].slice(2,4)}</text>`});
    let pth="";V.forEach((v,i)=>{if(v[1])pth+=(pth?"L":"M")+X(i)+","+YN(v[1])});
    g+=`<path d="${pth}" fill="none" stroke="#2563eb" stroke-width="2.5"/>`+V.map((v,i)=>v[1]?`<circle cx="${X(i)}" cy="${YN(v[1])}" r="3.5" fill="#2563eb"><title>${v[0]} NAV ${num(v[1],2)}</title></circle>`:"").join("");
    g+=`<text x="${l-6}" y="${t+10}" text-anchor="end" font-size="11" fill="#2563eb">${num(nmax,0)}</text><text x="${l-6}" y="${t+ih}" text-anchor="end" font-size="11" fill="#2563eb">${num(nmin,0)}</text><text x="${W-r+6}" y="${t+10}" font-size="11" fill="#5d6b78">${num(bmax,2)}</text></svg>`;
    chart=`<div class="fcard"><div class="fctl"><b>NAV, NII und Dividende je Quartal</b></div><div class="kleg"><span><i style="background:#2563eb"></i>NAV je Aktie (linke Achse)</span><span><i style="background:#15803d"></i>NII je Aktie</span><span><i style="background:#8cc63f"></i>Dividende je Aktie</span></div><div class="fscroll fit">${g}</div><p class="fnote">Liegen die dunkelgrünen Balken unter den lindgrünen, verdient die BDC ihre Dividende nicht vollständig. Ein fallender NAV kann auf Kreditausfälle hindeuten.</p></div>`}
  return chart+`<div class="kzgrid">${karten}</div><div class="stk kz"><p class="sn">Kurs: Schluss des letzten Handelstags (${esc(K.boerse||"Xetra")}, ${new Date(K.datum).toLocaleDateString("de-DE")}), Deutsche Börse, 15 Minuten verzögert. Kennzahlen aus dem Jahresbericht ${esc(K.gj)} ${K.bericht?"(Geschäftsbericht, maschinell übernommen, ungeprüft)":K.land&&K.land!=="US"?"(europäisches Einheitsformat ESEF)":"bei der US-Börsenaufsicht SEC"}, Kurs mit dem EZB-Referenzkurs umgerechnet.${K.hinweis?" "+esc(K.hinweis)+".":""} Keine Anlageberatung.</p></div>`;
}
/* Herkunft der Jahreswerte für Beschriftungen */
function quelleText(q,kurz){return q&&String(q).startsWith("SEC+vorab:")?(kurz?"SEC":"Jahresberichte bei der SEC")+"; "+String(q).slice(10).split("|")[0]+" vorläufig aus der Ergebnismeldung vom "+String(q).split("|")[1]+", Jahresbericht folgt":q==="CVM"?(kurz?"CVM":"Jahresabschlüsse bei der CVM (Brasilien), Open Data ODbL"):q==="EDINET"?(kurz?"EDINET":"Jahresberichte bei EDINET (Japan)"):q==="DART"?(kurz?"DART":"Jahresberichte bei DART (Korea)"):q==="boerse.de"?"boerse.de (Jahresabschlüsse)":q==="ESEF"?(kurz?"ESEF-Jahresberichte":"ESEF-Jahresberichte (europäisches Einheitsformat)"):q&&/Geschäftsbericht/.test(q)?(kurz?"Geschäftsbericht":"Geschäftsberichte (PDF), maschinell übernommen, ungeprüft"):(kurz?"SEC":"Jahresberichte bei der SEC")}
/* Ganzes Europa-Universum (data/esef/firma/<Kürzel>.json) und weitere Asien-Firmen (data/asien/firma/): erst beim Aufruf laden.
   Bei boerse.de-Firmen geht ESEF vor, boerse.de füllt nur fehlende Jahre. */
const FIRMA={};let FIDX=null;
function firmaIndex(){const v=Math.floor(Date.now()/864e5),j=u=>fetch(u+"?v="+v).then(r=>r.ok?r.json():{}).catch(()=>({}));
  return FIDX||(FIDX=Promise.all([j(FA_ROOT+"data/esef/firma/_index.json"),j(FA_ROOT+"data/asien/firma/_index.json"),j(FA_ROOT+"data/americas/firma/_index.json")]).then(([e,a,m])=>({...m,...a,...e})))}
async function firmaNachladen(S,sym){if(!S||!S.firmen)return;const t=String(sym).toUpperCase(),o=S.firmen[t];
  if(o&&!/^boerse\.de/.test(o.quelle||""))return;
  if(!(t in FIRMA)){FIRMA[t]=null;const v=Math.floor(Date.now()/864e5);
    for(const d of ["esef","asien","americas"]){const r=await fetch(FA_ROOT+`data/${d}/firma/${encodeURIComponent(t)}.json?v=${v}`).catch(()=>null);
      if(r&&r.ok){FIRMA[t]=await r.json().catch(()=>null);if(FIRMA[t])break}}}
  const f=FIRMA[t];if(!f)return;if(!o){S.firmen[t]=f;return}
  const n={...f,k:{...f.k}};for(const k in o.k||{}){const have=new Set((n.k[k]||[]).map(([d])=>secJahr(d)));const add=o.k[k].filter(([d])=>!have.has(secJahr(d)));if(add.length)n.k[k]=(n.k[k]||[]).concat(add).sort((x,y)=>x[0]<y[0]?-1:1)}
  S.firmen[t]=n}
function secFirma(S,sym){if(!S||!S.firmen)return null;const k=String(sym).toUpperCase();return S.firmen[k]||S.firmen[k.replace(/\./g,"-")]||null}
/* Geschäftsjahr wie bei FMP: endet es im Januar oder in der ersten Februarwoche, zählt es zum Vorjahr (Händler wie Home Depot) */
function secJahr(end){const d=new Date(end),m=d.getUTCMonth();return String(d.getUTCFullYear()-((m===0||(m===1&&d.getUTCDate()<=7))?1:0))}
function secReihe(f,k){const o={};(f.k[k]||[]).forEach(([e,v])=>o[secJahr(e)]=v);return o}
function secDaten(f){
  const R=k=>secReihe(f,k),gp=R("bruttogewinn"),opi=R("operatives_ergebnis"),zi=R("zinsaufwand"),stz=R("steuern"),abs_=R("abschreibungen"),skz=R("schulden_kurz"),rev=R("umsatz"),ni=R("gewinn"),eps=R("eps_verw"),epb=R("eps_ber"),sh=Object.fromEntries(Object.entries(R("aktien_verw")).map(([y,v])=>[y,v!=null&&v<1e6?v*1e6:v])),ocf=R("operativer_cf"),cx=R("capex"),dv=R("dividenden_gezahlt"),bb=R("aktienrueckkauf"),debt=R("schulden_lang"),cash=R("liquide_mittel"),eq=R("eigenkapital"),dps=R("dividende_je_aktie"),dpb=R("dividende_je_aktie_ber");
  const yrs=[...new Set([...Object.keys(rev),...Object.keys(ni),...Object.keys(ocf)])].sort();
  const neg=v=>v==null?undefined:-Math.abs(v),def=v=>v==null?undefined:v;
  /* Operatives Ergebnis: gemeldet oder näherungsweise Gewinn + Steuern + Zinsen */
  const ebit=y=>opi[y]??(ni[y]!=null&&stz[y]!=null&&zi[y]!=null?ni[y]+stz[y]+Math.abs(zi[y]):undefined);
  const inc=yrs.map(y=>({y,revenue:def(rev[y]),netIncome:def(ni[y]),epsDiluted:def(eps[y]??epb[y]),epsUnverw:eps[y]==null&&epb[y]!=null,weightedAverageShsOutDil:def(sh[y]),reportedCurrency:f.w,
    grossProfit:def(gp[y]),costOfRevenue:gp[y]!=null&&rev[y]!=null?rev[y]-gp[y]:undefined,operatingIncome:def(ebit(y)),interestExpense:zi[y]!=null?Math.abs(zi[y]):undefined,
    incomeTaxExpense:def(stz[y]),depreciationAndAmortization:abs_[y]!=null?Math.abs(abs_[y]):undefined,
    ebitda:ebit(y)!=null&&abs_[y]!=null?ebit(y)+Math.abs(abs_[y]):undefined}));
  const cf=yrs.map(y=>({y,depreciationAndAmortization:abs_[y]!=null?Math.abs(abs_[y]):undefined,operatingCashFlow:def(ocf[y]),capitalExpenditure:neg(cx[y]),freeCashFlow:ocf[y]!=null&&cx[y]!=null?ocf[y]-Math.abs(cx[y]):undefined,commonDividendsPaid:neg(dv[y]),commonStockRepurchased:neg(bb[y])}));
  const bs=yrs.map(y=>({y,longTermDebt:debt[y]!=null||skz[y]!=null?(debt[y]||0)+(skz[y]||0):undefined,cashAndCashEquivalents:def(cash[y]),totalStockholdersEquity:def(eq[y])}));
  const dy=Object.keys({...dps,...dpb}).sort().slice(-10).map(y=>({y,v:dps[y]??dpb[y],ber:dps[y]==null}));
  return {inc,cf,bs,dy,cur:f.w,gj:f.gj,q:f.quelle};
}
/* Jahreswerte zusammenführen: vorne = Vorrang, hinten füllt nur Lücken */
function mergeJ(vorne,hinten,n=10){const M={};const put=(a,prio)=>(a||[]).forEach(x=>{const y=String(x.y);M[y]=M[y]||{y};Object.entries(x).forEach(([k,v])=>{if(v==null||k==="y")return;if(prio||M[y][k]==null)M[y][k]=v})});put(hinten,true);put(vorne,true);return Object.values(M).sort((a,b)=>a.y-b.y).slice(-n)}

/* Formatierung */
const num=(v,d=2)=>v==null||isNaN(v)?"–":Number(v).toLocaleString("de-DE",{minimumFractionDigits:d,maximumFractionDigits:d});
const pct=v=>v==null||isNaN(v)?"–":num(v*100,2)+" %";
const big=v=>{if(v==null||isNaN(v))return "–";const a=Math.abs(v);return a>=1e12?num(v/1e12)+" Bio.":a>=1e9?num(v/1e9)+" Mrd.":a>=1e6?num(v/1e6)+" Mio.":num(v,0)};
const short=v=>{const a=Math.abs(v);return a>=1e12?num(v/1e12,1)+" Bio":a>=1e9?num(v/1e9,1)+" Mrd":a>=1e6?num(v/1e6,0)+" Mio":num(v,a<10?2:0)};
const first=(o,...ks)=>{for(const k of ks)if(o[k]!=null)return o[k]};

/* Diagramme (SVG) */
function bars(title,note,data,color="var(--bar)",f=short,kopf=""){
  data=data.filter(d=>d.v!=null&&!isNaN(d.v));
  if(!data.length)return `<div class="card"><h3>${title}</h3><p>Keine Daten verfügbar.</p></div>`;
  const W=480,H=210,pt=22,pb=24,n=data.length,gap=8,bw=(W-gap*(n+1))/n;
  const mx=Math.max(0,...data.map(d=>d.v)),mn=Math.min(0,...data.map(d=>d.v)),rng=(mx-mn)||1,ch=H-pt-pb;
  const y=v=>pt+(mx-v)/rng*ch,z=y(0);
  let s=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${title}"><line x1="0" x2="${W}" y1="${z}" y2="${z}" stroke="var(--line)"/>`;
  data.forEach((d,i)=>{
    const x=gap+i*(bw+gap),yy=y(d.v),h=Math.max(1,Math.abs(yy-z)),top=d.v>=0?yy:z;
    s+=`<rect x="${x}" y="${top}" width="${bw}" height="${h}" rx="2" fill="${d.v<0?"var(--neg)":color}"${d.part?' opacity=".45"':""}><title>${d.y}: ${f(d.v)}</title></rect>`;
    s+=`<text x="${x+bw/2}" y="${d.v>=0?top-4:top+h+11}" text-anchor="middle">${f(d.v)}</text>`;
    s+=`<text x="${x+bw/2}" y="${H-6}" text-anchor="middle">${String(d.y).slice(-n>8?-2:0)}</text>`;
  });
  return `<div class="card"><h3>${title}</h3>${kopf}${note?`<p>${note}</p>`:""}${s}</svg></div>`;
}

/* ===== Neue Diagramme: Farben nach Bedeutung ===== */
const pcs=v=>v==null||!isFinite(v)?"":(v>0?"+":"")+num(v*100,0)+" %";
const growth=(a,k)=>{const n=a.length;if(n<2)return null;const x=a[n-1][k],y=a[n-2][k];return x!=null&&y>0?x/y-1:null};
const kern=(t,main,col,sub)=>`<h3>${t}</h3><div class="kern" style="color:${col}">${main}${sub?`<small>${sub}</small>`:""}</div>`;
const yl=(y,n)=>n>7?"’"+String(y).slice(-2):String(y);
const nodata=t=>`<div class="card"><h3>${t}</h3><p>Keine Daten verfügbar.</p></div>`;
function combo(inc,cur){
  const D=inc.filter(x=>x.revenue!=null&&!isNaN(x.revenue));if(!D.length)return nodata("Umsatz &amp; Nettogewinn");
  const W=370,H=190,top=24,bot=H-22,n=D.length,mx=Math.max(...D.map(x=>x.revenue),1),mn=Math.min(0,...D.map(x=>x.netIncome||0)),rg=(mx-mn)||1,Y=v=>top+(mx-v)/rg*(bot-top),z=Y(0),bw=Math.min(44,(W-12)/n*.78);
  let s=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Umsatz und Nettogewinn"><line x1="0" x2="${W}" y1="${z}" y2="${z}" stroke="var(--line)"/>`;
  D.forEach((d,i)=>{const cx=6+(W-6)*(i+.5)/n,last=i===n-1,h=Math.max(1,z-Y(d.revenue));
    s+=`<rect x="${cx-bw/2}" y="${z-h}" width="${bw}" height="${h}" rx="3" fill="${last?"var(--c-umsatz)":"var(--c-umsatz-l)"}"><title>${d.y} Umsatz: ${big(d.revenue)}</title></rect>`;
    const g=d.netIncome;if(g!=null){const gh=Math.max(1,Math.abs(Y(g)-z)),gy=g>=0?z-gh:z,gw=Math.min(18,bw*.42);
      s+=`<rect x="${cx-gw/2}" y="${gy}" width="${gw}" height="${gh}" rx="2" fill="${g<0?"var(--neg)":last?"var(--c-gewinn)":"var(--c-gewinn-m)"}"><title>${d.y} Nettogewinn: ${big(g)}</title></rect>`;}
    if(i===0||last)s+=`<text x="${cx}" y="${z-h-5}" text-anchor="middle" font-size="11" font-weight="700" fill="${last?"var(--c-umsatz)":"var(--mut)"}">${short(d.revenue)}</text>`;
    s+=`<text x="${cx}" y="${H-5}" text-anchor="middle" font-size="11" ${last?'font-weight="700" style="fill:var(--ink)"':""}>${yl(d.y,n)}</text>`});
  const L=D[n-1],gu=growth(D,"revenue"),gg=growth(D.filter(x=>x.netIncome!=null),"netIncome");
  return `<div class="card">${kern("Umsatz &amp; Nettogewinn",big(L.revenue)+" "+esc(cur),"var(--c-umsatz)",gu!=null?pcs(gu):"")}<div class="kleg"><span><i style="background:var(--c-umsatz-l)"></i>Umsatz</span><span><i style="background:var(--c-gewinn)"></i>Nettogewinn${L.netIncome!=null?" "+big(L.netIncome)+(gg!=null?" ("+pcs(gg)+")":""):""}</span></div>${s}</svg></div>`;
}
function margins(inc,H0){
  const D=inc.filter(x=>x.revenue>0);if(!D.length)return nodata("Margen");
  const W=370,H=H0||170,pl=8,pr=84,top=14,bot=H-24,n=D.length;
  const S=[["Brutto","grossProfit","var(--c-umsatz)"],["Operativ","operatingIncome","var(--c-gewinn-m)"],["Netto","netIncome","var(--c-gewinn)"]].map(([l,k,c])=>({l,c,v:D.map(x=>x[k]==null?null:x[k]/x.revenue*100)})).filter(a=>a.v.some(v=>v!=null));
  const all=S.flatMap(a=>a.v.filter(v=>v!=null));if(!all.length)return nodata("Margen");
  const mx=Math.max(10,Math.ceil(Math.max(...all)/10)*10),mn=Math.min(0,Math.floor(Math.min(...all)/10)*10),rg=mx-mn,Y=v=>top+(mx-v)/rg*(bot-top),X=i=>pl+(W-pl-pr)*(i+.5)/n;
  let s=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Margen">`;
  [mn,(mn+mx)/2,mx].forEach(g=>{s+=`<line x1="0" x2="${W}" y1="${Y(g)}" y2="${Y(g)}" stroke="var(--line)"/><text x="2" y="${Y(g)-3}" font-size="10">${num(g,0)} %</text>`});
  const ends=[];
  S.forEach(a=>{const pts=a.v.map((v,i)=>v==null?null:[X(i),Y(v)]).filter(Boolean);if(!pts.length)return;
    s+=`<polyline points="${pts.map(q=>q.join(",")).join(" ")}" fill="none" stroke="${a.c}" stroke-width="3" stroke-linejoin="round"/>`;
    pts.forEach((q,i)=>s+=`<circle cx="${q[0]}" cy="${q[1]}" r="${i===pts.length-1?5:3}" fill="${a.c}"/>`);
    const lv=a.v[a.v.length-1];if(lv!=null)ends.push({y:pts[pts.length-1][1],x:pts[pts.length-1][0],t:a.l+" "+num(lv,0)+" %",c:a.c})});
  ends.sort((a,b)=>a.y-b.y);for(let i=1;i<ends.length;i++)if(ends[i].y-ends[i-1].y<13)ends[i].y=ends[i-1].y+13;
  ends.forEach(e=>s+=`<text x="${e.x+9}" y="${e.y+4}" font-size="11" font-weight="700" style="fill:${e.c}">${e.t}</text>`);
  D.forEach((d,i)=>s+=`<text x="${X(i)}" y="${H-5}" text-anchor="middle" font-size="11" ${i===n-1?'font-weight="700" style="fill:var(--ink)"':""}>${yl(d.y,n)}</text>`);
  const gl=S.find(a=>a.l==="Brutto"),ol=S.find(a=>a.l==="Operativ"),nl=S.find(a=>a.l==="Netto"),f=a=>a&&a.v[a.v.length-1]!=null?num(a.v[a.v.length-1],0)+" %":null;
  const zeile=(a,l)=>a&&a.v[a.v.length-1]!=null?`<div>${l} ${num(a.v[a.v.length-1],0)} %</div>`:"";
  return `<div class="card"><h3>Margen</h3><div class="kzl">${zeile(gl,"Brutto")}${zeile(ol,"operativ")}${zeile(nl,"netto")}</div><p>Anteil vom Umsatz</p>${s}</svg></div>`;
}
/* Cash, Zinsaufwand und Zinsdeckung des letzten Jahres mit Zinsangabe (für die Karte Free Cashflow) */
function zinsInfo(SD,cur){
  if(!SD)return null;
  const Z=(SD.inc||[]).filter(x=>x.interestExpense>0&&x.operatingIncome!=null).slice(-1)[0];
  const C=(SD.bs||[]).filter(x=>x.cashAndCashEquivalents!=null).slice(-1)[0];
  if(!Z&&!C)return null;
  const cash=C&&C.cashAndCashEquivalents,zins=Z&&Z.interestExpense,dz=Z?Z.operatingIncome/Z.interestExpense:null,jahr=(Z&&Z.y)||(C&&C.y);
  const parts=[];
  if(cash!=null)parts.push("Cash "+big(cash)+" "+esc(cur));
  if(zins!=null)parts.push("Zinsaufwand "+big(zins)+" "+esc(cur));
  if(dz!=null)parts.push("Zinsdeckung "+num(dz,1)+"×");
  return {jahr,parts,dz};
}
function fcfChart(cf,cur,zi){
  const D=cf.filter(x=>x.freeCashFlow!=null&&!isNaN(x.freeCashFlow));if(!D.length)return nodata("Free Cashflow");
  const W=370,H=205,top=22,bot=H-52,n=D.length,mx=Math.max(0,...D.map(x=>x.freeCashFlow)),mn=Math.min(0,...D.map(x=>x.freeCashFlow)),rg=(mx-mn)||1,Y=v=>top+(mx-v)/rg*(bot-top),z=Y(0),bw=Math.min(44,(W-12)/n*.78),mi=D.findIndex(x=>x.freeCashFlow===mx);
  let s=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Free Cashflow"><line x1="0" x2="${W}" y1="${z}" y2="${z}" stroke="var(--line)"/>`;
  D.forEach((d,i)=>{const v=d.freeCashFlow,cx=6+(W-6)*(i+.5)/n,last=i===n-1,h=Math.max(3,Math.abs(Y(v)-z));
    s+=`<rect x="${cx-bw/2}" y="${v>=0?z-h:z}" width="${bw}" height="${h}" rx="3" fill="${v<0?"var(--neg)":last?"var(--c-cash)":"var(--c-cash-l)"}"><title>${d.y}: ${big(v)}</title></rect>`;
    if(v<0)s+=`<text x="${cx}" y="${z+h+12}" text-anchor="middle" font-size="10" font-weight="700" style="fill:var(--neg)">−${short(Math.abs(v))}</text>`;
    else if(i===0||last||i===mi)s+=`<text x="${cx}" y="${z-h-5}" text-anchor="middle" font-size="11" font-weight="700" style="fill:${last?"var(--c-cash)":"var(--mut)"}">${short(v)}</text>`;
    s+=`<text x="${cx}" y="${H-6}" text-anchor="middle" font-size="11" ${last?'font-weight="700" style="fill:var(--ink)"':""}>${yl(d.y,n)}</text>`});
  const L=D[n-1],g=n>1&&D[n-2].freeCashFlow>0?L.freeCashFlow/D[n-2].freeCashFlow-1:null;
  return `<div class="card">${kern("Free Cashflow",big(L.freeCashFlow)+" "+esc(cur),L.freeCashFlow<0?"var(--neg)":"var(--c-cash)",g!=null?pcs(g):"")}<p>Rot = negativer Cashflow</p>${s}</svg>${zi&&zi.parts.length?`<div class="fnote">${zi.jahr?"Stand "+esc(String(zi.jahr).slice(0,4))+": ":""}${zi.parts.join(" · ")}. Zinsdeckung = Operatives Ergebnis / Zinsaufwand.</div>`:""}</div>`;
}
function epsChart(inc,cur,H0){
  const D=inc.map(x=>({y:x.y,v:first(x,"epsDiluted","eps"),u:x.epsUnverw})).filter(x=>x.v!=null&&!isNaN(x.v));if(!D.length)return nodata("Gewinn je Aktie (verwässert)");const epsT=D.some(x=>x.u)?"Gewinn je Aktie (unverwässert)":"Gewinn je Aktie (verwässert)";
  const W=370,H=H0||150,pl=20,pr=30,top=28,bot=H-26,n=D.length,vs=D.map(x=>x.v),mx0=Math.max(...vs),mn0=Math.min(...vs),pad=((mx0-mn0)||Math.abs(mx0)||1)*.15,mx=mx0+pad*.6,mn=mn0<0?mn0-pad:Math.max(0,mn0-pad*2.5)*(mn0>0?1:0)||mn0-pad,rg=(mx-mn)||1,Y=v=>top+(mx-v)/rg*(bot-top),X=i=>pl+(W-pl-pr)*(i+.5)/n;
  const pts=D.map((d,i)=>[X(i),Y(d.v)]);
  let s=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Gewinn je Aktie">`;
  if(mn<0&&mx>0)s+=`<line x1="0" x2="${W}" y1="${Y(0)}" y2="${Y(0)}" stroke="var(--line)"/>`;
  s+=`<polygon points="${pts.map(q=>q.join(",")).join(" ")} ${pts[n-1][0]},${bot} ${pts[0][0]},${bot}" fill="var(--c-gewinn-l)" opacity=".55"/><polyline points="${pts.map(q=>q.join(",")).join(" ")}" fill="none" stroke="var(--c-gewinn)" stroke-width="3" stroke-linejoin="round"/>`;
  pts.forEach((q,i)=>{const last=i===n-1;s+=`<circle cx="${q[0]}" cy="${q[1]}" r="${last?5.5:3.5}" fill="${D[i].v<0?"var(--neg)":"var(--c-gewinn)"}"><title>${D[i].y}: ${num(D[i].v)}</title></circle>`;
    if(i===0||last)s+=`<text x="${q[0]}" y="${q[1]-10}" text-anchor="middle" font-size="11" font-weight="700" style="fill:${last?"var(--c-gewinn)":"var(--mut)"}">${num(D[i].v)}</text>`;
    s+=`<text x="${q[0]}" y="${H-6}" text-anchor="middle" font-size="11" ${last?'font-weight="700" style="fill:var(--ink)"':""}>${yl(D[i].y,n)}</text>`});
  const g=n>1&&D[n-2].v>0?D[n-1].v/D[n-2].v-1:null;
  return `<div class="card">${kern(epsT,num(D[n-1].v)+" "+esc(cur),D[n-1].v<0?"var(--neg)":"var(--c-gewinn)",g!=null?pcs(g):"")}${s}</svg></div>`;
}
/* Zusätzliche SEC-Diagramme (Geschäftsjahre): Ausschüttungsquote, Eigenkapital und Schulden, Rückkäufe */
function secCharts(SD,cur,eps=""){
  if(!SD)return eps?`<div class="grid sec">${eps}</div>`:"";
  const epsM=Object.fromEntries(SD.inc.filter(x=>x.epsDiluted!=null).map(x=>[x.y,x.epsDiluted]));
  const quoteAlle=SD.dy.filter(x=>x.v!=null&&epsM[x.y]>0).map(x=>({y:x.y,v:x.v/epsM[x.y]*100}));
  /* Jahre über 200 % (Gewinn durch Einmaleffekte verzerrt) werden nicht gezeigt, weil bereinigte Gewinne nicht in den SEC-Daten stehen */
  const quote=quoteAlle.filter(x=>x.v<=200);
  const ausgeblendet=quoteAlle.filter(x=>x.v>200).map(x=>x.y);
  const quoteNotiz=ausgeblendet.length?` Ausgeblendet: ${ausgeblendet.join(", ")} (über 200 %, Gewinn durch Einmaleffekte verzerrt).`:"";
  const eq=SD.bs.filter(x=>x.totalStockholdersEquity!=null).map(x=>({y:x.y,v:x.totalStockholdersEquity}));
  const debt=SD.bs.filter(x=>x.longTermDebt!=null).map(x=>({y:x.y,v:x.longTermDebt}));
  const buy=SD.cf.filter(x=>x.commonStockRepurchased!=null).map(x=>({y:x.y,v:Math.abs(x.commonStockRepurchased)}));
  const q=SD.q?quelleText(SD.q,true):"";
  const letzt=a=>a[a.length-1],vor=a=>a[a.length-2];
  const kopf=(main,sub,col)=>`<div class="kern" style="color:${col}">${main}${sub?`<small>${sub}</small>`:""}</div>`;
  const qL=letzt(quote),qV=vor(quote);
  const kQ=kopf(qL?num(qL.v,0)+" %":"–",qV?"Vorjahr "+num(qV.v,0)+" %":"","var(--c-gold)");
  const eL=letzt(eq),dL=letzt(debt);
  const kE=kopf(eL?big(eL.v)+" "+esc(cur):"–",dL?"Schulden "+big(dL.v)+" "+esc(cur):"","var(--c-cash)");
  const bL=letzt(buy),bV=vor(buy);
  const kB=kopf(bL?big(bL.v)+" "+esc(cur):"–",bL&&bV?pcs(bL.v/bV.v-1)+" zum Vorjahr":"","var(--c-cash)");
  return `<div class="grid sec">
   ${eps}
   ${bars("Ausschüttungsquote",`Dividende je Aktie geteilt durch Gewinn je Aktie (GAAP, unbereinigt), je Geschäftsjahr.${quoteNotiz} Quelle: ${q}`,quote,"var(--c-gold)",v=>num(v,0)+" %",kQ)}
   ${paarBars("Eigenkapital und langfristige Schulden",`In ${esc(cur)}, je Geschäftsjahr. Quelle: ${q}`,eq,debt,"Eigenkapital","Langfristige Schulden",kE)}
   ${bars("Aktienrückkäufe",`Ausgaben je Geschäftsjahr, in Mrd. ${esc(cur)}. Quelle: ${q}`,buy,"var(--c-cash-l)",v=>num(v/1e9,1),kB)}
  </div>`;
}
/* Zwei Reihen nebeneinander je Jahr (z. B. Eigenkapital und Schulden) */
function paarBars(title,note,A,B,nameA,nameB,kopf=""){
  const jahre=[...new Set([...A,...B].map(x=>x.y))].sort();
  if(!jahre.length)return `<div class="card"><h3>${title}</h3><p>Keine Daten verfügbar.</p></div>`;
  const va=Object.fromEntries(A.map(x=>[x.y,x.v])),vb=Object.fromEntries(B.map(x=>[x.y,x.v]));
  const W=480,H=210,pt=22,pb=24,n=jahre.length,gap=8,grp=(W-gap*(n+1))/n,bw=(grp-4)/2;
  const all=[...A,...B].map(x=>x.v),mx=Math.max(0,...all),mn=Math.min(0,...all),rng=(mx-mn)||1,ch=H-pt-pb;
  const y=v=>pt+(mx-v)/rng*ch,z=y(0);
  let s=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${title}"><line x1="0" x2="${W}" y1="${z}" y2="${z}" stroke="var(--line)"/>`;
  jahre.forEach((j,i)=>{
    const x0=gap+i*(grp+gap);
    [[va[j],"var(--c-cash)",nameA,0],[vb[j],"var(--neg)",nameB,1]].forEach(([v,col,nm,k])=>{
      if(v==null)return;
      const bx=x0+2+k*bw,yy=y(v),h=Math.max(1,Math.abs(yy-z)),top=v>=0?yy:z;
      s+=`<rect x="${bx}" y="${top}" width="${bw}" height="${h}" rx="2" fill="${v<0?"var(--neg)":col}"><title>${j} ${nm}: ${big(v)}</title></rect>`;
    });
    s+=`<text x="${x0+grp/2}" y="${H-6}" text-anchor="middle">${String(j).slice(-n>8?-2:0)}</text>`;
  });
  const legende=`<span style="display:flex;gap:14px;font-size:12px;margin-top:4px"><span><i style="display:inline-block;width:10px;height:10px;border-radius:2px;background:var(--c-cash);margin-right:4px"></i>${nameA}</span><span><i style="display:inline-block;width:10px;height:10px;border-radius:2px;background:var(--neg);margin-right:4px"></i>${nameB}</span></span>`;
  return `<div class="card"><h3>${title}</h3>${kopf}<p>${note}${legende}</p>${s}</svg></div>`;
}
function line(title,pts){
  if(pts.length<2)return `<div class="card"><h3>${title}</h3><p>Keine Daten verfügbar.</p></div>`;
  const W=480,H=210,p=24,vs=pts.map(d=>d.v),mn=Math.min(...vs),mx=Math.max(...vs),r=(mx-mn)||1;
  const X=i=>p+i/(pts.length-1)*(W-2*p),Y=v=>10+(mx-v)/r*(H-40);
  const path=pts.map((d,i)=>`${i?"L":"M"}${X(i).toFixed(1)},${Y(d.v).toFixed(1)}`).join("");
  const up=pts[pts.length-1].v>=pts[0].v;
  return `<div class="card"><h3>${title}</h3><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${title}"><path d="${path}L${X(pts.length-1)},${H-24}L${X(0)},${H-24}Z" fill="${up?"var(--pos)":"var(--neg)"}" opacity=".12"/><path d="${path}" fill="none" stroke="${up?"var(--pos)":"var(--neg)"}" stroke-width="2"/><text x="${p}" y="${H-6}">${pts[0].d}</text><text x="${W-p}" y="${H-6}" text-anchor="end">${pts[pts.length-1].d}</text><text x="${W-p}" y="12" text-anchor="end">Hoch ${num(mx)}</text><text x="${p}" y="12">Tief ${num(mn)}</text></svg></div>`;
}



/* Kurschart mit Zeitraum-Auswahl (Tageskurse, letzter Punkt = aktueller Kurs) */
function kursChart(sym,cur,pr,q,price){
  const S=pr.map(x=>({d:x.date,v:+x.price})).filter(x=>isFinite(x.v));
  const nowD=new Date().toISOString().slice(0,10);
  if(price!=null&&isFinite(price)&&S.length&&nowD>=S[S.length-1].d){if(S[S.length-1].d===nowD)S[S.length-1].v=+price;else S.push({d:nowD,v:+price})}
  const id="kc"+Math.random().toString(36).slice(2,7);
  const R=[["1M","1 Monat"],["MAX","Maximum"]];
  const f=(o,...ks)=>{for(const k of ks)if(o&&o[k]!=null&&isFinite(o[k]))return +o[k]};
  const stats=[["Eröffnung",f(q,"open")],["Tageshoch",f(q,"dayHigh")],["Tagestief",f(q,"dayLow")],["Vortag",f(q,"previousClose")],["52-Wochen-Hoch",f(q,"yearHigh")],["52-Wochen-Tief",f(q,"yearLow")]].filter(x=>x[1]!=null);
  const vol=f(q,"volume");if(vol!=null)stats.push(["Handelsvolumen",big(vol)]);
  const html=`<div class="kc" id="${id}"><div class="kt" aria-live="polite"></div><div class="rubriken" role="tablist" aria-label="Zeitraum">${R.map((r,i)=>`<button type="button" class="rb${r[0]==="1M"?" on":""}" data-r="${r[0]}" role="tab" aria-selected="${r[0]==="1M"}">${r[0]==="MAX"?"Max":r[0]}</button>`).join("")}</div><div class="kcs"></div><p class="fnote">* Die Kurshistorie baut sich seit dem 10. November 2026 täglich auf.</p>${stats.length?`<div class="ks">${stats.map(x=>`<div><span>${x[0]}</span><b>${typeof x[1]==="string"?x[1]:num(x[1])}</b></div>`).join("")}</div>`:""}</div>`;
  let full=null;
  function slice(r){
    const last=S[S.length-1];if(!last)return [];const t=new Date(last.d);let from;
    if(r==="1M"){from=new Date(t);from.setMonth(from.getMonth()-1)}
    else if(r==="6M"){from=new Date(t);from.setMonth(from.getMonth()-6)}
    else if(r==="YTD"){from=new Date(t.getFullYear()-1,11,31)}
    else if(r==="1Y"){from=new Date(t);from.setFullYear(from.getFullYear()-1)}
    else if(r==="5Y"){from=new Date(t);from.setFullYear(from.getFullYear()-5)}
    else from=new Date(0);
    const fd=from.toISOString().slice(0,10),src=r==="MAX"&&full?full:S;
    let a=src.filter(x=>x.d>=fd);if(a.length<2)a=src.slice(-2);
    return a;
  }
  function draw(root,r){
    let a=slice(r);const box=root.querySelector(".kcs"),top=root.querySelector(".kt");
    if(a.length<2){box.innerHTML='<p class="desc">Keine Kursdaten verfügbar.</p>';top.innerHTML="";return}
    const stp=Math.max(1,Math.ceil(a.length/360)),b=a.filter((_,i)=>i%stp===0||i===a.length-1);
    const W=Math.max(300,Math.round(box.clientWidth||720)),H=W<520?230:270,pl=8,pr=48,pt=12,pb=26;
    const vs=b.map(x=>x.v),mn0=Math.min(...vs),mx0=Math.max(...vs),pad=(mx0-mn0||mx0*.02||1)*.08,mn=mn0-pad,mx=mx0+pad;
    const X=i=>pl+i/(b.length-1)*(W-pl-pr),Y=v=>pt+(mx-v)/(mx-mn)*(H-pt-pb);
    const up=b[b.length-1].v>=b[0].v,col=up?"var(--pos)":"var(--neg)";
    const path=b.map((x,i)=>`${i?"L":"M"}${X(i).toFixed(1)},${Y(x.v).toFixed(1)}`).join("");
    let sv=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Kursverlauf ${esc(sym)}">`;
    for(let k=0;k<=4;k++){const v=mn+(mx-mn)*k/4,y=Y(v);sv+=`<line x1="${pl}" x2="${W-pr}" y1="${y.toFixed(1)}" y2="${y.toFixed(1)}" stroke="var(--line)"/><text x="${W-pr+6}" y="${(y+4).toFixed(1)}" font-size="11">${num(v,v>=100?0:2)}</text>`}
    const dfmt=ds=>{const d=new Date(ds);return r==="MAX"||r==="5Y"?d.toLocaleDateString("de-DE",{month:"short",year:"2-digit"}):r==="1M"?d.toLocaleDateString("de-DE",{day:"numeric",month:"short"}):d.toLocaleDateString("de-DE",{month:"short",year:"2-digit"})};
    const nt=Math.min(5,b.length);for(let k=0;k<nt;k++){const i=Math.round(k*(b.length-1)/(nt-1||1));sv+=`<text x="${X(i).toFixed(1)}" y="${H-7}" font-size="11" text-anchor="${k===0?"start":k===nt-1?"end":"middle"}">${dfmt(b[i].d)}</text>`}
    sv+=`<path d="${path}L${X(b.length-1)},${H-pb}L${X(0)},${H-pb}Z" fill="${col}" opacity=".12"/><path d="${path}" fill="none" stroke="${col}" stroke-width="2" stroke-linejoin="round"/>`;
    sv+=`<g class="xh" style="display:none"><line y1="${pt}" y2="${H-pb}" stroke="var(--mut)" stroke-dasharray="3 3"/><circle r="4.5" fill="${col}" stroke="var(--bg)" stroke-width="2"/></g><circle class="ed" cx="${X(b.length-1).toFixed(1)}" cy="${Y(b[b.length-1].v).toFixed(1)}" r="4.5" fill="${col}"/></svg>`;
    box.innerHTML=sv;
    const first0=b[0].v,fmtD=ds=>new Date(ds).toLocaleDateString("de-DE",{day:"2-digit",month:"2-digit",year:"numeric"});
    const head=(i)=>{const v=b[i].v,dd=v-first0,pp=first0?dd/first0:0,c=dd>=0?"pos":"neg";
      top.innerHTML=`<b>${num(v)} ${esc(cur)}</b><span class="${c}">${dd>=0?"▲":"▼"} ${num(Math.abs(pp)*100)} % · ${dd>=0?"+":"−"}${num(Math.abs(dd))} ${esc(cur)}</span><span>${i===b.length-1?"aktuell, Änderung im Zeitraum":fmtD(b[i].d)}</span>`};
    head(b.length-1);
    const svg=box.querySelector("svg"),xh=svg.querySelector(".xh"),ed=svg.querySelector(".ed");
    const mv=ev=>{const rc=svg.getBoundingClientRect(),px=(ev.clientX-rc.left)/rc.width*W;let i=Math.round((px-pl)/(W-pl-pr)*(b.length-1));i=Math.max(0,Math.min(b.length-1,i));
      xh.style.display="";xh.setAttribute("transform",`translate(${X(i).toFixed(1)},0)`);xh.querySelector("circle").setAttribute("cy",Y(b[i].v).toFixed(1));ed.setAttribute("opacity","0");head(i)};
    const lv=()=>{xh.style.display="none";ed.setAttribute("opacity","1");head(b.length-1)};
    svg.addEventListener("pointermove",mv);svg.addEventListener("pointerdown",mv);svg.addEventListener("pointerleave",lv);
  }
  function init(){
    const root=document.getElementById(id);if(!root)return;
    let cur_r="1M";draw(root,cur_r);let lw=root.querySelector(".kcs").clientWidth,tm;window.addEventListener("resize",()=>{clearTimeout(tm);tm=setTimeout(()=>{if(!document.body.contains(root))return;const w=root.querySelector(".kcs").clientWidth;if(Math.abs(w-lw)>20){lw=w;draw(root,cur_r)}},150)});
    root.querySelector(".rubriken").addEventListener("click",async e=>{const bt=e.target.closest(".rb");if(!bt)return;
      cur_r=bt.dataset.r;root.querySelectorAll(".rb").forEach(x=>{const on=x===bt;x.classList.toggle("on",on);x.setAttribute("aria-selected",on)});
      if(cur_r==="MAX"&&!full){root.querySelector(".kcs").innerHTML='<p class="desc">Lade Kursverlauf …</p>';
        try{const j=await chain("historical-price-eod/light",{symbol:sym},[{from:"1970-01-01"},{}]);full=(Array.isArray(j)?j:[]).slice().reverse().map(x=>({d:x.date,v:+x.price})).filter(x=>isFinite(x.v));if(full.length&&price!=null&&full[full.length-1].d<nowD)full.push({d:nowD,v:+price})}catch(err){full=S}}
      draw(root,cur_r)});
  }
  return {html,init};
}

/* Steckbrief: Ampel nach festen Regeln, Zahlen aus FMP (TTM) */
function steckbrief(sym,p,r,m,inc,cf,KZ,SD){
  const K=KZ||{},k100=v=>v==null?undefined:v/100;
  const f=(o,...ks)=>{for(const k of ks)if(o&&o[k]!=null&&isFinite(o[k]))return +o[k]};
  const pe=f(r,"priceToEarningsRatioTTM","peRatioTTM"),pb=f(r,"priceToBookRatioTTM"),ev=f(m,"evToEBITDATTM")??f(r,"enterpriseValueMultipleTTM");
  const dyl=f(r,"dividendYieldTTM")??k100(K.rendite),po=f(r,"dividendPayoutRatioTTM")??k100(K.ausschuettung),fy=f(m,"freeCashFlowYieldTTM")??k100(K.fcf_rendite);
  const roic=f(m,"returnOnInvestedCapitalTTM")??k100(K.roic),roe=f(m,"returnOnEquityTTM")??k100(K.roe),om=f(r,"operatingProfitMarginTTM")??k100(K.operative_marge);
  const ic=f(r,"interestCoverageRatioTTM")??K.zinsdeckung??undefined,nd=f(m,"netDebtToEBITDATTM")??K.nettoschulden_ebitda??undefined;
  const fin=/financ|real estate/i.test(p.sector||"");
  const cagr=(a,b,n)=>a>0&&b>0&&n>0?Math.pow(b/a,1/n)-1:null;
  const yrs=inc.slice(-6),n=yrs.length-1;
  const rc=n>=2?cagr(yrs[0].revenue,yrs[n].revenue,n):null;
  const e0=yrs[0]&&f(yrs[0],"epsDiluted","eps"),e1=yrs[n]&&f(yrs[n],"epsDiluted","eps");
  const ec=n>=2?cagr(e0,e1,n):null;
  const P=(v,d=1)=>v==null?"–":num(v*100,d)+" %",X=(v)=>v==null?"–":num(v,1)+"×";
  const rows=[];
  /* Erwartete Jahresrendite bei gleichbleibendem KGV (data/kennzahlen.json): Dividendenrendite + Gewinnwachstum 5 Jahre */
  const er=K.erw_rendite;let bwc="g0",bwl="",bwt="Keine erwartete Rendite berechenbar, weil Dividende oder Gewinnwachstum fehlen",gauge="";
  if(typeof er==="number"){const txt=(er>0?"+":"")+num(er,1)+" %";
    const c=er>=10?"g":er>=5?"y":"r";const lab=er>=10?"Hohes erwartetes Wachstum":er>=5?"Mittleres erwartetes Wachstum":"Wenig Renditewachstum, eher teuer";
    bwc=c;bwl=txt;bwt=`${lab}: ${txt} Jahresrendite, wenn das KGV gleich bleibt (Dividendenrendite plus Gewinnwachstum der letzten 5 Jahre)`;
    const pos=(Math.max(-10,Math.min(25,er))+10)/35*100;
    gauge=`<div class="fvg" role="img" aria-label="${bwt}"><div class="fvq"><b>${txt}</b> erwartet pro Jahr bei gleichem KGV</div><div class="fvbar"><span class="fvc"></span><span class="fvm" style="left:${pos.toFixed(1)}%"></span></div><div class="fvl"><span>rot unter 5 %</span><span>gelb 5 bis 10 %</span><span>grün ab 10 %</span></div></div>`}
  rows.push(["Erwartete Rendite (1 Jahr)",bwc,bwl,bwt,"bew",gauge]);
  let dc,dg,dv,fcfFehlt=false;
  const dLast=SD&&SD.dy&&SD.dy.length?SD.dy[SD.dy.length-1]:null;
  if(!(dyl>0)&&dLast&&dLast.v>0){dg="";dv=num(dLast.v,2)+" "+esc(SD.cur||"")+" je Aktie";dc="Geschäftsjahr "+esc(dLast.y)+", Quelle: "+quelleText(SD.q,true)+" · Rendite: kein aktueller Kurs vorhanden"}
  else if(!(dyl>0)){dg="";dv="Keine Dividende";dc="–"}
  else{const cov=fy!=null?fy/dyl:null;
    /* Gewinn- und Cashflow-Ausschüttung nebeneinander, mit dem Zeitraum, auf den sie sich beziehen */
    const base=K.cf_basis==="ttm"?"letzte 4 Quartale":K.cf_basis?"Geschäftsjahr "+K.cf_basis:"";
    const cfPo=K.fcf_ausschuettung!=null?K.fcf_ausschuettung:(fy>0?dyl/fy*100:null);
    dc=["Rendite "+P(dyl),po!=null?"Ausschüttung vom Gewinn "+P(po,0):"Ausschüttung vom Gewinn: noch nicht erfasst",cfPo!=null?"vom freien Cashflow "+num(cfPo,0)+" % ("+base+")":"Cashflow-Ausschüttung: noch nicht erfasst"].join(" · ");
    if(cov!=null){dg=cov>=1.5?"g":cov>=1?"y":"r";dv=cov>=1.5?"Cashflow deckt Dividende":cov>=1?"Cashflow knapp":"Cashflow reicht nicht"}
    else if(po!=null){/* Kein Free Cashflow: Ersatz ist die Ausschüttungsquote, Richtwert 75 % */
      if(po<=.75){dg="g";dv="Gedeckt*"}else if(po<=.85){dg="y";dv="Hoch*"}else if(po<=1){dg="o";dv="Sehr hoch*"}else{dg="r";dv="Nicht gedeckt*"}
      fcfFehlt=true}
    else{dg="";dv="k. A."}}
  rows.push(["Dividende",dg,dv,dc]);
  const pg=roic==null?"":roic>=.10?"g":roic>=.05?"y":"r";
  rows.push(["Profitabilität",pg,pg==="g"?"Stark":pg==="y"?"Mittel":pg==="r"?"Schwach":"k. A.",[roic!=null?"ROIC "+P(roic,0):"ROIC: noch nicht erfasst",roe!=null?"ROE "+P(roe,0):"ROE: noch nicht erfasst",om!=null?"Operative Marge "+P(om):"Operative Marge: noch nicht erfasst"].filter(Boolean).join(" · ")]);
  let bg="",bv="k. A.";
  if(fin){bv="nicht bewertet"}
  else if(ic!=null||nd!=null){bg=(ic==null||ic>=6)&&(nd==null||nd<=3)?"g":(ic==null||ic>=3)&&(nd==null||nd<=4.5)?"y":"r";bv=bg==="g"?"Solide":bg==="y"?"Angespannt":"Schwach"}
  rows.push(["Bilanz",bg,bv,[ic!=null?"Zinsdeckung "+X(ic):"Zinsdeckung: noch nicht erfasst",nd!=null?(nd<0?"Netto-Cash":"Nettoschulden "+X(nd)+" EBITDA"):"Nettoschulden/EBITDA: noch nicht erfasst"].filter(Boolean).join(" · ")+(fin?" · Bei Banken, Versicherern und Immobilien nicht sinnvoll vergleichbar":"")]);
  let wg="",wv="k. A.";
  const rcz=rc??k100(K.umsatz_wachstum),ecz=ec??k100(K.eps_wachstum);
  if(rcz!=null||ecz!=null){const sc=(rc==null?0:rc>=.05?1:rc<.02?-1:0)+(ec==null?0:ec>=.05?1:ec<0?-1:0);wg=sc>=2?"g":sc<=-1?"r":"y";wv=sc>=2?"Stark":sc<=-1?"Schwach":"Mittel"}
  rows.push(["Wachstum",wg,wv,[rc!=null?"Umsatz "+P(rc)+" p. a. ("+n+" J.)":rcz!=null?"Umsatz zuletzt "+P(rcz):"Umsatz: noch nicht erfasst",ec!=null?"Gewinn je Aktie "+P(ec)+" p. a. ("+n+" J.)":ecz!=null?"Gewinn je Aktie zuletzt "+P(ecz):"Gewinn je Aktie: noch nicht erfasst"].join(" · ")]);
  const tr=rows.map(x=>`<tr${x[4]?` id="st-${x[4]}"`:""}><td class="k"><span class="dot ${x[1]==="g0"?"":x[1]}"></span>${x[0]}</td><td class="v">${x[2]}</td><td class="d">${x[5]||""}${esc(x[3])}</td></tr>`).join("");
  return `<div class="stk"><h3>Steckbrief</h3><table><tbody>${tr}</tbody></table><p class="sn">Ampel nach festen Regeln, keine Anlageberatung. Grün, gelb und rot ordnen nur ein, wie die Zahlen im Vergleich zu üblichen Schwellen oder zur eigenen Geschichte stehen.${fcfFehlt?" * Der Free Cashflow liegt nicht vor, weil Angaben fehlen. Die Ampel bewertet die Dividende deshalb nach der Ausschüttungsquote: grün bis 75 %, gelb bis 85 %, orange bis 100 %, rot darüber.":""}</p></div>`;
}

/* Hub laden */
/* Diagramme in einer Reihe: Kopfzeilen (Überschrift, Erläuterung, Kennzahl) gleich hoch, damit Grafiken oben und unten fluchten */
function alignCharts(){
  document.querySelectorAll("#hub .grid").forEach(g=>{
    const cs=[...g.children].filter(c=>c.classList.contains("card")&&c.querySelector("svg"));
    cs.forEach(c=>{
      if(c.querySelector(":scope>.chead"))return;
      const h=document.createElement("div");h.className="chead";
      [...c.childNodes].forEach(n=>{if(!(n.nodeName==="svg"||n.nodeName==="SVG"))h.appendChild(n)});
      c.insertBefore(h,c.firstChild);
    });
    const hs=cs.map(c=>c.querySelector(":scope>.chead")).filter(Boolean);
    hs.forEach(h=>h.style.minHeight="");
    const max=Math.max(0,...hs.map(h=>h.offsetHeight));
    hs.forEach(h=>h.style.minHeight=max+"px");
    /* Beschriftungen gleich groß: Schrift je Diagramm gegen dessen Skalierung rechnen */
    cs.forEach(c=>{
      const s=c.querySelector("svg"),vw=s.viewBox&&s.viewBox.baseVal&&s.viewBox.baseVal.width;
      if(!vw)return;
      const scale=s.getBoundingClientRect().width/vw;
      s.querySelectorAll("text").forEach(t=>{
        if(t.dataset.fs==null)t.dataset.fs=parseFloat(getComputedStyle(t).fontSize)||11;
        t.style.fontSize=(t.dataset.fs/scale)+"px";
      });
    });
    /* Jahresbeschriftung unten: gleicher Abstand zur Unterkante wie das knappste Diagramm der Reihe */
    const info=cs.map(c=>{
      const s=c.querySelector("svg"),sr=s.getBoundingClientRect(),vw=s.viewBox.baseVal.width,scale=sr.width/vw;
      const ts=[...s.querySelectorAll("text")].filter(t=>t.hasAttribute("y"));
      if(!ts.length)return null;
      const bots=ts.map(t=>t.getBoundingClientRect().bottom),low=Math.max(...bots);
      const low_=ts.filter((t,i)=>bots[i]>=low-0.5);
      return {s,scale,ts,lowT:low_,off:sr.bottom-low};
    }).filter(Boolean);
    if(info.length>1){
      info.forEach(i=>{i.ts.forEach(t=>{if(t.dataset.y0==null)t.dataset.y0=t.getAttribute("y")})});
      info.forEach(i=>{i.ts.forEach(t=>t.setAttribute("y",t.dataset.y0))});
      const target=Math.min(...info.map(i=>i.off));
      info.forEach(i=>{
        const shift=(i.off-target)/i.scale;
        i.ts.forEach(t=>{const y=parseFloat(t.dataset.y0);if(y>0.85*parseFloat(i.s.viewBox.baseVal.height))t.setAttribute("y",y+shift)});
      });
    }
  });
}
let alignT;addEventListener("resize",()=>{clearTimeout(alignT);alignT=setTimeout(alignCharts,150)});

const FCOL=["#2563eb","#16a34a","#f59e0b","#dc2626","#7c3aed","#0891b2","#db2777","#65a30d","#475569","#ea580c","#0d9488","#9333ea","#b45309"];
async function initFinance(sym,p,cur,inc,cf,SD){
  const box=$("fin");if(!box||!inc.length)return;
  const yr=x=>String(x.fiscalYear||x.calendarYear||String(x.date).slice(0,4));
  let bs=[];try{bs=await chain("balance-sheet-statement",{symbol:sym},[{limit:10},{limit:5},{}])}catch(e){}
  if(!document.body.contains(box))return;
  const fmpDa=Array.isArray(bs)&&bs.length>0;
  /* Bilanz: FMP zuerst; ohne FMP langfristige Schulden und Cash aus der SEC */
  bs=SD?mergeJ((Array.isArray(bs)?bs:[]).map(x=>({...x,y:yr(x)})),SD.bs.map(x=>({...x,totalDebt:x.longTermDebt,netDebt:x.longTermDebt!=null&&x.cashAndCashEquivalents!=null?x.longTermDebt-x.cashAndCashEquivalents:undefined}))):bs;
  const B={},I={},C={};
  inc.forEach(x=>I[String(x.y)]=x);cf.forEach(x=>C[String(x.y)]=x);(Array.isArray(bs)?bs:[]).forEach(x=>B[String(x.y||yr(x))]=x);
  const years=inc.map(x=>String(x.y)).slice(-10);
  const ab=v=>v==null?null:Math.abs(v);
  const S=[
    {k:"rev",l:"Umsatz",g:y=>I[y]?.revenue},{k:"gp",l:"Bruttogewinn",g:y=>I[y]?.grossProfit},{k:"op",l:"Operatives Ergebnis",g:y=>I[y]?.operatingIncome},
    {k:"ni",l:"Nettogewinn",g:y=>I[y]?.netIncome},{k:"ocf",l:"Operativer Cashflow",g:y=>first(C[y]||{},"operatingCashFlow","netCashProvidedByOperatingActivities")},
    {k:"fcf",l:"Freier Cashflow",g:y=>C[y]?.freeCashFlow},{k:"capex",l:"Capex (Investitionen)",g:y=>ab(C[y]?.capitalExpenditure)},
    {k:"da",l:"Abschreibungen",g:y=>first(C[y]||{},"depreciationAndAmortization")??I[y]?.depreciationAndAmortization},
    {k:"div",l:"Dividenden gezahlt",g:y=>ab(first(C[y]||{},"commonDividendsPaid","netDividendsPaid","dividendsPaid"))},
    {k:"buy",l:"Aktienrückkäufe",g:y=>ab(first(C[y]||{},"commonStockRepurchased"))},
    {k:"cash",l:"Cash",g:y=>first(B[y]||{},"cashAndCashEquivalents","cashAndShortTermInvestments")},
    {k:"debt",l:"Schulden gesamt",g:y=>B[y]?.totalDebt},{k:"nd",l:"Nettoschulden",g:y=>B[y]?.netDebt}
  ];
  S.forEach((s,i)=>{s.c=FCOL[i%FCOL.length];s.v=years.map(y=>{const v=s.g(y);return v==null||isNaN(v)?null:+v})});
  const have=S.filter(s=>s.v.some(v=>v!=null));
  let on=new Set(["ni","fcf","cash","debt"].filter(k=>have.some(s=>s.k===k)));let mode="line",sy=years[years.length-1];
  box.className="fin";
  box.innerHTML=`<h3>Finanzen im Überblick</h3><p class="fsub">Jahreswerte in ${esc(cur||"Berichtswährung")}. Quelle: ${SD?quelleText(SD.q):"FMP"}.</p>
  <div class="fcard"><div class="fctl"><b id="fst">Gewinnfluss</b><span class="ftoggle"><button type="button" data-f="gw" aria-pressed="true">Gewinn</button><button type="button" data-f="cf" aria-pressed="false">Cashflow</button></span><select id="fsy" aria-label="Jahr">${years.slice().reverse().map(y=>`<option>${y}</option>`).join("")}</select></div><div class="fscroll" id="fsk"></div><p class="fnote" id="fsn">Vom Umsatz bis zum Nettogewinn. Die Breite der Bänder ist proportional zum Betrag.</p></div>
  <div class="fcard"><div class="fctl"><b>Kennzahlen übereinander legen</b><button type="button" data-m="line" aria-pressed="true">Linien</button><button type="button" data-m="bar" aria-pressed="false">Balken</button></div><div class="fchips" id="fch"></div><div class="fscroll fit" id="fcm"></div><p class="fnote" id="fmn"></p></div>
  <div class="fcard"><div class="fctl"><b>Investitionen (Capex) und Dividendendeckung</b></div><div class="fscroll" id="fcx"></div><p class="fnote">Capex-Quote = Investitionen / Umsatz. Capex / Abschreibungen über 100 % heißt: Das Unternehmen investiert mehr, als sich Anlagen abnutzen. Deckung = freier Cashflow / gezahlte Dividenden; unter 100 % wird die Dividende nicht aus dem freien Cashflow bezahlt.</p></div>`;
  /* Cash und Zinsdeckung (Schulden stehen im Diagramm Eigenkapital und langfristige Schulden) */
  function debtCard(){
    const D=years.map(y=>{const b=B[y]||{},i=I[y]||{};const cash=first(b,"cashAndCashEquivalents","cashAndShortTermInvestments");
      return {y,cash,ic:i.interestExpense>0&&i.operatingIncome!=null?i.operatingIncome/i.interestExpense:null}}).filter(d=>d.cash!=null);
    if(D.length<1)return "";
    const W=370,H=190,top=24,bot=H-22,n=D.length,mx=Math.max(...D.map(d=>d.cash),1),Y=v=>top+(mx-v)/mx*(bot-top),bw=Math.min(44,(W-12)/n*.78);
    let sv=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Cash"><line x1="0" x2="${W}" y1="${bot}" y2="${bot}" stroke="var(--line)"/>`;
    D.forEach((d,i)=>{const cx=6+(W-6)*(i+.5)/n,last=i===n-1,h=Math.max(1,bot-Y(d.cash));
      sv+=`<rect x="${cx-bw/2}" y="${bot-h}" width="${bw}" height="${h}" rx="3" fill="${last?"var(--c-cash)":"#6cc4cc"}"><title>${d.y} Cash: ${big(d.cash)}</title></rect>`;
      if(i===0||last)sv+=`<text x="${cx}" y="${bot-h-5}" text-anchor="middle" font-size="11" font-weight="700" style="fill:${last?"var(--c-cash)":"var(--mut)"}">${short(d.cash)}</text>`;
      sv+=`<text x="${cx}" y="${H-5}" text-anchor="middle" font-size="11" ${last?'font-weight="700" style="fill:var(--ink)"':""}>${D.length>7?"’"+String(d.y).slice(-2):d.y}</text>`});
    const L=D[n-1];
    const sub=L.ic!=null?["Zinsdeckung "+num(L.ic,1)+"×"]:[];
    return `<div class="fcard"><div class="fctl"><b>Cash und Zinsdeckung</b></div><div class="kern" style="color:var(--c-cash)">${big(L.cash)} ${esc(cur)}</div><div class="kleg"><span><i style="background:var(--c-cash)"></i>Cash</span></div>${sv}</svg><p class="fnote">${sub.length?esc(sub.join(" · "))+". ":""}Zinsdeckung = Operatives Ergebnis / Zinsaufwand; je höher, desto sicherer lassen sich die Zinsen bezahlen.</p></div>`;
  }
  /* Sankey */
  let flow="gw";
  function sankey(){flow==="cf"?cashflow():sankeyP()}
  function sankeyP(){
    $("fst").textContent="Gewinnfluss";$("fsn").textContent="Vom Umsatz bis zum Nettogewinn. Die Breite der Bänder ist proportional zum Betrag."+(I[sy]&&I[sy].grossProfit==null?" Bruttogewinn wird von diesem Unternehmen nicht ausgewiesen.":"");
    const x=I[sy]||{},hasGP=x.grossProfit!=null,R=x.revenue,cog=hasGP?Math.max(x.costOfRevenue||0,0):0,gp=hasGP?x.grossProfit:R,op=x.operatingIncome,ni=x.netIncome,tax=Math.max(x.incomeTaxExpense||0,0),intr=Math.max(x.interestExpense||0,0);
    const el=$("fsk");if(!(R>0)||gp==null){el.innerHTML='<p class="fnote">Für dieses Jahr fehlen Umsatzdaten.</p>';return}
    const nar=el.clientWidth>0&&el.clientWidth<560;el.classList.toggle("fit",nar);const W=nar?Math.max(300,el.clientWidth):760,Ht=nar?300:330,top=14,gap=12,nw=14,xs=nar?[0,(W-nw)/3,(W-nw)*2/3,W-nw]:[0,215,385,W-190-nw];
    const nodes=[],L=[];const nd=(id,col,v,lab,c)=>{if(v>0){nodes.push({id,col,v,lab,c})}};
    nd("rev",0,R,"Umsatz","#2563eb");if(hasGP){nd("cog",1,cog,"Herstellungskosten","#94a3b8");nd("gp",1,Math.max(gp,0),"Bruttogewinn","#16a34a")}
    const opex=Math.max(gp-(op??gp),0);
    if(op!=null&&op>0&&gp>0){nd("opex",2,opex,"Betriebskosten","#94a3b8");nd("op",2,op,"Operatives Ergebnis","#16a34a");
      const intc=Math.min(intr,Math.max(op-tax,0)),oth=op-tax-intc-(ni??0);nd("tax",3,tax,"Steuern","#f59e0b");nd("int",3,intc,"Zinsaufwand","#ef4444");nd("oth",3,Math.abs(oth),oth>=0?"Sonstiges":"Sonstige Erträge","#a78bfa");nd("ni",3,Math.max(ni||0,0),"Nettogewinn","#15803d");}
    const nm=Object.fromEntries(nodes.map(n=>[n.id,n]));
    const lk=(a,b,v)=>{if(nm[a]&&nm[b]&&v>0)L.push({a,b,v,c:nm[b].c})};
    const src=hasGP?"gp":"rev";lk("rev","cog",cog);lk("rev","gp",Math.max(gp,0));lk(src,"opex",opex);lk(src,"op",op>0?op:0);
    if(nm.op){lk("op","tax",tax);lk("op","int",nm.int?.v||0);lk("op","oth",nm.oth?.v||0);lk("op","ni",Math.max(ni||0,0))}
    const sc=(Ht-top*2-70)/R;let svg=`<svg viewBox="0 0 ${W} ${Ht}" role="img" aria-label="Gewinnfluss ${sy}">`;
    for(let c=0;c<4;c++){let yy=top;nodes.filter(n=>n.col===c).forEach(n=>{n.h=Math.max(n.v*sc,2);n.y=yy;n.o=0;n.i=0;yy+=c===3?Math.max(n.h+gap,36):c===0?n.h+gap:n.h+30})}
    L.forEach(l=>{const a=nm[l.a],b=nm[l.b],hh=l.v*sc,x0=xs[a.col]+nw,x1=xs[b.col],y0=a.y+a.o,y1=b.y+b.i;a.o+=hh;b.i+=hh;const m=(x0+x1)/2;
      svg+=`<path d="M${x0},${y0} C${m},${y0} ${m},${y1} ${x1},${y1} L${x1},${y1+hh} C${m},${y1+hh} ${m},${y0+hh} ${x0},${y0+hh}Z" fill="${l.c}" opacity=".28"><title>${esc(a.lab)} → ${esc(b.lab)}: ${big(l.v)}</title></path>`});
    nodes.forEach(n=>{const x0=xs[n.col],right=n.col===3,tx=right?x0+nw+8:(n.col===0?x0+nw+8:x0+nw+8);
      svg+=`<rect x="${x0}" y="${n.y}" width="${nw}" height="${n.h}" rx="3" fill="${n.c}"/>`;
      if(nar)return;
      if(n.col===0)svg+=`<text x="${x0+nw+8}" y="${n.y+16}" font-size="13" font-weight="700" fill="#14202b">${esc(n.lab)}</text><text x="${x0+nw+8}" y="${n.y+32}" font-size="12" fill="#5d6b78">${big(n.v)}</text>`;
      else if(right)svg+=`<text x="${tx}" y="${n.y+Math.min(n.h,40)/2}" font-size="12.5" font-weight="600" fill="#14202b">${esc(n.lab)}</text><text x="${tx}" y="${n.y+Math.min(n.h,40)/2+15}" font-size="12" fill="#5d6b78">${big(n.v)} · ${num(n.v/R*100,1)} %</text>`;
      else svg+=`<text x="${x0+nw+6}" y="${n.y-3}" font-size="12" font-weight="600" fill="#14202b">${esc(n.lab)}</text><text x="${x0+nw+6}" y="${n.y+n.h+12}" font-size="11.5" fill="#5d6b78">${big(n.v)} · ${num(n.v/R*100,1)} %</text>`});
    el.innerHTML=svg+"</svg>"+(nar?'<ul class="fleg">'+nodes.map(n=>`<li><i style="background:${n.c}"></i>${esc(n.lab)}<span>${big(n.v)} · ${num(n.v/R*100,1)} %</span></li>`).join("")+'</ul>':"")+(op!=null&&op<=0?'<p class="fnote">In diesem Jahr war das operative Ergebnis nicht positiv, deshalb endet der Fluss beim Bruttogewinn.</p>':"");
  }
  /* Cashflow-Verwendung */
  function cashflow(){
    $("fst").textContent="Wohin fließt der Cashflow?";
    $("fsn").textContent="Operativer Cashflow und seine Verwendung: Investitionen, Dividenden, Aktienrückkäufe, Schuldentilgung und Zukäufe. Netto gerechnet, die Breite der Bänder ist proportional zum Betrag.";
    const el=$("fsk"),c=C[sy]||{},ocf=first(c,"operatingCashFlow","netCashProvidedByOperatingActivities");
    if(!(ocf>0)){el.innerHTML='<p class="fnote">Für dieses Jahr liegt kein positiver operativer Cashflow vor.</p>';return}
    const ndi=first(c,"netDebtIssuance")??first(c,"debtRepayment"),acq=first(c,"acquisitionsNet");
    const n0=v=>v==null||isNaN(v)?0:+v;
    const newDebt=n0(first(c,"netDebtIssuance"))>0?n0(first(c,"netDebtIssuance")):0;
    const repay=ndi==null?0:(first(c,"netDebtIssuance")!=null?Math.max(-n0(ndi),0):Math.abs(n0(ndi)));
    const U=[["capex","Investitionen (Capex)",Math.abs(n0(c.capitalExpenditure)),"#0ea5e9"],["div","Dividenden",Math.abs(n0(first(c,"commonDividendsPaid","netDividendsPaid","dividendsPaid"))),"#16a34a"],["buy","Aktienrückkäufe",Math.abs(n0(first(c,"commonStockRepurchased"))),"#f59e0b"],["rep","Schuldenabbau (netto)",repay,"#a78bfa"],["acq","Zukäufe",Math.max(-n0(acq),0),"#ec4899"]].filter(u=>u[2]>0);
    const L=[["ocf","Operativer Cashflow",ocf,"#2563eb"]];if(newDebt>0)L.push(["nd","Neue Schulden (netto)",newDebt,"#8b5cf6"]);
    const sumU=U.reduce((a,u)=>a+u[2],0),sumL=L.reduce((a,u)=>a+u[2],0),diff=sumL-sumU;
    if(diff>0)U.push(["rest","Bleibt übrig (Kasse u. a.)",diff,"#94a3b8"]);else if(diff<0)L.push(["gap","Aus Kasse und Sonstigem",-diff,"#94a3b8"]);
    const nar=el.clientWidth>0&&el.clientWidth<560;el.classList.toggle("fit",nar);const T2=Math.max(sumL,sumU),W=nar?Math.max(300,el.clientWidth):760,Ht=nar?300:330,top=14,gap=12,nw=14,xr=nar?W-nw:W-210-nw;
    const sc=(Ht-top*2-gap*Math.max(L.length,U.length))/T2;let svg=`<svg viewBox="0 0 ${W} ${Ht}" role="img" aria-label="Verwendung des Cashflows ${sy}">`;
    let yy=top;L.forEach(n=>{n.h=Math.max(n[2]*sc,2);n.y=yy;n.o=0;yy+=n.h+gap});yy=top;U.forEach(n=>{n.h=Math.max(n[2]*sc,2);n.y=yy;n.i=0;yy+=n.h+gap});
    const tot=U.reduce((a,u)=>a+u[2],0);
    L.forEach(l=>U.forEach(u=>{const v=l[2]*u[2]/tot,hh=v*sc,x0=nw,x1=xr,y0=l.y+l.o,y1=u.y+u.i;l.o+=hh;u.i+=hh;const m=(x0+x1)/2;
      svg+=`<path d="M${x0},${y0} C${m},${y0} ${m},${y1} ${x1},${y1} L${x1},${y1+hh} C${m},${y1+hh} ${m},${y0+hh} ${x0},${y0+hh}Z" fill="${u[3]}" opacity=".28"><title>${esc(l[1])} → ${esc(u[1])}: ${big(v)}</title></path>`}));
    L.forEach(n=>{if(nar){svg+=`<rect x="0" y="${n.y}" width="${nw}" height="${n.h}" rx="3" fill="${n[3]}"/>`;return}svg+=`<rect x="0" y="${n.y}" width="${nw}" height="${n.h}" rx="3" fill="${n[3]}"/><text x="${nw+8}" y="${n.y+16}" font-size="13" font-weight="700" fill="#14202b">${esc(n[1])}</text><text x="${nw+8}" y="${n.y+32}" font-size="12" fill="#5d6b78">${big(n[2])}</text>`});
    U.forEach(n=>{if(nar){svg+=`<rect x="${xr}" y="${n.y}" width="${nw}" height="${n.h}" rx="3" fill="${n[3]}"/>`;return}const ty=n.y+Math.min(n.h,40)/2;svg+=`<rect x="${xr}" y="${n.y}" width="${nw}" height="${n.h}" rx="3" fill="${n[3]}"/><text x="${xr+nw+8}" y="${ty}" font-size="12.5" font-weight="600" fill="#14202b">${esc(n[1])}</text><text x="${xr+nw+8}" y="${ty+15}" font-size="12" fill="#5d6b78">${big(n[2])} · ${num(n[2]/ocf*100,0)} % des Cashflows</text>`});
    el.innerHTML=svg+"</svg>"+(nar?'<ul class="fleg">'+L.concat(U).map(n=>`<li><i style="background:${n[3]}"></i>${esc(n[1])}<span>${big(n[2])} · ${num(n[2]/ocf*100,0)} %</span></li>`).join("")+"</ul>":"");
  }
  /* Uebereinander */
  function multi(){
    $("fch").innerHTML=have.map(s=>`<button type="button" class="fchip" data-k="${s.k}" aria-pressed="${on.has(s.k)}"><i style="background:${s.c}"></i>${esc(s.l)}</button>`).join("");
    const act=have.filter(s=>on.has(s.k)),el=$("fcm");
    if(!act.length){el.innerHTML='<p class="fnote">Wähle oben mindestens eine Kennzahl.</p>';return}
    const vals=act.flatMap(s=>s.v.filter(v=>v!=null)),mx=Math.max(0,...vals),mn=Math.min(0,...vals),W=Math.max(300,Math.min(760,el.clientWidth||760)),narrow=W<560,Ht=narrow?260:300,l=narrow?46:64,r=narrow?18:12,t=14,b=28,iw=W-l-r,ih=Ht-t-b,rng=(mx-mn)||1;
    const Y=v=>t+ih*(1-(v-mn)/rng),Xc=i=>l+iw*(i+.5)/years.length;
    let svg=`<svg viewBox="0 0 ${W} ${Ht}" role="img" aria-label="Kennzahlen im Jahresvergleich">`;
    for(let i=0;i<=4;i++){const v=mn+rng*i/4,yy=Y(v);svg+=`<line x1="${l}" x2="${W-r}" y1="${yy}" y2="${yy}" stroke="#e5eaee"/><text x="${l-6}" y="${yy+4}" text-anchor="end" font-size="11" fill="#5d6b78">${short(v)}</text>`}
    svg+=`<line x1="${l}" x2="${W-r}" y1="${Y(0)}" y2="${Y(0)}" stroke="#9aa7b2"/>`;
    years.forEach((y,i)=>{if(narrow&&i%2!==years.length%2)return;svg+=`<text x="${Xc(i)}" y="${Ht-8}" text-anchor="middle" font-size="11" fill="#5d6b78">${narrow?"'"+String(y).slice(2):y}</text>`});
    if(mode==="bar"){const bw=Math.min(22,iw/years.length/(act.length+.6));act.forEach((s,si)=>s.v.forEach((v,i)=>{if(v==null)return;const x0=Xc(i)-bw*act.length/2+si*bw,y0=Y(Math.max(v,0)),hh=Math.max(Math.abs(Y(v)-Y(0)),1);svg+=`<rect x="${x0}" y="${y0}" width="${bw-1}" height="${hh}" fill="${s.c}" rx="2"><title>${esc(s.l)} ${years[i]}: ${big(v)}</title></rect>`}))}
    else act.forEach(s=>{let d="";s.v.forEach((v,i)=>{if(v==null)return;d+=(d?"L":"M")+Xc(i)+","+Y(v)});svg+=`<path d="${d}" fill="none" stroke="${s.c}" stroke-width="2.4" stroke-linejoin="round"/>`;s.v.forEach((v,i)=>{if(v!=null)svg+=`<circle cx="${Xc(i)}" cy="${Y(v)}" r="3.4" fill="${s.c}"><title>${esc(s.l)} ${years[i]}: ${big(v)}</title></circle>`})});
    el.innerHTML=svg+"</svg>";
    const miss=S.filter(s=>!have.includes(s)).map(s=>s.l);$("fmn").textContent=miss.length?"Nicht verfügbar: "+miss.join(", ")+(SD?" (in den "+quelleText(SD.q,true)+"-Angaben nicht einheitlich ausgewiesen).":" (im FMP-Tarif oder in den Daten nicht enthalten)."):"";
  }
  /* Capex-Tabelle */
  function capex(){
    const g=k=>S.find(s=>s.k===k),cx=g("capex"),rv=g("rev"),da=g("da"),dv=g("div"),fc=g("fcf");
    const pc=(a,b)=>a==null||b==null||!b?"–":num(a/b*100,0)+" %";
    let h=`<table class="ftab"><thead><tr><th>Jahr</th><th>Capex</th><th title="Capex / Umsatz">Capex-Quote</th><th title="Capex / Abschreibungen">Capex / Abschr.</th><th>Dividenden</th><th title="Freier Cashflow / Dividenden">FCF-Deckung</th></tr></thead><tbody>`;
    years.slice().reverse().forEach(y=>{const i=years.indexOf(y);h+=`<tr><td>${y}</td><td>${big(cx.v[i])}</td><td>${pc(cx.v[i],rv.v[i])}</td><td>${pc(cx.v[i],da.v[i])}</td><td>${big(dv.v[i])}</td><td>${pc(fc.v[i],dv.v[i])}</td></tr>`});
    $("fcx").innerHTML=cx.v.some(v=>v!=null)?h+"</tbody></table>":'<p class="fnote">Für dieses Unternehmen liegen keine Cashflow-Daten vor.</p>';
  }
  $("fsy").onchange=e=>{sy=e.target.value;sankey()};$("fsy").value=sy;
  box.addEventListener("click",e=>{const c=e.target.closest(".fchip");if(c){on.has(c.dataset.k)?on.delete(c.dataset.k):on.add(c.dataset.k);multi();return}const f=e.target.closest("button[data-f]");if(f){flow=f.dataset.f;box.querySelectorAll("button[data-f]").forEach(x=>x.setAttribute("aria-pressed",x===f));sankey();return}const m=e.target.closest("button[data-m]");if(m){mode=m.dataset.m;box.querySelectorAll("button[data-m]").forEach(x=>x.setAttribute("aria-pressed",x===m));multi()}});
  sankey();multi();capex();
  let rw=innerWidth;addEventListener("resize",()=>{if(!document.body.contains(box)){return}if(Math.abs(innerWidth-rw)>40){rw=innerWidth;multi();sankey()}});
}
/* ===== Unternehmensmeldungen (IR-Feeds und SEC, vom GitHub-Workflow in data/news.json gesammelt) ===== */
function initReports(sym,p){
  const box=$("nr");if(!box)return;
  fetch(FA_ROOT+"data/news.json?v="+Math.floor(Date.now()/6e5)).then(r=>r.json()).then(j=>{
    const it=(j.items||[]).filter(x=>String(x.sym).toUpperCase()===String(sym).toUpperCase()).sort((a,b)=>new Date(b.date)-new Date(a.date)).slice(0,10);
    if(!it.length)return;
    box.innerHTML=`<div class="xhead"><h3>Unternehmensmeldungen</h3><small>direkt von der Firma (IR-Feed) oder der SEC, Stand ${j.updated?esc(new Date(j.updated).toLocaleString("de-DE",{dateStyle:"medium",timeStyle:"short"})):""}</small></div><div class="nwl nrl">`+it.map((x,i)=>`<div class="nri"><button type="button" class="nrb" aria-expanded="false"><b>${esc(x.title)}</b><span>${x.quelle==="SEC"?"SEC "+esc(x.form||"8-K")+(x.kat?" · "+esc(x.kat):""):"Pressemitteilung"} · ${esc(new Date(x.date).toLocaleDateString("de-DE",{day:"numeric",month:"short",year:"numeric"}))}</span></button><div class="nrt" hidden>${x.text?String(x.text).split(/\n+/).filter(Boolean).map(t=>"<p>"+esc(t)+"</p>").join(""):"<p>Der Feed liefert keinen Text.</p>"}${x.link?`<p><a href="${esc(x.link)}" target="_blank" rel="noopener nofollow">Originalmeldung öffnen</a></p>`:""}</div></div>`).join("")+"</div>";
    box.querySelectorAll(".nrb").forEach(b=>b.onclick=()=>{const t=b.nextElementSibling,o=t.hidden;t.hidden=!o;b.setAttribute("aria-expanded",o)});
  }).catch(()=>{});
}
/* ===== Unternehmens-News (Google News ueber eigenen Cloudflare-Worker) ===== */
const NEWS_API="https://news-proxy.dividenden-rechner.workers.dev/";
function initNews(sym,p){
  const box=$("nw");if(!box)return;
  const nm=String(p.companyName||sym).replace(/,?\s+(Inc\.?|Corp\.?|Corporation|Company|Co\.|Ltd\.?|plc|PLC|N\.V\.|S\.A\.|SE|AG|Holdings?)\b\.?/g,"").replace(/^The\s+/i,"").trim()||sym;
  box.innerHTML=`<div class="xhead"><h3>Unternehmens-News</h3><small id="nwsub"></small><span class="sp"><button type="button" data-l="de" aria-pressed="true">Deutsch</button><button type="button" data-l="en" aria-pressed="false">Englisch</button></span></div><div id="nwl" class="nwl" role="status">Lade News …</div>`;
  const ago=d=>{if(!d)return"";const m=Math.round((Date.now()-new Date(d))/6e4);if(m<60)return`vor ${Math.max(m,1)} Min.`;const h=Math.round(m/60);if(h<24)return`vor ${h} Std.`;const t=Math.round(h/24);return t===1?"gestern":`vor ${t} Tagen`};
  async function load(l){
    const q=l==="de"?`"${nm}" Aktie`:`"${nm}" stock`,ck="news:"+l+":"+q,out=$("nwl");
    out.textContent="Lade News …";
    // Kuratierte Firmen-News (tools/firmennews.py): Wirtschaftsmedien, deutsch und englisch, mit Link zur Nachrichtenseite
    try{
      const f=await fetch(FA_ROOT+"data/firmennews/"+encodeURIComponent(String(sym).toUpperCase())+".json?v="+Math.floor(Date.now()/36e5)).then(r=>r.ok?r.json():null);
      if(f&&f.meldungen&&f.meldungen.length){
        const hub=`<a class="nwm" href=FA_ROOT+"firmen-news/?s=${encodeURIComponent(String(sym).toUpperCase())}">Alle News zu ${esc(f.name||sym)} auf der Nachrichtenseite</a>`;
        out.innerHTML=f.meldungen.map(x=>`<a class="nwi" href="${esc(x.link)}" target="_blank" rel="noopener nofollow"><b>${x.typ==="pm"?'<small class="pmtag">Pressemitteilung</small> ':""}${esc(x.titel)}${x.sprache==="en"?' <small>(EN)</small>':""}</b><span>${esc(x.quelle||"")}${x.quelle&&x.datum?" · ":""}${esc(x.datum||"")}</span></a>`).join("")+hub;
        $("nwsub").textContent="Quelle: Google News, Wirtschaftsmedien · Stand "+(f.stand||"");
        return;
      }
    }catch(e){}
    const gl="https://news.google.com/search?q="+encodeURIComponent(q);
    let j=null;
    try{const c=JSON.parse(localStorage.getItem(ck)||"null");if(c&&Date.now()-c.t<36e5)j=c.j}catch(e){}
    if(!j){try{const r=await fetch(NEWS_API+"?lang="+l+"&q="+encodeURIComponent(q));j=await r.json().catch(()=>null);if(!r.ok)throw new Error("HTTP "+r.status+(j&&j.error?": "+j.error:""));try{localStorage.setItem(ck,JSON.stringify({t:Date.now(),j}))}catch(e){}}
      catch(e){out.innerHTML=`Die Nachrichten sind gerade nicht abrufbar. <a href="${gl}" target="_blank" rel="noopener nofollow">Suche bei Google News öffnen</a>`;return}}
    const it=j.items||[];
    out.innerHTML=it.length?it.map(x=>`<a class="nwi" href="${esc(x.link)}" target="_blank" rel="noopener nofollow"><b>${esc(x.title)}</b><span>${esc(x.source||"")}${x.source&&x.date?" · ":""}${esc(ago(x.date))}</span></a>`).join("")+`<a class="nwm" href="${gl}" target="_blank" rel="noopener nofollow">Mehr bei Google News</a>`:`Keine Treffer. <a href="${gl}" target="_blank" rel="noopener nofollow">Bei Google News suchen</a>`;
    $("nwsub").textContent="Suche: "+q;
  }
  box.querySelectorAll("button[data-l]").forEach(b=>b.onclick=()=>{box.querySelectorAll("button[data-l]").forEach(x=>x.setAttribute("aria-pressed",x===b));load(b.dataset.l)});
  load("de");
}


/* ===== Firmenansicht: Steckbrief, Bewertung, Diagramme, Meldungen (eine Quelle für Firmenseite und Hub) ===== */
/* Auf Firmenseiten kommen die Daten aus einer kleinen Datei je Firma (data/firma-ansicht/<Kürzel>.json, tools/build_firma_ansicht.py) */
function faStart(sym, daten){
  const key=String(sym).toUpperCase(), d=daten||{};
  SECP=Promise.resolve({firmen:{[key]:d.sec||null}});
  KZP=Promise.resolve({werte:{[key]:d.kz||null}});
  FA_NUR_EIGEN=!!d.hist;               /* Kursverlauf nur, wenn es eine Datei gibt */
  FIRMA[key]=null;                       /* Jahreswerte je Firma sind schon eingerechnet */
  return firmaAnsicht(key,d.ceo||null);
}
async function faHistorie(sym){
  /* Kursverlauf in Euro: eigenes Archiv der Deutschen Börse, davor Financial Modeling Prep (tools/firma_kurse.py) */
  try{
    const k=String(sym).toUpperCase().replace(/\//g,"_");
    const j=await fetch(FA_ROOT+"data/firma-kurse/"+encodeURIComponent(k)+".json?v="+Math.floor(Date.now()/36e5)).then(r=>r.ok?r.json():null);
    if(!j||!Array.isArray(j.kurse))return [];
    return j.kurse.map(r=>({date:r[0],price:r[1]})).filter(x=>x.date&&isFinite(+x.price));
  }catch(e){return []}
}
async function firmaAnsicht(sym,ceo){
  const msg=$("msg"),hub=$("hub");
  msg.className="";msg.textContent=`Lade ${sym} …`;
  const [S_,KZ_]=await Promise.all([secLoad(),kzLoad()]);
  await firmaNachladen(S_,sym);
  const SF=secFirma(S_,sym),SD=SF?secDaten(SF):null;
  const KZ=KZ_&&KZ_.werte?(KZ_.werte[String(sym).toUpperCase()]||KZ_.werte[String(sym).toUpperCase().replace(/\./g,"-")]||null):null;
  if(!SD&&!KZ){msg.className="err";msg.textContent=`Für ${sym} liegen noch keine Daten vor.`;return}
  const p={companyName:(SF&&SF.n)||(KZ&&KZ.name)||sym,sector:KZ&&KZ.sektor,exchange:KZ&&KZ.boerse,currency:(KZ&&KZ.waehrung)||(SD&&SD.cur)||"EUR"};
  const kzR=KZ?{priceToEarningsRatioTTM:KZ.kgv,priceToBookRatioTTM:KZ.kbv,dividendYieldTTM:KZ.rendite!=null?KZ.rendite/100:null,dividendPayoutRatioTTM:KZ.ausschuettung!=null?KZ.ausschuettung/100:null,operatingProfitMarginTTM:KZ.operative_marge!=null?KZ.operative_marge/100:null,interestCoverageRatioTTM:KZ.zinsdeckung}:{};
  const kzM=KZ?{evToEBITDATTM:KZ.ev_ebitda,freeCashFlowYieldTTM:KZ.fcf_rendite!=null?KZ.fcf_rendite/100:null,returnOnInvestedCapitalTTM:KZ.roic!=null?KZ.roic/100:null,returnOnEquityTTM:KZ.roe!=null?KZ.roe/100:null,netDebtToEBITDATTM:KZ.nettoschulden_ebitda}:{};
  const ohneNull=o=>Object.fromEntries(Object.entries(o||{}).filter(([k,v])=>v!=null));
  const r=ohneNull(kzR),m=ohneNull(kzM);
  const inc=SD?SD.inc:[],cf=SD?SD.cf:[];
  const cur=SD?SD.cur:p.currency;
  /* Dividende je Aktie: je Geschäftsjahr aus der SEC/ESEF-Auswertung */
  let divs=SD&&SD.dy.length?SD.dy.map(x=>({y:x.y,v:x.v,part:false})):[];
  let divNote=SD&&SD.dy.length?"je Geschäftsjahr, "+esc(SD.cur)+(SD.dy.some(x=>x.ber)?"; teils nachgerechnet aus gezahlten Dividenden und Aktienzahl":"")+". Quelle: "+quelleText(SD.q,true):"";
  /* Beschlossene Dividende: blasser Balken für das Jahr nach dem letzten Geschäftsjahr */
  const thisY=String(new Date().getFullYear());
  if(SD&&SD.dy.length&&KZ&&KZ.dividende_basis==="aktuell"&&KZ.dividende>0&&(!KZ.waehrung||KZ.waehrung===SD.cur)){
    const ny=+divs[divs.length-1].y+1;
    if(ny<=+thisY){divs=divs.concat([{y:String(ny),v:KZ.dividende,part:true}]).slice(-10);divNote+="; "+ny+" blass: aktuelle Jahresrate aus dem jüngsten Dividendenbeschluss"}}
  /* Kurs: eigener Schlusskurs in Euro (Deutsche Börse, verzögert) */
  const price=KZ?KZ.kurs_eur:null,chg=KZ?KZ.veraenderung:null;
  if(KZ)p.currency="EUR";
  const pr=await faHistorie(sym);
  const sg=v=>v==null?"":v>=0?"pos":"neg";
  const KC=kursChart(sym,p.currency||cur,pr,{},price);
  const img2=ceo?`<figure class="fa-ceo"><img src="${esc(FA_ROOT+ceo.datei)}" alt="${esc(ceo.name)}" loading="lazy"><figcaption><b>${esc(ceo.name)}</b><br>${esc(ceo.rolle||"")}</figcaption></figure>`:"";
  hub.innerHTML=`
  <div class="head"><div><small class="sub">${esc(["Stand: "+new Date().toLocaleDateString("de-DE",{day:"numeric",month:"long",year:"numeric"}),"Kürzel "+sym,p.sector].filter(Boolean).join(" · "))}</small></div>
  <div class="price">${num(price)} ${esc(p.currency||"")}<small class="${sg(chg)}">${chg==null?"":(chg>0?"+":"")+num(chg)+" % heute"}</small></div></div>
  ${steckbrief(sym,p,r,m,inc,cf,KZ,SD)}
  ${pr.length>1?KC.html:""}
  <div class="grid">
   ${bars("Dividende je Aktie",divNote,divs,"var(--c-gold)",v=>num(v))}
   ${combo(inc,cur)}
   ${margins(inc)}
   ${fcfChart(cf,cur,zinsInfo(SD,cur))}
  </div>
  ${kzTabelle(KZ)}
  ${secCharts(SD,cur,epsChart(inc,cur))}
  <div id="fin"></div>
  <div id="nr"></div>
  <div id="nw"></div>
  ${img2}`;
  const st=$("start");if(st)st.hidden=true;
  hub.hidden=false;msg.textContent="";
  alignCharts();
  if(pr.length>1)try{KC.init()}catch(e){console.error(e)}
  try{initFinance(sym,p,cur,inc,cf,SD)}catch(e){console.error(e)}
  try{initReports(sym,p)}catch(e){console.error(e)}
  try{initNews(sym,p)}catch(e){console.error(e)}
  return p;
}
