// "Not a Tree" — every pixel is a function of the frame number.
// Timing comes from timing.json (narration word times); nothing here uses a
// clock or unseeded randomness.
(function () {
  const { clamp, lerp, inv, ease, spring, keys, noise, rand, blink, pop, tf } = M;
  const T = M.bindTiming(window.TIMING);
  const FPS = 30, W = 1080, H = 1920;
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
  const CLOVER_X = 300, CORN_X = 790;
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
  // plants use the shared face rig, so they get eyelid acting and lip-sync
  function face(o) {
    const map = { curious: 'skeptical', wink: 'happy', open: 'surprised', chomp: 'surprised' };
    return Cast.face({ ...o, mood: map[o.mood] || o.mood || 'happy', wink: o.mood === 'wink', rx: 14, ry: 17, mouthY: 30, sep: o.sep || 21, lid: o.lid || C.leafHi });
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

  // ---------- captions ----------
  const LEAD = 2 / FPS; // captions land two frames before their word, so they read on it
  const KEY = new Set(['nitrogen', 'rhizobia', 'ammonia', 'clover', 'underground', 'soil', 'crop', 'bacteria', 'roots']);
  const CHUNKS = (() => {
    const out = [];
    for (const l of window.TIMING.lines) {
      if (l.id === 'later' || l.id === 'spring') continue;
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
        out.push({ words: ws.slice(i0, j).map(w => w.text), start: ws[i0].start, end: until(j), speaker: l.speaker });
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
      `<rect x="${f2(-pw / 2)}" y="${f2(-size * 0.92)}" width="${f2(pw)}" height="${f2(ph)}" rx="${f2(ph / 2)}" fill="#3d2616" fill-opacity="0.88" stroke="${SPK_COL[c.speaker] || '#fff'}" stroke-width="5"/>` +
      `<text x="6" y="8" font-size="${f2(size)}" font-weight="700" text-anchor="middle" fill="${C.ink}" opacity="0.45" stroke="${C.ink}" stroke-width="16" stroke-linejoin="round">${text}</text>` +
      `<text x="0" y="0" font-size="${f2(size)}" font-weight="700" text-anchor="middle" fill="${fill}" stroke="${C.ink}" stroke-width="16" stroke-linejoin="round" paint-order="stroke">${text}</text>`);
  }

  // ---------- lens (window into the nodule) ----------
  const LENS = { x: 790, y: 760, r: 250 };
  const LENS_BIG = { x: 760, y: 740, r: 295 };
  const lensZoom = t => keys(t, [[L.fix.start - 0.15, 0], [L.fix.start + 0.35, 1, 'inOutCubic'], [L.yum.start - 1.0, 1], [L.yum.start - 0.5, 0, 'inOutCubic']]);
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
    const rhT = at('nodules', 'rhizobia'), liveT = at('nodules', 'called');
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
      const x = 20 + side * (30 + p * 80), y = -80 - p * 120;
      out += nh3(x, y, sp.s * 1.4, { tag: tg ? { t, at: amT } : null });
    });
    return out;
  }
  function lens(t, cam) {
    const t0 = B.lensOpen, t1 = B.lensClose;
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

  // ================= story: "Not a Tree" =================
  const SPK_COL = { nana: '#f6d046', wiggs: '#a77bf0' };
  const MOUTH = window.TIMING.mouth || {};
  const talkOf = (spk, f) => (MOUTH[spk] && MOUTH[spk][f]) || 0;
  const NANA_X = 540, HOLE_X = 690;

  const B = {
    wigPop: L.stem.start - 0.25,
    sliceIn: at('stem', 'pseudostem') - 0.1, sliceOut: L.stem.end + 0.4,
    flowT: at('corm', 'everything'), cormT: at('corm', 'corm'),
    spikeA: L.coming.end, spikeB: at('spike', 'stops'), spikeC: L.spike.end + 0.2,
    bractT: at('bracts', 'bracts'), handsT: at('bracts', 'hands'),
    nineA: at('nine', 'nine') - 0.1, nineB: at('nine', 'bunch') + 0.4, twentyT: at('nine', 'twenty'),
    montA: L.nine.end + 0.1, montB: L.sucker.start - 0.1,
    suckT: at('sucker', 'sucker') - 0.2,
    endWink: L.herb.end + 0.55,
  };
  const END = L.herb.end + 1.5;

  // ---------- title card ----------
  function title(t) {
    const t0 = L.herb.start;
    if (t < t0 - 0.05) return '';
    const ps = 0.82 + 0.18 * spring(t - t0 + 0.05, { freq: 2.4, damping: 0.62 });
    const a = 0.6 + 0.4 * spring(t - t0, { freq: 3, damping: 0.5 });
    let out = `<rect x="-404" y="-160" width="808" height="330" rx="44" fill="${C.ink}" opacity="0.25" transform="translate(8 10)"/>`;
    out += `<rect x="-404" y="-160" width="808" height="330" rx="44" fill="${C.cream}" stroke="${C.ink}" stroke-width="8"/>`;
    out += G(tf(0, -26, 0, a), `<text x="0" y="0" font-size="118" font-weight="700" fill="#e0b324" text-anchor="middle" stroke="${C.ink}" stroke-width="10" paint-order="stroke" stroke-linejoin="round">BANANA</text>`);
    if (t > t0 + 0.3) {
      const b = 0.6 + 0.4 * spring(t - t0 - 0.3, { freq: 3, damping: 0.5 });
      out += G(tf(0, 66, 0, b), `<text x="0" y="0" font-size="58" font-weight="700" fill="${C.ink}" text-anchor="middle">Not a tree. A giant herb.</text>`);
    }
    out += `<text x="0" y="132" font-size="32" font-weight="600" fill="#6b5646" text-anchor="middle" opacity="${f2(inv(t0 + 0.6, t0 + 1.0, t))}">Source: Wikipedia, “Banana”</text>`;
    return G(tf(495, 330 + noise(77, t * 0.6) * 4, 0, ps, ps), out);
  }

  // ---------- camera ----------
  function camera(t) {
    const k = (cx, cy, z) => [cx, cy, z];
    const cam = keys(t, [
      [0, k(540, 700, 0.92)],
      [L.stem.start - 0.3, k(540, 700, 0.92), 'linear'],
      [L.stem.start + 0.4, k(580, 820, 1.25), 'inOutCubic'],
      [B.flowT - 0.1, k(580, 820, 1.25), 'linear'],
      [B.flowT + 0.5, k(560, 760, 1.0), 'inOutCubic'],
      [at('corm', 'this') - 0.2, k(560, 760, 1.0), 'linear'],
      [at('corm', 'this') + 0.5, k(540, 1080, 1.35), 'inOutCubic'],
      [L.coming.start - 0.3, k(540, 1080, 1.35), 'linear'],
      [L.coming.start + 0.4, k(500, 620, 1.0), 'inOutCubic'],
      [B.spikeB, k(500, 620, 1.0), 'linear'],
      [B.spikeC, k(420, 560, 1.08), 'inOutCubic'],
      [L.bracts.start - 0.2, k(420, 560, 1.08), 'linear'],
      [L.bracts.start + 0.5, k(360, 520, 1.42), 'inOutCubic'],
      [B.montA - 0.1, k(360, 520, 1.42), 'linear'],
      [B.montA + 0.6, k(540, 700, 0.92), 'inOutCubic'],
      [L.sucker.start - 0.1, k(540, 700, 0.92), 'linear'],
      [L.sucker.start + 0.5, k(610, 860, 1.12), 'inOutCubic'],
      [L.herb.start - 0.2, k(610, 860, 1.12), 'linear'],
      [L.herb.start + 0.5, k(540, 540, 0.85), 'inOutCubic'],
      [END, k(540, 540, 0.85), 'linear'],
    ]);
    return { cx: cam[0], cy: cam[1], z: cam[2] };
  }
  const toScreen = (cam, x, y) => [W / 2 + (x - cam.cx) * cam.z, H / 2 + (y - cam.cy) * cam.z];

  // ---------- Wiggs ----------
  const GR = GROUND;
  const POSE = {
    hide: [[HOLE_X + 10, GR + 150], [HOLE_X + 50, GR + 175], [HOLE_X + 40, GR + 250], [HOLE_X - 10, GR + 245]],
    rise: [[HOLE_X + 5, GR + 40], [HOLE_X + 15, GR + 110], [HOLE_X + 30, GR + 170], [HOLE_X + 20, GR + 230]],
    out: [[HOLE_X, GR - 175], [HOLE_X + 6, GR - 60], [HOLE_X + 2, GR + 40], [HOLE_X + 28, GR + 135]],
    point: [[HOLE_X - 30, GR + 60], [HOLE_X - 5, GR + 20], [HOLE_X + 10, GR + 70], [HOLE_X + 30, GR + 150]],
    peek: [[HOLE_X, GR - 70], [HOLE_X + 3, GR + 10], [HOLE_X + 8, GR + 70], [HOLE_X + 36, GR + 140]],
  };
  function wiggsPose(t) {
    const P = n => POSE[n].flat();
    const v = keys(t, [
      [0, P('hide')], [B.wigPop - 0.05, P('hide')], [B.wigPop + 0.12, P('rise'), 'inQuad'], [B.wigPop + 0.4, P('out'), 'outBack'],
      [at('corm', 'this') - 0.3, P('out')], [at('corm', 'this') + 0.3, P('point'), 'inOutCubic'],
      [L.coming.start, P('point')], [L.coming.start + 0.5, P('hide'), 'inOutCubic'],
      [B.montA, P('hide')], [B.montA + 0.6, P('peek'), 'outBack'],
      [L.herb.start - 0.5, P('peek')], [L.herb.start - 0.1, P('out'), 'outBack'],
    ]);
    return [[v[0], v[1]], [v[2], v[3]], [v[4], v[5]], [v[6], v[7]]];
  }

  // ---------- the film ----------
  function frame(f) {
    D.begin(f);
    const t = f / FPS;
    const cam = camera(t);
    // day/night cycles while the bunch ripens
    const mont = inv(B.montA, B.montB, t);
    const dusk = mont > 0 && mont < 1 ? 0.5 - 0.5 * Math.cos(mont * Math.PI * 4) : 0;
    const ripe = ease.inOutCubic(mont);

    // --- Big Nana ---
    const growth = lerp(0.94, 1, inv(at('spike', 'mature') - 0.2, at('spike', 'mature') + 0.4, t));
    const unfurl = 0.15 + 0.85 * ease.inOutCubic(inv(0.3, L.stem.end, t));
    const flower = 0.45 * ease.outCubic(inv(B.spikeA, B.spikeB, t)) + 0.55 * ease.inOutCubic(inv(B.spikeB, B.spikeC, t));
    const bracts = ease.outCubic(inv(B.bractT - 0.5, B.bractT + 0.6, t));
    const bunch = 0.34 * ease.outCubic(inv(B.handsT - 0.3, L.bracts.end, t)) + 0.66 * clamp(inv(B.nineA, B.nineB, t));
    const pup = ease.outBack(inv(B.suckT, B.suckT + 1.2, t), 1.2);
    let nMood = 'annoyed';
    if (t > L.hook.end) nMood = 'skeptical';
    if (t > B.sliceIn + 0.3) nMood = 'surprised';
    if (t > L.corm.start) nMood = 'excited';
    if (t > L.coming.start) nMood = 'surprised';
    if (t > L.spike.start) nMood = 'proud';
    if (t > L.bracts.start) nMood = 'happy';
    if (t > L.nine.start) nMood = 'proud';
    if (mont > 0 && mont < 1) nMood = dusk > 0.6 ? 'sleep' : 'happy';
    if (t > L.sucker.start) nMood = 'excited';
    if (t > L.herb.start) nMood = 'proud';
    const nLook = t > L.stem.start && t < L.coming.start ? [1, 0.6] : t > L.coming.start && t < B.montA ? [-0.8, -1] : t > L.sucker.start && t < L.herb.start ? [1, 0.7] : [0.3, 0];

    let world = ground(t, dusk);
    // light flowing up from the corm into everything above ground
    let glowW = '';
    if (t > B.flowT - 0.1 && t < B.cormT + 1.2) {
      const crownY = GROUND - lerp(110, 640, growth) + 8;
      for (let i = 0; i < 14; i++) {
        const p = ((t - B.flowT) * 0.9 + i / 14) % 1;
        const fade = Math.sin(clamp(inv(B.flowT - 0.1, B.flowT + 0.4, t)) * Math.PI / 2) * (1 - inv(B.cormT + 0.4, B.cormT + 1.2, t));
        const branch = i % 4, ang = [-150, -30, -110, -70][branch] * Math.PI / 180;
        let x, y;
        if (p < 0.6) { x = NANA_X + (i % 3 - 1) * 8; y = lerp(GROUND + 40, crownY, p / 0.6); }
        else { const q = (p - 0.6) / 0.4; x = NANA_X + Math.cos(ang) * 260 * q; y = crownY + Math.sin(ang) * 260 * q; }
        glowW += `<circle cx="${f2(x)}" cy="${f2(y)}" r="22" fill="url(#glow)" opacity="${f2(0.8 * fade)}"/><circle cx="${f2(x)}" cy="${f2(y)}" r="6" fill="#eaffb0" opacity="${f2(fade)}"/>`;
      }
    }
    // corm spotlight on "corm"
    {
      const g = Math.sin(clamp(inv(B.cormT - 0.15, B.cormT + 1.4, t)) * Math.PI);
      if (g > 0.01) {
        world += `<ellipse cx="${NANA_X}" cy="${GROUND + 44}" rx="${f2(150 + 20 * g)}" ry="${f2(90 + 12 * g)}" fill="url(#glow)" opacity="${f2(0.7 * g)}"/>`;
        world += `<ellipse cx="${NANA_X}" cy="${GROUND + 44}" rx="${f2(130 + 30 * (1 - g))}" ry="${f2(78 + 18 * (1 - g))}" fill="none" stroke="#fff" stroke-width="5" stroke-dasharray="16 12" opacity="${f2(0.9 * g)}"/>`;
      }
    }
    world += shadow(NANA_X, 130, 0.24);
    world += Cast.banana(NANA_X, GROUND + 6, {
      t, s: 1, growth, unfurl, flower, bunch, ripe, bracts, wind: D.wind(t, NANA_X) * 1.8, underground: true, pup, side: 1, spikeSide: -1, seed: 5,
      face: { mood: nMood, talk: talkOf('nana', f), lookX: nLook[0], lookY: nLook[1], bl: blink(t + 0.7, 3, 3.3), wink: t > B.endWink && t < B.endWink + 0.45 },
      colors: { blotch: '#4d3346' },
    });
    world += D.crumbs(t, B.wigPop + 0.1, HOLE_X, GROUND + 6, { seed: 41, n: 12, up: 520 });
    world += D.crumbs(t, B.suckT, NANA_X + 1.55 * 108, GROUND + 6, { seed: 23, n: 12, up: 480 });
    // Wiggs
    {
      const sp = wiggsPose(t);
      const pts = Cast.spine(sp[0], sp[1], sp[2], sp[3], t, t < B.wigPop ? 1.5 : 4, 24);
      let wm = t < B.wigPop ? 'sleep' : t < B.wigPop + 0.6 ? 'surprised' : 'smug';
      if (mont > 0 && mont < 1) wm = 'sleep';
      if (t > L.sucker.start) wm = 'happy';
      world += Cast.worm(pts, { t, talk: talkOf('wiggs', f), mood: wm, lookX: t > at('corm', 'this') && t < L.coming.start ? -1 : -0.6, lookY: t > at('corm', 'this') && t < L.coming.start ? 0.6 : 0,
        bl: blink(t, 4, 2.9), wink: t > B.endWink && t < B.endWink + 0.45, headS: 1.5 });
    }

    // backdrop layers
    const sunX = mont > 0 && mont < 1 ? lerp(-100, 1180, (mont * 2) % 1) : 880;
    const sunY = mont > 0 && mont < 1 ? 900 - Math.sin(((mont * 2) % 1) * Math.PI) * 700 : 290;
    const sunL = `<circle cx="${f2(sunX)}" cy="${f2(sunY)}" r="150" fill="${D.radial([[0, '#fff3b0', 0.7], [1, '#fff3b0', 0]], { cx: 0.5, cy: 0.5, r: 0.5 })}"/>` + D.sphere(sunX, sunY, 64, '#ffd75e', { w: 0, spec: false });
    let skyL = '';
    [[120, 220, 1.0, 1], [700, 160, 0.8, 2], [430, 420, 0.65, 3], [980, 380, 0.75, 4]].forEach(([x, y, s, sd]) => {
      const xx = ((x + t * (mont > 0 && mont < 1 ? 120 : 16) * s + 300) % 1500) - 300;
      skyL += D.cloud(xx, y, s, sd, D.mix('#ffffff', '#c9b6e6', dusk), D.mix('#dceef8', '#9f86c8', dusk));
    });
    const farL = hills(dusk, t), hedgeL = hedge(dusk);
    const fgL = D.fgGrass(1230, GROUND + 40, 560, 7, t);
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
    if (glowW) svg += `<g transform="${camT}">${glowW}</g>`;
    svg += `<g filter="${D.blurFilter(9)}"><g transform="${layerT(1.4)}">${fgL}</g></g>`;

    // the pseudostem cut-away: a slice pops out of the trunk showing layer on layer of leaf stalks
    {
      const pin = ease.outBack(inv(B.sliceIn, B.sliceIn + 0.5, t), 1.3), pout = 1 - ease.inCubic(inv(B.sliceOut - 0.35, B.sliceOut, t));
      const k = Math.min(pin, pout);
      if (k > 0.01) {
        const [sx, sy] = toScreen(cam, NANA_X + 20, GROUND - 330);
        const cx = lerp(sx, 800, ease.outCubic(Math.min(1, pin))), cy = lerp(sy, 700, ease.outCubic(Math.min(1, pin))), r = 175 * k;
        let rings = '';
        const nR = 7;
        for (let i = 0; i < nR; i++) {
          const ri = r * (1 - i / nR), ox = -i * r * 0.035, oy = i * r * 0.02;
          const show = clamp((t - B.sliceIn - 0.25 - i * 0.08) / 0.2);
          if (show <= 0) continue;
          const colr = D.mix(i % 2 ? '#8cc456' : '#b5dd7a', '#e9f6c9', i / nR * 0.6);
          rings += `<circle cx="${f2(cx + ox)}" cy="${f2(cy + oy)}" r="${f2(ri * (0.9 + 0.1 * show))}" fill="${colr}" stroke="${C.ink}" stroke-width="4" opacity="${f2(show)}"/>`;
          // each layer is a leaf stalk wrapped around the next: show its seam
          rings += `<path d="M${f2(cx + ox + ri * 0.98)} ${f2(cy + oy)} L${f2(cx + ox + ri * 0.82)} ${f2(cy + oy - ri * 0.06)}" stroke="${C.ink}" stroke-width="4" opacity="${f2(show)}"/>`;
        }
        const ang = Math.atan2(cy - sy, cx - sx), dist = Math.hypot(cx - sx, cy - sy);
        if (dist > r) {
          const spn = Math.asin(Math.min(1, r / dist));
          const a1 = ang + Math.PI - (Math.PI / 2 - spn), a2 = ang + Math.PI + (Math.PI / 2 - spn);
          svg += `<path d="M${f2(sx)} ${f2(sy)} L${f2(cx + Math.cos(a1) * r)} ${f2(cy + Math.sin(a1) * r)} L${f2(cx + Math.cos(a2) * r)} ${f2(cy + Math.sin(a2) * r)} Z" fill="#fff" opacity="${f2(0.35 * k)}"/>`;
        }
        svg += circle(cx + 8, cy + 10, r, C.ink, 0, 'none', 'opacity="0.25"');
        svg += circle(cx, cy, r, '#6aa83f', 9, C.ink) + rings + circle(cx, cy, r, 'none', 9, C.ink);
        svg += circle(sx, sy, 22 * cam.z, 'none', 5, '#fff', `opacity="${f2(k)}"`);
      }
    }
    // hands counter, then "up to 20 each"
    {
      const hands = Math.floor(clamp(bunch) * 9 + 1e-6);
      const on = clamp(inv(B.nineA - 0.1, B.nineA + 0.2, t)) * (1 - inv(B.montA - 0.2, B.montA + 0.2, t));
      if (on > 0.01 && hands > 0) {
        const bump = 1 + 0.12 * Math.exp(-((t * 9 * 1.0) % 1) * 0) * 0;
        const lastStep = (B.nineA + (hands - 3) / 6 * (B.nineB - B.nineA));
        const pp = 1 + 0.18 * Math.exp(-Math.max(0, t - lastStep) * 9);
        svg += G(tf(300, 330, -3, on * pp * bump), `<rect x="-170" y="-58" width="340" height="116" rx="58" fill="#fff8e8" stroke="${C.ink}" stroke-width="7"/>` +
          `<text x="0" y="24" font-size="70" font-weight="700" fill="${C.ink}" text-anchor="middle">${hands} <tspan fill="#4e9d31">HANDS</tspan></text>`);
      }
      const on2 = clamp(inv(B.twentyT - 0.05, B.twentyT + 0.25, t)) * (1 - inv(B.montA - 0.2, B.montA + 0.2, t));
      if (on2 > 0.01) svg += G(tf(700, 470, 3, on2 * (0.7 + 0.3 * ease.outBack(clamp(inv(B.twentyT, B.twentyT + 0.35, t))))),
        `<rect x="-230" y="-52" width="460" height="104" rx="52" fill="#f6d046" stroke="${C.ink}" stroke-width="7"/>` +
        `<text x="0" y="-2" font-size="40" font-weight="700" fill="${C.ink}" text-anchor="middle">UP TO 20</text><text x="0" y="36" font-size="30" font-weight="600" fill="${C.ink}" text-anchor="middle">bananas per hand</text>`);
    }
    svg += captions(t);
    svg += title(t);
    return svg + D.defs();
  }

  // ---------- sound cues (read by engine/audio.py) ----------
  const cue = (t, type, gain = 1) => ({ t: +t.toFixed(3), type, gain });
  window.CUES = [
    cue(L.stem.start - 0.3, 'whoosh'), cue(B.wigPop + 0.1, 'pop'), cue(B.wigPop + 0.15, 'sink', 0.6),
    cue(B.sliceIn, 'lens_open'), cue(B.sliceOut - 0.35, 'lens_close'),
    cue(B.flowT - 0.1, 'shimmer'), cue(at('corm', 'this') - 0.2, 'whoosh'), cue(B.cormT, 'chime', 0.7),
    cue(L.coming.start - 0.3, 'whoosh'), cue(B.spikeA, 'grow'), cue(B.spikeB + 0.2, 'grow_big', 0.8),
    cue(L.bracts.start - 0.2, 'whoosh'), cue(B.bractT - 0.3, 'sparkle'),
    ...Array.from({ length: 9 }, (_, h) => cue(h < 3 ? B.handsT - 0.3 + h * 0.5 : B.nineA + (h - 3) / 6 * (B.nineB - B.nineA), 'pop_small', 0.6)),
    cue(B.twentyT, 'chime', 0.7),
    cue(B.montA, 'whoosh'), cue(B.montA + 0.7, 'twinkle', 0.7), cue(B.montA + 2.1, 'twinkle', 0.7),
    cue(L.sucker.start - 0.1, 'whoosh'), cue(B.suckT, 'pop'), cue(B.suckT + 0.1, 'grow'),
    cue(L.herb.start - 0.2, 'whoosh'), cue(L.herb.start, 'chime'),
    cue(B.endWink, 'wink'),
  ].sort((a, b) => a.t - b.t);

  const stage = document.getElementById('stage');
  window.renderFrame = f => { stage.innerHTML = frame(f); };
  window.FILM = { width: W, height: H, fps: FPS, frames: Math.round(END * FPS), safe: SAFE, ready: false };
  document.fonts.load('700 40px Fredoka').then(() => { window.FILM.ready = true; });
})();
