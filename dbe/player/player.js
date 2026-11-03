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
    AVOID.push([cx - rx, cy - ry, cx + rx, cy + ry]); BUBBLES.push([cx - rx, cy - ry, cx + rx, cy + ry]);
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
  let BUBBLES = [], VIEW = [0, 0, 1];   // for visual lint: bubble boxes and the camera of the last frame drawn
  // bubbles are laid out in screen space, after the camera, so a zoomed or moving shot never pushes them out of frame
  function bubblesFor(sh, t, headsWorld, view) {
    const [vx, vy, vz] = view || [W / 2, H / 2, 1], toS = ([x, y]) => [W / 2 + (x - vx) * vz, H / 2 + (y - vy) * vz];
    const heads = {}; for (const [k, a] of Object.entries(headsWorld)) heads[k] = toS(a);
    const out = []; let idx = 0; BUBBLES = [];
    AVOID = (sh.overlays || []).filter(o => (o.start == null || t >= o.start) && (o.end == null || t <= o.end)).map(overlayBox).filter(Boolean)
      .map(r => [...toS([r[0], r[1]]), ...toS([r[2], r[3]])]);
    const hw = 150 * H / 1920 * (H > W ? 1 : 1.5) * vz;
    for (const a of Object.values(heads)) AVOID.push([a[0] - hw, a[1] - 10, a[0] + hw, a[1] + H * 0.22 * vz]);  // keep bubbles off the characters' heads and bodies
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

  // ---------- camera grammar (plan 2.6): "camera_auto": true | {"zoom": 1.5, "punch": 0.06, "handheld": 0.4, "ease": 0.6} ----------
  // Speaker framing during each line (medium shot), a two-shot otherwise, eased between; punch-ins on emphasised words
  // (long or stressed); seeded handheld drift; clamped so the frame never leaves the set; heads kept above captions.
  function autoCam(sh, t, casts) {
    const o = sh.camera_auto === true ? {} : sh.camera_auto, zMax = o.zoom ?? 1.45, ease = o.ease ?? 0.6;
    const byName = {}; casts.forEach(cc => { if (cc.c.speaker) byName[cc.c.speaker] = cc; });
    const box = list => { let x0 = 1e9, x1 = -1e9, y0 = 1e9, y1 = -1e9;
      for (const cc of list) { const h = cc.p.artboard[1] * cc.s * 0.95, w = cc.p.artboard[0] * cc.s * 0.6; x0 = Math.min(x0, cc.x - w / 2); x1 = Math.max(x1, cc.x + w / 2); y0 = Math.min(y0, cc.y - h); y1 = Math.max(y1, cc.y); }
      return [x0, y0, x1, y1]; };
    const frameFor = (list, single) => { if (!list.length) return [W / 2, H / 2, 1];
      const [x0, y0, x1, y1] = box(list), frac = single ? (o.medium ?? 0.62) : 1;   // singles: a medium shot, head to waist
      const bw = (x1 - x0) * 1.25, bh = (y1 - y0) * frac * 1.15;
      const z = Math.min(single ? (sh.bubbles ? (o.zoom_bubble ?? 1.5) : (o.zoom_single ?? 1.9)) : zMax, Math.max(1, Math.min(W / bw, H * 0.82 / bh)));
      // with speech bubbles a single keeps the head top at ~31% of the frame, leaving the bubble room above it
      if (single && sh.bubbles) return [(x0 + x1) / 2, y0 + (H / 2 - H * (H > W ? 0.31 : 0.36)) / z, z];
      return [(x0 + x1) / 2, y0 + bh * 0.46 + (H / z) * 0.08, z]; };   // heads high, room below for captions
    const wide = frameFor(casts);
    const lines = (T.lines || []).filter(l => byName[l.speaker] && l.end > sh.start - 0.5 && l.start < sh.end + 0.5);
    // target per instant: the speaker while a line plays (and 0.3 s before), else the two-shot
    const target = tt => { const l = lines.find(l => tt >= l.start - 0.3 && tt <= l.end + 0.2); return l && casts.length > 1 ? frameFor([byName[l.speaker]], true) : wide; };
    // ease: blend from the previous target over `ease` seconds after each change (pure: derived from the schedule)
    let cur = target(t); const changes = [];
    for (const l of lines) changes.push(l.start - 0.3, l.end + 0.2);
    const last = changes.filter(c => c <= t).pop();
    if (last != null && t - last < ease) { const prev = target(last - 0.01), u = (t - last) / ease, e = u * u * (3 - 2 * u); cur = cur.map((v, i) => prev[i] + (v - prev[i]) * e); }
    let [cx, cy, z] = cur;
    // punch-in on emphasised words (long words in the current line), 0.06 zoom over 0.35 s
    const punch = o.punch ?? 0.05;
    if (punch) for (const l of lines) for (const w of l.words || []) { const len = w.end - w.start, letters = w.text.replace(/\W/g, '').length || 1;
      if (len / letters > 0.085 || /!$/.test(w.text)) { const d = t - w.start; if (d > -0.05 && d < 0.6) z *= 1 + punch * Math.sin(Math.PI * Math.min(1, Math.max(0, (d + 0.05) / 0.65))); } }
    // handheld drift: sum of incommensurate sines (seeded by the shot id)
    const hh = o.handheld ?? 0; if (hh) { const sd = (sh.id || 's').length * 1.7; cx += hh * 9 * (Math.sin(t * 0.71 + sd) + 0.5 * Math.sin(t * 1.93 + sd * 2)); cy += hh * 7 * (Math.sin(t * 0.83 + sd * 3) + 0.5 * Math.sin(t * 2.31 + sd)); }
    const hw = W / (2 * z), hhh = H / (2 * z);
    cx = Math.min(W - hw, Math.max(hw, cx)); cy = Math.min(H - hhh, Math.max(hhh, cy));
    return [cx, cy, z];
  }

  function frameAt(t, bgOnly) {
    const sh = shotAt(t), st = sh.style || {};
    const tq = st.step ? Math.floor(t * st.step + 1e-6) / st.step : t;   // animate on 12s/24s like hand-drawn work
    const set = (window.SETS || {})[sh.set || 'plain'] || window.SETS.plain;
    let world = castOnly ? '' : set.draw(tq, sh.set_opts || {}, W, H), ink = '';   // castonly=1: the characters alone (WP-14 renderer parity)
    if (sh.underlays && !bgOnly && !castOnly) world += sh.underlays.filter(o => (o.start == null || tq >= o.start) && (o.end == null || tq <= o.end)).map(o => overlay(o, tq)).join('');
    const heads = {}, casts = []; CASTS = casts;
    const planeInk = {}, onPlane = c => sh.comp && c.plane && c.plane !== 'stage' && !bgOnly;   // WP-36: cast members on depth planes
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
      const shadow = st.shadow !== false && !castOnly ? `<ellipse cx="${x}" cy="${y + 6}" rx="${120 * s}" ry="${14 * s}" fill="#000" opacity="0.12"/>` : '';
      const drawn = Puppet.render(p, x, y, { ...pose, s, flip, ...(st.toon ? { toon: st.toon === true ? {} : st.toon } : {}) });
      if (onPlane(c)) planeInk[c.plane] = (planeInk[c.plane] || '') + shadow + drawn;
      else { world += shadow; ink += drawn; }
      if (c.speaker) heads[c.speaker] = Puppet.pointOf(p, 'head', (p.anchors || {}).bubble || null, x, y, { ...pose, s, flip });
    }
    if (!bgOnly && !castOnly) ink += (sh.props || []).map(pr => propSVG(pr, tq, casts)).join('');
    if (!bgOnly && !castOnly && sh.fx && window.FX) {  // motion effects from the motion itself (dbe/player/fx.js)
      const memo = {};
      const pointAt = (ci, part, tt) => { const cc = casts[ci]; if (!cc || tt < (sh.start || 0)) return null;
        const key = ci + ':' + tt.toFixed(4); let st2 = memo[key];
        if (!st2) { const [x2, y2, s2, f2] = placeAt(cc.c.place || { x: W / 2, y: set.floorAt ? set.floorAt(W, H) : set.floor }, tt); const tl2 = { ...cc.tl }; delete tl2.lookat;
          st2 = memo[key] = { x: x2, y: y2, s: s2, flip: f2, pose: Acting.evaluate(cc.p, tl2, tt, cc.L.clips, cc.L.presets) }; }
        return Puppet.pointOf(cc.p, part, null, st2.x, st2.y, { ...st2.pose, s: st2.s, flip: st2.flip }); };
      ink += FX.render(sh, tq, { casts, pointAt, propPos: (pr, tt, info) => propPos(pr, tt, casts, info) });
    }
    if (!bgOnly && !castOnly) { ink += (sh.overlays || []).filter(o => (o.start == null || tq >= o.start) && (o.end == null || tq <= o.end)).map(o => overlay(o, tq)).join(''); }
    world += st.boil && !castOnly ? `<g filter="url(#boil)">${ink}</g>` : ink;   // parity frames compare geometry, without the boil
    let svg = boilDefs(st, t) + world;
    if (st.float && !sh.camera) { const a = tq * 2 * Math.PI / 20, z = 1.012 + 0.008 * Math.sin(a * 0.7);   // slow orbit and breath (no dead frames)
      svg = boilDefs(st, t) + `<g transform="translate(${W / 2 + 6 * Math.cos(a)} ${H / 2 + 6 * Math.sin(a)}) scale(${z.toFixed(4)}) translate(${-W / 2} ${-H / 2})">${world}</g>`; }
    VIEW = [W / 2, H / 2, 1];
    if (st.float && !sh.camera) { const a = tq * 2 * Math.PI / 20; VIEW = [W / 2 - 6 * Math.cos(a), H / 2 - 6 * Math.sin(a), 1.012 + 0.008 * Math.sin(a * 0.7)]; }
    if (sh.camera_auto && !sh.camera && !bgOnly) { const [cx, cy, z] = autoCam(sh, tq, casts); VIEW = [cx, cy, z];   // camera grammar (plan 2.6)
      svg = boilDefs(st, t) + `<g transform="translate(${W / 2} ${H / 2}) scale(${z.toFixed(4)}) translate(${(-cx).toFixed(2)} ${(-cy).toFixed(2)})">${world}</g>`; }
    if (sh.camera) { const [cx, cy, z] = Acting.sampleKeys(sh.camera, tq) || [W / 2, H / 2, 1]; VIEW = [cx, cy, z]; svg = boilDefs(st, t) + `<g transform="translate(${W / 2} ${H / 2}) scale(${z}) translate(${-cx} ${-cy})">${world}</g>`; }
    if (sh.comp && window.COMP && !bgOnly) {   // WP-36: depth planes with parallax and depth of field, per-plane nodes
      const view = sh.camera ? (Acting.sampleKeys(sh.camera, tq) || [W / 2, H / 2, 1]) : sh.camera_auto ? autoCam(sh, tq, casts) : [W / 2, H / 2, 1];
      VIEW = view;
      svg = boilDefs(st, t) + COMP.compose(sh, { W, H, t: tq, view, stage: world, planeInk, tag: Math.round(t * FPS),
        drawSet: (name, opts, tt) => ((window.SETS || {})[name] || window.SETS.plain).draw(tt, opts, W, H), overlay }); }
    if (!bgOnly && !castOnly) { const bub = bubblesFor(sh, tq, heads, VIEW); if (bub) svg += st.boil ? `<g filter="url(#boil)">${bub}</g>` : bub; }
    // shot renders leave captions to the film-level pass (dbe/captions.py); the live web player draws them itself
    if (!bgOnly && !castOnly && !only && q.get('captions') !== '0' && sh.captions !== false && S.captions !== false) svg += captions(t);
    return svg;
  }
  const only = q.get('shot') ? S.shots.find(s => s.id === q.get('shot')) : null;
  const bgOnly = q.get('bg') === '1';
  const castOnly = q.get('castonly') === '1';
  if (castOnly) { document.documentElement.style.background = 'transparent'; document.body.style.background = 'transparent'; }
  const t0 = only ? only.start : 0, t1 = only ? only.end : S.shots[S.shots.length - 1].end;
  window.FILMTIME = { start: t0, end: t1, fps: FPS };
  window.frameAtTime = t => { stage.innerHTML = frameAt(t, bgOnly); };
  // the camera this player frames each moment with (auto camera, float drift): other renderers bake it as camera keys (WP-14)
  window.viewsAt = ts => ts.map(t => { frameAt(t, false); return VIEW.slice(); });
  // time warp (plan 2.13, the sound-off cut): shots.json "timewarp": [[cut time, film time], ...] knots, increasing;
  // the cut is rendered on its own clock and each frame shows the film at the warped time (lines held for reading)
  const WK = S.timewarp && S.timewarp.length > 1 ? S.timewarp : null;
  const lerpK = (k, i, j, v) => { if (v <= k[0][i]) return k[0][j] + (v - k[0][i]); for (let n = 1; n < k.length; n++) if (v <= k[n][i]) { const a = k[n - 1], b = k[n]; return a[j] + (b[j] - a[j]) * (v - a[i]) / ((b[i] - a[i]) || 1); } return k[k.length - 1][j] + (v - k[k.length - 1][i]); };
  const toFilm = tc => WK ? lerpK(WK, 0, 1, tc) : tc, toCut = tf => WK ? lerpK(WK, 1, 0, tf) : tf;
  window.TIMEWARP = { toFilm, toCut };
  window.renderFrame = f => window.frameAtTime(toFilm(toCut(t0) + f / FPS));
  window.FRAMES = Math.round((toCut(t1) - toCut(t0)) * FPS);
  // ---------- foley events (plan 2.7): footsteps on contacts, thuds on landings, swishes on fast moves, pops on catches ----------
  // Returns [{t, type, gain, pan}] for the whole film, computed from the same poses the frames show.
  function foleyEvents() {
    const ev = [], dt = 1 / FPS, pan = x => Math.max(-0.8, Math.min(0.8, (x / W) * 2 - 1));
    const prev = {};
    for (const sh of S.shots) {
      for (let t = sh.start; t < sh.end; t += dt) {
        frameAt(t, false);   // sets CASTS for this instant
        CASTS.forEach((cc, ci) => {
          const key = sh.id + ':' + ci, pv = prev[key] || {};
          const hip = Puppet.pointOf(cc.p, cc.p.parts.hip ? 'hip' : Object.keys(cc.p.parts)[0], null, cc.x, cc.y, { ...cc.pose, s: cc.s, flip: cc.flip });
          const hands = ['hand_R', 'hand_L'].filter(h => cc.p.parts[h]).map(h => Puppet.pointOf(cc.p, h, null, cc.x, cc.y, { ...cc.pose, s: cc.s, flip: cc.flip }));
          // footsteps: a foot's contact turning on
          for (const f of ['foot_L', 'foot_R']) { const on = !!(cc.pose.contacts && cc.pose.contacts[f]);
            if (on && pv[f] === false) ev.push({ t: +t.toFixed(3), type: 'step', gain: 0.8, pan: pan(cc.x) }); pv[f] = on; }
          // landing: hips falling then stopping (the dust test of fx.js)
          if (pv.hipY != null && pv.vy != null) { const vy = hip[1] - pv.hipY; if (pv.vy > 3 * cc.s && vy < pv.vy * 0.35 && (pv.fall || 0) > 12 * cc.s) ev.push({ t: +t.toFixed(3), type: 'thud', gain: 1, pan: pan(cc.x) });
            pv.fall = vy > 0.5 ? (pv.fall || 0) + vy : 0; pv.vy = vy; } else if (pv.hipY != null) pv.vy = hip[1] - pv.hipY;
          // hop: hips leaving the ground fast (a boing per hop by default; "foley": {"hop": "swish" | false})
          const hopSnd = (S.foley && S.foley.hop !== undefined) ? S.foley.hop : 'boing';
          if (hopSnd && pv.hipY != null) { const vy = hip[1] - pv.hipY, up = vy < -5 * cc.s;
            if (up && !pv.up && (pv.still || 0) >= 3) ev.push({ t: +t.toFixed(3), type: hopSnd, gain: hopSnd === 'boing' ? 0.55 : 0.8, pan: pan(cc.x) });
            pv.up = up; pv.still = vy > -1.5 * cc.s ? (pv.still || 0) + 1 : (up ? pv.still : 0); }   // still = frames since the hips last rose
          pv.hipY = hip[1];
          // swish: a hand crossing 1400 px/s (once per fast move)
          hands.forEach((h, i) => { const k = 'h' + i; if (pv[k]) { const v = Math.hypot(h[0] - pv[k][0], h[1] - pv[k][1]) / dt, fast = v > 1400 * Math.max(0.6, cc.s);
            if (fast && !pv[k + 'f']) ev.push({ t: +t.toFixed(3), type: 'swish', gain: Math.min(1.2, v / 2000), pan: pan(h[0]) }); pv[k + 'f'] = fast; } pv[k] = h; });
          prev[key] = pv;
        });
      }
      // pen-scratch ambience while kit drawings draw themselves (shots' underlays and overlays of type "draw")
      if (!S.foley || S.foley.scratch !== false) for (const o of [...(sh.underlays || []), ...(sh.overlays || [])]) if (o.type === 'draw' && o.sound !== false) {
        const n = (o.paths || [o.path]).length, dur = typeof o.until === 'number' ? Math.max(0.05, o.until - (o.start ?? 0)) : (typeof o.duration === 'number' ? o.duration : 1.2);
        const stag = o.stagger ?? dur / Math.max(1, n), len = Math.min(sh.end - (o.start ?? 0), dur + stag * (n - 1));
        if (len > 0.15) ev.push({ t: +(o.start ?? 0).toFixed(3), type: 'scratch', dur: +len.toFixed(3), gain: 1, pan: pan(o.x ?? W / 2) }); }
      // catches and drops: a prop arriving at the end of its travel, bounces of drops
      for (const pr of sh.props || []) { const keys = pr.attach || [];
        for (let k = 1; k < keys.length; k++) { const spec = keys[k][1] || {};
          if (spec.drop) { const info = {}; propPos(pr, sh.end, CASTS, info); (info.bounces || []).forEach(([bt, bx], i) => ev.push({ t: +bt.toFixed(3), type: 'thud', gain: Math.max(0.3, 0.9 - i * 0.25), pan: pan(bx) })); continue; }
          const arrive = spec.arrive != null ? spec.arrive : keys[k][0] + (pr.travel ?? 0.35); const pos = propPos(pr, arrive, CASTS);
          if (arrive < sh.end) ev.push({ t: +arrive.toFixed(3), type: 'pop_small', gain: 0.9, pan: pan(pos ? pos[0] : W / 2) }); } }
    }
    return ev.sort((a, b) => a.t - b.t);
  }
  window.FOLEY = foleyEvents;

  // ---------- visual lint (plan 2.8): problems in the picture, with frame ranges ----------
  // off-screen limbs and heads, bubbles over faces, faces under the caption band, arms locked straight by IK,
  // silhouettes tangent to the frame edge or to each other, props passing through someone who is not holding them.
  function visualLint(step = 3) {
    const hits = [], dt = 1 / FPS;
    const scr = ([x, y]) => [W / 2 + (x - VIEW[0]) * VIEW[2], H / 2 + (y - VIEW[1]) * VIEW[2]];
    const capTop = H - (H > W ? 420 : 260);   // where burned-in captions sit
    for (const sh of S.shots) {
      for (let f = Math.ceil(sh.start * FPS); f < sh.end * FPS; f += step) {
        const t = f / FPS; frameAt(t, false);
        const faces = [];
        CASTS.forEach((cc, ci) => {
          const P = (part, at) => cc.p.parts[part] ? scr(Puppet.pointOf(cc.p, part, at || null, cc.x, cc.y, { ...cc.pose, s: cc.s, flip: cc.flip })) : null;
          const k = cc.s * VIEW[2], name = cc.c.speaker || cc.p.name || 'cast ' + ci;
          // head box (around the head pivot, up to the bubble anchor)
          const hb = cc.p.anchors && cc.p.anchors.bubble ? P('head', cc.p.anchors.bubble) : null, hp = P('head');
          if (hp) { const top = hb ? hb[1] : hp[1] - 180 * k; faces.push({ ci, name, box: [hp[0] - 85 * k, top, hp[0] + 85 * k, hp[1] + 20 * k] }); }
          // off-screen, only for someone who is in the shot (their body is on screen): a head cut by the frame is an error;
          // a hand leaving the frame is a warning; feet out of frame only matter in a wide shot (z near 1), where nothing should be cropped
          const out = q => q && (q[0] < -10 || q[0] > W + 10 || q[1] < -10 || q[1] > H + 10), body = P('body') || P('hip');
          if (body && !out(body)) {
            const hd = P('head'); if (hd && (out(hd) || hd[1] - 150 * k < -10)) hits.push({ f, shot: sh.id, check: 'off-screen', level: 'error', who: name, msg: 'the head is cut by the frame' });
            for (const part of ['hand_R', 'hand_L']) if (out(P(part))) hits.push({ f, shot: sh.id, check: 'off-screen', level: 'warn', who: name, msg: `${part} leaves the frame` });
            if (VIEW[2] < 1.05) for (const part of ['foot_R', 'foot_L']) if (out(P(part))) hits.push({ f, shot: sh.id, check: 'off-screen', level: 'warn', who: name, msg: `${part} is cropped in a wide shot` });
          }
          // IK over-extension: the arm is straight while an IK target is set for it
          for (const side of ['R', 'L']) { const ik = (cc.tl.ik || {})['arm_' + side]; if (!ik) continue;
            const a = P('upperarm_' + side), b = P('forearm_' + side), c = P('hand_' + side); if (!a || !b || !c) continue;
            const full = Math.hypot(b[0] - a[0], b[1] - a[1]) + Math.hypot(c[0] - b[0], c[1] - b[1]), reach = Math.hypot(c[0] - a[0], c[1] - a[1]);
            if (reach > full * 0.997) hits.push({ f, shot: sh.id, check: 'ik overextended', level: 'warn', who: name, msg: `arm_${side} is locked straight: its target is out of reach` }); }
        });
        // bubbles over faces (any face but the speaker's own anchor region below the bubble)
        for (const bb of BUBBLES) for (const fc of faces) { const ix = Math.min(bb[2], fc.box[2]) - Math.max(bb[0], fc.box[0]), iy = Math.min(bb[3], fc.box[3]) - Math.max(bb[1], fc.box[1]);
          if (ix > 12 && iy > 12 && ix * iy > 0.12 * (fc.box[2] - fc.box[0]) * (fc.box[3] - fc.box[1])) hits.push({ f, shot: sh.id, check: 'bubble over face', level: 'error', who: fc.name, msg: 'a speech bubble covers the face' }); }
        // faces under the caption band (captions on)
        if (S.captions !== false) for (const fc of faces) if (Math.min(fc.box[3], H) - Math.max(fc.box[1], capTop) > 0.3 * (fc.box[3] - fc.box[1])) hits.push({ f, shot: sh.id, check: 'face under captions', level: 'warn', who: fc.name, msg: 'the face sits where captions are burned in' });
        // tangents: a silhouette edge within 6 px of the frame edge, or two characters' boxes almost touching
        const boxes = CASTS.map((cc, ci) => { const pts = ['head', 'hand_R', 'hand_L', 'foot_R', 'foot_L', 'arm_R', 'arm_L', 'body'].filter(p => cc.p.parts[p]).map(p => scr(Puppet.pointOf(cc.p, p, null, cc.x, cc.y, { ...cc.pose, s: cc.s, flip: cc.flip })));
          if (!pts.length) return null; const pad = 30 * cc.s * VIEW[2]; return [Math.min(...pts.map(q => q[0])) - pad, Math.min(...pts.map(q => q[1])) - pad, Math.max(...pts.map(q => q[0])) + pad, Math.max(...pts.map(q => q[1])) + pad, cc.c.speaker || cc.p.name || 'cast ' + ci]; });
        boxes.forEach(b => { if (b && ((b[0] > 0 && b[0] < 6) || (b[2] < W && b[2] > W - 6))) hits.push({ f, shot: sh.id, check: 'tangent', level: 'info', who: b[4], msg: 'the silhouette just touches the frame edge (move it in or crop it clearly)' }); });
        for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++) { const a = boxes[i], b = boxes[j]; if (!a || !b) continue;
          const gap = Math.max(b[0] - a[2], a[0] - b[2]); if (gap > -4 && gap < 4 && Math.min(a[3], b[3]) > Math.max(a[1], b[1])) hits.push({ f, shot: sh.id, check: 'tangent', level: 'info', who: a[4] + ' / ' + b[4], msg: 'two characters just touch: overlap them clearly or separate them' }); }
        // props through bodies: a prop inside a head that is not its current parent
        for (const pr of sh.props || []) { const pos0 = propPos(pr, t, CASTS); if (!pos0) continue; const pos = scr(pos0), r = (pr.r || 34) * VIEW[2];
          const keys = pr.attach || []; let kk = 0; while (kk + 1 < keys.length && keys[kk + 1][0] <= t) kk++; const holder = (keys[kk] && keys[kk][1] || {}).cast;
          for (const fc of faces) if (fc.ci !== holder && pos[0] > fc.box[0] - r * 0.5 && pos[0] < fc.box[2] + r * 0.5 && pos[1] > fc.box[1] && pos[1] < fc.box[3]) hits.push({ f, shot: sh.id, check: 'prop through body', level: 'warn', who: fc.name, msg: `prop ${pr.id || ''} passes through the head` }); }
      }
    }
    // group consecutive frames of the same problem into ranges
    const runs = [], key = h => h.shot + '|' + h.check + '|' + h.who + '|' + h.msg;
    hits.sort((a, b) => key(a) < key(b) ? -1 : key(a) > key(b) ? 1 : a.f - b.f);
    for (const h of hits) { const r = runs[runs.length - 1];
      if (r && key(r) === key(h) && h.f - r.to <= step) r.to = h.f; else runs.push({ ...h, from: h.f, to: h.f }); }
    // one-sample flickers (a camera move passing by) are noise unless they are errors
    return runs.filter(r => r.level === 'error' || r.to > r.from).map(({ f, ...r }) => ({ ...r, t0: +(r.from / FPS).toFixed(2), t1: +(r.to / FPS).toFixed(2) })).sort((a, b) => a.from - b.from);
  }
  window.LINT = visualLint;
  // motion probe (plan 3.4): a part's position on screen over a span, for the review critic's before/after checks
  window.PROBE = (ci, part, t0, t1, fps = FPS) => { const out = [];
    for (let f = Math.ceil(t0 * fps); f <= t1 * fps; f++) { const t = f / fps; frameAt(t, false); const cc = CASTS[ci]; if (!cc || !cc.p.parts[part]) { out.push([+t.toFixed(3), null, null]); continue; }
      const q = Puppet.pointOf(cc.p, part, null, cc.x, cc.y, { ...cc.pose, s: cc.s, flip: cc.flip });
      out.push([+t.toFixed(3), +(W / 2 + (q[0] - VIEW[0]) * VIEW[2]).toFixed(1), +(H / 2 + (q[1] - VIEW[1]) * VIEW[2]).toFixed(1)]); }
    return out; };
  window.FILM = { width: W, height: H, fps: FPS, frames: window.FRAMES, ready: false };
  (document.fonts ? Promise.all([document.fonts.load('700 40px Fredoka'), document.fonts.load("40px 'Patrick Hand'"), document.fonts.load("30px 'Atkinson Mono'"), document.fonts.load("40px 'Noto Sans Sinhala'", "\u0DB6\u0DD2"), document.fonts.load("700 40px 'Noto Sans Sinhala'", "\u0DB6\u0DD2")]) : Promise.resolve()).then(() => { window.FILM.ready = true; window.ready = true; });
})();
