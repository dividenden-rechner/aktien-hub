// Cloudflare Worker: Zwischenserver fuer die FMP-Daten.
// Der API-Schluessel liegt hier als Secret (FMP_API_KEY) und kommt nie in den Browser.
// Antworten werden zwischengespeichert, damit viele Besucher nicht das Tageslimit aufbrauchen.
const ERLAUBT = ["https://dividenden-rechner.github.io", "https://www.dividenden-rechner.de", "https://dividenden-rechner.de"];
const BASIS = "https://financialmodelingprep.com/stable/";
// Nur diese Endpunkte werden durchgereicht (Gratis-Datenabrufe, die die Seiten brauchen).
const PFADE = new Set([
  "profile", "quote", "quote-short", "ratios-ttm", "ratios", "key-metrics-ttm", "key-metrics", "financial-growth",
  "discounted-cash-flow", "price-target-consensus", "price-target-summary", "income-statement", "cash-flow-statement",
  "balance-sheet-statement", "dividends", "dividends-calendar", "historical-price-eod/light", "historical-price-eod/full",
  "grades-consensus", "grades", "analyst-estimates", "search-name", "search-symbol", "search-isin", "earnings",
  "earnings-calendar", "company-screener", "stock-peers", "enterprise-values", "financial-scores", "owner-earnings",
  "historical-market-cap", "ratings-snapshot",
]);
// Wie lange eine Antwort gemerkt wird (Sekunden).
function ttl(pfad) {
  if (/^(quote|quote-short)$/.test(pfad)) return 900;                       // Kurse: 15 Minuten
  if (/^(earnings-calendar|dividends-calendar|company-screener|earnings)$/.test(pfad)) return 3600;
  if (/^historical-price/.test(pfad)) return 6 * 3600;
  return 12 * 3600;                                                          // Berichte und Kennzahlen: 12 Stunden
}
const MAX_PRO_MINUTE = 40;   // neue (nicht gemerkte) Abrufe pro Besucher und Minute

export default {
  async fetch(req, env, ctx) {
    const o = req.headers.get("Origin") || "";
    const ok = ERLAUBT.includes(o) || /^http:\/\/localhost(:\d+)?$/.test(o);
    const cors = {
      "Access-Control-Allow-Origin": ok ? o : ERLAUBT[0], "Vary": "Origin",
      "Access-Control-Expose-Headers": "x-fmp-cache",
    };
    if (req.method === "OPTIONS") return new Response(null, { headers: { ...cors, "Access-Control-Allow-Methods": "GET", "Access-Control-Max-Age": "86400" } });
    if (req.method !== "GET") return new Response("method not allowed", { status: 405, headers: cors });
    if (!ok) return new Response("forbidden", { status: 403, headers: cors });
    if (!env.FMP_API_KEY) return new Response(JSON.stringify({ "Error Message": "Server nicht eingerichtet (FMP_API_KEY fehlt)" }), { status: 503, headers: { ...cors, "Content-Type": "application/json" } });

    const u = new URL(req.url), pfad = u.pathname.replace(/^\/+/, "");
    if (!PFADE.has(pfad)) return new Response(JSON.stringify({ "Error Message": "Endpunkt nicht freigegeben" }), { status: 403, headers: { ...cors, "Content-Type": "application/json" } });

    // Schluessel des Besuchers (falls mitgeschickt) wird nie weitergegeben
    const p = new URLSearchParams(u.search); p.delete("apikey");
    p.sort();
    const cacheKey = new Request("https://cache.fmp-proxy.internal/" + pfad + "?" + p.toString());
    const cache = caches.default;
    const hit = await cache.match(cacheKey);
    if (hit) {
      const r = new Response(hit.body, hit);
      Object.entries(cors).forEach(([k, v]) => r.headers.set(k, v));
      r.headers.set("x-fmp-cache", "HIT");
      return r;
    }

    // einfache Begrenzung pro Besucher (nur fuer neue Abrufe)
    const ip = req.headers.get("CF-Connecting-IP") || "x", minute = Math.floor(Date.now() / 60000);
    const rlKey = new Request("https://cache.fmp-proxy.internal/rl/" + encodeURIComponent(ip) + "/" + minute);
    const rl = await cache.match(rlKey);
    const n = rl ? parseInt(await rl.text(), 10) || 0 : 0;
    if (n >= MAX_PRO_MINUTE) return new Response(JSON.stringify({ "Error Message": "Zu viele Abrufe, bitte kurz warten." }), { status: 429, headers: { ...cors, "Content-Type": "application/json", "Retry-After": "60" } });
    ctx.waitUntil(cache.put(rlKey, new Response(String(n + 1), { headers: { "Cache-Control": "max-age=90" } })));

    p.set("apikey", env.FMP_API_KEY);
    let up;
    try { up = await fetch(BASIS + pfad + "?" + p.toString(), { headers: { "User-Agent": "dividenden-rechner-proxy" } }); }
    catch (e) { return new Response(JSON.stringify({ "Error Message": "FMP nicht erreichbar" }), { status: 502, headers: { ...cors, "Content-Type": "application/json" } }); }

    const body = await up.text();
    const heads = { ...cors, "Content-Type": up.headers.get("Content-Type") || "application/json", "x-fmp-cache": "MISS" };
    let maxAge = 0;
    if (up.status === 200 && body.length > 2 && !/"Error Message"/.test(body.slice(0, 200))) maxAge = ttl(pfad);
    else if (up.status === 402 || up.status === 403) maxAge = 3600;   // nicht im Tarif: nicht jedes Mal neu fragen
    heads["Cache-Control"] = maxAge ? "public, max-age=" + maxAge : "no-store";
    const resp = new Response(body, { status: up.status, headers: heads });
    if (maxAge) ctx.waitUntil(cache.put(cacheKey, resp.clone()));
    return resp;
  },
};
