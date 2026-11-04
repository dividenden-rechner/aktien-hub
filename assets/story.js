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
    String(t || "").replace(/\u202f/g, "\u00a0").split(/[ \t\r\n]+/).forEach(function (x) { if (!x) return; var y = cur ? cur + " " + x : x; if (c.measureText(y).width <= w) cur = y; else { out.push(cur); cur = x; } });
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
    /* Eigene Vorlage (gruene Balken mit Rubrik und Adresse); der Inhalt darin bleibt schlicht: weisser Grund, schwarze Schrift, keine Farbflaechen. */
    if (tpl) c.drawImage(tpl, 0, 0, W, H); else { c.fillStyle = "#fff"; c.fillRect(0, 0, W, H); c.fillStyle = "#99e6b1"; c.fillRect(0, 108, W, 86); c.fillRect(0, 1866, W, 54); }
    var F = 'InterS,Inter,"Segoe UI",Roboto,Helvetica,Arial,sans-serif', LIM = 1835 - ((S.chart && S.portrait) ? 560 : (S.chart ? 600 : (S.portrait ? 470 : 0))), G = "#111", D = "#111";
    c.textBaseline = "top";
    var pts = S.para ? [] : (S.points || []), lns = S.lines || [], ph = photo ? 470 : 0, fs = 30, fit = !!(photo && S.fit === "contain");
    if (fit) ph = Math.round(960 * photo.height / photo.width);
    /* Layout messen; passt der Text nicht, erst Foto verkleinern, dann Schrift (min. 26 px). Nie abschneiden. */
    function layout(draw, ph, fs) {
      var y = 232, lh = Math.round(fs * 1.32);
      function drawPhoto() {
        var r = fit ? Math.min(960 / photo.width, ph / photo.height) : Math.max(960 / photo.width, ph / photo.height), w = photo.width * r, h = photo.height * r;
        if (draw) { c.save(); rr(c, 60, y, 960, ph, 28); c.clip(); c.drawImage(photo, 60 + (960 - w) / 2, y + (ph - h) / 2, w, h); c.restore(); }
        y += ph + (fit ? 52 : 30);
      }
      if (photo && !fit) drawPhoto();
      /* Logo wie auf den Uebersichtsseiten: Plakette oben links im Foto. Rubrik steht schon in der Vorlage. */
      var sz = 132, tag = tpl ? "" : (S.ct || "");
      function plaque(px, py) {
        c.save(); c.shadowColor = "rgba(0,0,0,.28)"; c.shadowBlur = 20; c.shadowOffsetY = 5; c.fillStyle = light(logo) ? "#14202b" : "#fff"; rr(c, px, py, sz, sz, 28); c.fill(); c.restore();
        var q = Math.min((sz - 34) / logo.width, (sz - 34) / logo.height); c.drawImage(logo, px + (sz - logo.width * q) / 2, py + (sz - logo.height * q) / 2, logo.width * q, logo.height * q);
      }
      function pill(px, py) {
        c.font = "700 34px " + F; var w = c.measureText(tag).width + 40; c.fillStyle = "rgba(0,0,0,.72)"; rr(c, px, py, w, 56, 28); c.fill(); c.fillStyle = "#fff"; c.fillText(tag, px + 20, py + 11);
      }
      if ((photo && fit) || S.para) {
        /* Folie/Grafik: Logo und Kennung ueber dem Bild, damit nichts davon verdeckt wird */
        sz = S.para ? 150 : 104;
        var lw = sz;
        if (S.para && logo && S.logo_bg) {
          /* Logo auf farbiger Platte (z. B. weisse Schrift): sichtbaren Bereich ausschneiden und auf die Platte setzen */
          var bb = (function () { try { var k = document.createElement("canvas"); k.width = logo.width; k.height = logo.height; var x = k.getContext("2d"); x.drawImage(logo, 0, 0); var d = x.getImageData(0, 0, k.width, k.height).data, x0 = k.width, y0 = k.height, x1 = 0, y1 = 0;
            for (var yy = 0; yy < k.height; yy++) for (var xx = 0; xx < k.width; xx++) if (d[(yy * k.width + xx) * 4 + 3] > 40) { if (xx < x0) x0 = xx; if (xx > x1) x1 = xx; if (yy < y0) y0 = yy; if (yy > y1) y1 = yy; }
            return x1 > x0 ? { x: x0, y: y0, w: x1 - x0 + 1, h: y1 - y0 + 1 } : null; } catch (e) { return null; } })() || { x: 0, y: 0, w: logo.width, h: logo.height };
          var pw = 290, pad = 22, q2 = (pw - 2 * pad) / bb.w, plh = Math.round(bb.h * q2 + 2 * pad);
          lw = pw;
          if (draw) { var py2 = y + (sz - plh) / 2; c.fillStyle = S.logo_bg; rr(c, 60, py2, pw, plh, 18); c.fill(); c.drawImage(logo, bb.x, bb.y, bb.w, bb.h, 60 + pad, py2 + pad, bb.w * q2, bb.h * q2); }
        } else if (S.para && logo && !light(logo)) { lw = Math.min(260, logo.width * sz / logo.height); if (draw) c.drawImage(logo, 60, y, lw, logo.height * lw / logo.width); }
        else if (draw && logo) plaque(60, y);
        if (draw && tag) { c.fillStyle = G; c.font = "700 40px " + F; c.fillText(tag, logo ? 60 + sz + 24 : 60, y + (logo ? sz / 2 - 20 : 0)); }
        /* Kennzahlen (Umsatz, Gewinn) rechts neben dem Logo */
        var hl = (S.lines || []).slice(0, 2).map(function (t) { return t.replace(/\s*\((?:\u2014|\u2013|-)\)\s*$/, ""); });
        if (draw && hl.length) {
          var hx = logo ? 60 + lw + 32 : 60, hf = S.para ? 50 : 38, hh = Math.round(hf * 1.3), hy = y + (sz - hl.length * hh) / 2 + 2;
          /* Schrift verkleinern, bis die laengste Zeile neben das Logo passt */
          hl.forEach(function (t) { var i = t.indexOf(":"), k = i > 0 ? t.slice(0, i + 1) : ""; while (hf > 26) { c.font = "700 " + hf + "px " + F; var kw0 = k ? c.measureText(k + " ").width : 0; c.font = (S.para ? "700 " : "400 ") + hf + "px " + F; if (hx + kw0 + c.measureText(i > 0 ? t.slice(i + 1).trim() : t).width <= 1020) break; hf -= 1; } });
          hh = Math.round(hf * 1.3); hy = y + (sz - hl.length * hh) / 2 + 2;
          hl.forEach(function (t, n) {
            var i = t.indexOf(":"), k = i > 0 ? t.slice(0, i + 1) : "", v = i > 0 ? t.slice(i + 1).trim() : t;
            if (S.para) { c.font = "700 " + hf + "px " + F; c.fillStyle = D; c.textAlign = "right"; c.fillText(t, 1020, hy + n * hh); c.textAlign = "left"; return; }
            c.font = "700 " + hf + "px " + F; c.fillStyle = D; c.fillText(k, hx, hy + n * hh);
            var kw = k ? c.measureText(k + " ").width : 0; c.font = (S.para ? "700 " : "400 ") + hf + "px " + F; c.fillStyle = S.para ? D : "#262626"; c.fillText(v, hx + kw, hy + n * hh);
          });
        }
        if (logo || tag || hl.length) y += ((logo || hl.length) ? sz : 44) + 38;
        drawTitle();
        if (photo) drawPhoto();
      } else if (photo) {
        if (draw && logo) plaque(60 + 24, 232 + 24);
        if (draw && tag) pill(60 + 24, 232 + ph - 80);
      } else if (logo || tag) {
        if (draw && logo) plaque(60, y);
        if (draw && tag) { c.fillStyle = G; c.font = "700 40px " + F; c.fillText(tag, logo ? 60 + sz + 28 : 60, y + (logo ? sz / 2 - 20 : 0)); }
        y += (logo ? sz : 44) + 26;
      }
      function drawTitle() { if (S.title) { c.font = "700 " + (fs + 16) + "px " + F; c.fillStyle = D; wrap(c, S.title, 960, 5).forEach(function (l) { if (draw) c.fillText(l, 60, y); y += Math.round((fs + 16) * 1.2); }); y += (photo && fit) ? 34 : 16; } }
      if (!(photo && fit)) drawTitle();
      if (lns.length || pts.length) {
        /* Kasten "Kurz gesagt" wie im Artikel: heller Untergrund, Kennzahlen mit fettem Stichwort, nummerierte Punkte */
        var bx = 60, bw = 960, ix = 100, iw = 892, by0 = y, tc = "#262626", bare = !!((photo && fit) || S.para); if (bare) { ix = 60; iw = 960; lns = []; }
        function kv(t, x, w, fsz, num, doDraw, yy) {
          var i = t.indexOf(":"), k = (i > 0 && i < 30) ? t.slice(0, i + 1) : "", v = k ? t.slice(i + 1).trim() : t;
          c.font = "700 " + fsz + "px " + F; var kw = k ? c.measureText(k + " ").width : 0;
          c.font = "400 " + fsz + "px " + F;
          var ls = [], cur = "", lim = w - kw;
          v.replace(/\u202f/g, "\u00a0").split(/[ \t\r\n]+/).forEach(function (wd) {
            if (!wd) return; var t2 = cur ? cur + " " + wd : wd;
            if (c.measureText(t2).width <= lim || !cur) cur = t2; else { ls.push(cur); cur = wd; lim = w; }
          });
          if (cur) ls.push(cur);
          var lhh = Math.round(fsz * 1.34);
          if (doDraw) {
            if (num) { c.fillStyle = G; c.font = "700 " + fsz + "px " + F; c.fillText(num, ix, yy); }
            if (k) { c.fillStyle = D; c.font = "700 " + fsz + "px " + F; c.fillText(k, x, yy); }
            c.fillStyle = tc; c.font = "400 " + fsz + "px " + F;
            ls.forEach(function (l, n) { c.fillText(l, n === 0 ? x + kw : x, yy + n * lhh); });
          }
          return ls.length * lhh;
        }
        if (draw && layout.bh && !bare) {
          c.save(); rr(c, bx, by0, bw, layout.bh, 24); c.fillStyle = "#fafafa"; c.fill(); c.lineWidth = 2; c.strokeStyle = "#dbdbdb"; c.stroke(); c.restore();
        }
        y += bare ? 0 : 28;
        if (S.box && !bare) { if (draw) { c.fillStyle = G; c.font = "700 " + (fs - 8) + "px " + F; c.fillText(S.box.toUpperCase(), ix, y); } y += Math.round((fs - 8) * 1.6) + 6; }
        lns.forEach(function (l) { y += kv(l, ix, iw, fs, "", draw, y) + 12; });
        pts.forEach(function (t, n) { y += kv(t, ix + 48, iw - 48, fs, String(n + 1) + ".", draw, y) + 12; });
        y += bare ? 0 : 16; layout.bh = y - by0; y += bare ? 0 : 24;
      }
      if (S.text) { c.font = (S.para ? "700 " + (fs + 6) : "400 " + fs) + "px " + F; String(S.text).split(/\n+/).forEach(function (p) { wrap(c, p, 960, 0).forEach(function () { y += Math.round((fs + (S.para ? 6 : 0)) * 1.35); }); y += 14; }); }
      return y;
    }
    while (photo && ph > (fit ? 400 : 300) && layout(false, ph, fs) > LIM) ph -= 30;
    while (fs > 22 && layout(false, ph, fs) > LIM) fs -= 1;
    while (photo && ph > 200 && layout(false, ph, fs) > LIM) ph -= 20;
    while (photo && !fit && ph < 620 && layout(false, ph + 20, fs) <= LIM - 20) ph += 20;
    /* Ohne Foto (Kurzmeldungen) die Schrift vergroessern, damit die Story die Flaeche fuellt. */
    while (!photo && fs < 38 && layout(false, ph, fs + 1) <= LIM - 140) fs += 1;
    layout(false, ph, fs);
    var yy = layout(true, ph, fs);
    if (S.text) {
      var lh2 = Math.round((fs + (S.para ? 6 : 0)) * 1.35); c.fillStyle = S.para ? D : "#262626"; c.font = (S.para ? "700 " + (fs + 6) : "400 " + fs) + "px " + F;
      yy -= String(S.text).split(/\n+/).reduce(function (a, p) { return a + wrap(c, p, 960, 0).length * lh2 + 14; }, 0);
      String(S.text).split(/\n+/).forEach(function (p) { wrap(c, p, 960, 0).forEach(function (l) { c.fillText(l, 60, yy); yy += lh2; }); yy += 14; });
    }
    if (S.chart && S.portrait) {
      /* Kursbild links und Portrait rechts sitzen beide unten auf dem gruenen Balken; der Name steht klein links neben der Person */
      var kc = await load(S.chart), kp = await load(S.portrait), bar = 1866;
      /* Kursbild komplett zeigen (mit Preisachse rechts): Breite so, dass es links vom Portrait endet */
      var kpx0 = kp ? 1056 - Math.round(520 * kp.width / kp.height) : 1056;
      if (kc) { var kw2 = S.para ? Math.min(880, kpx0 - 24 + 130) : Math.min(880, kpx0 - 24 + 20), kh2 = Math.round(kw2 * kc.height / kc.width); c.drawImage(kc, 24, bar - kh2, kw2, kh2); }
      if (kp) {
        var kph = 520, kpw = Math.round(kph * kp.width / kp.height), kpx = 1056 - kpw;
        c.drawImage(kp, kpx, bar - kph, kpw, kph);
        if (S.quote_by && !S.para) {
          var nm = S.quote_by.split("|"); c.textAlign = "right"; c.textBaseline = "alphabetic"; c.fillStyle = "#111";
          c.font = "700 30px " + F; c.fillText(nm[0].trim(), kpx - 14, bar - 380);
          if (nm[1]) { c.font = "400 25px " + F; c.fillStyle = "#262626"; c.fillText(nm[1].trim(), kpx - 14, bar - 342); }
          c.textAlign = "left"; c.textBaseline = "top";
        }
      }
    } else if (S.portrait) {
      /* Freigestelltes Portrait unten links (steht auf dem unteren Balken), daneben das Zitat */
      var pt = await load(S.portrait);
      if (pt) {
        var phh = 450, pww = Math.round(phh * pt.width / pt.height), pyy = 1866 - phh;
        c.drawImage(pt, 60, pyy, pww, phh);
        if (S.quote) {
          var qx = 60 + pww + 36, qw = 1020 - qx, qf = 33;
          c.fillStyle = "#111"; c.font = "400 " + qf + "px " + F; c.textBaseline = "top";
          var ql = wrap(c, "\u201e" + S.quote + "\u201c", qw, 8), qh = ql.length * Math.round(qf * 1.35), by = S.quote_by ? 70 : 0;
          var qy = Math.max(yy + 30, pyy + (phh - qh - by) / 2 - 30);
          ql.forEach(function (l, n) { c.fillText(l, qx, qy + n * Math.round(qf * 1.35)); });
          if (S.quote_by) { c.font = "700 28px " + F; wrap(c, S.quote_by, qw, 2).forEach(function (l, n) { c.fillText(l, qx, qy + qh + 22 + n * 36); }); }
        }
      }
    }
    if (S.chart && !S.portrait) {
      var ch = await load(S.chart);
      if (ch) { var top = yy + 30, bot = 1835, r2 = Math.min(960 / ch.width, (bot - top) / ch.height), cw = ch.width * r2, chh = ch.height * r2; c.drawImage(ch, 60 + (960 - cw) / 2, top, cw, chh); }
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
