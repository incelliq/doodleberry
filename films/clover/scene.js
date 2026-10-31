// "Why farmers rotate clover" — every pixel is a function of the frame number.
// Timing comes from timing.json (narration word times); nothing here uses a
// clock or unseeded randomness.
(function () {
  const { clamp, lerp, inv, ease, spring, keys, noise, rand, blink, pop, tf } = M;
  const T = M.bindTiming(window.TIMING);
  const FPS = 30, W = 1080, H = 1920;
  const END = 31.7;
  const at = (line, word, nth = 0) => T.word(line, word, nth).start;
  const L = T.lines;

  // ---------- style bible ----------
  const C = {
    ink: '#3a2618',
    skyTop: '#79c6ee', skyBot: '#e2f5fb', duskTop: '#4f4f9e', duskBot: '#f5ad78',
    leaf: '#62c040', leafHi: '#86d957', leafMark: '#d4f0b4', leafDead: '#a8894c',
    soil: '#8a5c3c', soilDeep: '#5f3d27', soilLine: '#74492e',
    root: '#ecd6a9', nodule: '#ef9f95',
    nitro: '#58aef0', ammonia: '#c3f45f', bact: '#f5a94b',
    cream: '#fff8e8', white: '#ffffff',
  };
  const GROUND = 1080;
  const CLOVER_X = 330, CORN_X = 690;
  const ROOT_SX = 1.05, ROOT_SY = 0.62; // roots are squashed so captions stay clear
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
    const { x = 0, y = 0, s = 1, mood = 'happy', lookX = 0, lookY = 0, bl = 0, talk = 0, sep = 21, lid = C.leafHi } = o;
    let out = '';
    const arcEye = (ex, down) => D.inkTaper(down ? D.bez([ex - 12, -2], [ex - 5, 9], [ex + 5, 9], [ex + 12, -2], 8) : D.bez([ex - 12, 4], [ex - 5, -9], [ex + 5, -9], [ex + 12, 4], 8), 5, 3, C.ink, C.ink, 0);
    if (mood === 'sleep') out += arcEye(-sep, true) + arcEye(sep, true);
    else {
      out += D.eye(-sep, 0, { lookX, lookY, bl, lid });
      out += mood === 'wink' ? arcEye(sep, false) : D.eye(sep, 0, { lookX, lookY, bl, lid });
    }
    // brows carry the expression
    const brow = (ex, side) => {
      const lift = mood === 'curious' ? (side > 0 ? -7 : 0) : mood === 'sad' ? 0 : mood === 'chomp' || mood === 'open' ? -5 : -2;
      const tilt = mood === 'sad' ? side * 6 : mood === 'curious' && side > 0 ? -3 : 0;
      const by = -27 + lift;
      return D.taper(D.bez([ex - 11, by + tilt], [ex - 4, by - 4], [ex + 4, by - 4], [ex + 11, by - tilt], 6), 5, 2.4, C.ink);
    };
    if (mood !== 'sleep') out += brow(-sep, -1) + brow(sep, 1);
    // mouth
    const my = 30;
    if (mood === 'sad') out += D.taper(D.bez([-12, my + 5], [-5, my - 5], [5, my - 5], [12, my + 5], 8), 3, 5, C.ink);
    else if (mood === 'open' || mood === 'chomp' || talk > 0.05) {
      const h = mood === 'chomp' ? 4 + talk * 16 : 6 + talk * 10;
      const md = `M-12 ${my - 2} Q0 ${my - 4} 12 ${my - 2} Q8 ${my + h} 0 ${my + h} Q-8 ${my + h} -12 ${my - 2} Z`;
      out += `<path d="${md}" fill="${D.linear([[0, '#6e1f1c'], [1, '#a83a32']])}" stroke="${C.ink}" stroke-width="4.5" stroke-linejoin="round"/>`;
      if (h > 8) out += `<ellipse cx="2" cy="${f2(my + h * 0.7)}" rx="6" ry="${f2(h * 0.25)}" fill="#ff8a8a"/>`;
    } else if (mood === 'curious') out += D.taper(D.bez([-7, my], [-2, my - 3], [3, my - 2], [8, my + 1], 6), 3, 4.5, C.ink);
    else out += D.taper(D.bez([-14, my - 4], [-6, my + 9], [6, my + 9], [14, my - 4], 10), 3, 5.5, C.ink);
    if (mood !== 'sad') {
      const blush = D.radial([[0, '#ff7f7a', 0.75], [1, '#ff7f7a', 0]], { cx: 0.5, cy: 0.5, r: 0.5 });
      out += `<ellipse cx="${-sep - 14}" cy="20" rx="12" ry="8" fill="${blush}"/><ellipse cx="${sep + 14}" cy="20" rx="12" ry="8" fill="${blush}"/>`;
    }
    return G(tf(x, y, 0, s), out);
  }

  // light direction rotated into a shape's local frame
  const litDir = (rot, base = [0.55, 0.83]) => {
    const a = (-rot * Math.PI) / 180;
    return [base[0] * Math.cos(a) - base[1] * Math.sin(a), base[0] * Math.sin(a) + base[1] * Math.cos(a)];
  };
  const ellD = (rx, ry) => `M${-rx} 0 A${rx} ${ry} 0 1 0 ${rx} 0 A${rx} ${ry} 0 1 0 ${-rx} 0 Z`;
  function mound(w, h, color = '#8f6040') {
    const d = `M${-w} 6 C${-w * 0.72} ${-h * 0.8} ${-w * 0.28} ${-h} 0 ${-h} C${w * 0.3} ${-h} ${w * 0.7} ${-h * 0.8} ${w} 6 Z`;
    let s = D.shade(d, color, { depth: 7, light: 3, w: 4.5, ink: C.ink });
    [[-w * 0.85, 2, 9], [w * 0.8, 3, 7]].forEach(([cx, cy, r]) => {
      s += G(tf(cx, cy, 0, 1), D.shade(ellD(r, r * 0.75), D.mix(color, '#000', 0.1), { depth: 3, light: 1.5, w: 3, ink: C.ink }));
    });
    return s;
  }

  // ---------- clover ----------
  const HEART = 'M0 0 C-22 -18 -62 -48 -62 -84 C-62 -116 -30 -128 0 -102 C30 -128 62 -116 62 -84 C62 -48 22 -18 0 0 Z';
  function leaflet(rot, s, fill, markOpacity, inner = '', fold = 0) {
    const dark = D.shadowOf(fill);
    let veins = D.taper(D.bez([0, -4], [0, -40], [1, -70], [0, -98], 10), 5, 1.2, dark, 'opacity="0.75"');
    for (let k = 1; k <= 3; k++) for (const sd of [-1, 1]) {
      const y0 = -18 - k * 22;
      veins += D.taper(D.bez([0, y0], [sd * 14, y0 - 6], [sd * 28, y0 - 14], [sd * 40, y0 - 24], 6), 3, 0.5, dark, 'opacity="0.5"');
    }
    return G(tf(0, 0, rot, s * (1 - 0.55 * fold), s * (1 - 0.2 * fold)),
      D.shade(HEART, fill, { dir: litDir(rot), depth: 9, light: 5, w: 5.5, ink: C.ink, shadow: D.shadowOf(fill, 0.75) }) +
      `<path d="M-30 -74 Q0 -46 30 -74" fill="none" stroke="${C.leafMark}" stroke-width="8" stroke-linecap="round" opacity="${markOpacity * 0.85}"/>` +
      veins + D.glintMark(-36, -94, 0.75, -35) + inner);
  }
  function flower(x, y, s, t, wilt = 0) {
    if (s <= 0.001) return '';
    // white clover head: a ball of small florets, outer ones blushing pink
    let out = D.sphere(0, 0, 26, D.mix('#ffffff', '#b59c6a', wilt), { w: 4, spec: false });
    [[16, 30, '#f6d4e0'], [10, 19, '#fbeaf0'], [6, 9, '#ffffff']].forEach(([n, r, c]) => {
      for (let i = 0; i < n; i++) {
        const a = (i / n) * Math.PI * 2 + r;
        const fx = Math.cos(a) * r * 0.75, fy = Math.sin(a) * r * 0.75;
        const fc = D.mix(c, '#a88d5c', wilt);
        out += `<ellipse cx="${f2(fx)}" cy="${f2(fy)}" rx="5" ry="10" fill="${D.linear([[0, D.lightOf(fc)], [1, D.shadowOf(fc, 0.6)]])}" stroke="${C.ink}" stroke-width="2.6" transform="rotate(${f2(a * 180 / Math.PI + 90)} ${f2(fx)} ${f2(fy)})"/>`;
      }
    });
    return G(tf(x, y, noise(9, t * 0.7) * 4 - wilt * 50, s), out);
  }
  // o: t, s, wilt, sink, flower, mood, look, bl, talk, sq (squash), seed, face, wind
  function clover(x, o) {
    const t = o.t, s = o.s, seed = o.seed || 1;
    const wilt = o.wilt || 0;
    const w0 = o.wind || 0, w1 = o.windLag !== undefined ? o.windLag : w0;
    const sway = noise(seed, t * 0.55) * 3 + noise(seed + 7, t * 1.3) * 1.2 + w0 * 0.7;
    const Hs = 255;
    const bend = -wilt * 34 + sway;                     // degrees the tip leans
    const a = (bend * Math.PI) / 180;
    const tipX = Math.sin(a) * Hs * (1 - wilt * 0.25), tipY = -Math.cos(a) * Hs * (1 - wilt * 0.25);
    const leafCol = D.mix(C.leaf, C.leafDead, wilt), stemCol = D.mix('#4fa034', '#8d7440', wilt);
    let out = o.face === false ? '' : mound(46, 20);
    // flower on its own stalk
    const fl = o.flower || 0;
    if (fl > 0) {
      const fx = 74 + Math.sin(a) * 60, fy = -Hs * 0.62 * ease.outCubic(fl) + wilt * 40;
      out += D.inkTaper(D.bez([6, 0], [fx * 0.1, fy * 0.35], [fx * 0.45, fy * 0.85], [fx, fy], 12), 10, 6, stemCol, C.ink, 4.5);
      out += ell(fx, fy - 6, 10 * Math.min(1, fl * 3), 14 * Math.min(1, fl * 3), '#e9f7d9', 4) + flower(fx, fy, M.pop(o.t, o.flowerAt || 0, 0.5).s * (1 - wilt * 0.3), t, wilt);
    }
    // tapered stem with a lit edge
    const stem = D.bez([0, 0], [0, tipY * 0.35], [tipX * 0.35, tipY * 0.72], [tipX, tipY], 14);
    out += D.inkTaper(stem, 18, 10, stemCol, C.ink, 5.5);
    out += D.taper(stem.map(([px, py]) => [px - 3.5, py]), 4, 2, D.lightOf(stemCol), 'opacity="0.7"');
    const leafRot = bend * 1.1 - wilt * 22;
    const lS = 1.08;
    const mk = 0.75 * (1 - wilt);
    const fc = o.face === false ? '' : face({ x: 0, y: -72, s: 0.95, mood: o.mood, lookX: o.lookX || 0, lookY: o.lookY || 0, bl: o.bl || 0, talk: o.talk || 0, lid: D.mix(C.leafHi, C.leafDead, wilt) });
    // leaflets flutter on their own, a beat behind the stem (follow-through)
    const flut = i => noise(seed + 3 + i, t * 2.1) * 3 + (w1 - w0) * 1.2 + w1 * 0.5 * (i - 1);
    const crown =
      leaflet(-62 + flut(0) + wilt * 30, lS * 0.92, leafCol, mk, '', wilt) +
      leaflet(62 + flut(2) - wilt * 30, lS * 0.92, leafCol, mk, '', wilt) +
      leaflet(flut(1) * 0.5, lS * (1 - 0.15 * wilt), D.mix(C.leafHi, C.leafDead, wilt), mk, fc, wilt * 0.4);
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
  const ROOT_PTS = CLOVER_ROOTS.map(d => D.pathPts(d, 10));
  const rootCache = new Map();
  function rootSystem(fadeQ) {
    if (rootCache.has(fadeQ)) return rootCache.get(fadeQ);
    const fill = D.mix(C.root, '#9a7a55', fadeQ / 10);
    let inkS = '', fillS = '', hl = '';
    ROOT_PTS.forEach((pts, i) => {
      const w0 = i === 0 ? 14 : 9, w1 = i === 0 ? 4 : 3;
      inkS += D.taper(pts, w0 + 9, w1 + 5, C.ink);
      fillS += D.taper(pts, w0, w1, fill);
      hl += D.taper(pts.map(([x, y]) => [x - 2, y - 1]), w0 * 0.3, 0.6, D.lightOf(fill), 'opacity="0.8"');
      const r = D.rootlets(pts, 17 + i * 7, { count: i === 0 ? 9 : 5, len: i === 0 ? 50 : 38, w: 3.4, fill, ink: C.ink, depth: 1 });
      inkS += r.ink; fillS += r.fill;
    });
    const s = inkS + fillS + hl;
    rootCache.set(fadeQ, s);
    return s;
  }
  function roots(x, o) {
    const fade = o.fade || 0;
    let out = rootSystem(Math.round(fade * 10));
    NODULES.forEach(([nx, ny, r], i) => {
      const p = o.nodulePop ? M.pop(o.t, o.nodulePop + i * 0.05, 0.45) : { s: 1 };
      const base = 0.65 + 0.35 * p.s;
      const pulse = o.pulse ? 1 + 0.12 * Math.exp(-Math.max(0, o.t - o.pulse - i * 0.05) * 4) * Math.sin(Math.max(0, o.t - o.pulse - i * 0.05) * 18) : 1;
      const R = r * base * pulse * (1 - fade * 0.6);
      out += D.sphere(nx, ny, R, D.mix(C.nodule, '#9a7a55', fade), { w: 4 });
    });
    return G(tf(x, GROUND + 18, 0, ROOT_SX, ROOT_SY), out, `opacity="${f2(1 - (o.gone || 0))}"`);
  }
  const NODULE_WORLD = () => [CLOVER_X + NODULES[0][0] * ROOT_SX, GROUND + 18 + NODULES[0][1] * ROOT_SY];
  const CORN_ROOTS = ['M0 0 C-8 50 -30 90 -48 140', 'M0 0 C6 60 4 110 10 160', 'M0 0 C14 46 36 86 56 130', 'M-4 30 C-40 50 -64 70 -84 96', 'M4 34 C36 52 60 72 82 100'];
  const CORN_ROOT_SVG = (() => {
    let inkS = '', fillS = '';
    CORN_ROOTS.forEach((d, i) => {
      const pts = D.pathPts(d, 10);
      inkS += D.taper(pts, 15, 6, C.ink);
      fillS += D.taper(pts, 8, 2, C.root);
      const r = D.rootlets(pts, 41 + i * 5, { count: 4, len: 30, w: 2.8, fill: C.root, ink: C.ink, depth: 1 });
      inkS += r.ink; fillS += r.fill;
    });
    return inkS + fillS;
  })();
  function cornRoots(x, g) {
    return G(tf(x, GROUND + 14, 0, 0.35 + 0.65 * g, 0.3 + 0.7 * g), CORN_ROOT_SVG);
  }

  // ---------- corn ----------
  // o: t, grow, health, mood, flinch, s, face, cob, seed, bl, look, wind
  function corn(x, o) {
    const t = o.t, g = o.grow, seed = o.seed || 2;
    const Hh = lerp(150, 560, g);
    const w = lerp(28, 42, g);
    const leafC = D.mix('#a8cc34', '#4e9d31', o.health), leafHi = D.mix('#c0dd52', '#6dbb47', o.health);
    const wnd = o.wind || 0;
    const sway = noise(seed, t * 0.5) * 2.5 + (o.flinch || 0) + wnd * 0.45;
    let out = o.face === false ? '' : mound(lerp(40, 58, g), lerp(16, 22, g));
    // tassel
    if (g > 0.6) {
      const ts = inv(0.6, 1, g);
      let tas = '';
      for (let i = -2; i <= 2; i++) {
        const pts = D.bez([0, -Hh + 4], [i * 5, -Hh - 20], [i * 14, -Hh - 40], [i * 22 + noise(i + seed, t * 1.5) * 4, -Hh - 50 - (2 - Math.abs(i)) * 14], 10);
        tas += D.inkTaper(pts, 7, 2.5, '#e8c44f', C.ink, 3) + D.taper(pts.map(([px, py]) => [px - 1.5, py]), 2, 0.6, '#fff1b0');
      }
      out += `<g opacity="${f2(ts)}">${tas}</g>`;
    }
    // stalk with node rings
    const stalkD = `M${-w / 2} 0 C${-w / 2} ${-Hh * 0.5} ${-w * 0.3} ${-Hh * 0.8} ${-w * 0.18} ${-Hh} Q0 ${-Hh - 34} ${w * 0.18} ${-Hh} C${w * 0.3} ${-Hh * 0.8} ${w / 2} ${-Hh * 0.5} ${w / 2} 0 Z`;
    out += D.shade(stalkD, leafC, { dir: [1, 0.15], depth: w * 0.32, light: 3.5, w: 6, ink: C.ink });
    for (const k of [0.2, 0.4, 0.6, 0.78]) {
      const hy = -Hh * k, ww = lerp(w / 2, w * 0.2, k) * 0.95;
      out += `<path d="M${f2(-ww)} ${f2(hy)} Q0 ${f2(hy + 6)} ${f2(ww)} ${f2(hy)}" fill="none" stroke="${D.shadowOf(leafC, 1.3)}" stroke-width="3" opacity="0.7"/>`;
    }
    // leaves: filled tapered blades (wide near the stalk, pointed tip) with the midrib drawn inside,
    // fluttering with a lag up the stalk; attach heights keep clear of the face
    const n = 6;
    const HY = [0.6, 0.72, 0.84, 0.12, 0.24, 0.66];
    const profile = u => Math.pow(Math.sin(Math.PI * (0.12 + 0.88 * u)), 0.75) * (1 - u * 0.15);
    for (let i = 0; i < n; i++) {
      const app = i < 3 ? 1 : clamp((g - (i - 3) * 0.2) / 0.22);
      if (app <= 0) continue;
      const dir = i % 2 ? 1 : -1;
      const hy = -Hh * HY[i];
      const Ln = (i < 3 ? lerp(118 - i * 14, 150, g) : 150 + i * 8) * ease.outBack(app);
      const droop = lerp(0.05, -0.15, o.health) + noise(seed + i, t * 0.8) * 0.06 + (1 - o.health) * 0.35 + dir * wnd * 0.012 * (1 + i * 0.2);
      const arch = i === 3 || i === 4 ? 0.32 : 0.5;
      const cl = D.bez([0, 0], [dir * Ln * 0.35, -Ln * (arch - droop)], [dir * Ln * 0.75, -Ln * (arch * 0.6 - droop)], [dir * Ln, Ln * droop], 18);
      const Wd = lerp(20, 30, g) * (0.8 + 0.2 * app);
      const blade = D.taperPath(cl, 0, Wd, profile);
      const rib = cl.slice(1, -2);
      const fill = i % 2 ? leafC : leafHi;
      out += G(tf(dir * w * 0.3, hy, 0, 1), D.shade(blade, fill, { dir: [0.15 * dir, 1], depth: Wd * 0.28, light: 3, w: 4.5, ink: C.ink }) +
        D.taper(rib, 3.2, 0.6, D.lightOf(fill, 1.2), 'opacity="0.9"'));
    }
    // cob
    if ((o.cob || 0) > 0) {
      const cp = o.cob;
      let k = '';
      for (let r = 0; r < 7; r++) for (let c2 = -1; c2 <= 1; c2++) {
        k += `<ellipse cx="${c2 * 11}" cy="${-20 - r * 14}" rx="5.5" ry="6.5" fill="${D.radial([[0, '#fff3a8'], [1, '#e5ad1f']], { cx: 0.35, cy: 0.3, r: 0.8 })}" stroke="#b9861a" stroke-width="2"/>`;
      }
      out += G(tf(w * 0.45, -Hh * 0.5, 28, cp),
        `<g transform="translate(0 -62)">${D.shade(ellD(24, 58), '#ffd23f', { depth: 8, light: 3, w: 5, ink: C.ink })}</g>` + k +
        D.shade('M-18 -10 Q-34 -60 -10 -118 Q-14 -60 4 -6 Z', '#6fbe46', { depth: 6, w: 5, ink: C.ink }) +
        D.shade('M18 -10 Q34 -64 14 -112 Q10 -56 -2 -6 Z', '#5aa83a', { depth: 6, w: 5, ink: C.ink }));
    }
    if (o.face !== false) {
      out += face({ x: 0, y: -Hh * lerp(0.42, 0.42, g), s: lerp(0.95, 1.25, g), mood: o.mood, bl: o.bl || 0, lookX: o.lookX || 0, lookY: o.lookY || 0, talk: o.talk || 0, sep: 19, lid: leafC });
    }
    const sq = o.sq || [1, 1];
    return G(`translate(${f2(x)} ${GROUND + 8}) rotate(${f2(sway)}) scale(${f2(o.s * sq[0])} ${f2(o.s * sq[1])})`, out);
  }

  // ---------- molecules & microbes ----------
  function n2(x, y, s, rot, o = {}) {
    const a = 22;
    let out = `<rect x="${-a * 0.8}" y="-5" width="${a * 1.6}" height="10" fill="${D.shadowOf(C.nitro)}"/>`;
    out += D.sphere(-a * 0.8, 0, a, C.nitro, { w: 5 }) + D.sphere(a * 0.8, 0, a, C.nitro, { w: 5 });
    for (const ax of [-a * 0.8, a * 0.8]) out += `<text x="${f2(ax)}" y="9" font-size="24" font-weight="700" fill="#fff" text-anchor="middle" transform="rotate(${f2(-rot)} ${f2(ax)} 0)">N</text>`;
    if (o.tag) out += G(`rotate(${f2(-rot)})`, tag(0, -54, 'N₂', C.nitro, o.tag));
    return G(tf(x, y, rot, s), out, o.op !== undefined ? `opacity="${o.op}"` : '');
  }
  function nh3(x, y, s, o = {}) {
    let out = `<circle cx="0" cy="0" r="46" fill="url(#glow)" opacity="${o.glow ?? 0.9}"/>`;
    [[-24, -14], [24, -14], [0, 26]].forEach(([hx, hy]) => { out += D.sphere(hx, hy, 11, '#f4f7ff', { w: 4 }); });
    out += D.sphere(0, 0, 20, C.nitro, { w: 5 }) + `<text x="0" y="8" font-size="22" font-weight="700" fill="#fff" text-anchor="middle">N</text>`;
    if (o.tag) out += tag(0, -62, 'NH₃', '#6aa21c', o.tag);
    return G(tf(x, y, 0, s), out);
  }
  function tag(x, y, label, color, p) {
    const s = M.pop(p.t, p.at, 0.4);
    if (s.s <= 0.01) return '';
    const w = label.length * 19 + 34;
    return G(tf(x, y, 0, s.sx, s.sy), `<rect x="${-w / 2 + 3}" y="-20" width="${w}" height="44" rx="22" fill="${C.ink}" opacity="0.25"/>` +
      `<rect x="${-w / 2}" y="-24" width="${w}" height="44" rx="22" fill="${C.white}" stroke="${C.ink}" stroke-width="4.5"/>` +
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
  // o: t, chomp(0..1), s, seed, mood, sq
  const BACT = 'M-32 -30 H32 A30 30 0 0 1 32 30 H-32 A30 30 0 0 1 -32 -30 Z';
  function rhizobium(x, y, rot, o) {
    const t = o.t, ph = t * 7 + (o.seed || 0);
    const wig = Math.sin(ph) * 6;
    const tail = [[-60, 0]];
    for (let i = 1; i <= 12; i++) tail.push([-60 - i * 7, Math.sin(ph + i * 0.65) * 10 * Math.min(1, i / 4)]);
    const sq = 1 + (o.chomp || 0) * 0.14;
    const ex = o.sq || [1, 1];
    let out = D.inkTaper(tail, 7, 1.5, '#d98a35', C.ink, 2.5);
    let pili = '';
    for (let i = 0; i < 10; i++) {
      const a = (i / 10) * Math.PI * 2, px = Math.cos(a) * 58, py = Math.sin(a) * 30;
      const len = 9 + Math.sin(ph * 0.7 + i) * 2;
      pili += D.taper([[px, py], [px + Math.cos(a) * len, py + Math.sin(a) * len]], 3, 1, C.ink);
    }
    out += G(`scale(${f2(sq * ex[0])} ${f2(ex[1] / sq)})`,
      pili + D.shade(BACT, C.bact, { dir: litDir(rot + wig * 0.4), depth: 8, light: 5, w: 5.5, ink: C.ink, shadow: D.shadowOf(C.bact, 0.7), lit: '#ffe2a8' }) +
      `<rect x="-44" y="-22" width="70" height="12" rx="6" fill="#fff" opacity="0.45"/>` +
      D.sphere(-30, 12, 5, '#d9852a', { w: 0, spec: false }) + D.sphere(-12, 18, 4, '#d9852a', { w: 0, spec: false }) +
      face({ x: 24, y: -6, s: 0.62, mood: o.mood || 'happy', bl: blink(t, (o.seed || 0) + 11, 2.7), talk: o.talk || 0, lookX: 0.4, lid: C.bact }));
    return G(tf(x, y + wig * 0.3, rot + wig * 0.4, o.s || 1), out);
  }

  // ---------- environment ----------
  function sky(t, dusk) {
    const top = col(C.skyTop, C.duskTop, dusk), mid = col('#a8dcf3', '#b77fa8', dusk), bot = col(C.skyBot, C.duskBot, dusk);
    let stars = '';
    if (dusk > 0.01) for (let i = 0; i < 14; i++) {
      const x = 60 + rand(i + 40) * 960, y = 120 + rand(i + 90) * 600;
      stars += circle(x, y, 3 + rand(i) * 3, '#fff6d6', 0, 'none', `opacity="${f2(dusk * (0.55 + 0.45 * Math.sin(t * 3 + i)))}"`);
    }
    return `<defs><linearGradient id="sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${top}"/><stop offset="0.55" stop-color="${mid}"/><stop offset="1" stop-color="${bot}"/></linearGradient>` +
      `<radialGradient id="glow"><stop offset="0" stop-color="${C.ammonia}" stop-opacity="0.9"/><stop offset="1" stop-color="${C.ammonia}" stop-opacity="0"/></radialGradient>` +
      `<radialGradient id="spot"><stop offset="0.55" stop-color="#fff" stop-opacity="0.16"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>` +
      `<linearGradient id="soilband" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#3b2414" stop-opacity="0"/><stop offset="0.5" stop-color="#3b2414" stop-opacity="0.22"/><stop offset="1" stop-color="#3b2414" stop-opacity="0"/></linearGradient>` +
      `<radialGradient id="cshadow"><stop offset="0" stop-color="#1f3412" stop-opacity="1"/><stop offset="1" stop-color="#1f3412" stop-opacity="0"/></radialGradient>` +
      `<clipPath id="above"><rect x="-2000" y="-3000" width="5000" height="${3000 + GROUND + 4}"/></clipPath>` +
      `</defs><rect x="0" y="0" width="${W}" height="${H}" fill="url(#sky)"/>` + stars;
  }
  const cloud = (x, y, s, seed, dusk = 0) => D.cloud(x, y, s, seed, D.mix('#ffffff', '#c9b6e6', dusk), D.mix('#dceef8', '#9f86c8', dusk));
  // far backdrop (drawn blurred, with parallax): hills, a tree line, the barn
  function hills(dusk, t = 0) {
    const tint = c => col(c, '#7d6a9e', dusk * 0.45);
    let out = `<path d="M-900 ${GROUND + 700} L-900 880 C-500 800 -160 860 180 840 C480 820 700 740 960 790 C1220 840 1500 800 2000 850 L2000 ${GROUND + 700} Z" fill="${tint('#c4e3a0')}"/>`;
    out += `<path d="M-900 ${GROUND + 700} L-900 960 C-400 910 60 980 380 950 C660 922 940 890 1220 940 C1500 990 1800 950 2000 960 L2000 ${GROUND + 700} Z" fill="${tint('#a6d27a')}"/>`;
    // tree line: shaded round canopies of varied size
    for (let i = 0; i < 16; i++) {
      const tx = -700 + i * 170 + rand(i + 5) * 60, ty = 960 + rand(i + 9) * 20, ts = 0.8 + rand(i + 13) * 0.6;
      const c0 = tint(D.mix('#5ea840', '#7cc456', rand(i + 2)));
      out += G(tf(tx, ty, D.wind(t, tx) * 0.5 + noise(i + 40, t * 0.6) * 1.2, ts), `<rect x="-6" y="-46" width="12" height="46" fill="${tint('#7a5236')}"/>` +
        G(tf(-24, -66, 0, 1), D.shade(ellD(38, 34), c0, { depth: 12, light: 5, w: 0 })) +
        G(tf(22, -72, 0, 1), D.shade(ellD(42, 38), D.mix(c0, '#ffffff', 0.06), { depth: 12, light: 5, w: 0 })) +
        G(tf(0, -100, 0, 1), D.shade(ellD(36, 32), D.mix(c0, '#ffffff', 0.12), { depth: 10, light: 5, w: 0 })));
    }
    out += G(tf(880, 960, 0, 1.05),
      D.shade('M-60 0 L-60 -70 L0 -112 L60 -70 L60 0 Z', tint('#cf5a3f'), { dir: [1, 0.2], depth: 22, w: 0 }) +
      path('M-22 0 L-22 -40 L22 -40 L22 0 Z', tint('#f6efe0'), 0) + path('M-66 -66 L0 -118 L66 -66', 'none', 8, tint('#f6efe0')));
    return out;
  }
  // nearer hedge band (lightly blurred, parallax)
  function hedge(dusk) {
    const c0 = col('#a9da78', '#6f7f6a', dusk * 0.4);
    let d = `M-900 ${GROUND + 700} L-900 ${GROUND - 40}`;
    for (let x = -900; x <= 2000; x += 70) d += ` Q${x + 35} ${GROUND - 92 - rand(x) * 40} ${x + 70} ${GROUND - 40 - rand(x + 1) * 10}`;
    d += ` L2000 ${GROUND + 700} Z`;
    return D.shade(d, c0, { dir: [0, 1], depth: 26, light: 6, w: 0 });
  }
  // static soil detail, built once
  const SOIL_DETAIL = D.prebuilt('soil', () => {
    let s = '';
    // strata: each band a little darker going down, with a wavy boundary line
    [[GROUND + 330, '#6a4329'], [GROUND + 560, '#5e3b24'], [GROUND + 780, '#52331f']].forEach(([y, c], k) => {
      let d = `M-800 ${y}`;
      for (let x = -800; x <= 1900; x += 110) d += ` Q${x + 55} ${y - 18 + rand(x + k * 7) * 36} ${x + 110} ${y + (rand(x + k) - 0.5) * 10}`;
      s += `<path d="${d} L1900 ${GROUND + 1600} L-800 ${GROUND + 1600} Z" fill="${c}"/>`;
      s += `<path d="${d}" fill="none" stroke="#3b2414" stroke-width="3" opacity="0.35"/>`;
    });
    for (let i = 0; i < 60; i++) {
      const x = -300 + rand(i + 1200) * 1700, y = GROUND + 120 + rand(i + 1300) * 800;
      s += `<path d="M${f2(x)} ${f2(y)} q${f2(4 + rand(i) * 8)} ${f2(-3 + rand(i + 1) * 6)} ${f2(10 + rand(i + 2) * 12)} ${f2(-2 + rand(i + 3) * 4)}" fill="none" stroke="#2f1c10" stroke-width="3" stroke-linecap="round" opacity="0.4"/>`;
    }
    // a big buried stone with a cast shadow, low in the frame
    s += `<ellipse cx="170" cy="${GROUND + 640}" rx="70" ry="22" fill="#2b190d" opacity="0.35" transform="translate(16 18)"/>`;
    s += G(tf(170, GROUND + 630, -8, 1), D.shade(ellD(70, 40), '#8f8a80', { depth: 16, light: 5, w: 4, ink: '#3b2414' }));
    // soft darker bands in the subsoil
    for (let i = 0; i < 4; i++) {
      const y = GROUND + 200 + i * 160;
      s += `<path d="M-800 ${y} C-400 ${y - 30} -100 ${y + 26} 300 ${y} C700 ${y - 28} 1000 ${y + 24} 1900 ${y - 6} L1900 ${y + 70} L-800 ${y + 70} Z" fill="url(#soilband)"/>`;
    }
    for (let i = 0; i < 46; i++) {
      const x = -300 + rand(i + 3) * 1700, y = GROUND + 110 + rand(i + 50) * 820, r = 6 + rand(i + 99) * 12;
      const sc = ['#a37b58', '#8e8a82', '#b88a4a', '#9a5a3a', '#7b5134'][i % 5];
      s += G(tf(x, y, rand(i) * 80 - 40, 0.7 + rand(i + 7) * 0.7), D.shade(ellD(r * (1.1 + rand(i + 3) * 0.6), r), sc, { depth: r * 0.45, light: 2.5, w: 3, ink: '#3b2414' }));
    }
    for (let i = 0; i < 160; i++) {
      const x = -400 + rand(i + 500) * 1900, y = GROUND + 30 + rand(i + 600) * 900;
      s += `<circle cx="${f2(x)}" cy="${f2(y)}" r="${f2(1.5 + rand(i + 700) * 2.5)}" fill="${i % 2 ? '#c49a6f' : '#3f2717'}" opacity="0.55"/>`;
    }
    // topsoil clods along the band
    for (let i = 0; i < 40; i++) {
      const x = -500 + rand(i + 800) * 2100, y = GROUND + 34 + rand(i + 900) * 34;
      s += G(tf(x, y, 0, 1), D.shade(ellD(8 + rand(i) * 8, 5 + rand(i + 1) * 4), '#9a6a45', { depth: 3, light: 1.5, w: 2.5, ink: '#4a2e1c' }));
    }
    return s;
  });
  function ground(t, dusk) {
    let out = `<rect x="-800" y="${GROUND + 14}" width="2700" height="1600" fill="${D.linear([[0, '#7d5134'], [0.4, '#6a4329'], [1, '#4f311e']])}"/>`;
    // lighter topsoil band with a wavy lower edge
    let band = `M-800 ${GROUND + 14} L1900 ${GROUND + 14} L1900 ${GROUND + 70}`;
    for (let x = 1900; x >= -800; x -= 90) band += ` Q${x - 45} ${GROUND + 82 + rand(x) * 14} ${x - 90} ${GROUND + 70}`;
    out += `<path d="${band} Z" fill="${D.linear([[0, '#b98a5e'], [1, '#9c6d47']])}"/>`;
    out += `<path d="${band.replace(/^M-800 \S+ L1900 \S+ /, 'M1900 ' + (GROUND + 70) + ' ').replace(/^M1900 \S+ L/, 'M')}" fill="none" stroke="#4a2e1c" stroke-width="3" opacity="0.35"/>`;
    out += SOIL_DETAIL;
    // grass: tapered blades in three greens, leaning with the wind
    const gc = ['#4f9a33', '#6bb544', '#8ccf5c'].map(c => col(c, '#5a7a52', dusk * 0.4));
    out += `<rect x="-800" y="${GROUND - 2}" width="2700" height="18" fill="${gc[1]}"/>`;
    let blades = '';
    for (let x = -800; x <= 1900; x += 30) {
      const lean = D.wind(t, x) * 3.4;
      for (let k = 0; k < 3; k++) {
        const bx = x + k * 9 + rand(x + k) * 6, h = 20 + rand(x * 3 + k) * 18;
        const tipx = bx + (k - 1) * 6 + lean * (h / 30) + noise(x * 0.1 + k, t * 1.2) * 2;
        blades += D.taper(D.bez([bx, GROUND + 10], [bx, GROUND - h * 0.4], [tipx * 0.5 + bx * 0.5, GROUND - h * 0.8], [tipx, GROUND - h], 6), 7, 1, gc[(k + Math.round(rand(x))) % 3]);
      }
    }
    out += `<g stroke="${C.ink}" stroke-width="0">${blades}</g>`;
    out += `<path d="M-800 ${GROUND + 15} L1900 ${GROUND + 15}" stroke="${C.ink}" stroke-width="5"/>`;
    return out;
  }
  function shadow(x, w, op = 0.22) { return `<ellipse cx="${f2(x)}" cy="${GROUND + 6}" rx="${f2(w * 1.2)}" ry="14" fill="url(#cshadow)" opacity="${f2(op * 1.6)}"/>`; }

  // ---------- camera ----------
  function camera(t) {
    const k = (cx, cy, z) => [cx, cy, z];
    const cam = keys(t, [
      [0, k(345, 1060, 1.5)],
      [at('hook', 'fields') - 0.1, k(345, 1060, 1.5), 'linear'],
      [at('hook', 'fields') + 0.55, k(500, 1010, 1.22), 'outCubic'],
      [L.need.start - 0.1, k(500, 1010, 1.22), 'linear'],
      [L.need.start + 0.6, k(560, 1000, 1.22), 'inOutCubic'],
      [at('need', 'the') + 0.4, k(560, 985, 1.22), 'inOutCubic'],
      [at('need', 'but') + 0.1, k(830, 900, 1.6), 'inOutCubic'],
      [L.help.start - 0.55, k(830, 900, 1.6), 'linear'],
      [L.help.start + 0.15, k(300, 1130, 1.6), 'inOutCubic'],
      [L.nodules.start, k(300, 1130, 1.6), 'linear'],
      [L.nodules.start + 0.6, k(453, 1085, 1.65), 'inOutCubic'],
      [L.feed.start + 0.05, k(453, 1085, 1.65), 'linear'],
      [L.feed.start + 0.4, k(420, 990, 1.3), 'inOutCubic'],
      [L.release.start, k(470, 1000, 1.25), 'inOutCubic'],
      [L.next.start - 0.3, k(470, 1000, 1.25), 'linear'],
      [L.next.start + 0.35, k(660, 960, 1.35), 'inOutCubic'],
      [at('next', 'next') - 0.05, k(660, 960, 1.35), 'linear'],
      [at('next', 'next') + 0.7, k(600, 830, 0.85), 'outCubic'],
      [L.recap.start + 0.5, k(540, 596, 0.95), 'inOutCubic'],
      [END, k(540, 596, 0.95), 'linear'],
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
      // split each line into phrases with an additive cost (dynamic programme):
      // on screen at least 0.7 s and ~0.3 s per word, fits one line of type,
      // doesn't end on a function word, doesn't glue across a comma
      const ws = l.words, n = ws.length;
      const until = i => (i < n ? ws[i].start : l.end + 0.3);
      const FN = /^(the|a|an|in|of|to|into|on|and|is|their|its|for|from|that|do|has|it|but|they|called|when)$/i;
      const bare = w => w.replace(/[^a-z']/gi, '');
      const cost = (i, j) => {
        const k = j - i, d = until(j) - ws[i].start;
        const chars = ws.slice(i, j).map(w => bare(w.text)).join(' ').length;
        let c = Math.max(0, 0.7 - d) * 2 + Math.max(0, 0.3 * k - d);
        if (chars > 18) c += 5; else if (chars > 16) c += 0.4;
        if (FN.test(bare(ws[j - 1].text)) && j < n && !/[,.?!]$/.test(ws[j - 1].text)) c += 0.3;
        if (ws.slice(i, j - 1).some(w => /[,]$/.test(w.text))) c += 0.35;
        if (ws.slice(i, j - 1).some(w => /[.?!]$/.test(w.text))) c += 99;
        return c + 0.05; // slight preference for fewer, fuller phrases
      };
      const best = new Array(n + 1).fill(null);
      best[n] = { c: 0, cuts: [] };
      for (let i = n - 1; i >= 0; i--) {
        for (let j = i + 1; j <= Math.min(n, i + 4); j++) {
          const cand = { c: best[j].c + cost(i, j), cuts: [j, ...best[j].cuts] };
          if (!best[i] || cand.c < best[i].c) best[i] = cand;
        }
      }
      let i0 = 0;
      for (const j of best[0].cuts) {
        out.push({ words: ws.slice(i0, j).map(w => w.text), start: ws[i0].start, end: until(j) });
        i0 = j;
      }
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
    const q = c.start === 0 && t < 0.4 ? 1 : 0.9 + 0.1 * spring(t - c.start + LEAD, { freq: 4, damping: 0.5 });
    const p = { sx: q, sy: q };
    const y = 1478 - (1 - Math.min(1, q)) * 14;
    const pw = Math.min(800, Math.min(est, 730) + 70), ph = size * 1.22;
    const fill = isKey ? '#ffe45c' : C.white;
    return G(`translate(495 ${f2(y)}) scale(${f2(Math.max(0.01, p.sx))} ${f2(Math.max(0.01, p.sy))})`,
      `<rect x="${f2(-pw / 2)}" y="${f2(-size * 0.92)}" width="${f2(pw)}" height="${f2(ph)}" rx="${f2(ph / 2)}" fill="#3d2616" opacity="0.88"/>` +
      `<text x="6" y="8" font-size="${f2(size)}" font-weight="700" text-anchor="middle" fill="${C.ink}" opacity="0.45" stroke="${C.ink}" stroke-width="16" stroke-linejoin="round">${text}</text>` +
      `<text x="0" y="0" font-size="${f2(size)}" font-weight="700" text-anchor="middle" fill="${fill}" stroke="${C.ink}" stroke-width="16" stroke-linejoin="round" paint-order="stroke">${text}</text>`);
  }

  // ---------- lens (window into the nodule) ----------
  const LENS = { x: 588, y: 1010, r: 285 };
  const LENS_BIG = { x: 488, y: 900, r: 380 };
  const lensZoom = t => keys(t, [[L.fix.start - 0.15, 0], [L.fix.start + 0.35, 1, 'inOutCubic'], [L.feed.start - 1.0, 1], [L.feed.start - 0.5, 0, 'inOutCubic']]);
  const CELLS = Array.from({ length: 44 }, (_, i) => [(rand(i + 7) - 0.5) * 1100, (rand(i + 61) - 0.5) * 1100, 60 + rand(i + 17) * 50]);
  const BUGS = [[-170, -120, 18, 0.8], [170, -150, -24, 0.75], [-210, 120, 12, 0.7], [200, 140, -8, 0.78], [0, 260, 4, 0.7]];
  function lensInner(t, R, ce = 1) {
    let out = `<rect x="${-R * 1.6}" y="${-R * 1.6}" width="${R * 3.2}" height="${R * 3.2}" fill="#eaa392"/>`;
    const cellFill = D.radial([[0, '#fde9df'], [0.7, '#f8c9b8'], [1, '#efab98']], { cx: 0.42, cy: 0.38, r: 0.7 });
    for (const [cx, cy, r] of CELLS) {
      const dx = noise(cx, t * 0.3) * 6, dy = noise(cy, t * 0.3) * 6;
      out += circle(cx + dx, cy + dy, r, cellFill, 7, '#cf8572') + circle(cx + dx + r * 0.22, cy + dy - r * 0.12, r * 0.16, '#e3907d', 0, 'none', 'opacity="0.7"');
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
    out += n2path(fixT - 0.05, [-R * 0.82, R * 0.05], [44, 18], 0);
    out += n2path(fixT + 0.5, [R * 0.95, -R * 0.45], [170, -150], 1);
    out += n2path(fixT + 0.9, [-R * 1.0, R * 0.32], [-210, 120], 2);
    // NH3 out
    [[turnT + 0.15, -1, true], [amT, 1, false]].forEach(([t0, side, tg], i) => {
      const p = inv(t0, t0 + 1.6, t);
      if (p <= 0) return;
      const sp = pop(t, t0, 0.4);
      const x = 20 + side * (30 + p * 100), y = -80 - p * 170;
      out += nh3(x, y, sp.s * 1.4, { tag: tg ? { t, at: amT } : null });
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
    const lz = lensZoom(t), LX = lerp(LENS.x, LENS_BIG.x, lz), LY = lerp(LENS.y, LENS_BIG.y, lz), LR = lerp(LENS.r, LENS_BIG.r, lz);
    const cx = lerp(nx, LX, ce), cy = lerp(ny, LY, ce), r = Math.max(1, LR * e);
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
    out += `<g clip-path="url(#lensclip)">${G(tf(cx, cy, 0, (0.6 + 0.4 * ce) * (LR / 370) * (1 + 0.1 * inv(L.nodules.start + 0.6, L.fix.start, t))), lensInner(t, 370, ce))}</g>`;
    out += circle(cx, cy, rr - 16, 'none', 16, C.ink, 'opacity="0.16"');
    out += circle(cx, cy, rr, 'none', 24, C.ink) + circle(cx, cy, rr, 'none', 12, D.linear([[0, '#ffffff'], [1, '#bcd3e6']], { x1: 0.2, y1: 0, x2: 0.8, y2: 1 })) + circle(cx, cy, rr - 7, 'none', 2.5, '#8fa8bf', 'opacity="0.7"');
    out += `<path d="M${f2(cx - rr * 0.62)} ${f2(cy - rr * 0.5)} A${f2(rr * 0.8)} ${f2(rr * 0.8)} 0 0 1 ${f2(cx - rr * 0.1)} ${f2(cy - rr * 0.8)}" fill="none" stroke="#fff" stroke-width="12" stroke-linecap="round" opacity="0.55"/>` +
      `<circle cx="${f2(cx + rr * 0.55)}" cy="${f2(cy + rr * 0.52)}" r="${f2(rr * 0.045)}" fill="#fff" opacity="0.6"/>`;
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
    const ps = 0.82 + 0.18 * spring(t - t0 + 0.05, { freq: 2.4, damping: 0.62 });
    const plate = { sx: ps, sy: ps };
    const itT = L.recap.words[1].start;
    const ph = lerp(232, 340, ease.outCubic(inv(itT - 0.2, itT + 0.15, t)));
    const words = L.recap.words.slice(1);
    let out = `<rect x="-400" y="-170" width="800" height="${f2(ph)}" rx="44" fill="${C.cream}" stroke="${C.ink}" stroke-width="8"/>`;
    const cl = pop(t, t0, 0.45);
    out += G(tf(-322, -50, noise(81, t * 0.6) * 6, 0.5 * cl.s), tube('M0 0 L0 40', '#4fa034', 12, 6) + leaflet(-62, 0.92, C.leaf, 0.75) + leaflet(62, 0.92, C.leaf, 0.75) + leaflet(0, 1, C.leafHi, 0.75)) +
      G(tf(36, -25, 0, cl.sx, cl.sy), `<text x="0" y="0" font-size="150" font-weight="700" fill="#4e9d31" text-anchor="middle" stroke="${C.ink}" stroke-width="10" paint-order="stroke" stroke-linejoin="round">CLOVER</text>`);
    // words build into the line, each on its narration time
    const line = words.map(w => w.text.replace(/[.]/g, ''));
    const widths = line.map((w, i) => textWidth(w + (i === line.length - 1 ? '.' : ''), 62, 600) + 18);
    const total = widths.reduce((a, b) => a + b, 0);
    let x = -total / 2;
    words.forEach((w, i) => {
      const ws = t < w.start - 0.02 ? 0 : 0.6 + 0.4 * spring(t - w.start + 0.02, { freq: 3, damping: 0.5 });
      const p = { s: ws, sx: ws, sy: ws };
      const cx = x + widths[i] / 2;
      if (p.s > 0.01) out += G(tf(cx, 68, 0, p.sx, p.sy),
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
    D.begin(f);
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

    const endWink = L.recap.end + 0.7;

    // corn: appears on "Crops", droops, flinches at the bounce, grows on "next"
    const cornIn = pop(t, L.need.start, 0.5);
    const bounceT = at('need', "can't");
    const flinch = t > bounceT ? Math.exp(-(t - bounceT) * 3.5) * Math.sin((t - bounceT) * 22) * 9 : 0;
    const cg = spring(t - growT, { freq: 1.4, damping: 0.5 }) * (t > growT ? 1 : 0);
    const cornHealth = clamp(inv(L.next.start, growT + 0.6, t));
    const nod = t > endWink ? Math.exp(-(t - endWink) * 4) * Math.sin((t - endWink) * 14) * 5 : 0;
    const cornMood = t < L.next.start ? (t > bounceT - 0.1 ? 'sad' : 'curious') : t < growT ? 'curious' : t > endWink && t < endWink + 0.45 ? 'wink' : 'happy';

    // --- world ---
    // backdrop layers: sky (sun, soft clouds), far hills and trees, the hedge; each with its own parallax
    const sunY = keys(t, [[0, 290], [L.release.start - 0.3, 290], [L.release.start + 0.4, 1080, 'inQuad'], [L.next.start - 0.45, 1080], [L.next.start + 0.4, 290, 'outCubic']]);
    let sunL = `<circle cx="880" cy="${f2(sunY)}" r="150" fill="${D.radial([[0, '#fff3b0', 0.7], [1, '#fff3b0', 0]], { cx: 0.5, cy: 0.5, r: 0.5 })}"/>` +
      D.sphere(880, sunY, 64, '#ffd75e', { w: 0, spec: false });
    let skyL = '';
    [[120, 220, 1.0, 1], [700, 160, 0.8, 2], [430, 420, 0.65, 3], [980, 380, 0.75, 4]].forEach(([x, y, s, sd]) => {
      const xx = ((x + t * 16 * s + 300) % 1500) - 300;
      skyL += cloud(xx, y, s, sd, dusk);
    });
    const farL = hills(dusk, t), hedgeL = hedge(dusk);
    let world = ground(t, dusk);

    // underground spotlight on clover roots
    const spot = inv(helpT - 0.1, helpT + 0.35, t) * (1 - inv(L.feed.start + 0.3, L.feed.start + 0.9, t));
    if (spot > 0) {
      const pr = 1 + 0.04 * Math.sin(Math.max(0, t - at('help', 'underground')) * 9) * Math.exp(-Math.max(0, t - at('help', 'underground')) * 2) * (t > at('help', 'underground') ? 1 : 0);
      world += ell(CLOVER_X - 5, GROUND + 160, 190 * pr, 170 * pr, 'url(#spot)', 0, 'none', `opacity="${f2(spot)}"`);
      world += ell(CLOVER_X - 5, GROUND + 160, 175 * pr, 158 * pr, 'none', 5, '#fff', `stroke-dasharray="18 14" opacity="${f2(spot * 0.8)}"`);
    }

    // roots (clover's fade after it dies), corn roots
    if (t < L.recap.start + 0.5) world += roots(CLOVER_X, { t, nodulePop: at('nodules', 'bumps'), pulse: at('nodules', 'bumps'), fade: inv(dieT, dieT + 1, t), gone: 0.55 * inv(relT, relT + 0.8, t) + 0.45 * inv(L.next.start, L.recap.start + 0.4, t) });
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
    {
      const fixT = at('fix', 'pull'), d0 = fixT - 0.7, d1 = fixT - 0.05;
      if (t > d0 && t < d1 + 0.25) {
        const [nx, ny] = NODULE_WORLD();
        const p = ease.inQuad(inv(d0, d1, t));
        world += n2(lerp(nx + 70, nx, p), lerp(GROUND - 640, ny, p), 0.85 * (1 - inv(d1, d1 + 0.2, t)), p * 160);
        if (t > d1) world += circle(nx, ny, 18 + (t - d1) * 120, 'none', 5, '#fff', `opacity="${f2(1 - inv(d1, d1 + 0.25, t))}"`);
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
        world += nDot(x, y, 0.42, 1 - inv(0.55, 0.85, p));
      }
    }

    // background field: small clovers (pop on "fields"), then small corn
    const BG = [40, 150, 480, 880, 1000];
    let bgPlants = '';
    BG.forEach((x, i) => {
      const p = pop(t, fieldsT + i * 0.06, 0.5);
      if (p.s > 0.01 && sinkP < 1) bgPlants += G(tf(x, 0, (rand(i + 71) - 0.5) * 8, 1), clover(0, { t, s: 0.42 * (0.82 + rand(i + 61) * 0.36) * p.s, seed: 10 + i, wilt, wind: D.wind(t, x), sink: sinkP * 120, face: false, mood: 'happy', sq: [p.sx / Math.max(p.s, 0.01), p.sy / Math.max(p.s, 0.01)] }));
    });
    [150, 480, 900].forEach((x, i) => {
      const g = spring(t - (growT + 0.15 + i * 0.08), { freq: 1.4, damping: 0.5 }) * (t > growT + 0.15 + i * 0.08 ? 1 : 0);
      if (g > 0.01) bgPlants += corn(x, { t, grow: g * 0.9, health: cornHealth, wind: D.wind(t, x), s: 0.5 * Math.min(1, g * 1.4), face: false, seed: 20 + i, cob: 0 });
    });
    world += `<g clip-path="url(#above)">${bgPlants}</g>`;

    // hero clover
    if (sinkP < 1) {
      world += shadow(CLOVER_X, 70 * (1 - sinkP), 0.2);
      world += `<g clip-path="url(#above)">` + clover(CLOVER_X, {
        t, s: 1.0 * clGrow, wilt, sink: sinkP * 330, flower: inv(feedT - 0.05, flowerT, t), flowerAt: flowerT,
        mood: clMood, lookX: clLook[0], lookY: clLook[1], bl: blink(t, 1, 3.1), sq: bounceSq, seed: 1,
        wind: D.wind(t, CLOVER_X) * (1 - wilt), windLag: D.wind(t - 0.15, CLOVER_X) * (1 - wilt),
      }) + `</g>`;
    }
    // the old clover's remains glow on "Clover." under the end card
    {
      const g = pop(t, L.recap.start, 0.6).s * (1 - 0.5 * inv(L.recap.start + 0.8, L.recap.start + 1.6, t));
      void g;
    }

    // hero corn
    if (cornIn.s > 0.01) {
      world += shadow(CORN_X, lerp(55, 120, cg), 0.2);
      world += `<g clip-path="url(#above)">` + corn(CORN_X, {
        t, grow: cg, health: cornHealth, mood: cornMood, flinch: flinch + nod, s: cornIn.s * 1.35, bl: blink(t, 2, 3.4), wind: D.wind(t, CORN_X),
        lookX: t < bounceT ? -0.3 : 0.2, lookY: t < bounceT && t > at('need', 'the') ? -1 : 0,
        cob: pop(t, growT + 0.75, 0.5).s, sq: [cornIn.sx / Math.max(cornIn.s, 0.01), cornIn.sy / Math.max(cornIn.s, 0.01)],
      }) + `</g>`;
    }

    // soil crumbs where things break the surface
    world += D.crumbs(t, L.need.start, CORN_X, GROUND + 6, { seed: 5, n: 10 });
    world += D.crumbs(t, dieT + 0.75, CLOVER_X, GROUND + 6, { seed: 9, n: 14, up: 420 });
    world += D.crumbs(t, growT, CORN_X, GROUND + 6, { seed: 13, n: 12, up: 600 });
    BG.forEach((x, i) => { world += D.crumbs(t, fieldsT + i * 0.06, x, GROUND + 6, { seed: 30 + i, n: 5, up: 300 }); });
    // nitrogen in the air
    const airT = at('need', 'air');
    for (let i = 0; i < 9; i++) {
      const p = pop(t, airT - 0.15 + i * 0.07, 0.5);
      const out = 1 - ease.inCubic(inv(L.help.start + 0.2 + i * 0.03, L.help.start + 0.7 + i * 0.03, t));
      const edge = (() => { const [sx] = toScreen(cam, 230 + (i % 3) * 230 + (Math.floor(i / 3) % 2) * 105 + t * 4, 0); return clamp(inv(20, 90, sx) * inv(1060, 960, sx)); })();
      if (p.s * out * edge <= 0.01) continue;
      const row = Math.floor(i / 3), colm = i % 3;
      const bx = 230 + colm * 230 + (row % 2) * 105 + (rand(i + 200) - 0.5) * 40, by = 410 + row * 125 + (rand(i + 300) - 0.5) * 30;
      const x = bx + noise(i + 400, t * 0.4) * 22 + t * 4, y = by + noise(i + 500, t * 0.35) * 18;
      world += n2(x, y - (1 - out) * 120, 1.15 * p.s * out * (0.4 + 0.6 * edge), noise(i + 600, t * 0.3) * 40, i === 4 ? { tag: { t, at: airT + 0.3 } } : {});
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
          world += `<g opacity="${f2(1 - q)}">` + D.shock(CORN_X - 6, GROUND - 230, -Math.PI * 0.62, 1 + q * 0.4) + D.shock(CORN_X - 6, GROUND - 230, -Math.PI * 0.2, 0.8 + q * 0.4) + `</g>`;
        }
      }
    }

    // the new clover's nitrogen flows to the corn under the end card
    if (t > L.recap.start + 0.4) {
      for (let i = 0; i < 6; i++) {
        const ph = ((t - L.recap.start - 0.4) / 1.8 + i / 6) % 1;
        const x = lerp(CLOVER_X + 30, CORN_X - 20, ph), y = GROUND + 120 - Math.sin(ph * Math.PI) * 40;
        world += nDot(x, y, 0.75, Math.sin(ph * Math.PI) * inv(L.recap.start + 0.4, L.recap.start + 0.9, t));
      }
    }
    // released nitrogen spreading through soil, then flowing to the corn
    let glowLayer = '';
    if (t > nitroT - 0.1 && t < L.recap.start + 1.5) {
      for (let i = 0; i < 26; i++) {
        const a = rand(i + 700) * Math.PI * 2, d = 60 + rand(i + 800) * 220;
        const sx = CLOVER_X + 60 + Math.cos(a) * d * 0.85, sy = GROUND + 120 + Math.sin(a) * d * 0.35;
        const spread = ease.outCubic(inv(nitroT - 0.1 + i * 0.03, relT + 0.6 + i * 0.02, t));
        const toCorn = ease.inOutCubic(inv(L.next.start - 0.1 + i * 0.025, growT + 0.35 + i * 0.02, t));
        const x0 = lerp(CLOVER_X, sx, spread), y0 = lerp(GROUND + 120, sy, spread);
        const tx = CORN_X + (rand(i + 900) - 0.5) * 120, ty = GROUND + 40 + rand(i + 950) * 100;
        const x = lerp(x0, tx, toCorn) + noise(i + 1000, t) * 6, y = lerp(y0, ty, toCorn) + noise(i + 1100, t) * 6;
        const op = spread * (1 - inv(growT + 0.2, growT + 0.9, t));
        const bright = 1 + 0.25 * Math.exp(-Math.max(0, t - relT) * 3) * (t > relT ? 1 : 0);
        const [, scrY] = toScreen(cam, x, y);
        const clear = 1 - inv(1300, 1345, scrY);
        if (op * clear > 0.01 && i % 3 !== 2) glowLayer += nDot(x, y, 0.58 * bright, op * clear);
      }
    }

    // assemble: camera transform over the world
    const camT = `translate(${W / 2} ${H / 2}) scale(${f2(cam.z)}) translate(${f2(-cam.cx)} ${f2(-cam.cy)})`;
    const layerT = p => `translate(${W / 2} ${H / 2}) scale(${f2(1 + (cam.z - 1) * p)}) translate(${f2(-(540 + (cam.cx - 540) * p))} ${f2(-(960 + (cam.cy - 960) * p))})`;
    const dof = 1 + Math.max(0, cam.z - 1) * 1.4;
    let svg = sky(t, dusk);
    svg += `<g transform="${layerT(0.15)}">${sunL}</g>`;
    svg += `<g filter="${D.blurFilter(3.5)}"><g transform="${layerT(0.15)}">${skyL}</g></g>`;
    svg += `<g filter="${D.blurFilter(5 * dof)}"><g transform="${layerT(0.45)}">${farL}</g></g>`;
    svg += `<g filter="${D.blurFilter(2.4 * dof)}"><g transform="${layerT(0.75)}">${hedgeL}</g></g>`;
    svg += `<g transform="${camT}">${world}</g>`;
    if (dusk > 0.01) svg += `<rect width="${W}" height="${H}" fill="#5a4a8a" opacity="${f2(dusk * 0.38)}" style="mix-blend-mode:multiply"/>`;
    if (glowLayer) svg += `<g transform="${camT}">${glowLayer}</g>`;
    svg += lens(t, cam);
    svg += t < L.recap.start - 0.05 ? captions(t) : '';
    svg += title(t);
    // hook mark: a question bubble beside the clover on frame one
    const q = 1 - inv(at('hook', 'fields'), at('hook', 'fields') + 0.25, t);
    if (q > 0) {
      const [qx, qy] = toScreen(cam, CLOVER_X + 130, GROUND - 400);
      const b = 1 + 0.06 * Math.sin(t * 5);
      svg += G(tf(qx, qy + Math.sin(t * 3) * 6, 8, b * q), circle(0, 0, 58, C.white, 6) + path('M-30 44 L-50 74 L-6 56', C.white, 6) + `<rect x="-40" y="34" width="44" height="22" fill="#fff"/>` +
        `<text x="0" y="26" font-size="78" font-weight="700" fill="${C.nitro}" text-anchor="middle">?</text>`);
    }
    return svg + D.defs();
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
    cue(at('fix', 'pull') - 0.05, 'pop_small', 0.6),
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
