// "Why farmers rotate clover" — every pixel is a function of the frame number.
// Timing comes from timing.json (narration word times); nothing here uses a
// clock or unseeded randomness.
(function () {
  const { clamp, lerp, inv, ease, spring, keys, noise, rand, blink, pop, tf } = M;
  const T = M.bindTiming(window.TIMING);
  const FPS = 30, W = 1080, H = 1920;
  const END = 32.3;
  const at = (line, word, nth = 0) => T.word(line, word, nth).start;
  const L = T.lines;

  // ---------- style bible ----------
  const C = {
    ink: '#3a2618',
    skyTop: '#79c6ee', skyBot: '#e2f5fb', duskTop: '#4f4f9e', duskBot: '#f5ad78',
    leaf: '#5fb33d', leafHi: '#86cf5a', leafMark: '#d4f0b4', leafDead: '#a8894c',
    soil: '#8a5c3c', soilDeep: '#5f3d27', soilLine: '#74492e',
    root: '#ecd6a9', nodule: '#ef9f95',
    nitro: '#58aef0', ammonia: '#c3f45f', bact: '#f5a94b',
    cream: '#fff8e8', white: '#ffffff',
  };
  const GROUND = 1080;
  const CLOVER_X = 330, CORN_X = 690;
  const ROOT_SX = 1.05, ROOT_SY = 0.78; // roots are squashed so captions stay clear
  const SAFE = { left: 70, right: 920, top: 230, bottom: 1520 };

  // ---------- small svg helpers ----------
  const hex = h => [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16));
  const col = (a, b, t) => {
    const A = hex(a), B = hex(b);
    return '#' + A.map((v, i) => Math.round(lerp(v, B[i], clamp(t))).toString(16).padStart(2, '0')).join('');
  };
  const f2 = n => n.toFixed(2);
  const path = (d, fill, sw = 6, stroke = C.ink, extra = '') =>
    `<path d="${d}" fill="${fill}" stroke="${stroke}" stroke-width="${sw}" stroke-linejoin="round" stroke-linecap="round" ${extra}/>`;
  const circle = (x, y, r, fill, sw = 6, stroke = C.ink, extra = '') =>
    `<circle cx="${f2(x)}" cy="${f2(y)}" r="${f2(Math.max(0, r))}" fill="${fill}" stroke="${stroke}" stroke-width="${sw}" ${extra}/>`;
  const ell = (x, y, rx, ry, fill, sw = 6, stroke = C.ink, extra = '') =>
    `<ellipse cx="${f2(x)}" cy="${f2(y)}" rx="${f2(Math.max(0, rx))}" ry="${f2(Math.max(0, ry))}" fill="${fill}" stroke="${stroke}" stroke-width="${sw}" ${extra}/>`;
  const G = (transform, inner, extra = '') => `<g transform="${transform}" ${extra}>${inner}</g>`;
  // tube: ink outline under a coloured stroke, for stems and roots
  const tube = (d, color, w, ink = 6) =>
    `<path d="${d}" fill="none" stroke="${C.ink}" stroke-width="${w + ink * 2}" stroke-linecap="round" stroke-linejoin="round"/>` +
    `<path d="${d}" fill="none" stroke="${color}" stroke-width="${w}" stroke-linecap="round" stroke-linejoin="round"/>`;

  // ---------- face ----------
  // mood: happy | curious | sad | wink | sleep | open | chomp
  function face(o) {
    const { x = 0, y = 0, s = 1, mood = 'happy', lookX = 0, lookY = 0, bl = 0, talk = 0, sep = 21 } = o;
    let out = '';
    const eye = (ex, closed, kind) => {
      if (kind === 'wink' || kind === 'sleep') {
        const d = kind === 'sleep' ? `M${ex - 11} -2 Q${ex} 8 ${ex + 11} -2` : `M${ex - 11} 3 Q${ex} -9 ${ex + 11} 3`;
        return path(d, 'none', 5);
      }
      const ry = 16 * (1 - closed * 0.92);
      return ell(ex, 0, 13.5, ry, C.white, 4.5) +
        (closed < 0.7 ? circle(ex + lookX * 4.5, lookY * 4.5 + 1, 7.5 * (1 - closed * 0.5), C.ink, 0) +
          circle(ex + lookX * 4.5 + 2.6, lookY * 4.5 - 2.2, 2.4, C.white, 0) : '');
    };
    const lw = mood === 'wink' ? 'wink' : mood === 'sleep' ? 'sleep' : null;
    out += eye(-sep, bl, mood === 'sleep' ? 'sleep' : null);
    out += eye(sep, bl, lw);
    if (mood === 'sad') {
      out += path(`M${-sep - 12} -24 L${-sep + 8} -19`, 'none', 4.5) + path(`M${sep + 12} -24 L${sep - 8} -19`, 'none', 4.5);
    }
    if (mood === 'curious') out += path(`M${sep - 10} -27 Q${sep} -33 ${sep + 11} -26`, 'none', 4.5);
    // mouth
    const my = 30;
    if (mood === 'sad') out += path(`M-11 ${my + 4} Q0 ${my - 6} 11 ${my + 4}`, 'none', 5);
    else if (mood === 'open' || mood === 'chomp' || talk > 0.05) {
      const h = mood === 'chomp' ? 4 + talk * 16 : 6 + talk * 10;
      out += path(`M-12 ${my - 2} Q0 ${my - 4} 12 ${my - 2} Q8 ${my + h} 0 ${my + h} Q-8 ${my + h} -12 ${my - 2} Z`, '#8c2f2a', 4.5);
    } else if (mood === 'curious') out += path(`M-7 ${my} Q0 ${my - 3} 7 ${my + 1}`, 'none', 5);
    else out += path(`M-13 ${my - 3} Q0 ${my + 10} 13 ${my - 3}`, 'none', 5);
    // cheeks
    if (mood !== 'sad') out += ell(-sep - 14, 20, 8, 5, '#ff8f86', 0, 'none', 'opacity="0.55"') + ell(sep + 14, 20, 8, 5, '#ff8f86', 0, 'none', 'opacity="0.55"');
    return G(tf(x, y, 0, s), out);
  }

  // ---------- clover ----------
  const HEART = 'M0 0 C-22 -18 -62 -48 -62 -84 C-62 -116 -30 -128 0 -102 C30 -128 62 -116 62 -84 C62 -48 22 -18 0 0 Z';
  function leaflet(rot, s, fill, markOpacity, inner = '', fold = 0) {
    return G(tf(0, 0, rot, s * (1 - 0.55 * fold), s * (1 - 0.2 * fold)),
      path(HEART, fill, 6) +
      `<path d="M-30 -74 Q0 -46 30 -74" fill="none" stroke="${C.leafMark}" stroke-width="8" stroke-linecap="round" opacity="${markOpacity}"/>` +
      `<path d="M-40 -96 Q-46 -84 -40 -70" fill="none" stroke="${C.white}" stroke-width="5" stroke-linecap="round" opacity="0.35"/>` + inner);
  }
  function flower(x, y, s, t) {
    if (s <= 0.001) return '';
    let petals = '';
    for (let i = 0; i < 18; i++) {
      const a = (i / 18) * Math.PI * 2, r = 30 + (i % 2) * 6;
      petals += ell(Math.cos(a) * r * 0.55, Math.sin(a) * r * 0.55 - 4, 9, 20, i % 3 ? C.white : '#ffe6ef', 3.5, C.ink,
        `transform="rotate(${f2(a * 180 / Math.PI + 90)} ${f2(Math.cos(a) * r * 0.55)} ${f2(Math.sin(a) * r * 0.55 - 4)})"`);
    }
    return G(tf(x, y, noise(9, t * 0.7) * 4, s), petals + circle(0, -4, 14, '#fff3c9', 3.5));
  }
  // o: t, s, wilt, sink, flower, mood, look, bl, talk, sq (squash), seed, face
  function clover(x, o) {
    const t = o.t, s = o.s, seed = o.seed || 1;
    const wilt = o.wilt || 0;
    const sway = noise(seed, t * 0.55) * 3 + noise(seed + 7, t * 1.3) * 1.2;
    const Hs = 255;
    const bend = wilt * 34 + sway;                     // degrees the tip leans
    const a = (bend * Math.PI) / 180;
    const tipX = Math.sin(a) * Hs * (1 - wilt * 0.25), tipY = -Math.cos(a) * Hs * (1 - wilt * 0.25);
    const ctrlX = tipX * 0.15, ctrlY = tipY * 0.6;
    const leafCol = col(C.leaf, C.leafDead, wilt), stemCol = col('#4fa034', '#8d7440', wilt);
    let out = '';
    // flower on its own stalk
    const fl = o.flower || 0;
    if (fl > 0) {
      const fx = -48 + Math.sin(a) * 40, fy = -Hs * 0.95 * ease.outCubic(fl);
      out += tube(`M-6 0 Q-30 ${f2(fy * 0.5)} ${f2(fx)} ${f2(fy)}`, stemCol, 8, 5);
      out += circle(fx, fy, 9 * Math.min(1, fl * 3), '#e9f7d9', 4) + flower(fx, fy, M.pop(o.t, o.flowerAt || 0, 0.5).s * (1 - wilt * 0.4), t);
    }
    out += tube(`M0 0 Q${f2(ctrlX)} ${f2(ctrlY)} ${f2(tipX)} ${f2(tipY)}`, stemCol, 12, 6);
    const leafRot = bend * 1.1 + wilt * 22;
    const lS = 1.08;
    const mk = 0.75 * (1 - wilt);
    const fc = o.face === false ? '' : face({ x: 0, y: -72, s: 0.95, mood: o.mood, lookX: o.lookX || 0, lookY: o.lookY || 0, bl: o.bl || 0, talk: o.talk || 0 });
    const crown =
      leaflet(-62 + noise(seed + 3, t) * 3 + wilt * 30, lS * 0.92, leafCol, mk, '', wilt) +
      leaflet(62 + noise(seed + 4, t) * 3 - wilt * 30, lS * 0.92, leafCol, mk, '', wilt) +
      leaflet(0, lS * (1 - 0.15 * wilt), col(C.leafHi, C.leafDead, wilt), mk, fc, wilt * 0.4);
    const sq = o.sq || [1, 1];
    out += G(`translate(${f2(tipX)} ${f2(tipY)}) rotate(${f2(leafRot)}) scale(${f2(sq[0])} ${f2(sq[1])})`, crown);
    return G(tf(x, GROUND + 6 + (o.sink || 0), 0, s), out);
  }

  // ---------- roots ----------
  const CLOVER_ROOTS = [
    'M0 0 C4 60 -6 120 6 190 C12 230 4 260 10 300',
    'M3 70 C-30 90 -60 110 -96 160',
    'M-50 104 C-60 130 -78 150 -84 196',
    'M5 120 C40 140 70 150 104 196',
    'M60 148 C70 170 66 200 80 236',
    'M7 210 C-24 230 -40 250 -52 290',
  ];
  // nodule positions (local to root origin), first one is the hero nodule
  const NODULES = [[-62, 116, 15], [52, 143, 13], [-82, 178, 12], [8, 240, 13], [-36, 262, 11], [88, 214, 11], [-2, 160, 10]];
  function roots(x, o) {
    const fade = o.fade || 0;
    const rc = col(C.root, '#9a7a55', fade);
    let out = '';
    for (const d of CLOVER_ROOTS) out += tube(d, rc, 9, 5);
    NODULES.forEach(([nx, ny, r], i) => {
      const p = o.nodulePop ? M.pop(o.t, o.nodulePop + i * 0.05, 0.45) : { s: 1 };
      const base = 0.65 + 0.35 * p.s;
      const pulse = o.pulse ? 1 + 0.12 * Math.exp(-Math.max(0, o.t - o.pulse - i * 0.05) * 4) * Math.sin(Math.max(0, o.t - o.pulse - i * 0.05) * 18) : 1;
      const R = r * base * pulse * (1 - fade * 0.6);
      out += circle(nx, ny, R, col(C.nodule, '#9a7a55', fade), 4.5) + circle(nx - R * 0.35, ny - R * 0.35, R * 0.28, '#ffd9d2', 0, 'none', `opacity="${1 - fade}"`);
    });
    return G(tf(x, GROUND + 18, 0, ROOT_SX, ROOT_SY), out, `opacity="${1 - (o.gone || 0)}"`);
  }
  const NODULE_WORLD = () => [CLOVER_X + NODULES[0][0] * ROOT_SX, GROUND + 18 + NODULES[0][1] * ROOT_SY];
  const CORN_ROOTS = ['M0 0 C-8 50 -30 90 -48 140', 'M0 0 C6 60 4 110 10 160', 'M0 0 C14 46 36 86 56 130', 'M-4 30 C-40 50 -64 70 -84 96', 'M4 34 C36 52 60 72 82 100'];
  function cornRoots(x, g) {
    let out = '';
    for (const d of CORN_ROOTS) out += tube(d, C.root, 7, 4.5);
    return G(tf(x, GROUND + 14, 0, 0.35 + 0.65 * g, 0.3 + 0.7 * g), out);
  }

  // ---------- corn ----------
  // o: t, grow, health, mood, flinch, s, face, cob, seed, bl, look
  function corn(x, o) {
    const t = o.t, g = o.grow, seed = o.seed || 2;
    const Hh = lerp(150, 560, g);
    const w = lerp(28, 42, g);
    const leafC = col('#a7c25a', '#4e9d31', o.health), leafHi = col('#c4d97a', '#6dbb47', o.health);
    const sway = noise(seed, t * 0.5) * 2.5 + (o.flinch || 0);
    let out = '';
    // tassel
    if (g > 0.6) {
      const ts = inv(0.6, 1, g);
      for (let i = -2; i <= 2; i++) out += tube(`M0 ${-Hh + 4} q${i * 10} -30 ${i * 22} -${50 + (2 - Math.abs(i)) * 14}`, '#e3c24f', 5, 3.5).replace(/<path/g, `<path opacity="${ts}"`);
    }
    // stalk
    out += path(`M${-w / 2} 0 C${-w / 2} ${-Hh * 0.5} ${-w * 0.3} ${-Hh * 0.8} ${-w * 0.18} ${-Hh} L${w * 0.18} ${-Hh} C${w * 0.3} ${-Hh * 0.8} ${w / 2} ${-Hh * 0.5} ${w / 2} 0 Z`, leafC, 6);
    out += path(`M${-w * 0.15} -10 L${-w * 0.06} ${-Hh + 20}`, 'none', 4, leafHi);
    // leaves
    const n = 6;
    for (let i = 0; i < n; i++) {
      const app = i < 3 ? 1 : clamp((g - (i - 3) * 0.2) / 0.22);
      if (app <= 0) continue;
      const dir = i % 2 ? 1 : -1;
      const hy = -Hh * (i < 2 ? 0.55 + i * 0.18 : 0.18 + (i - 2) * 0.17);
      const Ln = (i < 3 ? lerp(118 - i * 14, 150, g) : 150 + i * 8) * ease.outBack(app);
      const droop = lerp(0.05, -0.15, o.health) + noise(seed + i, t * 0.8) * 0.06 + (1 - o.health) * 0.35;
      const d = `M0 0 Q${dir * Ln * 0.55} ${-Ln * (0.5 - droop)} ${dir * Ln} ${Ln * droop} Q${dir * Ln * 0.5} ${-Ln * (0.32 - droop)} 0 -16 Z`;
      out += G(tf(dir * w * 0.3, hy, 0, 1), path(d, i % 2 ? leafC : leafHi, 5.5) +
        `<path d="M0 -8 Q${dir * Ln * 0.5} ${-Ln * (0.4 - droop)} ${dir * Ln * 0.92} ${Ln * droop}" fill="none" stroke="${leafHi}" stroke-width="3" opacity="0.8"/>`);
    }
    // cob
    if ((o.cob || 0) > 0) {
      const cp = o.cob;
      let k = '';
      for (let r = 0; r < 7; r++) for (let c2 = -1; c2 <= 1; c2++) k += ell(c2 * 11, -20 - r * 14, 5, 6, '#ffd84d', 2, '#c99a1d');
      out += G(tf(w * 0.45, -Hh * 0.5, 28, cp),
        ell(0, -62, 24, 58, '#ffd23f', 5) + k +
        path('M-18 -10 Q-34 -60 -10 -118 Q-14 -60 4 -6 Z', '#6fbe46', 5) + path('M18 -10 Q34 -64 14 -112 Q10 -56 -2 -6 Z', '#5aa83a', 5));
    }
    if (o.face !== false) {
      out += face({ x: 0, y: -Hh * lerp(0.55, 0.42, g), s: lerp(0.78, 0.95, g), mood: o.mood, bl: o.bl || 0, lookX: o.lookX || 0, lookY: o.lookY || 0, talk: o.talk || 0, sep: 19 });
    }
    const sq = o.sq || [1, 1];
    return G(`translate(${f2(x)} ${GROUND + 8}) rotate(${f2(sway)}) scale(${f2(o.s * sq[0])} ${f2(o.s * sq[1])})`, out);
  }

  // ---------- molecules & microbes ----------
  function n2(x, y, s, rot, o = {}) {
    const a = 22;
    let out = circle(-a * 0.8, 0, a, C.nitro, 5) + circle(a * 0.8, 0, a, C.nitro, 5);
    out += circle(-a * 0.8 - 8, -9, 6, '#bfe3ff', 0) + circle(a * 0.8 - 8, -9, 6, '#bfe3ff', 0);
    out += `<text x="${-a * 0.8}" y="9" font-size="24" font-weight="700" fill="#fff" text-anchor="middle">N</text><text x="${a * 0.8}" y="9" font-size="24" font-weight="700" fill="#fff" text-anchor="middle">N</text>`;
    if (o.tag) out += tag(0, -54, 'N₂', C.nitro, o.tag);
    return G(tf(x, y, rot, s), out, o.op !== undefined ? `opacity="${o.op}"` : '');
  }
  function nh3(x, y, s, o = {}) {
    let out = `<circle cx="0" cy="0" r="46" fill="url(#glow)" opacity="${o.glow ?? 0.9}"/>`;
    [[-24, -14], [24, -14], [0, 26]].forEach(([hx, hy]) => { out += circle(hx, hy, 11, C.white, 4); });
    out += circle(0, 0, 20, C.nitro, 5) + `<text x="0" y="8" font-size="22" font-weight="700" fill="#fff" text-anchor="middle">N</text>`;
    if (o.tag) out += tag(0, -62, 'NH₃', '#6aa21c', o.tag);
    return G(tf(x, y, 0, s), out);
  }
  function tag(x, y, label, color, p) {
    const s = M.pop(p.t, p.at, 0.4);
    if (s.s <= 0.01) return '';
    const w = label.length * 19 + 34;
    return G(tf(x, y, 0, s.sx, s.sy), `<rect x="${-w / 2}" y="-24" width="${w}" height="44" rx="22" fill="${C.white}" stroke="${C.ink}" stroke-width="4.5"/>` +
      `<text x="0" y="9" font-size="28" font-weight="700" fill="${color}" text-anchor="middle">${label}</text>`);
  }
  // the travelling nitrogen keeps the NH3 look it had in the window
  function nDot(x, y, s, op = 1) {
    return G(tf(x, y, 0, s), nh3(0, 0, 1, { glow: 0.8 }), `opacity="${f2(clamp(op))}"`);
  }
  function glowDot(x, y, r, op = 1) {
    return `<circle cx="${f2(x)}" cy="${f2(y)}" r="${f2(r * 2.6)}" fill="url(#glow)" opacity="${f2(op * 0.85)}"/>` +
      `<circle cx="${f2(x)}" cy="${f2(y)}" r="${f2(r)}" fill="${C.ammonia}" stroke="#4d7d14" stroke-width="3" opacity="${f2(op)}"/>`;
  }
  // o: t, chomp(0..1), s, seed, mood
  function rhizobium(x, y, rot, o) {
    const t = o.t, ph = t * 7 + (o.seed || 0);
    const wig = Math.sin(ph) * 6;
    let tail = 'M-58 0';
    for (let i = 1; i <= 6; i++) tail += ` Q${-58 - i * 14 + 7} ${f2(Math.sin(ph + i * 1.3) * 14)} ${-58 - i * 14} ${f2(Math.sin(ph + i * 1.3 + 0.6) * 4)}`;
    const sq = 1 + (o.chomp || 0) * 0.14;
    const ex = o.sq || [1, 1];
    let out = `<path d="${tail}" fill="none" stroke="${C.ink}" stroke-width="5" stroke-linecap="round"/>`;
    out += G(`scale(${f2(sq * ex[0])} ${f2(ex[1] / sq)})`,
      `<rect x="-62" y="-30" width="124" height="60" rx="30" fill="${C.bact}" stroke="${C.ink}" stroke-width="5.5"/>` +
      `<rect x="-44" y="-21" width="70" height="12" rx="6" fill="#ffd79a" opacity="0.8"/>` +
      circle(-30, 12, 4, '#d9852a', 0) + circle(-14, 18, 3, '#d9852a', 0) +
      face({ x: 24, y: -6, s: 0.62, mood: o.mood || 'happy', bl: blink(t, (o.seed || 0) + 11, 2.7), talk: o.talk || 0, lookX: 0.4 }));
    return G(tf(x, y + wig * 0.3, rot + wig * 0.4, o.s || 1), out);
  }

  // ---------- environment ----------
  function sky(t, dusk) {
    const top = col(C.skyTop, C.duskTop, dusk), bot = col(C.skyBot, C.duskBot, dusk);
    let stars = '';
    if (dusk > 0.01) for (let i = 0; i < 14; i++) {
      const x = 60 + rand(i + 40) * 960, y = 120 + rand(i + 90) * 600;
      stars += circle(x, y, 3 + rand(i) * 3, '#fff6d6', 0, 'none', `opacity="${f2(dusk * (0.55 + 0.45 * Math.sin(t * 3 + i)))}"`);
    }
    return `<defs><linearGradient id="sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${top}"/><stop offset="1" stop-color="${bot}"/></linearGradient>` +
      `<radialGradient id="glow"><stop offset="0" stop-color="${C.ammonia}" stop-opacity="0.9"/><stop offset="1" stop-color="${C.ammonia}" stop-opacity="0"/></radialGradient>` +
      `<radialGradient id="spot"><stop offset="0.55" stop-color="#fff" stop-opacity="0.16"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>` +
      `<clipPath id="above"><rect x="-2000" y="-3000" width="5000" height="${3000 + GROUND + 4}"/></clipPath>` +
      `</defs><rect x="0" y="0" width="${W}" height="${H}" fill="url(#sky)"/>` + stars;
  }
  function cloud(x, y, s, seed) {
    const blobs = [[0, 0, 56], [-60, 14, 40], [58, 12, 44], [-22, -26, 40], [28, -30, 36]];
    let back = '', front = '';
    blobs.forEach(([bx, by, r]) => { back += circle(bx, by, r, '#fff', 10, '#a9d6ea'); front += circle(bx, by, r, '#fff', 0); });
    return G(tf(x, y, 0, s), back + front + ell(0, 28, 90, 10, '#e4f3fa', 0, 'none'));
  }
  function hills(dusk) {
    const tint = c => col(c, '#7d6a9e', dusk * 0.45);
    let out = path(`M-600 ${GROUND} L-600 900 C-300 820 -60 880 180 860 C420 840 600 760 860 800 C1100 840 1300 820 1700 860 L1700 ${GROUND} Z`, tint('#b9de8a'), 5, col('#7fb05a', '#5b4f78', dusk * 0.5));
    out += path(`M-600 ${GROUND} L-600 980 C-200 930 100 990 380 960 C640 932 900 900 1180 950 C1400 990 1600 960 1700 970 L1700 ${GROUND} Z`, tint('#97cb64'), 5, col('#6aa046', '#5b4f78', dusk * 0.5));
    // barn
    out += G(tf(880, 930, 0, 0.9),
      path('M-60 0 L-60 -70 L0 -112 L60 -70 L60 0 Z', tint('#cf5a3f'), 5) +
      path('M-22 0 L-22 -40 L22 -40 L22 0 Z', tint('#f6efe0'), 4) + path('M-22 -40 L22 0 M22 -40 L-22 0', 'none', 4) +
      path('M-66 -66 L0 -118 L66 -66', 'none', 8, tint('#f6efe0')));
    // round trees
    [[-40, 905, 1], [90, 900, 0.8], [620, 905, 0.9], [1010, 930, 0.7]].forEach(([tx, ty, ts], i) => {
      out += G(tf(tx, ty, 0, ts), tube('M0 0 L0 -40', '#8a5c3c', 10, 4) + circle(-18, -60, 34, tint('#5ea840'), 5) + circle(20, -66, 38, tint('#6bb64b'), 5) + circle(0, -92, 32, tint('#78c256'), 5));
    });
    return out;
  }
  function ground(t, dusk) {
    let out = `<defs><linearGradient id="soilg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${C.soil}"/><stop offset="1" stop-color="${C.soilDeep}"/></linearGradient></defs>`;
    out += `<rect x="-800" y="${GROUND + 14}" width="2700" height="1600" fill="url(#soilg)"/>`;
    for (let i = 0; i < 4; i++) {
      const y = GROUND + 190 + i * 170;
      out += `<path d="M-800 ${y} C-400 ${y - 26} -100 ${y + 22} 300 ${y} C700 ${y - 24} 1000 ${y + 20} 1900 ${y - 6}" fill="none" stroke="${C.soilLine}" stroke-width="7" opacity="0.6"/>`;
    }
    for (let i = 0; i < 46; i++) {
      const x = -300 + rand(i + 3) * 1700, y = GROUND + 60 + rand(i + 50) * 860, r = 6 + rand(i + 99) * 12;
      out += ell(x, y, r * 1.4, r, i % 3 ? '#a37b58' : '#7b5134', 3.5, '#5a3a24');
    }
    // grass band with tufts
    let tufts = `M-800 ${GROUND + 18} L-800 ${GROUND - 4}`;
    for (let x = -800; x <= 1900; x += 26) {
      const sw = noise(x * 0.01, t * 0.8) * 5;
      tufts += ` L${x + 8 + sw} ${GROUND - 16 - (x % 52 === 0 ? 8 : 0)} L${x + 16} ${GROUND - 4}`;
    }
    tufts += ` L1900 ${GROUND + 18} Z`;
    out += path(tufts, col('#73b844', '#5a7a52', dusk * 0.4), 5);
    out += `<rect x="-800" y="${GROUND + 8}" width="2700" height="12" fill="${col('#73b844', '#5a7a52', dusk * 0.4)}"/>`;
    out += `<path d="M-800 ${GROUND + 18} L1900 ${GROUND + 18}" stroke="${C.ink}" stroke-width="6"/>`;
    return out;
  }
  function shadow(x, w, op = 0.22) { return ell(x, GROUND + 4, w, 9, '#2d4a1e', 0, 'none', `opacity="${op}"`); }

  // ---------- camera ----------
  function camera(t) {
    const k = (cx, cy, z) => [cx, cy, z];
    const cam = keys(t, [
      [0, k(345, 1060, 1.5)],
      [at('hook', 'fields') - 0.1, k(350, 1062, 1.47), 'linear'],
      [at('hook', 'fields') + 0.55, k(500, 1010, 1.22), 'outCubic'],
      [L.need.start - 0.1, k(505, 1010, 1.22), 'linear'],
      [L.need.start + 0.6, k(560, 930, 1.22), 'inOutCubic'],
      [at('need', 'the') + 0.4, k(560, 860, 1.22), 'inOutCubic'],
      [at('need', 'but') + 0.1, k(760, 900, 1.6), 'inOutCubic'],
      [L.help.start - 0.15, k(762, 902, 1.61), 'linear'],
      [L.help.start + 0.75, k(300, 1130, 1.6), 'inOutCubic'],
      [L.nodules.start, k(310, 1135, 1.6), 'linear'],
      [L.nodules.start + 0.6, k(453, 1103, 1.65), 'inOutCubic'],
      [L.feed.start + 0.05, k(455, 1104, 1.66), 'linear'],
      [L.feed.start + 0.6, k(420, 990, 1.3), 'inOutCubic'],
      [L.release.start, k(470, 1000, 1.25), 'inOutCubic'],
      [L.next.start - 0.3, k(480, 1005, 1.24), 'linear'],
      [L.next.start + 0.35, k(660, 960, 1.35), 'inOutCubic'],
      [at('next', 'next') - 0.05, k(660, 958, 1.35), 'linear'],
      [at('next', 'next') + 0.7, k(600, 780, 1.0), 'outCubic'],
      [L.recap.start + 0.5, k(540, 596, 0.95), 'inOutCubic'],
      [END, k(540, 588, 0.96), 'linear'],
    ]);
    return { cx: cam[0], cy: cam[1], z: cam[2] };
  }
  const toScreen = (cam, x, y) => [W / 2 + (x - cam.cx) * cam.z, H / 2 + (y - cam.cy) * cam.z];

  // ---------- captions ----------
  const LEAD = 2 / FPS; // captions land two frames before their word, so they read on it
  const KEY = new Set(['nitrogen', 'rhizobia', 'ammonia', 'clover', 'underground', 'soil', 'crop', 'bacteria', 'roots']);
  const CHUNKS = (() => {
    const out = [];
    for (const l of window.TIMING.lines) {
      if (l.id === 'recap') continue;
      let cur = null;
      l.words.forEach((w, i) => {
        const nxt = l.words[i + 1];
        const dur = (nxt ? nxt.start : l.end) - w.start;
        if (!cur) cur = { words: [], start: w.start };
        cur.words.push(w.text);
        const short = dur < 0.3 && nxt && cur.words.length < 3;
        if (!short || !nxt) {
          cur.end = nxt ? nxt.start : l.end + 0.3;
          out.push(cur);
          cur = null;
        }
      });
    }
    out[0].start = 0; // frame one carries the hook
    return out;
  })();
  function captions(t) {
    const c = CHUNKS.find(c => t >= c.start - LEAD && t < c.end - LEAD);
    if (!c) return '';
    const words = c.words.map(w => w.replace(/[.,?!]/g, ''));
    const text = words.join(' ').toUpperCase();
    const isKey = words.some(w => KEY.has(w.toLowerCase()));
    let size = isKey ? 118 : 100;
    const est = textWidth(text, size);
    if (est > 730) size *= 730 / est;
    const q = c.start === 0 && t < 0.4 ? 1 : 0.72 + 0.28 * spring(t - c.start + LEAD, { freq: 3, damping: 0.5 });
    const p = { sx: q, sy: q };
    const y = 1478 - (1 - Math.min(1, q)) * 14;
    const pw = Math.min(800, Math.min(est, 730) + 70), ph = size * 1.22;
    const fill = isKey ? '#ffe45c' : C.white;
    return G(`translate(495 ${f2(y)}) scale(${f2(Math.max(0.01, p.sx))} ${f2(Math.max(0.01, p.sy))})`,
      `<rect x="${f2(-pw / 2)}" y="${f2(-size * 0.92)}" width="${f2(pw)}" height="${f2(ph)}" rx="${f2(ph / 2)}" fill="#3d2616" opacity="0.5"/>` +
      `<text x="6" y="8" font-size="${f2(size)}" font-weight="700" text-anchor="middle" fill="${C.ink}" opacity="0.45" stroke="${C.ink}" stroke-width="16" stroke-linejoin="round">${text}</text>` +
      `<text x="0" y="0" font-size="${f2(size)}" font-weight="700" text-anchor="middle" fill="${fill}" stroke="${C.ink}" stroke-width="16" stroke-linejoin="round" paint-order="stroke">${text}</text>`);
  }

  // ---------- lens (window into the nodule) ----------
  const LENS = { x: 615, y: 1010, r: 290 };
  const CELLS = Array.from({ length: 34 }, (_, i) => [(rand(i + 7) - 0.5) * 900, (rand(i + 61) - 0.5) * 900, 60 + rand(i + 17) * 50]);
  const BUGS = [[-170, -120, 18, 0.8], [170, -150, -24, 0.75], [-210, 120, 12, 0.7], [200, 140, -8, 0.78], [0, 260, 4, 0.7]];
  function lensInner(t, R, ce = 1) {
    let out = `<rect x="${-R - 10}" y="${-R - 10}" width="${2 * R + 20}" height="${2 * R + 20}" fill="#f9d6cd"/>`;
    for (const [cx, cy, r] of CELLS) {
      const dx = noise(cx, t * 0.3) * 6, dy = noise(cy, t * 0.3) * 6;
      out += circle(cx + dx, cy + dy, r, '#fbe3dc', 6, '#eaaea3');
    }
    const fixT = at('fix', 'pull'), turnT = at('fix', 'turn'), amT = at('fix', 'ammonia');
    const rhT = at('nodules', 'rhizobia'), liveT = at('nodules', 'live');
    const swim = ease.outBack(inv(rhT - 0.45, rhT + 0.15, t), 1.2);
    const settle = squash(t, liveT, 0.1);
    // background bugs
    BUGS.forEach(([bx, by, br, bs], i) => {
      out += rhizobium(bx + noise(i + 30, t * 0.6) * 18, by + noise(i + 50, t * 0.6) * 14, br + noise(i, t) * 10, { t, s: bs, seed: i * 3, mood: 'happy', sq: squash(t, liveT + i * 0.05, 0.1) });
    });
    // hero bug and the fixing sequence
    const arrive = fixT + 0.6;
    const chomp = t < arrive - 0.2 ? 0 : t < arrive + 0.35 ? Math.sin(inv(arrive - 0.2, arrive + 0.35, t) * Math.PI) : 0;
    const glowUp = inv(arrive + 0.2, turnT + 0.1, t);
    out += `<circle cx="10" cy="20" r="${f2(130 * glowUp)}" fill="url(#glow)" opacity="${f2(0.6 * glowUp * (t < amT + 0.6 ? 1 : Math.max(0, 1 - (t - amT - 0.6) * 2)))}"/>`;
    out += rhizobium(lerp(-R * 1.3, 10, swim) + noise(5, t * 0.6) * 6, 20 + (1 - swim) * 80, -4 + (1 - swim) * 20, { sq: settle, t, s: 1.25, seed: 1, chomp, mood: chomp > 0.2 ? 'chomp' : t > turnT ? 'happy' : 'happy', talk: chomp });
    // incoming N2 pairs (the hero one plus two background ones)
    const n2path = (t0, from, to, i) => {
      const p = inv(t0, t0 + 0.7, t);
      if (p <= 0 || p >= 1) return '';
      const e = ease.outCubic(p);
      return n2(lerp(from[0], to[0], e) + Math.sin(p * 9 + i) * 10, lerp(from[1], to[1], e), 0.95 * (1 - Math.max(0, p - 0.85) * 5), p * 120 + i * 30,
        i === 0 ? { tag: { t, at: t0 + 0.25 } } : {});
    };
    out += n2path(fixT - 0.1, [-R * 0.62, -R * 0.55], [44, 18], 0);
    out += n2path(fixT + 0.5, [R * 0.9, -R * 0.4], [170, -150], 1);
    out += n2path(fixT + 0.9, [-R * 0.9, R * 0.3], [-210, 120], 2);
    // NH3 out
    [[turnT + 0.15, -1, true], [amT, 1, false]].forEach(([t0, side, tg], i) => {
      const p = inv(t0, t0 + 1.6, t);
      if (p <= 0) return;
      const sp = pop(t, t0, 0.4);
      const x = 30 + side * (40 + p * 120), y = 0 - p * 300;
      out += nh3(x, y, sp.s * 1.05, { tag: tg ? { t, at: amT } : null });
    });
    return out;
  }
  function lens(t, cam) {
    const t0 = L.nodules.start - 0.05, t1 = L.feed.start - 0.45;
    const openP = t < t1 ? inv(t0, t0 + 0.6, t) : 1 - inv(t1, t1 + 0.5, t);
    if (openP <= 0) return '';
    const [nx, ny] = toScreen(cam, ...NODULE_WORLD());
    const e = t < t1 ? ease.outBack(openP, 1.3) : ease.inCubic(openP);
    const ce = ease.outCubic(openP);
    const cx = lerp(nx, LENS.x, ce), cy = lerp(ny, LENS.y, ce), r = Math.max(1, LENS.r * e);
    // leader cone from the nodule to the lens
    const ang = Math.atan2(cy - ny, cx - nx), dist = Math.hypot(cx - nx, cy - ny);
    let out = '';
    if (dist > r) {
      const sp = Math.asin(Math.min(1, r / dist));
      const p1 = [cx - Math.cos(ang - Math.PI / 2 + 0) * 0, 0];
      const a1 = ang + Math.PI / 2 + sp * 0, a2 = ang - Math.PI / 2;
      const t1x = cx + Math.cos(ang + Math.PI - (Math.PI / 2 - sp)) * r, t1y = cy + Math.sin(ang + Math.PI - (Math.PI / 2 - sp)) * r;
      const t2x = cx + Math.cos(ang + Math.PI + (Math.PI / 2 - sp)) * r, t2y = cy + Math.sin(ang + Math.PI + (Math.PI / 2 - sp)) * r;
      out += `<path d="M${f2(nx)} ${f2(ny)} L${f2(t1x)} ${f2(t1y)} L${f2(t2x)} ${f2(t2y)} Z" fill="#fff" opacity="${f2(0.38 * openP)}"/>` +
        `<path d="M${f2(t1x)} ${f2(t1y)} L${f2(nx)} ${f2(ny)} L${f2(t2x)} ${f2(t2y)}" fill="none" stroke="#fff" stroke-width="4" stroke-dasharray="14 10" opacity="${f2(0.9 * openP)}"/>`;
      void p1; void a1; void a2;
    }
    out += circle(nx, ny, 26 * cam.z, 'none', 5, '#fff', `opacity="${f2(openP)}"`);
    const bumps = at('nodules', 'bumps');
    const rimPulse = 1 + 0.03 * Math.exp(-Math.max(0, t - bumps) * 5) * Math.sin(Math.max(0, t - bumps) * 20) * (t > bumps ? 1 : 0);
    const rr = r * rimPulse;
    out += `<defs><clipPath id="lensclip"><circle cx="${f2(cx)}" cy="${f2(cy)}" r="${f2(rr)}"/></clipPath></defs>`;
    out += `<g clip-path="url(#lensclip)">${G(tf(cx, cy, 0, (0.6 + 0.4 * ce) * (LENS.r / 370) * (1 + 0.1 * inv(L.nodules.start + 0.6, L.fix.start, t))), lensInner(t, LENS.r, ce))}</g>`;
    out += circle(cx, cy, rr, 'none', 22, C.ink) + circle(cx, cy, rr, 'none', 10, '#ffffff') + circle(cx, cy, rr - 12, 'none', 4, '#e7c3bb');
    out += `<path d="M${f2(cx - rr * 0.62)} ${f2(cy - rr * 0.5)} A${f2(rr * 0.8)} ${f2(rr * 0.8)} 0 0 1 ${f2(cx - rr * 0.1)} ${f2(cy - rr * 0.8)}" fill="none" stroke="#fff" stroke-width="12" stroke-linecap="round" opacity="0.55"/>`;
    return out;
  }

  const measure = document.createElement('canvas').getContext('2d');
  function textWidth(str, size, weight = 700) {
    measure.font = `${weight} ${size}px Fredoka`;
    return measure.measureText(str).width;
  }

  // ---------- title card ----------
  function title(t) {
    const t0 = L.recap.start;
    if (t < t0 - 0.05) return '';
    const plate = pop(t, t0 - 0.05, 0.5);
    const words = L.recap.words.slice(1);
    let out = `<rect x="-400" y="-170" width="800" height="340" rx="44" fill="${C.cream}" stroke="${C.ink}" stroke-width="8"/>`;
    const cl = pop(t, t0, 0.45);
    out += G(tf(0, -25, 0, cl.sx, cl.sy), `<text x="0" y="0" font-size="150" font-weight="700" fill="#4e9d31" text-anchor="middle" stroke="${C.ink}" stroke-width="10" paint-order="stroke" stroke-linejoin="round">CLOVER</text>`);
    // words build into the line, each on its narration time
    const line = words.map(w => w.text.replace(/[.]/g, ''));
    const widths = line.map((w, i) => textWidth(w + (i === line.length - 1 ? '.' : ''), 62, 600) + 18);
    const total = widths.reduce((a, b) => a + b, 0);
    let x = -total / 2;
    words.forEach((w, i) => {
      const p = pop(t, w.start, 0.35);
      const cx = x + widths[i] / 2;
      if (p.s > 0.01) out += G(tf(cx, 68 + (1 - Math.min(1, p.s)) * 20, 0, p.sx, p.sy),
        `<text x="0" y="0" font-size="62" font-weight="600" fill="${C.ink}" text-anchor="middle">${line[i]}${i === line.length - 1 ? '.' : ''}</text>`);
      x += widths[i];
    });
    const src = inv(L.recap.end + 0.1, L.recap.end + 0.6, t);
    out += `<text x="0" y="132" font-size="30" font-weight="500" fill="#7a6553" text-anchor="middle" opacity="${f2(src)}">Source: Wikipedia, “Nitrogen fixation”</text>`;
    const bob = noise(77, t * 0.6) * 4;
    return G(tf(495, 410 + bob, noise(78, t * 0.5) * 0.6, plate.sx, plate.sy), out);
  }

  // squash-and-stretch around rest: anticipation dip, overshoot, settle
  function squash(t, t0, amt = 0.14) {
    const d = t - t0;
    if (d < -0.12 || d > 0.9) return [1, 1];
    const k = d < 0 ? -Math.sin((d + 0.12) / 0.12 * Math.PI) * 0.35 : Math.exp(-d * 5) * Math.sin(d * 16);
    return [1 + amt * k, 1 - amt * k];
  }

  // ---------- the film ----------
  function frame(f) {
    const t = f / FPS;
    const cam = camera(t);
    const dusk = keys(t, [[L.release.start - 0.1, 0], [L.release.start + 0.6, 1, 'inOutQuad'], [L.next.start - 0.7, 1], [L.next.start, 0, 'inOutQuad']]);

    // --- characters' state ---
    const fieldsT = at('hook', 'fields');
    const helpT = at('help', 'help');
    const dieT = at('release', 'dies');
    const nitroT = at('release', 'nitrogen');
    const relT = at('release', 'released');
    const growT = at('next', 'next');
    const feedT = L.feed.start;
    const flowerT = at('feed', 'clover');
    const wilt = ease.inOutCubic(inv(dieT, dieT + 0.7, t));
    const sinkP = ease.inCubic(inv(dieT + 0.75, dieT + 1.25, t));
    const clGrow = 1 + 0.12 * spring(t - feedT, { freq: 1.8, damping: 0.4 });
    const bounceSq = squash(t, at('hook', 'clover') - 0.05);
    let clMood = 'curious';
    if (t > L.need.start) clMood = 'happy';
    if (t > helpT - 0.05 && t < helpT + 0.8) clMood = 'wink';
    if (t > dieT + 0.2) clMood = 'sleep';
    const clLook = t < L.need.start ? [0.3, -0.6] : t < L.help.start ? [1, -0.2] : t < L.feed.start ? [0, 1] : [0.2, 0];

    const sprout = pop(t, L.recap.start, 0.6);
    const endWink = L.recap.end + 0.7;

    // corn: appears on "Crops", droops, flinches at the bounce, grows on "next"
    const cornIn = pop(t, L.need.start, 0.5);
    const bounceT = at('need', "can't");
    const flinch = t > bounceT ? Math.exp(-(t - bounceT) * 3.5) * Math.sin((t - bounceT) * 22) * 9 : 0;
    const cg = spring(t - growT, { freq: 1.4, damping: 0.5 }) * (t > growT ? 1 : 0);
    const cornHealth = clamp(inv(L.next.start, growT + 0.6, t));
    const nod = t > endWink ? Math.exp(-(t - endWink) * 4) * Math.sin((t - endWink) * 14) * 5 : 0;
    const cornMood = t < L.next.start ? (t > bounceT - 0.1 ? 'sad' : 'curious') : t < growT ? 'curious' : 'happy';

    // --- world ---
    let world = hills(dusk);
    // sun
    const sunY = keys(t, [[0, 300], [L.release.start, 300], [L.release.start + 0.8, 1060, 'inQuad'], [L.next.start - 0.8, 1060], [L.next.start, 300, 'outCubic']]);
    world = circle(190, sunY, 64, '#ffe27a', 6, '#f2b84b') + world;
    // clouds (parallax drift)
    let clouds = '';
    [[120, 220, 1.0, 1], [700, 160, 0.8, 2], [430, 420, 0.65, 3], [980, 380, 0.75, 4]].forEach(([x, y, s, sd]) => {
      const xx = ((x + t * 9 * s + 300) % 1500) - 300;
      clouds += cloud(xx, y, s, sd);
    });
    world = clouds + world;
    world += ground(t, dusk);

    // underground spotlight on clover roots
    const spot = inv(helpT - 0.1, helpT + 0.35, t) * (1 - inv(L.feed.start + 0.3, L.feed.start + 0.9, t));
    if (spot > 0) {
      const pr = 1 + 0.04 * Math.sin(Math.max(0, t - at('help', 'underground')) * 9) * Math.exp(-Math.max(0, t - at('help', 'underground')) * 2) * (t > at('help', 'underground') ? 1 : 0);
      world += ell(CLOVER_X - 5, GROUND + 160, 190 * pr, 170 * pr, 'url(#spot)', 0, 'none', `opacity="${f2(spot)}"`);
      world += ell(CLOVER_X - 5, GROUND + 160, 175 * pr, 158 * pr, 'none', 5, '#fff', `stroke-dasharray="18 14" opacity="${f2(spot * 0.8)}"`);
    }

    // roots (clover's fade after it dies), corn roots
    world += roots(CLOVER_X, { t, nodulePop: at('nodules', 'bumps'), pulse: at('nodules', 'bumps'), fade: inv(dieT, dieT + 1, t), gone: inv(relT, relT + 0.8, t) });
    if (sprout.s > 0) world += G(tf(CLOVER_X, GROUND + 18, 0, sprout.s * 0.5 * ROOT_SX, sprout.s * 0.5 * ROOT_SY), tube(CLOVER_ROOTS[0], C.root, 9, 5));
    if (t > L.need.start) world += cornRoots(CORN_X, cg);

    {
      const bT = at('nodules', 'bumps'), rT = at('nodules', 'roots');
      const vis = 1 - inv(L.feed.start, L.feed.start + 0.4, t);
      if (t > bT - 0.05 && vis > 0) {
        NODULES.forEach(([nx, ny, r], i) => {
          const d = t - bT - i * 0.05;
          if (d < 0) return;
          const rr = r + 8 + (d % 1.2) * 34, op = Math.max(0, 1 - (d % 1.2) / 1.2) * vis;
          world += G(tf(CLOVER_X, GROUND + 18, 0, ROOT_SX, ROOT_SY), circle(nx, ny, rr, 'none', 5, '#fff', `opacity="${f2(op)}"`));
        });
      }
      const tr = inv(rT - 0.05, rT + 0.55, t);
      if (tr > 0 && tr < 1) {
        world += G(tf(CLOVER_X, GROUND + 18, 0, ROOT_SX, ROOT_SY), CLOVER_ROOTS.map(d =>
          `<path d="${d}" fill="none" stroke="#fff6c8" stroke-width="8" stroke-linecap="round" pathLength="100" stroke-dasharray="${f2(tr * 100)} 100" opacity="${f2(Math.sin(tr * Math.PI))}"/>`).join(''));
      }
    }
    // ammonia travelling up the roots to the clover
    if (t > feedT - 0.1 && t < feedT + 1.3) {
      const [nx, ny] = NODULE_WORLD();
      for (let i = 0; i < 6; i++) {
        const p = inv(feedT - 0.05 + i * 0.08, feedT + 0.6 + i * 0.08, t);
        if (p <= 0 || p >= 1) continue;
        const sx = nx + NODULES[i % NODULES.length][0] * 0.0 + (i % 3 - 1) * 20, sy = ny + (i % 2) * 40;
        const x = lerp(sx, CLOVER_X, ease.inOutQuad(p)), y = lerp(sy, GROUND - 160, ease.inQuad(p));
        world += nDot(x, y, 0.42, 1 - Math.max(0, p - 0.8) * 5);
      }
    }

    // background field: small clovers (pop on "fields"), then small corn
    const BG = [40, 150, 480, 880, 1000];
    let bgPlants = '';
    BG.forEach((x, i) => {
      const p = pop(t, fieldsT + i * 0.06, 0.5);
      if (p.s > 0.01 && sinkP < 1) bgPlants += G(tf(x, 0, 0, 1), clover(0, { t, s: 0.42 * p.s, seed: 10 + i, wilt, sink: sinkP * 120, face: false, mood: 'happy', sq: [p.sx / Math.max(p.s, 0.01), p.sy / Math.max(p.s, 0.01)] }));
    });
    [150, 480, 900].forEach((x, i) => {
      const g = spring(t - (growT + 0.15 + i * 0.08), { freq: 1.4, damping: 0.5 }) * (t > growT + 0.15 + i * 0.08 ? 1 : 0);
      if (g > 0.01) bgPlants += corn(x, { t, grow: g * 0.9, health: cornHealth, s: 0.5 * Math.min(1, g * 1.4), face: false, seed: 20 + i, cob: 0 });
    });
    world += `<g clip-path="url(#above)">${bgPlants}</g>`;

    // hero clover
    if (sinkP < 1) {
      world += shadow(CLOVER_X, 70 * (1 - sinkP), 0.2);
      world += `<g clip-path="url(#above)">` + clover(CLOVER_X, {
        t, s: 1.0 * clGrow, wilt, sink: sinkP * 330, flower: inv(feedT - 0.05, flowerT, t), flowerAt: flowerT,
        mood: clMood, lookX: clLook[0], lookY: clLook[1], bl: blink(t, 1, 3.1), sq: bounceSq, seed: 1,
      }) + `</g>`;
    }
    // new sprout at the end (the cycle starts again)
    if (sprout.s > 0.01) {
      world += `<g clip-path="url(#above)">` + clover(CLOVER_X, { t, s: 0.85 * sprout.s, seed: 5, mood: (t > at('recap', 'it') && t < endWink) || t > endWink + 0.45 ? 'happy' : 'wink', bl: blink(t, 4, 2.8), sq: [sprout.sx / Math.max(sprout.s, 0.01), sprout.sy / Math.max(sprout.s, 0.01)] }) + `</g>`;
    }

    // hero corn
    if (cornIn.s > 0.01) {
      world += shadow(CORN_X, lerp(55, 120, cg), 0.2);
      world += `<g clip-path="url(#above)">` + corn(CORN_X, {
        t, grow: cg, health: cornHealth, mood: cornMood, flinch: flinch + nod, s: cornIn.s * 1.35, bl: blink(t, 2, 3.4),
        lookX: t < bounceT ? -0.3 : 0.2, lookY: t < bounceT && t > at('need', 'the') ? -1 : 0,
        cob: pop(t, growT + 0.75, 0.5).s, sq: [cornIn.sx / Math.max(cornIn.s, 0.01), cornIn.sy / Math.max(cornIn.s, 0.01)],
      }) + `</g>`;
    }

    // nitrogen in the air
    const airT = at('need', 'air');
    for (let i = 0; i < 9; i++) {
      const p = pop(t, airT - 0.15 + i * 0.07, 0.5);
      const out = 1 - ease.inCubic(inv(L.help.start + 0.2 + i * 0.03, L.help.start + 0.7 + i * 0.03, t));
      if (p.s * out <= 0.01) continue;
      const bx = 210 + rand(i + 200) * 540, by = 260 + rand(i + 300) * 420;
      const x = bx + noise(i + 400, t * 0.4) * 50 + t * 6, y = by + noise(i + 500, t * 0.35) * 40;
      world += n2(x, y - (1 - out) * 120, 1.15 * p.s * out, noise(i + 600, t * 0.3) * 40, i === 2 ? { tag: { t, at: airT + 0.3 } } : {});
    }
    // the bounce: one pair drops onto the seedling and is shrugged off
    {
      const t0 = at('need', 'but') - 0.25, hit = bounceT;
      if (t > t0 && t < hit + 1.4) {
        let x, y, r;
        if (t < hit) { const p = ease.inQuad(inv(t0, hit, t)); x = lerp(560, CORN_X - 6, p); y = lerp(560, GROUND - 215, p); r = p * 90; }
        else { const p = (t - hit); x = CORN_X - 6 + p * 260; y = GROUND - 215 - 520 * p + 330 * p * p; r = 90 + p * 300; }
        const sqz = t > hit && t < hit + 0.12 ? [1.25, 0.75] : [1, 1];
        world += G(`translate(${f2(x)} ${f2(y)}) scale(${sqz[0]} ${sqz[1]})`, n2(0, 0, 0.95, r));
        if (t > hit && t < hit + 0.35) {
          const q = inv(hit, hit + 0.35, t);
          for (let k = 0; k < 5; k++) {
            const a = -Math.PI * (0.15 + k * 0.17);
            world += `<path d="M${f2(CORN_X - 6 + Math.cos(a) * (40 + q * 30))} ${f2(GROUND - 215 + Math.sin(a) * (40 + q * 30))} l${f2(Math.cos(a) * 22)} ${f2(Math.sin(a) * 22)}" stroke="${C.ink}" stroke-width="6" stroke-linecap="round" opacity="${f2(1 - q)}"/>`;
          }
        }
      }
    }

    // the new clover's nitrogen flows to the corn under the end card
    if (t > L.recap.start + 0.4) {
      for (let i = 0; i < 5; i++) {
        const ph = ((t - L.recap.start - 0.4) / 1.6 + i / 5) % 1;
        const x = lerp(CLOVER_X + 30, CORN_X - 20, ph), y = GROUND + 120 - Math.sin(ph * Math.PI) * 40;
        world += nDot(x, y, 0.34, Math.sin(ph * Math.PI) * inv(L.recap.start + 0.4, L.recap.start + 0.9, t));
      }
    }
    // released nitrogen spreading through soil, then flowing to the corn
    let glowLayer = '';
    if (t > nitroT - 0.1 && t < L.recap.start + 1.5) {
      for (let i = 0; i < 26; i++) {
        const a = rand(i + 700) * Math.PI * 2, d = 60 + rand(i + 800) * 300;
        const sx = CLOVER_X + Math.cos(a) * d * 1.2, sy = GROUND + 140 + Math.sin(a) * d * 0.55;
        const spread = ease.outCubic(inv(nitroT - 0.1 + i * 0.03, relT + 0.6 + i * 0.02, t));
        const toCorn = ease.inOutCubic(inv(L.next.start - 0.1 + i * 0.025, growT + 0.35 + i * 0.02, t));
        const x0 = lerp(CLOVER_X, sx, spread), y0 = lerp(GROUND + 120, sy, spread);
        const tx = CORN_X + (rand(i + 900) - 0.5) * 120, ty = GROUND + 40 + rand(i + 950) * 100;
        const x = lerp(x0, tx, toCorn) + noise(i + 1000, t) * 6, y = lerp(y0, ty, toCorn) + noise(i + 1100, t) * 6;
        const op = spread * (1 - inv(growT + 0.2, growT + 0.9, t));
        const bright = 1 + 0.25 * Math.exp(-Math.max(0, t - relT) * 3) * (t > relT ? 1 : 0);
        if (op > 0.01 && i % 3 !== 2) glowLayer += nDot(x, y, 0.36 * bright, op);
      }
    }

    // assemble: camera transform over the world
    const camT = `translate(${W / 2} ${H / 2}) scale(${f2(cam.z)}) translate(${f2(-cam.cx)} ${f2(-cam.cy)})`;
    let svg = sky(t, dusk);
    svg += `<g transform="${camT}">${world}</g>`;
    if (dusk > 0.01) svg += `<rect width="${W}" height="${H}" fill="#3b2a6b" opacity="${f2(dusk * 0.24)}" style="mix-blend-mode:multiply"/>`;
    if (glowLayer) svg += `<g transform="${camT}">${glowLayer}</g>`;
    svg += lens(t, cam);
    svg += t < L.recap.start - 0.05 ? captions(t) : '';
    svg += title(t);
    {
      const lp = ease.outCubic(inv(L.recap.start + 0.3, L.recap.start + 0.8, t));
      if (lp > 0) {
        const [sx, sy] = toScreen(cam, CLOVER_X, GROUND - 330 * 0.85);
        const x0 = 300, y0 = 588;
        const ex = lerp(x0, sx, lp), ey = lerp(y0, sy - 40, lp);
        svg += `<path d="M${x0} ${y0} Q${f2(x0 - 40)} ${f2((y0 + ey) / 2)} ${f2(ex)} ${f2(ey)}" fill="none" stroke="${C.ink}" stroke-width="12" stroke-linecap="round" opacity="0.85"/>` +
          `<path d="M${x0} ${y0} Q${f2(x0 - 40)} ${f2((y0 + ey) / 2)} ${f2(ex)} ${f2(ey)}" fill="none" stroke="${C.cream}" stroke-width="5" stroke-dasharray="14 12" stroke-linecap="round"/>` +
          circle(ex, ey, 10 * lp, C.cream, 4.5);
      }
    }
    // hook mark: a question bubble beside the clover on frame one
    const q = 1 - inv(at('hook', 'fields'), at('hook', 'fields') + 0.25, t);
    if (q > 0) {
      const [qx, qy] = toScreen(cam, CLOVER_X + 130, GROUND - 400);
      const b = 1 + 0.06 * Math.sin(t * 5);
      svg += G(tf(qx, qy + Math.sin(t * 3) * 6, 8, b * q), circle(0, 0, 58, C.white, 6) + path('M-30 44 L-50 74 L-6 56', C.white, 6) + `<rect x="-40" y="34" width="44" height="22" fill="#fff"/>` +
        `<text x="0" y="26" font-size="78" font-weight="700" fill="${C.nitro}" text-anchor="middle">?</text>`);
    }
    return svg;
  }

  // ---------- sound cues (read by engine/audio.py) ----------
  const cue = (t, type, gain = 1) => ({ t: +t.toFixed(3), type, gain });
  window.CUES = [
    cue(at('hook', 'clover') - 0.05, 'pop'),
    ...[0, 1, 2, 3, 4].map(i => cue(at('hook', 'fields') + i * 0.06, 'pop_small', 0.55)),
    cue(L.need.start - 0.05, 'whoosh'), cue(L.need.start, 'pop'),
    cue(at('need', 'air') - 0.15, 'twinkle'),
    cue(at('need', "can't"), 'boing'),
    cue(L.help.start - 0.1, 'whoosh'), cue(at('help', 'help'), 'wink'),
    cue(L.nodules.start - 0.05, 'lens_open'),
    cue(at('nodules', 'bumps'), 'pop_small', 0.7),
    cue(at('fix', 'pull') + 0.6, 'chomp'),
    cue(at('fix', 'turn') + 0.15, 'sparkle'), cue(at('fix', 'ammonia'), 'sparkle'),
    cue(L.feed.start - 0.3, 'lens_close'), cue(L.feed.start, 'grow'),
    cue(at('feed', 'clover'), 'pop'),
    cue(at('release', 'dies'), 'wilt'), cue(at('release', 'dies') + 0.75, 'sink'),
    cue(at('release', 'nitrogen') - 0.1, 'shimmer'),
    cue(L.next.start - 0.1, 'whoosh'), cue(at('next', 'next'), 'grow_big'),
    cue(at('next', 'next') + 0.75, 'pop'),
    cue(L.recap.start - 0.05, 'pop'),
    cue(at('recap', 'it'), 'chime'),
    cue(L.recap.end + 0.7, 'wink'),
  ].sort((a, b) => a.t - b.t);

  const stage = document.getElementById('stage');
  window.renderFrame = f => { stage.innerHTML = frame(f); };
  window.FILM = { width: W, height: H, fps: FPS, frames: Math.round(END * FPS), safe: SAFE, ready: false };
  document.fonts.load('700 40px Fredoka').then(() => { window.FILM.ready = true; });
})();
