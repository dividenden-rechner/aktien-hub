// Cloudflare Worker: Newsletter-Anmeldung (Double-Opt-in ueber Brevo).
// Der Brevo-Schluessel liegt hier als Secret (BREVO_API_KEY) und kommt nie in den Browser.
// Listen-ID, Vorlagen-ID und Weiterleitungsseite stehen in wrangler.toml (keine Geheimnisse).
const ERLAUBT = ["https://dividenden-rechner.github.io", "https://www.dividenden-rechner.de", "https://dividenden-rechner.de"];

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

export default {
  async fetch(req, env) {
    if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: cors(req) });
    const url = new URL(req.url);
    if (req.method !== "POST" || url.pathname !== "/anmelden") return antwort(req, 404, { fehler: "nicht gefunden" });
    const origin = req.headers.get("Origin") || "";
    if (!ERLAUBT.includes(origin)) return antwort(req, 403, { fehler: "nicht erlaubt" });

    let d;
    try { d = await req.json(); } catch (e) { return antwort(req, 400, { fehler: "ungueltige Anfrage" }); }
    // Honigtopf: Bots fuellen das versteckte Feld aus. Dann tun wir so, als waere alles gut.
    if (d.website) return antwort(req, 200, { ok: true });
    const mail = String(d.email || "").trim().toLowerCase();
    if (mail.length > 200 || !/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(mail)) return antwort(req, 400, { fehler: "Bitte eine gueltige E-Mail-Adresse eingeben." });
    if (d.einwilligung !== true) return antwort(req, 400, { fehler: "Bitte die Einwilligung bestaetigen." });

    // Einfache Bremse je Besucher (pro Worker-Instanz): hoechstens 5 Anmeldungen je 10 Minuten.
    const ip = req.headers.get("CF-Connecting-IP") || "?";
    globalThis.__rate = globalThis.__rate || new Map();
    const jetzt = Date.now(), liste = (globalThis.__rate.get(ip) || []).filter(t => jetzt - t < 600000);
    if (liste.length >= 5) return antwort(req, 429, { fehler: "Zu viele Versuche. Bitte spaeter erneut probieren." });
    liste.push(jetzt); globalThis.__rate.set(ip, liste);

    const listeId = Number(env.BREVO_LIST_ID), vorlageId = Number(env.BREVO_DOI_TEMPLATE_ID);
    if (!env.BREVO_API_KEY || !listeId || !vorlageId) return antwort(req, 500, { fehler: "Newsletter ist noch nicht eingerichtet." });

    const r = await fetch("https://api.brevo.com/v3/contacts/doubleOptinConfirmation", {
      method: "POST",
      headers: { "api-key": env.BREVO_API_KEY, "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify({
        email: mail,
        includeListIds: [listeId],
        templateId: vorlageId,
        redirectionUrl: env.BREVO_REDIRECT_URL,
      }),
    });
    // 201/204 = Bestaetigungsmail verschickt. Bei bekannter Adresse meldet Brevo 400 "duplicate": nach aussen gleich behandeln.
    if (r.ok) return antwort(req, 200, { ok: true });
    const t = await r.text();
    if (/duplicate|already/i.test(t)) return antwort(req, 200, { ok: true });
    return antwort(req, 502, { fehler: "Anmeldung gerade nicht moeglich. Bitte spaeter erneut versuchen. [Brevo " + r.status + ": " + t.slice(0, 200) + "]" }); // TEMPORAER: Fehlerdetail zur Diagnose
  },
};
