// Cloudflare Worker: Freigabe von Entwuerfen per Knopfdruck (Push-Meldung ueber ntfy).
// Die Meldung enthaelt signierte Links. Der Worker prueft die Signatur und aendert dann die Artikeldatei im
// GitHub-Repository: "Freigeben" entfernt die Zeile "draft: true", "Verwerfen" loescht die Datei.
// Secrets: APPROVE_SECRET (Signaturschluessel), GH_TOKEN (GitHub-Zugriffstoken mit Schreibrecht auf Inhalte).
const enc = new TextEncoder(), dec = new TextDecoder();
const hex = b => [...new Uint8Array(b)].map(x => x.toString(16).padStart(2, "0")).join("");

async function sign(secret, text) {
  const k = await crypto.subtle.importKey("raw", enc.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  return hex(await crypto.subtle.sign("HMAC", k, enc.encode(text)));
}
function same(a, b) {
  if (a.length !== b.length) return false;
  let d = 0; for (let i = 0; i < a.length; i++) d |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return d === 0;
}
const b64e = s => { let bin = ""; for (const x of enc.encode(s)) bin += String.fromCharCode(x); return btoa(bin); };
const b64d = s => { const bin = atob(s.replace(/\s/g, "")); return dec.decode(Uint8Array.from(bin, c => c.charCodeAt(0))); };
const page = (titel, text, extra = "", status = 200) => new Response(
  `<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${titel}</title>
<style>body{font:18px/1.5 system-ui,sans-serif;max-width:560px;margin:12vh auto;padding:0 20px;color:#14202b}button{font:inherit;font-weight:700;padding:14px 28px;border:0;border-radius:10px;background:#1a7a45;color:#fff;width:100%}
button.r{background:#b3372d}small{color:#6a7783}</style></head><body><h1>${titel}</h1><p>${text}</p>${extra}</body></html>`,
  { status, headers: { "content-type": "text/html; charset=utf-8", "cache-control": "no-store" } });

async function gh(env, method, path, body) {
  const r = await fetch(`https://api.github.com/repos/${env.REPO}/${path}`, {
    method, headers: { "Authorization": `Bearer ${env.GH_TOKEN}`, "Accept": "application/vnd.github+json", "User-Agent": "freigabe-worker", "X-GitHub-Api-Version": "2022-11-28" },
    body: body ? JSON.stringify(body) : undefined });
  const t = await r.text(); let j = {}; try { j = JSON.parse(t); } catch (e) {}
  return { ok: r.ok, status: r.status, j };
}

export default {
  async fetch(req, env) {
    const u = new URL(req.url);
    const a = u.searchParams.get("a"), f = u.searchParams.get("f") || "", t = u.searchParams.get("t") || "";
    if (u.pathname !== "/" || !a) return page("Freigabe", "Dieser Dienst gibt Entwürfe frei. Er wird über die Push-Meldung bedient.");
    if (!env.APPROVE_SECRET || !env.GH_TOKEN) return page("Nicht eingerichtet", "Es fehlen Secrets im Worker.", "", 500);
    if (!["approve", "reject"].includes(a) || !/^[0-9a-z][0-9a-z\-]{3,160}\.md$/.test(f)) return page("Ungültig", "Die Anfrage ist nicht gültig.", "", 400);
    if (!same(await sign(env.APPROVE_SECRET, `${a}:${f}`), t)) return page("Ungültiger Link", "Die Signatur stimmt nicht.", "", 403);
    const verb = a === "approve" ? "freigeben" : "verwerfen";
    if (req.method === "GET") {   // Bestaetigungsseite: ein Tipp auf den Knopf fuehrt die Aktion aus
      return page(`Entwurf ${verb}?`, f.replace(/^\d{4}-\d{2}-\d{2}-\d{4}-/, "").replace(/\.md$/, "").replace(/-/g, " "),
        `<form method="post" action="${u.pathname}${u.search.replace(/&/g, "&amp;")}"><button class="${a === "reject" ? "r" : ""}">${verb[0].toUpperCase() + verb.slice(1)}</button></form>`);
    }
    if (req.method !== "POST") return page("Nicht erlaubt", "", "", 405);
    const path = `contents/content/magazin/${f}`;
    const cur = await gh(env, "GET", `${path}?ref=${env.BRANCH}`);
    if (!cur.ok) return page("Nicht gefunden", cur.status === 404 ? "Die Datei gibt es nicht mehr (schon verworfen?)." : `GitHub-Fehler ${cur.status}.`, "", 404);
    if (a === "reject") {
      const d = await gh(env, "DELETE", path, { message: `Entwurf verworfen: ${f}`, sha: cur.j.sha, branch: env.BRANCH });
      return d.ok ? page("Verworfen", "Der Entwurf wurde gelöscht.") : page("Fehler", `GitHub-Fehler ${d.status}.`, "", 502);
    }
    const text = b64d(cur.j.content);
    const neu = text.replace(/^draft:[ \t]*(true|ja|1|yes)[ \t]*\r?\n/mi, "");
    if (neu === text) return page("Schon online", "Dieser Artikel war bereits freigegeben.");
    const p = await gh(env, "PUT", path, { message: `Freigabe: ${f}`, content: b64e(neu), sha: cur.j.sha, branch: env.BRANCH });
    return p.ok ? page("Freigegeben", "Der Artikel geht in etwa einer Minute online.") : page("Fehler", `GitHub-Fehler ${p.status}.`, "", 502);
  },
};
