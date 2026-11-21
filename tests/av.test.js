// Tests für das Altersvorsorgedepot: Kostenmodell je Depotmodell, Zulagen, Steuer, Daten und Quellen.
// Aufruf: node --test tests/av.test.js
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("fs");
const path = require("path");
const RM = require("../assets/rechner.js");

const ROOT = path.join(__dirname, "..");
const D = JSON.parse(fs.readFileSync(path.join(ROOT, "data", "av-anbieter.json"), "utf8"));
const PAGE = fs.readFileSync(path.join(ROOT, "altersvorsorgedepot", "index.html"), "utf8");
const FLAT = JSON.parse(PAGE.match(/<script type="application\/json" id="av-data">([\s\S]*?)<\/script>/)[1].replace(/<\\\//g, "</"));
// Engine-Tests rechnen mit allen Depotmodellen aus den Daten, nicht nur mit denen in der Tabelle
const P = Object.fromEntries(D.anbieter.flatMap((a) => a.produkte.map((p) => [p.id, { id: p.id, b: p.bestandteile, k: p.konditionen }])));

// Vertragsmonat für ein Kalenderdatum bei gegebener Eröffnung
const t = (eroeffnung, ym) => { const [y0, m0] = eroeffnung.split("-").map(Number), [y, m] = ym.split("-").map(Number); return (y - y0) * 12 + (m - m0); };
const k = (id, ym, opt = {}, bal = 0) => { const e = opt.eroeffnung || "2027-01"; return RM.avKostenAm(P[id], t(e, ym), bal, Object.assign({ eroeffnung: e }, opt)); };
const BASE = { alter: 30, rentenalter: 67, endalter: 85, beitrag: 150, kinderAlter: [], kindBis: 18, einsteiger: false, rendite: 6, kosten: 1, rAus: 3, steuerAlter: 20, ter: 0.2 };

test("zeitabhängige Gebühren: flatex Core 0 % in den Jahren 1–5, danach höchstens 0,07 %", () => {
  assert.equal(k("flatex-core", "2031-12").pct, 0);
  const j6 = k("flatex-core", "2032-01");
  assert.equal(j6.pct, 0.07); assert.equal(j6.flags.max, true);
});

test("zeitabhängige Gebühren: DWS-Standarddepot über die Deutsche Bank 0,10 % zwei Jahre, danach 0,28 %", () => {
  assert.equal(k("db-dws-standard", "2028-12").pct, 0.10);
  assert.equal(k("db-dws-standard", "2029-01").pct, 0.28);
  // Vertragsjahre zählen ab Eröffnung, nicht ab Kalenderjahr
  assert.equal(k("db-dws-standard", "2030-05", { eroeffnung: "2028-06" }).pct, 0.10);
  assert.equal(k("db-dws-standard", "2030-06", { eroeffnung: "2028-06" }).pct, 0.28);
});

test("Erstattungszeiträume bis Kalenderdatum: N26 bis 12/2028, Consorsbank bis 12/2030", () => {
  assert.equal(k("n26-standard", "2028-12").pct, 0);
  assert.equal(k("n26-standard", "2029-01").pct, 0.09);
  assert.equal(k("consors-standard", "2030-12").pct, 0);
  assert.equal(k("consors-standard", "2031-01").pct, 0.12);
  assert.equal(k("consors-fokus", "2031-01").pct, 0.20);
});

test("N26: Servicegebühr hängt vom Eröffnungsmonat ab, 0,09 % sind nicht die Gesamtkosten für alle", () => {
  assert.equal(k("n26-standard", "2029-01", { eroeffnung: "2027-06" }).pct, 0.09);
  assert.equal(k("n26-standard", "2027-07", { eroeffnung: "2027-07" }).pct, 0.10);
  assert.equal(k("n26-standard", "2029-01", { eroeffnung: "2027-07" }).pct, 0.19);
  const a = RM.avdCalc(Object.assign({}, BASE, { kostenFn: RM.avKostenFn(P["n26-standard"], { eroeffnung: "2027-06" }) }));
  const b = RM.avdCalc(Object.assign({}, BASE, { kostenFn: RM.avKostenFn(P["n26-standard"], { eroeffnung: "2027-07" }) }));
  assert.ok(a.netto > b.netto, "spätere Eröffnung mit Servicegebühr muss weniger Auszahlung ergeben");
});

test("freiwillige Erstattung ohne Enddatum: Scalable-Rentenbonus und Trade Republic nur mit Schalter", () => {
  assert.equal(k("sc-standard", "2027-06").pct, 0);
  const mit = k("sc-standard", "2028-01");
  assert.equal(mit.pct, 0); assert.equal(mit.flags.freiwillig, true);
  assert.equal(k("sc-standard", "2028-01", { freiwillig: false }).pct, 0.15);
  assert.equal(k("sc-standard", "2027-06", { freiwillig: false }).pct, 0, "befristete Erstattung bis 2027 ist nicht freiwillig");
  assert.equal(k("tr-standard", "2040-01").pct, 0);
  assert.equal(k("tr-standard", "2040-01", { freiwillig: false }).offen, true, "ohne Erstattung ist die TER von Trade Republic nicht veröffentlicht");
});

test("fehlende Kostenangaben ergeben 'offen' statt einer geschätzten Zahl", () => {
  assert.equal(k("sb-standard", "2029-12").pct, 0);
  assert.equal(k("sb-standard", "2030-01").offen, true);
  assert.equal(k("raisin-standard", "2027-01").offen, true);
  assert.equal(k("comdirect-standard", "2027-01").offen, true);
  assert.equal(k("bp-standard", "2030-01").offen, true);
  const r = RM.avdCalc(Object.assign({}, BASE, { kostenFn: RM.avKostenFn(P["sb-standard"], {}) }));
  assert.equal(r.offen, true); assert.equal(r.abJahr, 4);
  // kein Anbieterpreis aus der eigenen 1-%-Annahme
  assert.ok(!("netto" in r));
});

test("Erstattungsgrenze beim Depotwert: nur der Anteil bis zur Grenze wird erstattet", () => {
  const p = { k: "veroeffentlicht", b: [{ art: "fund_ter", pct: 0.2 }, { art: "ter_erstattung", pct: null, voll: true, max_volumen: 25000 }] };
  assert.equal(RM.avKostenAm(p, 0, 10000, {}).pct, 0);
  assert.equal(RM.avKostenAm(p, 0, 50000, {}).pct, 0.1);
  // unbekannte TER oberhalb der Grenze: offen
  assert.equal(k("sb-standard", "2027-03", {}, 50000).offen, true);
});

test("feste Euro-Gebühren (Fidelity 1 € im Monat) mindern das Ergebnis", () => {
  const c = k("fidelity-vorsorgedepot", "2027-01");
  assert.equal(c.pct, 0.35); assert.equal(c.eur, 12); assert.equal(c.flags.ca, true);
  const mitGebuehr = RM.avdCalc(Object.assign({}, BASE, { kostenFn: RM.avKostenFn(P["fidelity-vorsorgedepot"], {}) }));
  const ohne = RM.avdCalc(Object.assign({}, BASE, { kostenFn: () => ({ pct: 0.35, eur: 0 }) }));
  assert.ok(ohne.wert - mitGebuehr.wert > 12 * 37, "37 Jahre à 12 € plus entgangene Erträge");
});

test("Kostenfunktion mit konstanten Kosten entspricht der bisherigen Rechnung", () => {
  const alt = RM.avdCalc(Object.assign({}, BASE, { kosten: 0.2 }));
  const neu = RM.avdCalc(Object.assign({}, BASE, { kostenFn: RM.avKostenFn(P["ing-relax"], {}) }));
  assert.ok(Math.abs(alt.wert - neu.wert) < 1e-6);
  assert.ok(Math.abs(alt.netto - neu.netto) < 1e-6);
});

test("mehrere Depotmodelle je Anbieter werden getrennt erfasst", () => {
  const ids = new Set();
  for (const a of D.anbieter) for (const p of a.produkte) { assert.ok(!ids.has(p.id), "doppelte id " + p.id); ids.add(p.id); assert.ok(["standard", "gesteuert", "frei", "beratung", "garantie"].includes(p.art), p.id); }
  const anzahl = (id) => D.anbieter.find((a) => a.id === id).produkte.length;
  assert.equal(anzahl("n26"), 2); assert.equal(anzahl("consorsbank"), 3); assert.equal(anzahl("allianz"), 3);
});

test("Tabelle zeigt nur zertifizierte Altersvorsorgedepots mit Anbieterbeleg, alle anderen stehen im Aufklappbereich", () => {
  const imVergleich = (p) => (p.zertifikate || []).length > 0 && p.pruefstatus === "primary_verified" && p.art !== "garantie";
  const soll = D.anbieter.flatMap((a) => a.produkte.filter(imVergleich).map((p) => p.id)).sort();
  assert.deepEqual(FLAT.map((p) => p.id).sort(), soll);
  for (const p of FLAT) assert.notEqual(p.art, "garantie", p.id);
  for (const id of ["sc-standard", "tr-standard", "allianz-standard"]) assert.ok(soll.includes(id), id);
  for (const id of ["n26-standard", "allianz-investflex80", "tp-standard"]) assert.ok(!soll.includes(id), id);
  for (const a of D.anbieter) for (const p of a.produkte) for (const z of p.zertifikate || []) { assert.match(z.nr, /^\d{6}$/, p.id); assert.ok(p.quellen.includes("bzst"), p.id); }
  const more = PAGE.match(/<details class="av-more">([\s\S]*?)<\/details>/);
  assert.ok(more, "Aufklappbereich fehlt");
  for (const a of D.anbieter) if (!a.produkte.some(imVergleich)) assert.ok(more[1].includes(a.name.replace(/&/g, "&amp;")), a.name + " fehlt im Aufklappbereich");
});

test("Quellenzuordnung: jede Aussage hat eine Quelle mit URL und Abrufdatum", () => {
  for (const [id, q] of Object.entries(D.quellen)) { assert.match(q.url, /^https:\/\//, id); assert.equal(q.abgerufen.length, 10, id); assert.ok(["primaer", "sekundaer", "amtlich"].includes(q.typ), id); }
  for (const a of D.anbieter) for (const p of a.produkte) {
    assert.ok(p.quellen.length >= 1, p.id);
    for (const s of p.quellen) assert.ok(D.quellen[s], p.id + " -> " + s);
    for (const b of p.bestandteile) assert.ok(b.quelle && D.quellen[b.quelle], p.id + " Bestandteil ohne Quelle");
    if (p.pruefstatus === "primary_verified") assert.ok(p.quellen.some((s) => D.quellen[s].typ === "primaer"), p.id + " ohne Anbieterquelle");
  }
});

test("nur mit Anbieterquellen belegte Angebote kommen in den Rechner", () => {
  for (const p of FLAT) if (p.r) assert.equal(p.pr, "primary_verified", p.id);
  const ids = new Set(FLAT.filter((p) => p.r).map((p) => p.id));
  for (const id of ["tp-standard", "dws-vorsorgedepot", "union-basis", "deka-plus", "n26-standard"]) assert.ok(!ids.has(id), id);
});

test("Python (build_av.py) und JavaScript rechnen gleich", () => {
  for (const p of FLAT) {
    const kz = RM.avKennzahlen(p, { eroeffnung: "2027-01", freiwillig: true });
    assert.equal(kz.start, p.ks, p.id + " Beginn");
    assert.equal(kz.lang, p.kd, p.id + " 10. Jahr");
  }
});

test("Zulagen nach § 84 ff. EStG", () => {
  assert.deepEqual(RM.zulage(1800, 0), { grund: 540, kind: 0 });
  assert.deepEqual(RM.zulage(360, 0), { grund: 180, kind: 0 });
  assert.deepEqual(RM.zulage(119, 2), { grund: 0, kind: 0 }, "unter 120 € Mindesteigenbeitrag keine Zulage");
  assert.deepEqual(RM.zulage(300, 2), { grund: 150, kind: 600 });
  assert.deepEqual(RM.zulage(6840, 1), { grund: 540, kind: 300 });
});

test("Berufseinsteiger-Bonus nur mit Mindesteigenbeitrag", () => {
  const o = Object.assign({}, BASE, { alter: 22, einsteiger: true });
  assert.equal(RM.avdCalc(o).bonus, 200);
  assert.equal(RM.avdCalc(Object.assign({}, o, { beitrag: 9 })).bonus, 0);
});

test("Steuer und Auszahlung: nachgelagerte Besteuerung und ETF-Vergleich", () => {
  const r = RM.avdCalc(BASE);
  assert.ok(Math.abs(r.netto - r.brutto * 0.8) < 1e-9);
  assert.ok(Math.abs(r.brutto - RM.pension(r.wert, 0.03, 18)) < 1e-9);
  const gain = r.etfWert - r.eingezahlt;
  assert.ok(Math.abs(r.etfSteuer - Math.max(0, gain * 0.7 - 1000) * 0.26375) < 1e-6);
  // Beispiel aus dem Ratgebertext der Seite (Voreinstellungen, 1,0 % Kosten)
  assert.equal(Math.round(r.wert), 241965);
});
