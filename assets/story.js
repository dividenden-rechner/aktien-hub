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
  function light(img) {
    try { var k = document.createElement("canvas"); k.width = k.height = 40; var x = k.getContext("2d"); x.drawImage(img, 0, 0, 40, 40); var d = x.getImageData(0, 0, 40, 40).data, n = 0, t = 0;
      for (var i = 0; i < d.length; i += 4) { if (d[i + 3] < 40) continue; n++; t += 0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2]; }
      return n > 20 && t / n > 190; } catch (e) { return false; }
  }
  function rr(c, x, y, w, h, r) { c.beginPath(); if (c.roundRect) c.roundRect(x, y, w, h, r); else c.rect(x, y, w, h); }
  /* S: {tpl, title, cat, ct, lines:[], points:[], text, img, logo} */
  async function draw(S, withPhoto) {
    var W = 1080, H = 1920, cv = document.createElement("canvas"); cv.width = W; cv.height = H; var c = cv.getContext("2d");
    var tpl = await load(S.tpl), photo = withPhoto ? await load(S.img) : null, logo = await load(S.logo);
    if (tpl) c.drawImage(tpl, 0, 0, W, H); else { c.fillStyle = "#fff"; c.fillRect(0, 0, W, H); c.fillStyle = "#99e6b1"; c.fillRect(0, 108, W, 86); c.fillRect(0, 1866, W, 54); }
    var F = 'InterS,Inter,"Segoe UI",Roboto,Helvetica,Arial,sans-serif', LIM = 1835, G = "#1a7a45", D = "#14202b";
    c.textBaseline = "top";
    var pts = S.points || [], lns = S.lines || [], ph = photo ? 470 : 0, fs = 35;
    /* Layout messen; passt der Text nicht, erst Foto verkleinern, dann Schrift (min. 26 px). Nie abschneiden. */
    function layout(draw, ph, fs) {
      var y = 232, lh = Math.round(fs * 1.32);
      if (photo) {
        var r = Math.max(960 / photo.width, ph / photo.height), w = photo.width * r, h = photo.height * r;
        if (draw) { c.save(); rr(c, 60, y, 960, ph, 28); c.clip(); c.drawImage(photo, 60 + (960 - w) / 2, y + (ph - h) / 2, w, h); c.restore(); }
        y += ph + 30;
      }
      /* Logo wie auf den Uebersichtsseiten: Plakette oben links im Foto. Rubrik steht schon in der Vorlage. */
      var sz = 132, tag = S.ct || "";
      function plaque(px, py) {
        c.save(); c.shadowColor = "rgba(0,0,0,.28)"; c.shadowBlur = 20; c.shadowOffsetY = 5; c.fillStyle = light(logo) ? "#14202b" : "#fff"; rr(c, px, py, sz, sz, 28); c.fill(); c.restore();
        var q = Math.min((sz - 34) / logo.width, (sz - 34) / logo.height); c.drawImage(logo, px + (sz - logo.width * q) / 2, py + (sz - logo.height * q) / 2, logo.width * q, logo.height * q);
      }
      function pill(px, py) {
        c.font = "700 34px " + F; var w = c.measureText(tag).width + 40; c.fillStyle = "rgba(20,32,43,.82)"; rr(c, px, py, w, 56, 28); c.fill(); c.fillStyle = "#fff"; c.fillText(tag, px + 20, py + 11);
      }
      if (photo) {
        if (draw && logo) plaque(60 + 24, 232 + 24);
        if (draw && tag) pill(60 + 24, 232 + ph - 80);
      } else if (logo || tag) {
        if (draw && logo) plaque(60, y);
        if (draw && tag) { c.fillStyle = G; c.font = "700 40px " + F; c.fillText(tag, logo ? 60 + sz + 28 : 60, y + (logo ? sz / 2 - 20 : 0)); }
        y += (logo ? sz : 44) + 26;
      }
      if (S.title) { c.font = "700 " + (fs + 25) + "px " + F; c.fillStyle = D; wrap(c, S.title, 960, 5).forEach(function (l) { if (draw) c.fillText(l, 60, y); y += Math.round((fs + 25) * 1.2); }); y += 16; }
      lns.forEach(function (l) {
        var i = l.indexOf(":"), k = i > 0 ? l.slice(0, i + 1) : "", v = i > 0 ? l.slice(i + 1).trim() : l;
        c.font = "700 " + (fs + 7) + "px " + F; var kw = c.measureText(k + " ").width; c.font = "700 " + (fs + 17) + "px " + F; var ls = wrap(c, v, 960 - kw, 2);
        if (draw) { c.fillStyle = G; c.font = "700 " + (fs + 7) + "px " + F; c.fillText(k, 60, y + 6); c.fillStyle = D; c.font = "700 " + (fs + 17) + "px " + F; ls.forEach(function (t, n) { c.fillText(t, 60 + kw, y + n * (fs + 27)); }); }
        y += ls.length * (fs + 27) + 14;
      });
      if (lns.length) y += 10;
      pts.forEach(function (t, n) {
        c.font = "400 " + fs + "px " + F; var ls = wrap(c, t, 880, 0);
        if (draw) { c.fillStyle = G; c.font = "700 " + (fs + 1) + "px " + F; c.fillText(String(n + 1) + ".", 60, y); c.fillStyle = "#33414d"; c.font = "400 " + fs + "px " + F; ls.forEach(function (l, m) { c.fillText(l, 118, y + m * lh); }); }
        y += ls.length * lh + 16;
      });
      if (S.text) { c.font = "400 " + (fs + 2) + "px " + F; String(S.text).split(/\n+/).forEach(function (p) { wrap(c, p, 960, 0).forEach(function () { y += Math.round((fs + 2) * 1.35); }); y += 14; }); }
      return y;
    }
    while (photo && ph > 300 && layout(false, ph, fs) > LIM) ph -= 30;
    while (fs > 26 && layout(false, ph, fs) > LIM) fs -= 1;
    while (photo && ph > 200 && layout(false, ph, fs) > LIM) ph -= 20;
    while (photo && ph < 620 && layout(false, ph + 20, fs) <= LIM - 20) ph += 20;
    var yy = layout(true, ph, fs);
    if (S.text) {
      var lh2 = Math.round((fs + 2) * 1.35); c.fillStyle = "#33414d"; c.font = "400 " + (fs + 2) + "px " + F;
      yy -= String(S.text).split(/\n+/).reduce(function (a, p) { return a + wrap(c, p, 960, 0).length * lh2 + 14; }, 0);
      String(S.text).split(/\n+/).forEach(function (p) { wrap(c, p, 960, 0).forEach(function (l) { c.fillText(l, 60, yy); yy += lh2; }); yy += 14; });
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
