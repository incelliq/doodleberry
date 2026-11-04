// Explainer kit 2 (from the reference reels): elements for history, science and motivational shorts.
// Each element is a pure function of time (seeded where random), drawn as SVG by the shot player.
//   draw     paths that draw themselves (diagrams, arrows, outlines), then optionally fill
//   title    bold outlined words that pop in one by one
//   paper    a torn-paper sign with tape; [bracketed] words take the accent colour
//   roots    a root system that grows from a point (seeded branching)
//   section  ground strata for cross-sections (soil, clay, rock) with pebbles
//   water    a water body (level can rise or fall) with a moving surface and flow lines along paths
//   face     a face for any object (eyes, pupils, brows, mouth) with lip-sync from a speaker, blinks, gaze, moods
// Elements in shots.json "underlays" draw behind the cast; "overlays" draw in front. Times can be line-relative.
// Text in any element may be Sinhala (or mixed): the font stack falls back to Noto Sans Sinhala per glyph.
(function () {
  const INK = '#181e26';
  const XF = (window.SCRIPT_FONTS || []).map(f => `'${f.family}'`).join(',') || "'Noto Sans Sinhala'";   // WP-25: every script's font
  const BODY = `'Fredoka',${XF},sans-serif`, HAND = `'Patrick Hand','Fredoka',${XF},sans-serif`;
  const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const clamp = u => Math.min(1, Math.max(0, u)), ease = u => (u = clamp(u), u * u * (3 - 2 * u));
  const f1 = n => (+n).toFixed(1), f3 = n => (+n).toFixed(3);
  const since = (o, t) => t - (o.start ?? 0);
  const durOf = (o, d) => typeof o.until === 'number' ? Math.max(0.05, o.until - (o.start ?? 0)) : (typeof o.duration === 'number' ? o.duration : d);  // "until" may be line-relative
  const sinhala = s => /[඀-෿]/.test(s || '');
  const RTLX = (() => { const r = (window.SCRIPT_FONTS || []).filter(f => f.rtl).map(f => f.ranges).join(''); return r ? new RegExp('[' + r + ']') : /(?!)/; })();
  const rtl = s => RTLX.test(s || '');   // WP-25: right-to-left text lays its words out from the right
  const fontFor = (s, base) => sinhala(s) ? "'Noto Sans Sinhala'," + base : base;
  function rng(seed) { let a = (seed | 0) * 2654435761 >>> 0 || 1; return () => { a ^= a << 13; a >>>= 0; a ^= a >> 17; a ^= a << 5; a >>>= 0; return a / 4294967296; }; }
  // back-out pop: 0 -> overshoot -> 1
  const pop = u => { u = clamp(u); const c = 1.9; return 1 + (c + 1) * Math.pow(u - 1, 3) + c * Math.pow(u - 1, 2); };
  const keysAt = (keys, t, d) => { if (!Array.isArray(keys)) return keys ?? d; if (!keys.length) return d; if (t <= keys[0][0]) return keys[0][1];
    for (let i = 1; i < keys.length; i++) if (t <= keys[i][0]) { const [t0, a] = keys[i - 1], [t1, b] = keys[i], u = ease((t - t0) / (t1 - t0)); return typeof a === 'number' ? a + (b - a) * u : (u < 0.5 ? a : b); }
    return keys[keys.length - 1][1]; };

  // ---------- draw: paths that draw themselves ----------
  function draw(o, t) {
    const paths = o.paths || [o.path], dur = durOf(o, 1.2), stag = o.stagger ?? dur / Math.max(1, paths.length), s = since(o, t);
    let out = '';
    // WP-15 drawing off: "off": t (seconds, or a line-relative time resolved before the player) undraws each path over
    // `off_duration` (default its draw time), staggered as it drew; "off_from": "start" (default: the line clears from
    // where it began, like a pen's tail catching up) or "end" (it retracts the way it came); a fill fades first
    const offT = o.off != null ? +o.off : null, odur = o.off_duration ?? dur;
    if (o.profile || o.colors) return drawGraded(o, t, paths, dur, stag, s, offT, odur);
    paths.forEach((d, i) => {
      const u = ease((s - i * stag) / dur); if (u <= 0) return;
      const uo = offT == null ? 0 : ease((t - offT - i * stag) / odur); if (uo >= 1) return;
      const fillOp = o.fill ? ease((s - i * stag - dur) / 0.4) * (o.fill_opacity ?? 1) * (1 - ease(uo * 3)) : 0;
      const dash = offT == null || uo <= 0 ? ` stroke-dasharray="1 1" stroke-dashoffset="${f3(1 - u)}"`   // drawing on: unchanged markup
        : (o.off_from === 'end' ? ` stroke-dasharray="${f3(u * (1 - uo))} 2" stroke-dashoffset="0"` : ` stroke-dasharray="${f3(u - uo * u)} 2" stroke-dashoffset="${f3(-uo * u)}"`);
      out += `<path d="${d}" pathLength="1" fill="${o.fill || 'none'}" fill-opacity="${f3(fillOp)}" stroke="${o.stroke || INK}" stroke-width="${o.width || 5}"` +
        ` stroke-linecap="round" stroke-linejoin="round"${dash}${o.dash ? ` stroke-dasharray="${o.dash}"` : ''}/>`;
    });
    return out;
  }

  // WP-15 width profiles and colour along a shape: "profile": [[0, 2], [0.5, 12], [1, 2]] (position along the path 0..1
  // -> width) and "colors": [[0, "#e8590c"], [1, "#1c7ed6"]] (position -> colour), drawn as `segments` short round-capped
  // pieces (default 48) sampled from the path in the page, so the line swells and changes colour along its length;
  // drawing on and off reveal and clear whole pieces in order
  const _gp = {};
  function samplePath(d, n) {
    const k = d + '|' + n; if (_gp[k]) return _gp[k];
    const el = document.createElementNS('http://www.w3.org/2000/svg', 'path'); el.setAttribute('d', d);
    const L = el.getTotalLength(), pts = [];
    for (let i = 0; i <= n; i++) { const p = el.getPointAtLength(L * i / n); pts.push([p.x, p.y]); }
    return (_gp[k] = pts);
  }
  const lerpKeys = (keys, u) => { if (u <= keys[0][0]) return keys[0][1]; for (let i = 0; i < keys.length - 1; i++) { const [a, va] = keys[i], [b, vb] = keys[i + 1]; if (u <= b) return [a, va, b, vb]; } return keys[keys.length - 1][1]; };
  const numAt = (keys, u) => { const r = lerpKeys(keys, u); if (!Array.isArray(r)) return r; const [a, va, b, vb] = r; return va + (vb - va) * (u - a) / Math.max(1e-9, b - a); };
  const hexRgb = h => [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16));
  const colAt = (keys, u) => { const r = lerpKeys(keys, u); if (!Array.isArray(r)) return r; const [a, va, b, vb] = r, k = (u - a) / Math.max(1e-9, b - a), A = hexRgb(va), B = hexRgb(vb);
    return '#' + A.map((x, i) => Math.round(x + (B[i] - x) * k).toString(16).padStart(2, '0')).join(''); };
  function drawGraded(o, t, paths, dur, stag, s, offT, odur) {
    const n = o.segments || 48; let out = '';
    paths.forEach((d, i) => {
      const u = ease((s - i * stag) / dur); if (u <= 0) return;
      const uo = offT == null ? 0 : ease((t - offT - i * stag) / odur); if (uo >= 1) return;
      const pts = samplePath(d, n), lo = o.off_from === 'end' ? 0 : uo * u, hi = o.off_from === 'end' ? u * (1 - uo) : u;
      for (let j = 0; j < n; j++) {
        const a = j / n, b = (j + 1) / n; if (b <= lo || a >= hi) continue;
        const m = (a + b) / 2, w = o.profile ? numAt(o.profile, m) : (o.width || 5), c = o.colors ? colAt(o.colors, m) : (o.stroke || INK);
        out += `<line x1="${f1(pts[j][0])}" y1="${f1(pts[j][1])}" x2="${f1(pts[j + 1][0])}" y2="${f1(pts[j + 1][1])}" stroke="${c}" stroke-width="${f1(w)}" stroke-linecap="round"/>`;
      }
    });
    return out;
  }

  // ---------- title: words pop in one by one ----------
  function title(o, t, ctx) {
    const W = ctx.W, words = String(o.text).split(/\s+/), fs = o.size || 120, per = o.per_word ?? 0.14, s = since(o, t);
    const font = fontFor(o.text, BODY), cw = sinhala(o.text) ? 0.62 : 0.56;
    const ew = c => /[A-Z]/.test(c) ? cw * 1.22 : /[0-9]/.test(c) ? cw * 1.08 : cw;   // Fredoka Bold capitals are wider: estimated at 0.56 em they overlapped and swallowed the gaps
    const lens = words.map(w => [...w].reduce((a, c) => a + ew(c), 0) * fs), gap = fs * 0.28, total = lens.reduce((a, b) => a + b, 0) + gap * (words.length - 1);
    let x = (o.x ?? W / 2) - total / 2, out = '';
    words.forEach((w, i) => {
      const u = (s - i * per) / 0.32; if (u <= 0) { x += lens[i] + gap; return; }
      const k = pop(u) * (1 + (o.breathe ?? 0.025) * Math.sin(t * 3 + i * 0.9) * clamp(u - 1)), y = o.y ?? ctx.H * 0.62;
      const cx = rtl(o.text) ? 2 * (o.x ?? W / 2) - (x + lens[i] / 2) : x + lens[i] / 2;   // the first word at the right in right-to-left text
      out += `<g transform="translate(${f1(cx)} ${f1(y)}) scale(${f3(k)}) rotate(${f1((o.tilt ?? -3) * (1 - clamp(u)))})">` +
        `<text x="0" y="0" text-anchor="middle" font-family="${font}" font-weight="700" font-size="${fs}" fill="${o.color || '#9bd23c'}" stroke="${o.outline || '#1d3a10'}"` +
        ` stroke-width="${fs * 0.12}" paint-order="stroke" stroke-linejoin="round">${esc(w)}</text></g>`;
      x += lens[i] + gap;
    });
    return out;
  }

  // ---------- paper: torn-paper sign with tape ----------
  function paper(o, t, ctx) {
    const lines = [].concat(o.text), fs = o.size || 64, s = since(o, t), u = ease(s / 0.4), r = rng(o.seed || 7);
    const w = o.w || Math.max(...lines.map(l => l.replace(/[\[\]]/g, '').length)) * fs * (sinhala(lines.join('')) ? 0.62 : 0.56) + fs * 1.6;
    const h = lines.length * fs * 1.25 + fs * 0.9, x = (o.x ?? ctx.W / 2) - w / 2, y = (o.y ?? ctx.H * 0.12) + (1 - u) * -30;
    const edge = (x0, y0, x1, y1, n, amp) => { let p = ''; for (let i = 1; i <= n; i++) { const k = i / n; p += ` L${f1(x0 + (x1 - x0) * k + (r() - 0.5) * amp)} ${f1(y0 + (y1 - y0) * k + (r() - 0.5) * amp)}`; } return p; };
    const d = `M${f1(x)} ${f1(y)}` + edge(x, y, x + w, y, 22, 7) + edge(x + w, y, x + w, y + h, 8, 7) + edge(x + w, y + h, x, y + h, 22, 7) + edge(x, y + h, x, y, 8, 7) + 'Z';
    let txt = '';
    lines.forEach((l, i) => {
      const parts = l.split(/(\[[^\]]+\])/).filter(Boolean).map(p => p.startsWith('[') ? `<tspan fill="${o.accent || '#d0402c'}">${esc(p.slice(1, -1))}</tspan>` : esc(p)).join('');
      txt += `<text x="${f1(x + w / 2)}" y="${f1(y + fs * 1.1 + i * fs * 1.25)}" text-anchor="middle" font-family="${fontFor(l, BODY)}" font-weight="700" font-size="${fs}" fill="${INK}">${parts}</text>`;
    });
    const tape = (tx, ty, a) => `<rect x="${f1(tx - 45)}" y="${f1(ty - 16)}" width="90" height="32" fill="#d9c9a0" fill-opacity="0.85" transform="rotate(${a} ${f1(tx)} ${f1(ty)})"/>`;
    const rot = (o.rotate ?? -2) + (o.sway ?? 0.8) * Math.sin(t * 1.6 + (o.seed || 7));  // gentle sway: no dead frames
    return `<g opacity="${f3(u)}" transform="rotate(${rot} ${f1(x + w / 2)} ${f1(y + h / 2)})"><path d="${d}" fill="${o.fill || '#f3ead6'}" stroke="#b9ab8a" stroke-width="2"/>${txt}` +
      (o.tape === false ? '' : tape(x + 30, y + 4, -32) + tape(x + w - 30, y + 4, 28)) + `</g>`;
  }

  // ---------- roots: seeded branching growth ----------
  const ROOTS = {};
  function rootTree(o) {
    const key = JSON.stringify([o.seed, o.depth, o.spread, o.levels, o.branches, o.main]);
    if (ROOTS[key]) return ROOTS[key];
    const r = rng(o.seed || 3), segs = [], depth = o.depth || 500, levels = o.levels ?? 4, br = o.branches ?? 3;
    // each branch: polyline points, birth (0..1 of growth), length share; children start along the parent
    function grow(x, y, ang, len, lvl, birth, width, main) {
      const pts = [[x, y]], n = 10; let a = ang;
      for (let i = 1; i <= n; i++) { a += (r() - 0.5) * (o.wiggle ?? 0.5); pts.push([pts[i - 1][0] + Math.cos(a) * len / n, pts[i - 1][1] + Math.sin(a) * len / n]); }
      const span = (1 - birth) * (lvl === 0 ? 0.9 : 0.75);
      segs.push({ pts, birth, span, width, main });
      if (lvl >= levels) return;
      const k = lvl === 0 ? br + 2 : br;
      for (let j = 0; j < k; j++) {
        const at = 0.2 + 0.7 * (j + r() * 0.6) / k, idx = Math.min(n, Math.round(at * n)), side = j % 2 ? 1 : -1;
        grow(pts[idx][0], pts[idx][1], a + side * (0.5 + r() * (o.spread ?? 0.9)), len * (0.45 + r() * 0.25), lvl + 1, birth + span * at, width * 0.55, false);
      }
    }
    grow(0, 0, Math.PI / 2, depth, 0, 0, o.width || 9, true);
    return (ROOTS[key] = segs);
  }
  function roots(o, t) {
    const g = ease(since(o, t) / durOf(o, 4)), x0 = o.x ?? 540, y0 = o.y ?? 1000;
    let out = `<g transform="translate(${x0} ${y0})" fill="none" stroke-linecap="round" stroke-linejoin="round">`;
    for (const s of rootTree(o)) {
      const u = clamp((g - s.birth) / s.span); if (u <= 0) continue;
      const n = s.pts.length - 1, m = u * n, i = Math.floor(m), fr = m - i;
      const pts = s.pts.slice(0, i + 1); if (i < n) pts.push([s.pts[i][0] + (s.pts[i + 1][0] - s.pts[i][0]) * fr, s.pts[i][1] + (s.pts[i + 1][1] - s.pts[i][1]) * fr]);
      out += `<path d="M${pts.map(p => f1(p[0]) + ' ' + f1(p[1])).join(' L')}" stroke="${s.main ? (o.main || o.color || '#2a1d14') : (o.color || '#2a1d14')}" stroke-width="${f1(s.width)}"/>`;
    }
    return out + '</g>';
  }

  // ---------- section: ground strata ----------
  function section(o, t, ctx) {
    const W = ctx.W, H = ctx.H, layers = o.layers || [{ h: 220, color: '#b98c5a' }, { h: 260, color: '#9d7146' }, { h: 2000, color: '#7d5634' }];
    let y = o.y ?? H * 0.55, out = '', r = rng(o.seed || 11);
    out += `<rect x="0" y="${f1(y)}" width="${W}" height="${f1(H - y)}" fill="${layers[0].color}"/>`;
    for (const L of layers) {
      const wav = []; for (let i = 0; i <= 12; i++) wav.push([i * W / 12, y + (r() - 0.5) * (o.rough ?? 18)]);
      out += `<path d="M0 ${f1(H)} L${wav.map(p => f1(p[0]) + ' ' + f1(p[1])).join(' L')} L${W} ${f1(H)} Z" fill="${L.color}"/>`;
      out += `<path d="M${wav.map(p => f1(p[0]) + ' ' + f1(p[1])).join(' L')}" fill="none" stroke="${INK}" stroke-opacity="0.35" stroke-width="3"/>`;
      for (let k = 0; k < (L.pebbles ?? 10); k++) { const px = r() * W, py = y + 30 + r() * Math.max(10, Math.min(L.h, H - y) - 60), pr = 5 + r() * 9;
        out += `<ellipse cx="${f1(px)}" cy="${f1(py)}" rx="${f1(pr * 1.4)}" ry="${f1(pr)}" fill="${L.pebble || '#00000022'}"/>`; }
      y += L.h;
    }
    return out;
  }

  // ---------- water: body with level, surface and flow lines ----------
  function water(o, t) {
    const level = keysAt(o.level, t, o.y ?? 1000), x = o.x ?? 0, w = o.w ?? 1080, bottom = o.bottom ?? level + 400, s = since(o, t);
    const amp = o.wave ?? 6, ph = t * (o.wave_speed ?? 2.2);
    const surf = []; for (let i = 0; i <= 24; i++) { const px = x + w * i / 24; surf.push([px, level + Math.sin(px * 0.018 + ph) * amp + Math.sin(px * 0.041 - ph * 1.3) * amp * 0.4]); }
    let out = '';
    if (o.body !== false) out += `<path d="M${f1(x)} ${f1(bottom)} L${surf.map(p => f1(p[0]) + ' ' + f1(p[1])).join(' L')} L${f1(x + w)} ${f1(bottom)} Z" fill="${o.color || '#5aa7d6'}" fill-opacity="${o.opacity ?? 0.85}"/>` +
      `<path d="M${surf.map(p => f1(p[0]) + ' ' + f1(p[1])).join(' L')}" fill="none" stroke="${o.edge || '#2d6f99'}" stroke-width="4"/>`;
    // flow lines: dashes travelling along each path; speed in px/s, turbulence wobbles the dash pattern
    (o.flows || []).forEach((fl, i) => {
      const sp = fl.speed ?? 220, dash = fl.dash || [26, 34], off = -(s * sp) % (dash[0] + dash[1]);
      out += `<path d="${fl.path}" fill="none" stroke="${fl.color || '#e8f6ff'}" stroke-width="${fl.width || 5}" stroke-linecap="round" stroke-dasharray="${dash.join(' ')}" stroke-dashoffset="${f1(off)}" opacity="${fl.opacity ?? 0.9}"/>`;
    });
    return out;
  }

  // ---------- face: a face for any object ----------
  const MOODS = {  // brow tilt (deg, inner end), brow lift, mouth curve for closed mouth
    neutral: [0, 0, 0.1], happy: [-6, -4, 0.7], worried: [18, -6, -0.4], angry: [-20, 4, -0.5], surprised: [4, -12, 0], smug: [-10, 0, 0.5] };
  const OPEN = { closed: 0, small: 0.25, mid: 0.5, wide: 0.85, O: 0.7, FV: 0.2, smile: 0.1, frown: 0.05, E: 0.35, rest: 0 };
  function face(o, t, ctx) {
    const s = o.s ?? 1, att = o.attach && ctx.pointOf ? ctx.pointOf(o.attach, t) : null;
    const [x0, y0] = att || [keysAt(o.x, t, 540), keysAt(o.y, t, 900)];
    const x = x0, y = y0 + (o.bob ?? 3) * s * Math.sin(t * 2.4 + (o.seed || 5));  // idle bob
    const mood = MOODS[keysAt(o.mood, t, 'neutral')] || MOODS.neutral;
    const look = keysAt(o.look, t, [0, 0]) || [0, 0];
    // blinks: seeded every 2.5-4.5 s, plus scripted ones
    const r = rng(o.seed || 5); let blink = 0, bt = r() * 2;
    while (bt < t + 0.3) { const d = t - bt; if (d >= 0 && d < 0.15) blink = 1 - Math.abs(d - 0.075) / 0.075; bt += 2.5 + r() * 2; }
    for (const b of o.blinks || []) { const d = t - b; if (d >= 0 && d < 0.15) blink = Math.max(blink, 1 - Math.abs(d - 0.075) / 0.075); }
    // mouth from the speaker's visemes (with a short hold so it does not flicker)
    let shape = keysAt(o.mouth, t, null);
    if (!shape && o.speaker && ctx.visemes) { shape = 'closed'; for (const [ct, sh] of (ctx.visemes[o.speaker] || [])) { if (ct > t + 0.033) break; shape = sh; } }
    const open = OPEN[shape || 'closed'] ?? 0.2;
    const ex = (o.eye_gap ?? 46) * s, er = (o.eye ?? 26) * s, pr = er * 0.48, lift = mood[1] * s;
    let out = `<g transform="translate(${f1(x)} ${f1(y)}) rotate(${o.rotate ?? 0})">`;
    for (const side of [-1, 1]) {
      const cx = side * ex / 2, ry = er * (1 - 0.92 * blink);
      out += `<ellipse cx="${f1(cx)}" cy="0" rx="${f1(er)}" ry="${f1(Math.max(1.2, ry))}" fill="#fff" stroke="${INK}" stroke-width="${f1(3.2 * s)}"/>`;
      if (blink < 0.6) out += `<circle cx="${f1(cx + look[0] * er * 0.42)}" cy="${f1(look[1] * er * 0.42)}" r="${f1(pr)}" fill="${INK}"/>` +
        `<circle cx="${f1(cx + look[0] * er * 0.42 + pr * 0.35)}" cy="${f1(look[1] * er * 0.42 - pr * 0.35)}" r="${f1(pr * 0.3)}" fill="#fff"/>`;
      // brow: inner end towards the centre; positive tilt raises the inner end (worried)
      const bx0 = cx - side * er * 0.9, bx1 = cx + side * er * 0.9, by = -er * 1.45 + lift, tilt = mood[0] * Math.PI / 180;
      out += `<path d="M${f1(bx0)} ${f1(by - Math.sin(tilt) * er * 0.5)} Q${f1(cx)} ${f1(by - er * 0.25)} ${f1(bx1)} ${f1(by + Math.sin(tilt) * er * 0.5)}" fill="none" stroke="${INK}" stroke-width="${f1(5 * s)}" stroke-linecap="round"/>`;
    }
    const mw = er * 1.3, my = er * 1.6;
    if (open < 0.12) { const c = mood[2] * er * 0.5; out += `<path d="M${f1(-mw / 2)} ${f1(my)} Q0 ${f1(my + c)} ${f1(mw / 2)} ${f1(my)}" fill="none" stroke="${INK}" stroke-width="${f1(4.5 * s)}" stroke-linecap="round"/>`; }
    else { const mh = er * 0.9 * open, rx = shape === 'O' ? mw * 0.28 : mw / 2;
      out += `<ellipse cx="0" cy="${f1(my + mh * 0.3)}" rx="${f1(rx)}" ry="${f1(mh / 2 + 2)}" fill="#6a2a2a" stroke="${INK}" stroke-width="${f1(3.5 * s)}"/>` +
        (open > 0.4 ? `<ellipse cx="0" cy="${f1(my + mh * 0.62)}" rx="${f1(rx * 0.55)}" ry="${f1(mh * 0.16)}" fill="#d9706a"/>` : ''); }
    return out + '</g>';
  }

  // ---------- icon: any Lucide icon (ISC, assets/icons/lucide.js), popping in, optional badge circle ----------
  function icon(o, t) {
    const body = (window.ICONS || {})[o.name]; if (!body) return '';
    const size = o.size || 140, k = pop((t - (o.start ?? 0)) / 0.3) * (1 + 0.02 * Math.sin(t * 2.6 + (o.x || 0)));
    const sc = size / 24, x = o.x ?? 540, y = o.y ?? 900;
    const badge = o.badge ? `<circle cx="12" cy="12" r="15" fill="${o.badge}" stroke="${INK}" stroke-width="${f1(3 / sc)}"/>` : '';
    return `<g transform="translate(${f1(x)} ${f1(y)}) scale(${f3(k * sc)}) translate(-12 -12)">${badge}<g fill="none" stroke="${o.color || INK}" stroke-width="${o.stroke_width || 2}" stroke-linecap="round" stroke-linejoin="round">${body}</g></g>`;
  }

  window.KIT = { draw, title, paper, roots, section, water, face, icon, sinhala, fontFor };
})();
