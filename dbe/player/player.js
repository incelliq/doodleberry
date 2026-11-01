// Shot player: renders any frame of a shots.json film in the browser (the SVG renderer, background plates for the
// other renderers, and the interactive web export). Query: ?shot=<id> (render that shot) | ?bg=1 (set only) | none (whole film).
(function () {
  const S = window.SHOTS, T = window.TIMING || {}, PUP = window.PUPPETS || {}, LIB = (window.CLIPLIB || {}).humanoid || { clips: {}, presets: {} };
  const q = new URLSearchParams(location.search);
  const W = (S.size || [1080, 1920])[0], H = (S.size || [1080, 1920])[1], FPS = S.fps || 30;
  const stage = document.getElementById('stage');
  stage.setAttribute('viewBox', `0 0 ${W} ${H}`); stage.style.width = W + 'px'; stage.style.height = H + 'px';
  const words = (T.lines || []).flatMap(l => l.words.map(w => ({ ...w, speaker: l.speaker })));
  const shotAt = t => S.shots.reduce((a, s) => (t >= s.start ? s : a), S.shots[0]);
  const placeAt = (pl, t) => Array.isArray(pl) ? Acting.sampleKeys(pl.map(([k, v]) => [k, [v.x, v.y, v.s ?? 1, v.flip ?? 1]]), t) : [pl.x, pl.y, pl.s ?? 1, pl.flip ?? 1];

  function captions(t, style) {
    const w = words.filter(v => v.start <= t + 0.05 && v.end + 0.2 > t);
    if (!w.length) return '';
    const text = w.slice(-3).map(v => v.text.replace(/[.,?!]$/, '')).join(' ').toUpperCase();
    const size = 84, pw = Math.min(980, text.length * size * 0.58 + 80);
    return `<g transform="translate(${W / 2} ${H - 300})"><rect x="${-pw / 2}" y="${-size * 0.95}" width="${pw}" height="${size * 1.25}" rx="${size * 0.62}" fill="#1a0f08" fill-opacity="0.82"/>` +
      `<text x="0" y="0" font-size="${size}" font-weight="700" text-anchor="middle" fill="#fff" stroke="#24160e" stroke-width="12" paint-order="stroke" stroke-linejoin="round">${text}</text></g>`;
  }
  // ---------- doodle style: boil, ink overlays, speech bubbles ----------
  const SCRIPT = window.SCRIPT || {};
  const libFor = p => (window.CLIPLIB || {})[p.template] || LIB;
  const hash = (a, b) => { let h = (a * 374761393 + b * 668265263) | 0; h = (h ^ (h >>> 13)) * 1274126177; return ((h ^ (h >>> 16)) >>> 0) / 4294967296; };
  const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const INK = '#181e26', HAND = "'Patrick Hand','Fredoka',sans-serif";
  function boilDefs(st, t) {
    const b = st.boil; if (!b) return '';
    const k = Math.floor(t * (b.fps || 12)) % (b.frames || 8);
    return `<defs><filter id="boil" x="-10%" y="-10%" width="120%" height="120%"><feTurbulence type="fractalNoise" baseFrequency="${b.freq || 0.022}" numOctaves="2" seed="${k + 1}"/>` +
      `<feDisplacementMap in="SourceGraphic" scale="${b.amount ?? 5}" xChannelSelector="R" yChannelSelector="G"/></filter></defs>`;
  }
  function overlay(o) {
    if (o.type === 'sign') { const fs = o.size || 56, w = o.text.length * fs * 0.52 + 50, h = fs * 1.5, x = o.x, y = o.y;
      return `<g stroke="${INK}" stroke-width="4" stroke-linecap="round" fill="none"><path d="M${x - w * 0.32} ${y - h * 1.1} L${x - w * 0.28} ${y}"/><path d="M${x + w * 0.32} ${y - h * 1.1} L${x + w * 0.28} ${y}"/>` +
        `<rect x="${x - w / 2}" y="${y}" width="${w}" height="${h}" rx="6" fill="#f6f5ef"/></g><text x="${x}" y="${y + h * 0.7}" font-family="${HAND}" font-size="${fs}" text-anchor="middle" fill="${INK}">${esc(o.text)}</text>`; }
    if (o.type === 'text') return `<text x="${o.x}" y="${o.y}" font-family="${HAND}" font-size="${o.size || 58}" text-anchor="middle" fill="${o.color || '#707a84'}">${esc(o.text)}</text>`;
    return '';
  }
  // rows for a bubble: explicit \n wins, else greedy wrap
  function rows(text, max) { if (text.includes('\n')) return text.split('\n'); const out = []; let cur = '';
    for (const w of text.split(/\s+/)) { if ((cur + ' ' + w).trim().length > max && cur) { out.push(cur); cur = w; } else cur = (cur + ' ' + w).trim(); } if (cur) out.push(cur); return out; }
  // boxes other elements occupy (signs, text overlays), so bubbles can avoid them
  const overlayBox = o => o.type === 'sign' ? (() => { const fs = o.size || 56, w = o.text.length * fs * 0.52 + 50; return [o.x - w / 2, o.y - fs * 1.6, o.x + w / 2, o.y + fs * 1.6]; })()
    : o.type === 'text' ? [o.x - o.text.length * (o.size || 58) * 0.27, o.y - (o.size || 58), o.x + o.text.length * (o.size || 58) * 0.27, o.y + 10] : null;
  let AVOID = [];
  const hits = (a, b) => a[0] < b[2] && a[2] > b[0] && a[1] < b[3] && a[3] > b[1];
  function bubble(b, anchor, t, idx) {
    const step = 1 / 12, f = Math.floor(t / step), f0 = Math.floor(b.t0 / step), f1 = Math.floor(b.t1 / step);
    if (f < f0 || f > f1) return '';
    const i = f - f0, j = f1 - f, pop = i === 0 ? 0.55 : i === 1 ? 1.12 : j === 0 ? 0.5 : j === 1 ? 0.85 : 1;
    const style = b.style || 'say', base = { say: 72, shout: 118, whisper: 50 }[style] || 72;
    const R = rows(b.text, { say: 13, shout: 9, whisper: 18 }[style] || 13), lh = base * 1.08;
    const bw = Math.max(...R.map(r => r.length)) * base * 0.5, bh = lh * R.length;
    let rx = (bw / 2 + 60) * pop, ry = (bh / 2 + 46) * pop; if (style === 'shout') { rx *= 1.2; ry *= 1.3; }
    // placement: above the speaker toward the frame centre, then the other side, then higher or lower, avoiding
    // signs, overlays and earlier bubbles; inside the platform-safe area where possible
    const side = anchor[0] < W / 2 ? 1 : -1, clampX = x => Math.min(Math.max(x, rx + 70), W - rx - 130), clampY = y => Math.max(y, ry + 210);
    const cands = [];
    for (const dy of [0, -80, 60, -160]) for (const dx of [90, -90, 230, -230, 0]) cands.push([clampX(anchor[0] + dx * side), clampY(anchor[1] - 70 - ry + dy)]);
    const overlap = (a, r) => Math.max(0, Math.min(a[2], r[2]) - Math.max(a[0], r[0])) * Math.max(0, Math.min(a[3], r[3]) - Math.max(a[1], r[1]));
    const cost = ([x, y], k) => AVOID.reduce((acc, r) => acc + overlap([x - rx, y - ry, x + rx, y + ry], r), 0) + k * 40;  // prefer earlier (closer) spots
    let [cx, cy] = cands.map((c, k) => [c, cost(c, k)]).sort((a, b) => a[1] - b[1])[0][0];
    AVOID.push([cx - rx, cy - ry, cx + rx, cy + ry]);
    const n = 64, pts = [], k = Math.floor(t * 12) % 8;
    for (let q = 0; q < n; q++) { const th = 2 * Math.PI * q / n;
      let r = 1 + 0.018 * (Math.sin(3 * th + 6.28 * hash(k, idx)) + Math.sin(5 * th + 6.28 * hash(k + 9, idx)) + 0.6 * Math.sin(9 * th + 6.28 * hash(k + 17, idx)));
      if (style === 'shout') r *= q % 4 < 2 ? 1 : 0.8; pts.push([cx + rx * r * Math.cos(th), cy + ry * r * Math.sin(th), th]); }
    // tail: replace a few outline points with a spike to the speaker
    const [tx, ty] = [anchor[0], anchor[1] - 18], ang = (Math.atan2((ty - cy) / ry, (tx - cx) / rx) + 2 * Math.PI) % (2 * Math.PI), i0 = Math.round(ang / (2 * Math.PI) * n) % n;
    const path = []; for (let q = 0; q < n; q++) { const d = (q - i0 + n) % n; if (d === n - 3) path.push(pts[q], [tx, ty, 0]); else if (d > n - 3 || d < 3) continue; else path.push(pts[q]); }
    const dstr = 'M' + path.map(([x, y]) => `${x.toFixed(1)} ${y.toFixed(1)}`).join(' L') + ' Z';
    let svg = `<path d="${dstr}" fill="#f6f5ef" stroke="${INK}" stroke-width="${style === 'whisper' ? 4 : 5}" stroke-linejoin="round"${style === 'whisper' ? ' stroke-dasharray="12 12"' : ''}/>`;
    // typewriter: voiced lines reveal word by word as spoken; silent ones letter by letter
    // voiced: word by word as spoken; custom bubble text: letters spread over the spoken line; silent: typed out
    const total = R.join('').length;
    const shown = b.words ? b.words.filter(w => w.start <= t).length
      : b.speak ? Math.ceil(total * Math.min(1, Math.max(0, (t - b.speak[0]) / Math.max(0.2, b.speak[1] - b.speak[0]))))
      : Math.floor(Math.max(0, t - b.t0 - 0.2) / (b.slow ? 0.42 : 0.05)) + (pop < 1 && i > 1 ? 99 : 0);
    let left = shown, tspans = '';
    R.forEach((row, ri) => { let txt = row;
      if (b.words) { const ws = row.split(/\s+/); txt = ws.slice(0, Math.max(0, left)).join(' '); left -= ws.length; } else { txt = row.slice(0, Math.max(0, left)); left -= row.length; }
      const y = cy - bh / 2 + lh * (ri + 0.78) * pop;
      if (style === 'shout') [...txt].forEach((ch, ci) => { const jx = (hash(k * 31 + ci, idx) - 0.5) * 8, jy = (hash(k * 17 + ci, idx + 3) - 0.5) * 10;
        tspans += `<text x="${(cx - txt.length * base * 0.27 + ci * base * 0.54 + jx).toFixed(1)}" y="${(y + jy).toFixed(1)}" font-size="${base * pop}">${esc(ch)}</text>`; });
      else tspans += `<text x="${cx}" y="${y.toFixed(1)}" font-size="${base * pop}" text-anchor="middle"${style === 'whisper' ? ' fill="#59636d"' : ''}>${esc(txt)}</text>`; });
    return svg + `<g font-family="${HAND}" fill="${INK}">${tspans}</g>`;
  }
  function bubblesFor(sh, t, heads) {
    const out = []; let idx = 0;
    AVOID = (sh.overlays || []).filter(o => (o.start == null || t >= o.start) && (o.end == null || t <= o.end)).map(overlayBox).filter(Boolean);
    for (const a of Object.values(heads)) AVOID.push([a[0] - 150, a[1] - 10, a[0] + 150, a[1] + H * 0.22]);  // keep bubbles off the characters' heads and bodies
    if (sh.bubbles !== false) for (const ln of T.lines || []) { // voiced lines become bubbles for speakers in the shot
      const who = heads[ln.speaker]; if (!who || !sh.bubbles) continue;
      const sl = (SCRIPT.lines || []).find(l => l.id === ln.id) || {};
      out.push(bubble({ t0: ln.start - 0.12, t1: ln.end + 0.5, text: sl.bubble || ln.text, style: sl.style, words: sl.bubble ? null : ln.words, speak: [ln.start, ln.end] }, who, t, idx++));
    }
    for (const b of (sh.extra_bubbles || [])) if (heads[b.who]) out.push(bubble({ ...b, t0: b.start, t1: b.end }, heads[b.who], t, 50 + idx++));  // silent bubbles
    return out.join('');
  }

  function frameAt(t, bgOnly) {
    const sh = shotAt(t), st = sh.style || {};
    const tq = st.step ? Math.floor(t * st.step + 1e-6) / st.step : t;   // animate on 12s/24s like hand-drawn work
    const set = (window.SETS || {})[sh.set || 'plain'] || window.SETS.plain;
    let world = set.draw(tq, sh.set_opts || {}), ink = '';
    const heads = {};
    for (const c of sh.cast || []) {
      const p = PUP[c.puppet]; if (!p) continue;
      if (bgOnly) { // the set plate for other renderers keeps each character's ground shadow
        const [x, y, s] = placeAt(c.place || { x: W / 2, y: set.floor }, tq);
        if (st.shadow !== false) world += `<ellipse cx="${x}" cy="${y + 6}" rx="${120 * s}" ry="${14 * s}" fill="#000" opacity="0.12"/>`; continue;
      }
      const tl = { ...(c.timeline || {}) }, L = libFor(p);
      if (tl.visemes_from) { tl.visemes = (T.visemes || {})[tl.visemes_from] || []; delete tl.visemes_from; }
      const pose = Acting.evaluate(p, tl, tq, L.clips, L.presets);
      const [x, y, s, flip] = placeAt(c.place || { x: W / 2, y: set.floor }, tq);
      if (st.shadow !== false) world += `<ellipse cx="${x}" cy="${y + 6}" rx="${120 * s}" ry="${14 * s}" fill="#000" opacity="0.12"/>`;
      ink += Puppet.render(p, x, y, { ...pose, s, flip });
      if (c.speaker) heads[c.speaker] = Puppet.pointOf(p, 'head', (p.anchors || {}).bubble || null, x, y, { ...pose, s, flip });
    }
    if (!bgOnly) { ink += (sh.overlays || []).filter(o => (o.start == null || tq >= o.start) && (o.end == null || tq <= o.end)).map(overlay).join('') + bubblesFor(sh, tq, heads); }
    world += st.boil ? `<g filter="url(#boil)">${ink}</g>` : ink;
    let svg = boilDefs(st, t) + world;
    if (sh.camera) { const [cx, cy, z] = Acting.sampleKeys(sh.camera, tq) || [W / 2, H / 2, 1]; svg = boilDefs(st, t) + `<g transform="translate(${W / 2} ${H / 2}) scale(${z}) translate(${-cx} ${-cy})">${world}</g>`; }
    // shot renders leave captions to the film-level pass (dbe/captions.py); the live web player draws them itself
    if (!bgOnly && !only && q.get('captions') !== '0' && sh.captions !== false && S.captions !== false) svg += captions(t);
    return svg;
  }
  const only = q.get('shot') ? S.shots.find(s => s.id === q.get('shot')) : null;
  const bgOnly = q.get('bg') === '1';
  const t0 = only ? only.start : 0, t1 = only ? only.end : S.shots[S.shots.length - 1].end;
  window.FILMTIME = { start: t0, end: t1, fps: FPS };
  window.frameAtTime = t => { stage.innerHTML = frameAt(t, bgOnly); };
  window.renderFrame = f => window.frameAtTime(t0 + f / FPS);
  window.FRAMES = Math.round((t1 - t0) * FPS);
  window.FILM = { width: W, height: H, fps: FPS, frames: window.FRAMES, ready: false };
  (document.fonts ? Promise.all([document.fonts.load('700 40px Fredoka'), document.fonts.load("40px 'Patrick Hand'")]) : Promise.resolve()).then(() => { window.FILM.ready = true; window.ready = true; });
})();
