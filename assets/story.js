/* Story-Bild (1080x1920) auf den Vorlagen aus assets/story-vorlagen. Wird von den Artikelseiten (Teilen) und der Werkstatt genutzt. */
(function () {
  var base = (document.currentScript && document.currentScript.src || "").replace(/story\.js.*$/, "");
  var fontsReady = null;
  function fonts() {
    if (fontsReady) return fontsReady;
    fontsReady = Promise.all([["400", "Inter-Regular.otf"], ["700", "Inter-Bold.otf"]].map(function (f) {
      try { var ff = new FontFace("InterS", "url(" + base + "fonts/" + f[1] + ")", { weight: f[0] }); return ff.load().then(function (x) { document.fonts.add(x); }); } catch (e) { return Promise.resolve(); }
    })).catch(function () {});
    return fontsReady;
  }
  function load(u) {
    return new Promise(function (res) { if (!u) return res(null); var i = new Image(); i.crossOrigin = "anonymous"; i.onload = function () { res(i); }; i.onerror = function () { res(null); }; i.src = u; });
  }
  function wrap(c, t, w, max) {
    var out = [], cur = "";
    String(t || "").split(/\s+/).forEach(function (x) { if (!x) return; var y = cur ? cur + " " + x : x; if (c.measureText(y).width <= w) cur = y; else { out.push(cur); cur = x; } });
    if (cur) out.push(cur);
    if (max && out.length > max) { out = out.slice(0, max); out[max - 1] = out[max - 1].replace(/\s+\S*$/, "") + " …"; }
    return out;
  }
  function rr(c, x, y, w, h, r) { c.beginPath(); if (c.roundRect) c.roundRect(x, y, w, h, r); else c.rect(x, y, w, h); }
  /* S: {tpl, title, cat, ct, lines:[], points:[], text, img, logo} */
  async function draw(S, withPhoto) {
    var W = 1080, H = 1920, cv = document.createElement("canvas"); cv.width = W; cv.height = H; var c = cv.getContext("2d");
    var tpl = await load(S.tpl), photo = withPhoto ? await load(S.img) : null, logo = await load(S.logo);
    if (tpl) c.drawImage(tpl, 0, 0, W, H); else { c.fillStyle = "#fff"; c.fillRect(0, 0, W, H); c.fillStyle = "#99e6b1"; c.fillRect(0, 108, W, 86); c.fillRect(0, 1866, W, 54); }
    var F = 'InterS,Inter,"Segoe UI",Roboto,Helvetica,Arial,sans-serif', LIM = 1835, y = 232, G = "#1a7a45", D = "#14202b";
    c.textBaseline = "top";
    if (photo) {
      var ph = 470, r = Math.max(960 / photo.width, ph / photo.height), w = photo.width * r, h = photo.height * r;
      c.save(); rr(c, 60, y, 960, ph, 28); c.clip(); c.drawImage(photo, 60 + (960 - w) / 2, y + (ph - h) / 2, w, h); c.restore(); y += ph + 34;
    }
    var hasHead = logo || S.cat || S.ct;
    if (logo) {
      c.save(); c.shadowColor = "rgba(0,0,0,.14)"; c.shadowBlur = 14; c.shadowOffsetY = 4; c.fillStyle = "#fff"; rr(c, 60, y, 128, 128, 28); c.fill(); c.restore();
      c.strokeStyle = "#dbe5ec"; c.lineWidth = 2; rr(c, 60, y, 128, 128, 28); c.stroke();
      var s = Math.min(92 / logo.width, 92 / logo.height); c.drawImage(logo, 60 + (128 - logo.width * s) / 2, y + (128 - logo.height * s) / 2, logo.width * s, logo.height * s);
    }
    if (S.cat || S.ct) { c.fillStyle = G; c.font = "700 34px " + F; c.fillText(((S.cat || "") + (S.ct ? (S.cat ? "  ·  " : "") + S.ct : "")).toUpperCase(), logo ? 216 : 60, logo ? y + 46 : y); }
    if (hasHead) y += logo ? 128 + 30 : 52;
    if (S.title) { c.fillStyle = D; c.font = "700 62px " + F; wrap(c, S.title, 960, 5).forEach(function (l) { c.fillText(l, 60, y); y += 76; }); y += 22; }
    (S.lines || []).forEach(function (l) {
      if (y > LIM - 70) return; var i = l.indexOf(":"), k = i > 0 ? l.slice(0, i + 1) : "", v = i > 0 ? l.slice(i + 1).trim() : l;
      c.fillStyle = G; c.font = "700 44px " + F; c.fillText(k, 60, y + 6); var kw = c.measureText(k + " ").width;
      c.fillStyle = D; c.font = "700 54px " + F; var ls = wrap(c, v, 960 - kw, 2); ls.forEach(function (t, n) { c.fillText(t, 60 + kw, y + n * 62); }); y += ls.length * 62 + 22;
    });
    var stop = false; if ((S.lines || []).length) y += 8;
    (S.points || []).forEach(function (t, n) {
      if (stop) return; c.font = "400 35px " + F; var ls = wrap(c, t, 870, 3); if (y + ls.length * 46 > LIM) { stop = true; return; }
      c.fillStyle = G; c.font = "700 36px " + F; c.fillText(String(n + 1) + ".", 60, y); c.fillStyle = "#33414d"; c.font = "400 35px " + F;
      ls.forEach(function (l) { c.fillText(l, 118, y); y += 46; }); y += 20;
    });
    if (S.text) {
      c.fillStyle = "#33414d"; c.font = "400 38px " + F;
      String(S.text).split(/\n+/).forEach(function (p) { wrap(c, p, 960, 0).forEach(function (l) { if (y + 52 <= LIM) { c.fillText(l, 60, y); y += 52; } }); y += 20; });
    }
    return new Promise(function (res) { cv.toBlob(res, "image/png"); });
  }
  window.StoryRender = async function (S) {
    await fonts(); var bl = null;
    try { bl = await draw(S, true); } catch (e) { bl = null; }
    if (!bl) { try { bl = await draw(S, false); } catch (e) {} }
    return bl;
  };
  window.StoryShare = async function (S, msgEl) {
    var m = msgEl; if (m) m.textContent = "Story-Bild wird erstellt …";
    var bl = await window.StoryRender(S); if (!bl) { if (m) m.textContent = "Das Story-Bild konnte nicht erstellt werden."; return; }
    var f = new File([bl], "story.png", { type: "image/png" }); if (m) m.textContent = "";
    try { if (navigator.canShare && navigator.canShare({ files: [f] })) { await navigator.share({ files: [f] }); return; } } catch (e) { if (e && e.name === "AbortError") return; }
    var a = document.createElement("a"); a.href = URL.createObjectURL(bl); a.download = "story.png"; document.body.appendChild(a); a.click(); a.remove();
    if (m) m.textContent = "Bild gespeichert. In Instagram: Story → Bild aus der Galerie wählen.";
  };
})();
