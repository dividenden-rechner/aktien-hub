// Cloudflare Worker: Newsletter-Anmeldung mit eigenem Double-Opt-in, Versand und Kontaktverwaltung ueber Brevo.
// Ablauf: POST /anmelden -> Bestaetigungsmail mit signiertem Link -> GET /bestaetigen -> Kontakt wird in die Liste eingetragen.
// Der Brevo-Schluessel liegt hier als Secret (BREVO_API_KEY) und kommt nie in den Browser. Er dient auch zum Signieren der Links.
const ERLAUBT = ["https://dividenden-rechner.github.io", "https://www.dividenden-rechner.de", "https://dividenden-rechner.de"];
const GUELTIG_MS = 48 * 3600 * 1000;

function cors(req) {
  const o = req.headers.get("Origin") || "";
  return {
    "Access-Control-Allow-Origin": ERLAUBT.includes(o) ? o : ERLAUBT[0],
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Vary": "Origin",
  };
}
function antwort(req, status, obj) {
  return new Response(JSON.stringify(obj), { status, headers: { "Content-Type": "application/json", ...cors(req) } });
}
const b64u = (buf) => btoa(String.fromCharCode(...new Uint8Array(buf))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
const unb64u = (s) => atob(s.replace(/-/g, "+").replace(/_/g, "/"));
async function signatur(env, text) {
  const k = await crypto.subtle.importKey("raw", new TextEncoder().encode("newsletter:" + env.BREVO_API_KEY), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  return b64u(await crypto.subtle.sign("HMAC", k, new TextEncoder().encode(text)));
}
async function token(env, mail) {
  const nutz = b64u(new TextEncoder().encode(mail + "|" + Date.now()));
  return nutz + "." + await signatur(env, nutz);
}
async function pruefe(env, t) {
  const [nutz, sig] = String(t || "").split(".");
  if (!nutz || !sig || sig !== await signatur(env, nutz)) return null;
  let roh; try { roh = new TextDecoder().decode(Uint8Array.from(unb64u(nutz), c => c.charCodeAt(0))); } catch (e) { return null; }
  const i = roh.lastIndexOf("|"), mail = roh.slice(0, i), ts = Number(roh.slice(i + 1));
  if (!mail || !ts || Date.now() - ts > GUELTIG_MS) return null;
  return mail;
}
function seite(titel, text) {
  return new Response('<!DOCTYPE html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>' + titel + '</title></head><body style="font-family:Arial,sans-serif;max-width:520px;margin:15vh auto;padding:0 16px;color:#14202b"><h1>' + titel + '</h1><p>' + text + '</p><p><a href="https://www.dividenden-rechner.de/" style="color:#1a7a45">Zur Startseite</a></p></body></html>', { status: 200, headers: { "Content-Type": "text/html; charset=utf-8" } });
}
function mailHtml(link) {
  return '<!DOCTYPE html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Newsletter-Anmeldung bestätigen</title></head><body style="margin:0;padding:0;background:#f0f8f3;"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f0f8f3;"><tr><td align="center" style="padding:28px 12px;"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:540px;background:#ffffff;border:1px solid #dfe5ea;font-family:Arial,Helvetica,sans-serif;font-size:16px;line-height:1.55;color:#14202b;">'
    + '<tr><td style="background:#2f9e5b;height:6px;font-size:0;line-height:0;">&nbsp;</td></tr>'
    + '<tr><td style="padding:28px 32px 8px 32px;font-size:20px;font-weight:bold;color:#14202b;">Dividenden-Rechner<span style="color:#2f9e5b;">.de</span></td></tr>'
    + '<tr><td style="padding:8px 32px 0 32px;font-size:22px;font-weight:bold;line-height:1.3;">Fast geschafft: Bitte bestätige deine Anmeldung</td></tr>'
    + '<tr><td style="padding:14px 32px 0 32px;">Schön, dass du dabei sein möchtest. Einmal pro Woche schicken wir dir die wichtigsten Neuigkeiten zu Dividenden, Quartalszahlen und dem Aktien-Hub.</td></tr>'
    + '<tr><td style="padding:12px 32px 0 32px;">Damit wir sicher sind, dass die Adresse dir gehört, bestätige sie bitte mit einem Klick:</td></tr>'
    + '<tr><td style="padding:24px 32px 8px 32px;"><a href="' + link + '" style="display:inline-block;padding:14px 28px;background:#2f9e5b;color:#ffffff;font-weight:bold;text-decoration:none;border-radius:6px;">Anmeldung bestätigen</a></td></tr>'
    + '<tr><td style="padding:20px 32px 0 32px;font-size:13px;color:#5d6b78;">Funktioniert der Button nicht? Kopiere diesen Link in den Browser:<br><a href="' + link + '" style="color:#1a7a45;word-break:break-all;">' + link + '</a></td></tr>'
    + '<tr><td style="padding:20px 32px 28px 32px;font-size:13px;color:#5d6b78;border-bottom:1px solid #dfe5ea;">Wenn du dich nicht angemeldet hast, ignoriere diese Mail einfach. Dann passiert nichts. Der Link ist 48 Stunden gültig. Abmelden kannst du dich später jederzeit über den Link in jeder Newsletter-Mail.</td></tr>'
    + '<tr><td style="padding:14px 32px;font-size:12px;color:#5d6b78;">Dividenden-Rechner.de · Alle Angaben ohne Gewähr, keine Anlageberatung.</td></tr></table></td></tr></table></body></html>';
}

export default {
  async fetch(req, env) {
    const url = new URL(req.url);

    // Klick auf den Bestaetigungslink: Kontakt in die Liste eintragen.
    if (req.method === "GET" && url.pathname === "/bestaetigen") {
      const mail = await pruefe(env, url.searchParams.get("t"));
      if (!mail) return seite("Link ungültig oder abgelaufen", "Bitte melde dich auf der Seite noch einmal zum Newsletter an.");
      const r = await fetch("https://api.brevo.com/v3/contacts", {
        method: "POST",
        headers: { "api-key": env.BREVO_API_KEY, "Content-Type": "application/json", "Accept": "application/json" },
        body: JSON.stringify({ email: mail, listIds: [Number(env.BREVO_LIST_ID)], updateEnabled: true }),
      });
      if (!r.ok && r.status !== 204) return seite("Das hat leider nicht geklappt", "Bitte versuche es später noch einmal.");
      return Response.redirect(env.BREVO_REDIRECT_URL, 302);
    }

    if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: cors(req) });
    if (req.method !== "POST" || url.pathname !== "/anmelden") return antwort(req, 404, { fehler: "nicht gefunden" });
    const origin = req.headers.get("Origin") || "";
    if (!ERLAUBT.includes(origin)) return antwort(req, 403, { fehler: "nicht erlaubt" });

    let d;
    try { d = await req.json(); } catch (e) { return antwort(req, 400, { fehler: "ungueltige Anfrage" }); }
    if (d.website) return antwort(req, 200, { ok: true });   // Honigtopf: Bots
    const mail = String(d.email || "").trim().toLowerCase();
    if (mail.length > 200 || !/^[^\s@<>"]+@[^\s@<>"]+\.[^\s@<>"]{2,}$/.test(mail)) return antwort(req, 400, { fehler: "Bitte eine gueltige E-Mail-Adresse eingeben." });
    if (d.einwilligung !== true) return antwort(req, 400, { fehler: "Bitte die Einwilligung bestaetigen." });

    // Bremse je Besucher (pro Worker-Instanz): hoechstens 5 Anmeldungen je 10 Minuten.
    const ip = req.headers.get("CF-Connecting-IP") || "?";
    globalThis.__rate = globalThis.__rate || new Map();
    const jetzt = Date.now(), liste = (globalThis.__rate.get(ip) || []).filter(t => jetzt - t < 600000);
    if (liste.length >= 5) return antwort(req, 429, { fehler: "Zu viele Versuche. Bitte spaeter erneut probieren." });
    liste.push(jetzt); globalThis.__rate.set(ip, liste);

    if (!env.BREVO_API_KEY || !Number(env.BREVO_LIST_ID)) return antwort(req, 500, { fehler: "Newsletter ist noch nicht eingerichtet." });

    const link = url.origin + "/bestaetigen?t=" + await token(env, mail);
    const r = await fetch("https://api.brevo.com/v3/smtp/email", {
      method: "POST",
      headers: { "api-key": env.BREVO_API_KEY, "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify({
        sender: { name: "Dividenden-Rechner.de", email: env.ABSENDER_MAIL },
        to: [{ email: mail }],
        subject: "Bitte bestätige deine Newsletter-Anmeldung",
        htmlContent: mailHtml(link),
      }),
    });
    if (r.ok) return antwort(req, 200, { ok: true });
    const t = await r.text();
    return antwort(req, 502, { fehler: "Anmeldung gerade nicht moeglich. Bitte spaeter erneut versuchen. [Brevo " + r.status + ": " + t.slice(0, 200) + "]" }); // TEMPORAER: Fehlerdetail zur Diagnose
  },
};
