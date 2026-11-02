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
  const INK = '#181e26', HAND = "'Patrick Hand','Fredoka','Noto Sans Sinhala',sans-serif";
  function boilDefs(st, t) {
    const b = st.boil; if (!b) return '';
    const k = Math.floor(t * (b.fps || 12)) % (b.frames || 8);
    return `<defs><filter id="boil" x="-10%" y="-10%" width="120%" height="120%"><feTurbulence type="fractalNoise" baseFrequency="${b.freq || 0.022}" numOctaves="2" seed="${k + 1}"/>` +
      `<feDisplacementMap in="SourceGraphic" scale="${b.amount ?? 5}" xChannelSelector="R" yChannelSelector="G"/></filter></defs>`;
  }
  function overlay(o, t) {
    if (o.type === 'sign') { const fs = o.size || 56, w = o.text.length * fs * 0.52 + 50, h = fs * 1.5, x = o.x, y = o.y;
      return `<g stroke="${INK}" stroke-width="4" stroke-linecap="round" fill="none"><path d="M${x - w * 0.32} ${y - h * 1.1} L${x - w * 0.28} ${y}"/><path d="M${x + w * 0.32} ${y - h * 1.1} L${x + w * 0.28} ${y}"/>` +
        `<rect x="${x - w / 2}" y="${y}" width="${w}" height="${h}" rx="6" fill="#f6f5ef"/></g><text x="${x}" y="${y + h * 0.7}" font-family="${HAND}" font-size="${fs}" text-anchor="middle" fill="${INK}">${esc(o.text)}</text>`; }
    if (o.type === 'text') return `<text x="${o.x}" y="${o.y}" font-family="${HAND}" font-size="${o.size || 58}" text-anchor="middle" fill="${o.color || '#707a84'}">${esc(o.text)}</text>`;
    return explainer(o, t);
  }

  // ---------- explainer scene library (plan 1.13): every element is a pure function of t ----------
  const BODY = "'Fredoka','Noto Sans Sinhala',sans-serif", MONO = "'Atkinson Mono',monospace";
  // brand defaults (films that set "brand": true get window.BRAND); explicit overlay values always win
  const BR = window.BRAND || null, BP = (BR && BR.palette) || {};
  const brandColor = (v, d) => v || (BR ? d : undefined);
  const ease = u => (u = Math.min(1, Math.max(0, u)), u * u * (3 - 2 * u));
  const since = (o, t) => t - (o.start ?? 0);
  const fmt = (v, d = 0) => Number(v).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
  const dataOf = o => o.data || (o.data_from ? String(o.data_from).split('.').reduce((a, k) => (a || {})[k], window.DATA || {}) : []) || [];
  const plate = (x, y, w, h, fill = '#fbfaf5') => `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="10" fill="${fill}" stroke="${INK}" stroke-width="3"/>`;
  function wrapText(text, maxChars) { const out = []; let cur = ''; for (const w of String(text).split(/\s+/)) { if ((cur + ' ' + w).trim().length > maxChars && cur) { out.push(cur); cur = w; } else cur = (cur + ' ' + w).trim(); } if (cur) out.push(cur); return out; }
  function explainer(o, t) {
    const u = ease(since(o, t) / 0.35), slide = (1 - u) * 40, op = u.toFixed(3);
    const fsT = o.title_size || (H > W ? 64 : 56), fsB = o.size || (H > W ? 42 : 36);
    if (o.type === 'card') { // a definition card: term in bold, plain-language meaning below
      const w = o.w || (H > W ? 860 : 900), lines = wrapText(o.body || '', Math.floor(w / (fsB * 0.52)));
      const h = fsT * 1.6 + lines.length * fsB * 1.25 + 40, x = o.x ?? (W - w) / 2, y = (o.y ?? H * 0.2) + slide;
      return `<g opacity="${op}">${plate(x, y, w, h)}<text x="${x + 36}" y="${y + fsT * 1.15}" font-family="${BODY}" font-weight="700" font-size="${fsT}" fill="${o.color || BP.primary || '#1a62c2'}">${esc(o.title || '')}</text>` +
        lines.map((l, i) => `<text x="${x + 36}" y="${y + fsT * 1.6 + 20 + (i + 0.8) * fsB * 1.25}" font-family="${BODY}" font-size="${fsB}" fill="${INK}">${esc(l)}</text>`).join('') + `</g>`;
    }
    if (o.type === 'counter') { // a number that counts up to its value, with its label
      const v = (o.from ?? 0) + ((o.to ?? 0) - (o.from ?? 0)) * ease(since(o, t) / (o.duration ?? 1.2)), fs = o.size || (H > W ? 150 : 120);
      return `<g opacity="${op}"><text x="${o.x ?? W / 2}" y="${o.y ?? H * 0.4}" text-anchor="middle" font-family="${BODY}" font-weight="700" font-size="${fs}" fill="${o.color || INK}">${esc((o.prefix || '') + fmt(v, o.decimals || 0) + (o.suffix || ''))}</text>` +
        (o.label ? `<text x="${o.x ?? W / 2}" y="${(o.y ?? H * 0.4) + fsB * 1.6}" text-anchor="middle" font-family="${BODY}" font-size="${fsB}" fill="#4a4e57">${esc(o.label)}</text>` : '') + `</g>`;
    }
    if (o.type === 'console') { // typed terminal lines; lines starting with "!" are output in the error colour
      const fs = o.size || (H > W ? 34 : 30), w = o.w || (H > W ? 900 : 1100), lh = fs * 1.4, x = o.x ?? (W - w) / 2, y = o.y ?? H * 0.3, cps = o.cps || 28;
      let budget = Math.max(0, since(o, t)) * cps, rowsOut = '';
      (o.lines || []).forEach((ln, i) => { const isOut = ln.startsWith('!') || ln.startsWith('>'); const txt = isOut ? ln.slice(1) : ln;
        const n = isOut ? (budget > 0 ? txt.length : 0) : Math.min(txt.length, Math.floor(budget)); budget -= isOut ? 0 : txt.length + 6;
        if (n > 0 || (!isOut && budget > -6)) rowsOut += `<text x="${x + 28}" y="${y + 44 + (i + 0.7) * lh}" font-family="${MONO}" font-size="${fs}" fill="${ln.startsWith('!') ? '#b8560f' : isOut ? '#9fb0c0' : '#e8ecef'}"${ln.startsWith('!') ? ' font-weight="700"' : ''}>${esc((isOut ? '' : '$ ') + txt.slice(0, n))}</text>`; });
      return `<g opacity="${op}"><rect x="${x}" y="${y}" width="${w}" height="${44 + (o.lines || []).length * lh + 24}" rx="12" fill="#1d201a"/>` +
        `<circle cx="${x + 26}" cy="${y + 22}" r="7" fill="#e0584a"/><circle cx="${x + 48}" cy="${y + 22}" r="7" fill="#e8b33a"/><circle cx="${x + 70}" cy="${y + 22}" r="7" fill="#5aae5a"/>${rowsOut}</g>`;
    }
    if (o.type === 'bars') { // a bar chart from data ([[label, value], ...] or data_from: "key.path" in data.json)
      const data = dataOf(o), w = o.w || (H > W ? 900 : 1300), h = o.h || (H > W ? 700 : 560), x = o.x ?? (W - w) / 2, y = o.y ?? H * 0.25;
      const max = o.max || Math.max(...data.map(d => d[1]), 1), n = data.length || 1, bw = w / n * 0.62, g = ease(since(o, t) / (o.duration ?? 1.0));
      let svg = `<g opacity="${op}"><path d="M${x} ${y + h} L${x + w} ${y + h}" stroke="${INK}" stroke-width="3"/>`;
      data.forEach(([lab, v], i) => { const bh = (v / max) * (h - 90) * g, bx = x + (i + 0.19) * (w / n);
        svg += `<rect x="${bx}" y="${y + h - bh}" width="${bw}" height="${bh}" fill="${(o.colors || [])[i] || o.color || '#1a62c2'}" stroke="${INK}" stroke-width="2"/>` +
          `<text x="${bx + bw / 2}" y="${y + h + fsB * 1.1}" text-anchor="middle" font-family="${BODY}" font-size="${fsB * 0.8}" fill="${INK}">${esc(lab)}</text>` +
          (g > 0.98 ? `<text x="${bx + bw / 2}" y="${y + h - bh - 14}" text-anchor="middle" font-family="${BODY}" font-weight="700" font-size="${fsB * 0.8}" fill="${INK}">${esc((o.prefix || '') + fmt(v, o.decimals || 0) + (o.unit || ''))}</text>` : ''); });
      return svg + (o.title ? `<text x="${x + 12}" y="${y - 20}" font-family="${BODY}" font-weight="700" font-size="${fsB}" fill="${INK}">${esc(o.title)}</text>` : '') + `</g>`;
    }
    if (o.type === 'quote') {
      const w = o.w || (H > W ? 880 : 1200), lines = wrapText(o.text || '', Math.floor(w / (fsB * 0.5))), x = o.x ?? (W - w) / 2, y = (o.y ?? H * 0.25) + slide, h = lines.length * fsB * 1.3 + (o.by ? fsB * 1.6 : 0) + 60;
      return `<g opacity="${op}">${plate(x, y, w, h, '#fffdf4')}` + lines.map((l, i) => `<text x="${x + 40}" y="${y + 50 + (i + 0.6) * fsB * 1.3}" font-family="${BODY}" font-size="${fsB}" font-style="italic" fill="${INK}">${esc((i ? '' : '“') + l + (i === lines.length - 1 ? '”' : ''))}</text>`).join('') +
        (o.by ? `<text x="${x + w - 40}" y="${y + h - 30}" text-anchor="end" font-family="${MONO}" font-size="${Math.max(H > W ? 30 : 24, fsB * 0.7)}" fill="#4a4e57">${esc('— ' + o.by)}</text>` : '') + `</g>`;
    }
    if (o.type === 'citation') { // small mono source line on a soft plate (inside the safe area by default)
      const fs = o.size || (H > W ? 30 : 24), w = String(o.text).length * fs * 0.6 + 40, x = o.x ?? (H > W ? 64 : W * 0.05), y = o.y ?? (H > W ? 1490 : H * 0.88);
      return `<g opacity="${op}"><rect x="${x}" y="${y}" width="${w}" height="${fs * 1.7}" rx="8" fill="#f4f3ee" fill-opacity="0.92"/><text x="${x + 20}" y="${y + fs * 1.15}" font-family="${MONO}" font-size="${fs}" fill="#4a4e57">${esc(o.text)}</text></g>`;
    }
    if (o.type === 'wordmark') {
      const fs = o.size || (H > W ? 40 : 34), x = o.x ?? (H > W ? 80 : W * 0.05 + 12), y = o.y ?? (H > W ? 262 : H * 0.1);  // inset: glyph bearings stay inside the safe area
      const wmk = (BR && BR.wordmark) || {};
      return `<text x="${x}" y="${y}" font-family="${BODY}" font-weight="700" font-size="${fs}" fill="${o.color || BP.ink || INK}">${esc(o.text || wmk.text || '')}<tspan fill="${o.accent || BP[(BR || {}).wordmark_accent] || '#1a62c2'}">${esc(o.accent_text ?? wmk.accent_text ?? '')}</tspan></text>`;
    }
    if (window.KIT && KIT[o.type]) return KIT[o.type](o, t, { W, H, visemes: T.visemes || {}, pointOf: (tg, tt) => worldOf(tg, tt, CASTS) });  // explainer kit 2 (dbe/player/kit.js)
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
    const style = b.style || 'say', base = ({ say: 72, shout: 118, whisper: 50 }[style] || 72) * Math.min(1, H / 1920 * 1.4);  // landscape: smaller type, still >= the 16:9 minimum
    const R = rows(b.text, { say: 13, shout: 9, whisper: 18 }[style] || 13), lh = base * 1.08;
    const bw = Math.max(...R.map(r => r.length)) * base * 0.5, bh = lh * R.length;
    let rx = (bw / 2 + 60) * pop, ry = (bh / 2 + 46) * pop; if (style === 'shout') { rx *= 1.2; ry *= 1.3; }
    // placement: above the speaker toward the frame centre, then the other side, then higher or lower, avoiding
    // signs, overlays and earlier bubbles; inside the platform-safe area where possible
    const SAFE = H > W ? [64, 200, 960] : [W * 0.05, H * 0.05, W * 0.95];  // platform-safe text area (9:16 rail and top bar; 16:9 title-safe)
    const side = anchor[0] < W / 2 ? 1 : -1, clampX = x => Math.min(Math.max(x, rx + SAFE[0] + 6), SAFE[2] - rx - 6), clampY = y => Math.max(y, ry + SAFE[1] + 10);
    const cands = [];
    const u = H / 1920 * (H > W ? 1 : 1.6);
    for (const dy of [0, -80, 60, -160].map(v => v * u)) for (const dx of [90, -90, 230, -230, 330, -330, 0].map(v => v * (H > W ? 1 : 2))) cands.push([clampX(anchor[0] + dx * side), clampY(anchor[1] - 70 - ry + dy)]);
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
    for (const a of Object.values(heads)) AVOID.push([a[0] - 150 * H / 1920 * (H > W ? 1 : 1.5), a[1] - 10, a[0] + 150 * H / 1920 * (H > W ? 1 : 1.5), a[1] + H * 0.22]);  // keep bubbles off the characters' heads and bodies
    if (sh.bubbles !== false) for (const ln of T.lines || []) { // voiced lines become bubbles for speakers in the shot
      const who = heads[ln.speaker]; if (!who || !sh.bubbles) continue;
      const sl = (SCRIPT.lines || []).find(l => l.id === ln.id) || {};
      out.push(bubble({ t0: ln.start - 0.12, t1: ln.end + 0.5, text: sl.bubble || ln.text, style: sl.style, words: sl.bubble ? null : ln.words, speak: [ln.start, ln.end] }, who, t, idx++));
    }
    for (const b of (sh.extra_bubbles || [])) if (heads[b.who]) out.push(bubble({ ...b, t0: b.start, t1: b.end }, heads[b.who], t, 50 + idx++));  // silent bubbles
    return out.join('');
  }

  // ---------- constraints and props (plan 1.2) ----------
  // a target is [x, y] in the frame, or {cast: i, part: "hand_R", at: [x, y]} (a point on another character)
  let CASTS = [];
  function worldOf(tg, t, casts) {
    if (!tg) return null;
    if (Array.isArray(tg)) return tg;
    const c = casts[tg.cast]; if (!c) return null;
    return Puppet.pointOf(c.p, tg.part, tg.at || null, c.x, c.y, { ...c.pose, s: c.s, flip: c.flip });
  }
  function toLocal(p, w, x, y, s, flip) {  // frame point -> the puppet's artboard space (inverse of its root transform)
    if (!w) return null;
    const hip = (p.parts.hip && p.parts.hip.pivot) || [p.artboard[0] / 2, p.ground];
    return [(w[0] - x) / (s * flip) + hip[0], (w[1] - y) / s + (p.ground ?? p.artboard[1])];
  }
  // props switch parents over time: attach [[t, {cast, part, at} | {x, y}], ...]; each switch travels on an arc
  // v2.19 cartoon physics for props. A key spec may ask for
  //   "flight": "ballistic"  a true gravity arc that leaves the previous parent at the key time and lands on this target
  //                          exactly `travel` later (or at "arrive", which may be line-relative): sync survives re-voicing
  //   "drop": {"floor": y, "x": x, "e": 0.5, "roll": 0.6}  released at the key time: falls, bounces and rolls to rest
  // Gravity is pr.gravity px/s^2 (default 2600). Both are deterministic functions of time.
  function dropSim(pr, from, d, t0, t) {   // fixed-step integration from the release; returns {pos, bounces, spin}
    const g = pr.gravity ?? 2600, r = pr.r || 34, floor = (d.floor ?? 1500) - r, e = d.e ?? 0.5, dt = 1 / 240;
    let x = from[0], y = from[1], vy = d.vy ?? 0;
    const tFall = Math.sqrt(Math.max(0, 2 * (floor - y) / g)) || 0.3;
    let vx = d.vx ?? (d.x != null ? (d.x - x) / (tFall + 0.35) : 0), spin = 0;
    const bounces = []; let tt = t0;
    while (tt + dt <= t) {
      vy += g * dt; x += vx * dt; y += vy * dt; tt += dt;
      if (y >= floor) { y = floor; if (vy > 60) bounces.push([tt, x, floor + r]); vy = vy > 60 ? -vy * e : 0; vx *= vy === 0 ? (1 - (d.roll_friction ?? 2.2) * dt) : (d.roll ?? 0.8); }
      spin += vx * dt / r * 57.3;
    }
    return { pos: [x, y], bounces, spin };
  }
  function propPos(pr, t, casts, info) {
    const keys = pr.attach || []; if (!keys.length || t < keys[0][0]) return null;
    let k = 0; while (k + 1 < keys.length && keys[k + 1][0] <= t) k++;
    const at = spec => Array.isArray(spec) ? spec : (spec.x != null && !spec.drop ? [spec.x, spec.y] : worldOf(spec, t, casts));
    const spec = keys[k][1];
    if (spec && spec.drop && k > 0) {   // released from the previous parent: fall, bounce, roll
      const from = at(keys[k - 1][1]); if (!from) return null;
      const sim = dropSim(pr, from, spec.drop, keys[k][0], t); if (info) { info.bounces = sim.bounces; info.spin = sim.spin; }
      return sim.pos;
    }
    let pos = at(spec);
    const travel = spec && spec.arrive != null ? Math.max(0.05, spec.arrive - keys[k][0]) : (pr.travel ?? 0.35), since = t - keys[k][0];
    if (k > 0 && since < travel && pos && spec && spec.flight === 'ballistic') {   // exact projectile: lands on the target at the end of travel
      const from = at(keys[k - 1][1]) || pos, g = pr.gravity ?? 2600, T = travel, vy = (pos[1] - from[1] - g * T * T / 2) / T;
      return [from[0] + (pos[0] - from[0]) * since / T, from[1] + vy * since + g * since * since / 2];
    }
    if (k > 0 && since < travel && pos) {
      const from = at(keys[k - 1][1]) || pos, u = since / travel, e = u * u * (3 - 2 * u), lift = (pr.arc ?? 140) * 4 * u * (1 - u);
      pos = [from[0] + (pos[0] - from[0]) * e, from[1] + (pos[1] - from[1]) * e - lift];
    }
    return pos;
  }
  function propSVG(pr, t, casts) {
    const info = {}, pos = propPos(pr, t, casts, info);
    if (!pos) return '';
    const r = pr.r || 34, spin = info.spin != null ? info.spin : (pr.spin ? t * pr.spin : 0);
    if (pr.svg) return `<g transform="translate(${pos[0].toFixed(1)} ${pos[1].toFixed(1)}) rotate(${spin.toFixed(1)})">${pr.svg}</g>`;
    return `<g transform="translate(${pos[0].toFixed(1)} ${pos[1].toFixed(1)}) rotate(${spin.toFixed(1)})"><circle r="${r}" fill="${pr.color || '#e8603c'}" stroke="${INK}" stroke-width="5"/>` +
      `<path d="M${-r} 0 Q0 ${r * 0.5} ${r} 0 M0 ${-r} Q${r * 0.45} 0 0 ${r}" fill="none" stroke="${INK}" stroke-width="3" opacity="0.55"/></g>`;
  }

  function frameAt(t, bgOnly) {
    const sh = shotAt(t), st = sh.style || {};
    const tq = st.step ? Math.floor(t * st.step + 1e-6) / st.step : t;   // animate on 12s/24s like hand-drawn work
    const set = (window.SETS || {})[sh.set || 'plain'] || window.SETS.plain;
    let world = set.draw(tq, sh.set_opts || {}, W, H), ink = '';
    if (sh.underlays && !bgOnly) world += sh.underlays.filter(o => (o.start == null || tq >= o.start) && (o.end == null || tq <= o.end)).map(o => overlay(o, tq)).join('');
    const heads = {}, casts = []; CASTS = casts;
    for (const c of sh.cast || []) {
      const p = PUP[c.puppet]; if (!p) continue;
      if (bgOnly) { // the set plate for other renderers keeps each character's ground shadow
        const [x, y, s] = placeAt(c.place || { x: W / 2, y: set.floorAt ? set.floorAt(W, H) : set.floor }, tq);
        if (st.shadow !== false) world += `<ellipse cx="${x}" cy="${y + 6}" rx="${120 * s}" ry="${14 * s}" fill="#000" opacity="0.12"/>`; continue;
      }
      const tl = { ...(c.timeline || {}) }, L = libFor(p);
      if (tl.visemes_from) { tl.visemes = (T.visemes || {})[tl.visemes_from] || []; delete tl.visemes_from; }
      const [x, y, s, flip] = placeAt(c.place || { x: W / 2, y: set.floorAt ? set.floorAt(W, H) : set.floor }, tq);
      if (tl.lookat) tl.lookat = [].concat(tl.lookat).map(la => ({ ...la, target_local: toLocal(p, worldOf(la.target, tq, casts), x, y, s, flip) }));
      const pose = Acting.evaluate(p, tl, tq, L.clips, L.presets);
      casts.push({ p, x, y, s, flip, pose, c, tl, L });
      if (st.shadow !== false) world += `<ellipse cx="${x}" cy="${y + 6}" rx="${120 * s}" ry="${14 * s}" fill="#000" opacity="0.12"/>`;
      ink += Puppet.render(p, x, y, { ...pose, s, flip });
      if (c.speaker) heads[c.speaker] = Puppet.pointOf(p, 'head', (p.anchors || {}).bubble || null, x, y, { ...pose, s, flip });
    }
    if (!bgOnly) ink += (sh.props || []).map(pr => propSVG(pr, tq, casts)).join('');
    if (!bgOnly && sh.fx && window.FX) {  // motion effects from the motion itself (dbe/player/fx.js)
      const memo = {};
      const pointAt = (ci, part, tt) => { const cc = casts[ci]; if (!cc || tt < (sh.start || 0)) return null;
        const key = ci + ':' + tt.toFixed(4); let st2 = memo[key];
        if (!st2) { const [x2, y2, s2, f2] = placeAt(cc.c.place || { x: W / 2, y: set.floorAt ? set.floorAt(W, H) : set.floor }, tt); const tl2 = { ...cc.tl }; delete tl2.lookat;
          st2 = memo[key] = { x: x2, y: y2, s: s2, flip: f2, pose: Acting.evaluate(cc.p, tl2, tt, cc.L.clips, cc.L.presets) }; }
        return Puppet.pointOf(cc.p, part, null, st2.x, st2.y, { ...st2.pose, s: st2.s, flip: st2.flip }); };
      ink += FX.render(sh, tq, { casts, pointAt, propPos: (pr, tt, info) => propPos(pr, tt, casts, info) });
    }
    if (!bgOnly) { ink += (sh.overlays || []).filter(o => (o.start == null || tq >= o.start) && (o.end == null || tq <= o.end)).map(o => overlay(o, tq)).join('') + bubblesFor(sh, tq, heads); }
    world += st.boil ? `<g filter="url(#boil)">${ink}</g>` : ink;
    let svg = boilDefs(st, t) + world;
    if (st.float && !sh.camera) { const a = tq * 2 * Math.PI / 20, z = 1.012 + 0.008 * Math.sin(a * 0.7);   // slow orbit and breath (no dead frames)
      svg = boilDefs(st, t) + `<g transform="translate(${W / 2 + 6 * Math.cos(a)} ${H / 2 + 6 * Math.sin(a)}) scale(${z.toFixed(4)}) translate(${-W / 2} ${-H / 2})">${world}</g>`; }
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
  (document.fonts ? Promise.all([document.fonts.load('700 40px Fredoka'), document.fonts.load("40px 'Patrick Hand'"), document.fonts.load("30px 'Atkinson Mono'"), document.fonts.load("40px 'Noto Sans Sinhala'", "\u0DB6\u0DD2"), document.fonts.load("700 40px 'Noto Sans Sinhala'", "\u0DB6\u0DD2")]) : Promise.resolve()).then(() => { window.FILM.ready = true; window.ready = true; });
})();
