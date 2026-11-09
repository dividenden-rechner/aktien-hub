// Cloudflare Worker: Konto mit Anmeldung per E-Mail-Link (ohne Passwort) und gespeicherter Watchlist.
// Ablauf: POST /login -> Mail mit Einmal-Link auf SEITE/konto/?t=... -> POST /verify -> Sitzungsschluessel (im Browser) -> GET/PUT /watchlist.
// Gespeichert werden nur E-Mail-Adresse, Zeitpunkt der Einwilligung und die Liste der Kuerzel. Brevo verschickt die Mails (Secret BREVO_API_KEY).
const ERLAUBT = ["https://dividenden-rechner.github.io", "https://www.dividenden-rechner.de", "https://dividenden-rechner.de"];
const LINK_MS = 15 * 60 * 1000;                 // Einmal-Link: 15 Minuten gueltig
const SESSION_MS = 90 * 24 * 3600 * 1000;       // Sitzung: 90 Tage
const MAX_EINTRAEGE = 300;
const MAX_MAILS_PRO_STUNDE = 5;                 // je E-Mail-Adresse
const MAX_ANFRAGEN_IP_STUNDE = 20;              // je Besucher

function cors(req) {
  const o = req.headers.get("Origin") || "";
  return {
    "Access-Control-Allow-Origin": ERLAUBT.includes(o) ? o : ERLAUBT[0],
    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
    "Vary": "Origin",
  };
}
function antwort(req, status, obj) {
  return new Response(JSON.stringify(obj), { status, headers: { "Content-Type": "application/json", "Cache-Control": "no-store", ...cors(req) } });
}
const b64u = (buf) => btoa(String.fromCharCode(...new Uint8Array(buf))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
const zufall = () => b64u(crypto.getRandomValues(new Uint8Array(32)));
async function hash(text) { return b64u(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text))); }

function mailHtml(link) {
  return '<!DOCTYPE html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Anmelden bei Dividenden-Rechner.de</title></head>'
    + '<body style="margin:0;background:#f4f6f8;font-family:Arial,Helvetica,sans-serif;color:#14202b;"><table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f4f6f8;"><tr><td align="center" style="padding:24px 12px;">'
    + '<table role="presentation" width="560" cellspacing="0" cellpadding="0" style="max-width:560px;background:#ffffff;border:1px solid #dfe5ea;">'
    + '<tr><td style="background:#2f9e5b;height:6px;font-size:0;line-height:0;">&nbsp;</td></tr>'
    + '<tr><td style="padding:28px 32px 8px 32px;font-size:20px;font-weight:bold;">Dividenden-Rechner<span style="color:#2f9e5b;">.de</span></td></tr>'
    + '<tr><td style="padding:8px 32px 0 32px;font-size:22px;font-weight:bold;line-height:1.3;">Dein Anmelde-Link</td></tr>'
    + '<tr><td style="padding:14px 32px 0 32px;">Mit einem Klick meldest du dich an und kannst deine Watchlist auf jedem Gerät nutzen. Der Link gilt 15 Minuten und funktioniert nur einmal.</td></tr>'
    + '<tr><td style="padding:24px 32px 8px 32px;"><a href="' + link + '" style="display:inline-block;padding:14px 28px;background:#2f9e5b;color:#ffffff;font-weight:bold;text-decoration:none;">Jetzt anmelden</a></td></tr>'
    + '<tr><td style="padding:20px 32px 0 32px;font-size:13px;color:#5d6b78;">Funktioniert der Button nicht? Kopiere diesen Link in den Browser:<br><a href="' + link + '" style="color:#2f9e5b;word-break:break-all;">' + link + '</a></td></tr>'
    + '<tr><td style="padding:20px 32px 28px 32px;font-size:13px;color:#5d6b78;border-bottom:1px solid #dfe5ea;">Wenn du dich nicht anmelden wolltest, ignoriere diese Mail einfach. Es passiert nichts.</td></tr>'
    + '<tr><td style="padding:14px 32px;font-size:12px;color:#5d6b78;">Dividenden-Rechner.de · Alle Angaben ohne Gewähr, keine Anlageberatung.</td></tr></table></td></tr></table></body></html>';
}

function bereinigeListe(items) {
  if (!Array.isArray(items) || items.length > MAX_EINTRAEGE) return null;
  const aus = [], gesehen = new Set();
  for (const x of items) {
    const s = String((x && x.s) || "").trim().toUpperCase();
    if (!/^[A-Z0-9.\-^=]{1,15}$/.test(s) || gesehen.has(s)) continue;
    gesehen.add(s);
    const e = { s, n: String((x && x.n) || s).slice(0, 80) };
    const i = String((x && x.i) || "").trim().toUpperCase();
    if (/^[A-Z]{2}[A-Z0-9]{9}\d$/.test(i)) e.i = i;
    aus.push(e);
  }
  return aus;
}

async function nutzerAusSitzung(req, env) {
  const m = /^Bearer\s+([A-Za-z0-9_-]{20,80})$/.exec(req.headers.get("Authorization") || "");
  if (!m) return null;
  const h = await hash(m[1]);
  const z = await env.DB.prepare("SELECT s.user_id AS id, u.email AS email FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.hash = ? AND s.exp > ?").bind(h, Date.now()).first();
  return z ? { id: z.id, email: z.email, hash: h } : null;
}

export default {
  async fetch(req, env) {
    const url = new URL(req.url), pfad = url.pathname;
    if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: cors(req) });
    const origin = req.headers.get("Origin") || "";
    if (!ERLAUBT.includes(origin) && !/^http:\/\/localhost(:\d+)?$/.test(origin)) return antwort(req, 403, { fehler: "nicht erlaubt" });
    if (!env.DB) return antwort(req, 500, { fehler: "Konto ist noch nicht eingerichtet." });
    const jetzt = Date.now();

    // 1. Anmelde-Link anfordern
    if (req.method === "POST" && pfad === "/login") {
      let d; try { d = await req.json(); } catch (e) { return antwort(req, 400, { fehler: "ungueltige Anfrage" }); }
      if (d.website) return antwort(req, 200, { ok: true });   // Honigtopf: Bots
      const mail = String(d.email || "").trim().toLowerCase();
      if (mail.length > 200 || !/^[^\s@<>"]+@[^\s@<>"]+\.[^\s@<>"]{2,}$/.test(mail)) return antwort(req, 400, { fehler: "Bitte eine gueltige E-Mail-Adresse eingeben." });
      if (d.einwilligung !== true) return antwort(req, 400, { fehler: "Bitte der Speicherung deiner E-Mail-Adresse zustimmen." });
      if (!env.BREVO_API_KEY) return antwort(req, 500, { fehler: "Konto ist noch nicht eingerichtet." });
      const ip = req.headers.get("CF-Connecting-IP") || "?";
      await env.DB.prepare("DELETE FROM loginlog WHERE ts < ?").bind(jetzt - 3600000).run();
      await env.DB.prepare("DELETE FROM links WHERE exp < ?").bind(jetzt).run();
      await env.DB.prepare("DELETE FROM sessions WHERE exp < ?").bind(jetzt).run();
      const nm = await env.DB.prepare("SELECT COUNT(*) AS n FROM loginlog WHERE email = ?").bind(mail).first();
      const ni = await env.DB.prepare("SELECT COUNT(*) AS n FROM loginlog WHERE ip = ?").bind(ip).first();
      if (nm.n >= MAX_MAILS_PRO_STUNDE || ni.n >= MAX_ANFRAGEN_IP_STUNDE) return antwort(req, 429, { fehler: "Zu viele Versuche. Bitte spaeter erneut probieren." });
      await env.DB.prepare("INSERT INTO loginlog (email, ip, ts) VALUES (?, ?, ?)").bind(mail, ip, jetzt).run();
      const t = zufall();
      await env.DB.prepare("INSERT INTO links (hash, email, exp, consent_at) VALUES (?, ?, ?, ?)").bind(await hash(t), mail, jetzt + LINK_MS, jetzt).run();
      const link = (env.SEITE || ERLAUBT[1]) + "/konto/?t=" + t;
      const r = await fetch("https://api.brevo.com/v3/smtp/email", {
        method: "POST",
        headers: { "api-key": env.BREVO_API_KEY, "Content-Type": "application/json", "Accept": "application/json" },
        body: JSON.stringify({ sender: { name: "Dividenden-Rechner.de", email: env.ABSENDER_MAIL }, to: [{ email: mail }], subject: "Dein Anmelde-Link für Dividenden-Rechner.de", htmlContent: mailHtml(link) }),
      });
      if (!r.ok) { console.log("Brevo", r.status, (await r.text()).slice(0, 200)); return antwort(req, 502, { fehler: "Anmeldung gerade nicht moeglich. Bitte spaeter erneut versuchen." }); }
      return antwort(req, 200, { ok: true });   // gleiche Antwort, ob die Adresse schon ein Konto hat oder nicht
    }

    // 2. Link einloesen: Konto anlegen (falls neu) und Sitzung ausgeben
    if (req.method === "POST" && pfad === "/verify") {
      let d; try { d = await req.json(); } catch (e) { return antwort(req, 400, { fehler: "ungueltige Anfrage" }); }
      const t = String(d.t || "");
      if (!/^[A-Za-z0-9_-]{20,80}$/.test(t)) return antwort(req, 400, { fehler: "Link ungueltig." });
      const h = await hash(t);
      const l = await env.DB.prepare("SELECT email, exp, consent_at FROM links WHERE hash = ?").bind(h).first();
      await env.DB.prepare("DELETE FROM links WHERE hash = ?").bind(h).run();   // Einmal-Link: sofort verbraucht
      if (!l || l.exp < jetzt) return antwort(req, 400, { fehler: "Der Link ist abgelaufen oder wurde schon benutzt. Bitte fordere einen neuen an." });
      await env.DB.prepare("INSERT OR IGNORE INTO users (email, created, consent_at) VALUES (?, ?, ?)").bind(l.email, jetzt, l.consent_at).run();
      const u = await env.DB.prepare("SELECT id FROM users WHERE email = ?").bind(l.email).first();
      const s = zufall();
      await env.DB.prepare("INSERT INTO sessions (hash, user_id, created, exp) VALUES (?, ?, ?, ?)").bind(await hash(s), u.id, jetzt, jetzt + SESSION_MS).run();
      return antwort(req, 200, { ok: true, session: s, email: l.email });
    }

    const nutzer = await nutzerAusSitzung(req, env);
    if (!nutzer) return antwort(req, 401, { fehler: "nicht angemeldet" });

    if (req.method === "GET" && pfad === "/watchlist") {
      const w = await env.DB.prepare("SELECT data, updated FROM watchlist WHERE user_id = ?").bind(nutzer.id).first();
      return antwort(req, 200, { email: nutzer.email, items: w ? JSON.parse(w.data) : [], updated: w ? w.updated : 0 });
    }
    if (req.method === "PUT" && pfad === "/watchlist") {
      let d; try { d = await req.json(); } catch (e) { return antwort(req, 400, { fehler: "ungueltige Anfrage" }); }
      const liste = bereinigeListe(d.items);
      if (!liste) return antwort(req, 400, { fehler: "Die Watchlist ist ungueltig oder zu lang (hoechstens " + MAX_EINTRAEGE + " Eintraege)." });
      await env.DB.prepare("INSERT INTO watchlist (user_id, data, updated) VALUES (?, ?, ?) ON CONFLICT(user_id) DO UPDATE SET data = excluded.data, updated = excluded.updated").bind(nutzer.id, JSON.stringify(liste), jetzt).run();
      return antwort(req, 200, { ok: true, items: liste, updated: jetzt });
    }
    if (req.method === "GET" && pfad === "/export") {
      const w = await env.DB.prepare("SELECT data FROM watchlist WHERE user_id = ?").bind(nutzer.id).first();
      const u = await env.DB.prepare("SELECT created, consent_at FROM users WHERE id = ?").bind(nutzer.id).first();
      return antwort(req, 200, { email: nutzer.email, angelegt: new Date(u.created).toISOString(), einwilligung: new Date(u.consent_at).toISOString(), watchlist: w ? JSON.parse(w.data) : [] });
    }
    if (req.method === "POST" && pfad === "/logout") {
      await env.DB.prepare("DELETE FROM sessions WHERE hash = ?").bind(nutzer.hash).run();
      return antwort(req, 200, { ok: true });
    }
    if (req.method === "DELETE" && pfad === "/konto") {   // alles loeschen: Konto, Sitzungen, Watchlist
      await env.DB.prepare("DELETE FROM watchlist WHERE user_id = ?").bind(nutzer.id).run();
      await env.DB.prepare("DELETE FROM sessions WHERE user_id = ?").bind(nutzer.id).run();
      await env.DB.prepare("DELETE FROM users WHERE id = ?").bind(nutzer.id).run();
      return antwort(req, 200, { ok: true });
    }
    return antwort(req, 404, { fehler: "nicht gefunden" });
  },
};
