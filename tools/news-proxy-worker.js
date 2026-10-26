// Cloudflare Worker: holt Google-News-Treffer fuer eine Suche und liefert sie als JSON (mit CORS nur fuer deine Seiten).
const ERLAUBT = ["https://dividenden-rechner.github.io", "https://www.dividenden-rechner.de", "https://dividenden-rechner.de"];
const dec = s => s.replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, "$1").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&#39;|&apos;/g, "'").replace(/&amp;/g, "&").trim();
const tg = (b, t) => { const m = b.match(new RegExp("<" + t + "(?:\\s[^>]*)?>([\\s\\S]*?)</" + t + ">")); return m ? dec(m[1]) : ""; };
const json = (o, st, h) => new Response(JSON.stringify(o), { status: st || 200, headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "public, max-age=900", ...h } });
export default {
  async fetch(req) {
    const o = req.headers.get("Origin") || "";
    const ok = ERLAUBT.includes(o) || /^http:\/\/localhost(:\d+)?$/.test(o);
    const cors = { "Access-Control-Allow-Origin": ok ? o : ERLAUBT[0], "Vary": "Origin" };
    if (req.method === "OPTIONS") return new Response(null, { headers: { ...cors, "Access-Control-Allow-Methods": "GET", "Access-Control-Max-Age": "86400" } });
    if (!ok) return new Response("forbidden", { status: 403, headers: cors });
    const u = new URL(req.url), q = (u.searchParams.get("q") || "").trim().slice(0, 100), en = u.searchParams.get("lang") === "en";
    if (q.length < 2) return json({ error: "q fehlt" }, 400, cors);
    const feed = "https://news.google.com/rss/search?q=" + encodeURIComponent(q) + (en ? "&hl=en-US&gl=US&ceid=US:en" : "&hl=de&gl=DE&ceid=DE:de");
    let r;
    try { r = await fetch(feed, { headers: { "User-Agent": "Mozilla/5.0 (compatible; news-proxy)" }, cf: { cacheTtl: 900, cacheEverything: true } }); } catch (e) { return json({ error: "Quelle nicht erreichbar" }, 502, cors); }
    if (!r.ok) return json({ error: "Quelle antwortet mit " + r.status }, 502, cors);
    const xml = await r.text(), items = [];
    for (const b of xml.split("<item>").slice(1)) {
      let title = tg(b, "title"); const src = tg(b, "source"), link = tg(b, "link"), d = tg(b, "pubDate");
      if (src && title.endsWith(" - " + src)) title = title.slice(0, -(src.length + 3));
      if (title && link) items.push({ title, source: src, link, date: d ? new Date(d).toISOString() : null });
      if (items.length >= 10) break;
    }
    return json({ q, items }, 200, cors);
  }
};
