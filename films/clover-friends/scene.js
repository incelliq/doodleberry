// "Clover Friends" — every pixel is a function of the frame number.
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

  // ================= story: "Clover Friends" =================
  const SPK_COL = { mina: '#ff8a6e', kernel: '#ffd23f', wiggs: '#a77bf0', clover: '#86d957', narrator: '#ffffff' };
  const MOUTH = window.TIMING.mouth || {};
  const talkOf = (spk, f) => (MOUTH[spk] && MOUTH[spk][f]) || 0;
  const DIV_X = 560, MINA_X = -40, MINA_X2 = 60, TALL_X = 330;

  // ---------- title card ----------
  function title(t) {
    const t0 = L.rotate.start;
    if (t < t0 - 0.05) return '';
    const ps = 0.82 + 0.18 * spring(t - t0 + 0.05, { freq: 2.4, damping: 0.62 });
    const w2 = t0 + 0.3;
    let out = `<rect x="-404" y="-160" width="808" height="330" rx="44" fill="${C.ink}" opacity="0.25" transform="translate(8 10)"/>`;
    out += `<rect x="-404" y="-160" width="808" height="330" rx="44" fill="${C.cream}" stroke="${C.ink}" stroke-width="8"/>`;
    const a = 0.6 + 0.4 * spring(t - t0, { freq: 3, damping: 0.5 });
    out += G(tf(-250, -40, noise(81, t * 0.6) * 6, 0.5 * a), tube('M0 0 L0 40', '#4fa034', 12, 6) + leaflet(-62, 0.92, C.leaf, 0.75) + leaflet(62, 0.92, C.leaf, 0.75) + leaflet(0, 1, C.leafHi, 0.75));
    out += G(tf(60, -26, 0, a), `<text x="0" y="0" font-size="118" font-weight="700" fill="#4e9d31" text-anchor="middle" stroke="${C.ink}" stroke-width="10" paint-order="stroke" stroke-linejoin="round">CLOVER</text>`);
    if (t > w2 - 0.02) {
      const b = 0.6 + 0.4 * spring(t - w2 + 0.02, { freq: 3, damping: 0.5 });
      out += G(tf(0, 66, 0, b), `<text x="0" y="0" font-size="64" font-weight="700" fill="${C.ink}" text-anchor="middle">first. Then corn.</text>`);
    }
    out += `<text x="0" y="132" font-size="32" font-weight="600" fill="#6b5646" text-anchor="middle" opacity="${f2(inv(t0 + 0.6, t0 + 1.0, t))}">Source: Wikipedia, “Nitrogen fixation”</text>`;
    return G(tf(495, 330 + noise(77, t * 0.6) * 4, 0, ps, ps), out);
  }
  function squash(t, t0, amt = 0.14) {
    const d = t - t0;
    if (d < -0.12 || d > 0.9) return [1, 1];
    const k = d < 0 ? -Math.sin((d + 0.12) / 0.12 * Math.PI) * 0.35 : Math.exp(-d * 5) * Math.sin(d * 16);
    return [1 + amt * k, 1 - amt * k];
  }

  // ---------- beats ----------
  const B = {
    throws: [0.85, 1.65, 2.45],
    wigPop: L.need.start - 0.25,
    airT: at('air', 'air'),
    cantT: at('cant', "can't"),
    followT: at('cant', 'follow'),
    lensOpen: at('nodules', 'bacteria') - 0.25,
    lensClose: L.yum.start - 0.45,
    cardIn: L.later.start - 0.45, cardOut: L.release.start - 0.05,
    springIn: L.spring.start - 0.45, springOut: L.plant.start - 0.05,
    dieT: at('release', 'dies'), nitroT: at('release', 'nitrogen'), relT: at('release', 'released'),
    rainOff: L.spring.start - 0.1,
    seedL: at('plant', 'corn'), seedR: at('plant', 'sides'),
    growT: L.plant.end + 0.35,
    endWink: L.rotate.end + 0.6,
  };
  const END = L.rotate.end + 1.6;

  // ---------- camera ----------
  function camera(t) {
    const k = (cx, cy, z) => [cx, cy, z];
    const cam = keys(t, [
      [0, k(270, 930, 1.12)],
      [L.hungry.start - 0.25, k(270, 930, 1.12), 'linear'],
      [L.hungry.start + 0.4, k(720, 960, 1.3), 'inOutCubic'],
      [B.wigPop - 0.15, k(720, 960, 1.3), 'linear'],
      [B.wigPop + 0.45, k(640, 950, 1.14), 'inOutCubic'],
      [L.air.start - 0.3, k(640, 950, 1.14), 'linear'],
      [L.air.start + 0.4, k(360, 820, 1.0), 'inOutCubic'],
      [L.cant.start - 0.2, k(360, 820, 1.0), 'linear'],
      [L.cant.start + 0.35, k(640, 920, 1.2), 'inOutCubic'],
      [B.followT + 0.1, k(640, 920, 1.2), 'linear'],
      [B.followT + 1.3, k(420, 1150, 1.45), 'inOutCubic'],
      [B.lensOpen, k(420, 1150, 1.45), 'linear'],
      [B.lensOpen + 0.6, k(430, 1090, 1.6), 'inOutCubic'],
      [B.lensClose + 0.5, k(430, 1090, 1.6), 'linear'],
      [B.lensClose + 0.95, k(330, 900, 1.25), 'inOutCubic'],
      [B.cardOut, k(500, 960, 1.05), 'linear'],
      [L.plant.start - 0.3, k(500, 960, 1.05), 'linear'],
      [L.plant.start + 0.3, k(360, 930, 1.05), 'inOutCubic'],
      [B.growT - 0.1, k(360, 930, 1.05), 'linear'],
      [B.growT + 0.8, k(470, 780, 0.88), 'outCubic'],
      [L.rotate.start - 0.2, k(470, 780, 0.88), 'linear'],
      [L.rotate.start + 0.4, k(480, 650, 0.9), 'inOutCubic'],
      [END, k(480, 650, 0.9), 'linear'],
    ]);
    return { cx: cam[0], cy: cam[1], z: cam[2] };
  }
  const toScreen = (cam, x, y) => [W / 2 + (x - cam.cx) * cam.z, H / 2 + (y - cam.cy) * cam.z];

  // ---------- Wiggs: spine poses keyed in time ----------
  const GR = GROUND;
  const POSE = {
    sleep: [[600, GR + 150], [652, GR + 178], [642, GR + 252], [586, GR + 246]],
    peek: [[560, GR - 70], [563, GR + 10], [568, GR + 70], [596, GR + 140]],
    rise: [[565, GR + 40], [575, GR + 120], [600, GR + 190], [595, GR + 260]],
    out: [[560, GR - 175], [566, GR - 60], [562, GR + 40], [588, GR + 135]],
    wind: [[578, GR - 225], [560, GR - 105], [560, GR + 10], [575, GR + 110]],
    arc: [[522, GR + 40], [530, GR - 140], [585, GR - 150], [592, GR - 4]],
    slide: [[480, GR + 150], [520, GR + 60], [548, GR - 60], [562, GR + 18]],
    roots: [[452, GR + 192], [492, GR + 176], [536, GR + 122], [560, GR + 42]],
    watch: [[602, GR + 112], [636, GR + 150], [642, GR + 222], [592, GR + 252]],
  };
  function wiggsPose(t) {
    const P = n => POSE[n].flat();
    const seq = [
      [0, P('sleep')], [B.wigPop - 0.05, P('sleep')], [B.wigPop + 0.12, P('rise'), 'inQuad'], [B.wigPop + 0.4, P('out'), 'outBack'],
      [B.followT - 0.15, P('out')], [B.followT + 0.05, P('wind'), 'outCubic'], [B.followT + 0.35, P('arc'), 'inCubic'],
      [B.followT + 0.65, P('slide'), 'linear'], [B.followT + 1.2, P('roots'), 'outCubic'],
      [B.lensClose + 0.2, P('roots')], [B.lensClose + 1.0, P('peek'), 'inOutCubic'],
      [B.cardIn + 0.4, P('peek')], [B.cardOut - 0.01, P('out'), 'linear'],
      [B.springIn + 0.4, P('out')], [B.springOut, P('peek'), 'linear'],
      [L.rotate.start - 0.6, P('peek')], [L.rotate.start - 0.1, P('out'), 'outBack'],
    ];
    const v = keys(t, seq);
    return [[v[0], v[1]], [v[2], v[3]], [v[4], v[5]], [v[6], v[7]]];
  }
  function wiggsMood(t) {
    if (t < B.wigPop) return 'sleep';
    if (t < B.wigPop + 0.6) return 'surprised';
    if (t > B.endWink - 0.1 && t < B.endWink + 0.5) return 'happy';
    if (t > L.release.start && t < B.rainOff) return 'sad';
    if (t > B.springOut && t < L.rotate.start - 0.2) return 'happy';
    if (t > B.lensClose && t < B.cardIn) return 'excited';
    return 'smug';
  }

  // ---------- the film ----------
  function frame(f) {
    D.begin(f);
    const t = f / FPS;
    const cam = camera(t);
    const card = t > B.cardIn + 0.36 && t < B.cardOut - 0.36;
    // weather: autumn rain after the card, spring sun after the rain
    const storm = clamp(inv(B.cardOut - 0.4, B.cardOut, t) * (1 - inv(B.springIn + 0.36, B.springOut - 0.36, t)));
    const rainAmt = clamp(inv(B.cardOut - 0.3, B.cardOut + 0.3, t) * (1 - inv(B.springIn + 0.36, B.springOut - 0.36, t)));
    const wet = clamp(inv(B.cardOut, B.cardOut + 1.5, t) * (1 - inv(B.springIn + 0.3, B.springOut - 0.3, t)));
    const dusk = 0;

    // --- the clover ---
    const sprout = pop(t, 0.12, 0.6);
    const yumT = L.yum.start, feedsT = at('yum', 'feeds');
    const wilt = ease.inOutCubic(inv(B.dieT, B.dieT + 0.7, t));
    const sinkP = ease.inCubic(inv(B.dieT + 0.75, B.dieT + 1.25, t));
    const clGrow = 1 + 0.12 * spring(t - yumT, { freq: 1.8, damping: 0.4 });
    let clMood = t < L.hungry.start ? 'happy' : 'happy';
    if (t > B.lensClose - 0.2 && t < B.cardIn) clMood = 'excited';
    if (t > B.cardOut && t < B.dieT) clMood = 'sad';
    if (t > B.dieT + 0.2) clMood = 'sleep';

    // --- Kernel (the corn that never gets clover) ---
    const kIn = pop(t, 0, 0.5);
    const flinch = t > B.cantT ? Math.exp(-(t - B.cantT) * 3.5) * Math.sin((t - B.cantT) * 22) * 9 : 0;
    let kMood = 'hungry';
    if (t < L.hungry.start) kMood = 'skeptical';
    else if (t < L.hungry.end) kMood = 'sad';
    else if (t < B.wigPop + 0.6 && t > B.wigPop) kMood = 'surprised';
    else if (t > L.air.start && t < L.air.end) kMood = 'skeptical';
    if (t > B.cantT - 0.1 && t < B.cantT + 1.2) kMood = 'sad';
    if (t > B.cardOut && t < B.rainOff) kMood = 'sleep';
    if (t > B.growT + 0.3) kMood = 'envious';
    if (t > L.fed.start + 0.5) kMood = 'hungry';
    const kLook = t > B.growT + 0.3 && t < L.fed.end ? [-1, -1] : t < L.hungry.start ? [-1, 0] : t > B.wigPop && t < L.air.start ? [-1, 0.3] : [-0.6, 0.2];

    // --- the tall corn on the clover side (spring) ---
    const tg = spring(t - B.growT, { freq: 1.4, damping: 0.5 }) * (t > B.growT ? 1 : 0);
    const tallIn = pop(t, B.seedL + 0.55, 0.5);

    // --- world ---
    let world = ground(t, dusk);
    if (wet > 0.01) {
      world += `<rect x="-800" y="${GROUND - 4}" width="2700" height="96" fill="#2a1a0e" opacity="${f2(0.45 * wet)}"/>`;
    }
    // the dividing stake and string between the two halves of the field
    world += G(tf(DIV_X, GROUND + 4), D.shade('M-9 0 L-8 -96 L0 -112 L8 -96 L9 0 Z', '#b07a46', { depth: 6, light: 2, w: 4.5, ink: C.ink }));
    world += `<path d="M-800 ${GROUND - 70} Q${DIV_X - 200} ${GROUND - 58} ${DIV_X} ${GROUND - 78}" fill="none" stroke="#f3e2b8" stroke-width="3" opacity="0"/>`;
    // ground signs make the comparison readable: which side had clover (drawn behind the cast)
    [[472, ['AFTER', 'CLOVER'], '#4e9d31', B.seedL + 0.4], [652, ['NO', 'CLOVER'], '#9a6a45', B.seedR + 0.4]].forEach(([sx, label, colr, t0]) => {
      const p = pop(t, t0, 0.5);
      if (p.s < 0.01) return;
      world += G(`translate(${sx} ${GROUND + 6}) scale(${f2(p.sx)} ${f2(p.sy)})`,
        D.shade('M-7 0 L-7 -240 L7 -240 L7 0 Z', '#b07a46', { depth: 4, light: 2, w: 4, ink: C.ink }) +
        G(tf(0, -282, sx < DIV_X ? -3 : 3), D.shade('M-82 -48 H82 V48 H-82 Z', '#f6e7c8', { depth: 7, light: 3, w: 5, ink: C.ink }) +
          `<text x="0" y="-6" font-size="34" font-weight="700" fill="${colr}" text-anchor="middle">${label[0]}</text>` +
          `<text x="0" y="32" font-size="34" font-weight="700" fill="${colr}" text-anchor="middle">${label[1]}</text>`));
    });
    // Wiggs's tunnel from the hole to the clover roots, once he has dug it
    const tun = inv(B.followT + 0.3, B.followT + 1.2, t);
    if (tun > 0) {
      const pts = D.bez([DIV_X, GROUND + 14], [DIV_X, GROUND + 90], [520, GROUND + 160], [446, GROUND + 196], 16);
      const tunOp = 0.55 * (1 - inv(B.lensClose + 0.6, B.lensClose + 1.4, t));
      if (tunOp > 0.01) world += D.taper(pts.slice(0, Math.max(2, Math.round(pts.length * tun))), 62, 54, '#3f2817', `opacity="${f2(tunOp)}"`);
    }
    // roots
    if (t < B.growT + 1.5) world += roots(CLOVER_X, { t, nodulePop: at('nodules', 'bumps'), pulse: at('nodules', 'bumps'), fade: inv(B.dieT, B.dieT + 1, t), gone: Math.max(1 - sprout.s, 0.55 * inv(B.relT, B.relT + 0.8, t) + 0.45 * inv(L.plant.start, B.growT + 1.2, t)) });
    world += cornRoots(CORN_X, 0.15);
    if (t > B.seedL + 0.5) world += cornRoots(TALL_X, tg);
    {
      const bT = at('nodules', 'bumps'), rT = at('nodules', 'roots');
      const vis = 1 - inv(B.lensClose, B.lensClose + 0.4, t);
      if (t > bT - 0.05 && vis > 0) NODULES.forEach(([nx, ny, r], i) => {
        const d = t - bT - i * 0.05;
        if (d < 0) return;
        const rr = r + 8 + (d % 1.2) * 34, op = Math.max(0, 1 - (d % 1.2) / 1.2) * vis;
        world += G(tf(CLOVER_X, GROUND + 18, 0, ROOT_SX, ROOT_SY), circle(nx, ny, rr, 'none', 5, '#fff', `opacity="${f2(op)}"`));
      });
      const tr = inv(rT - 0.05, rT + 0.55, t);
      if (tr > 0 && tr < 1) world += G(tf(CLOVER_X, GROUND + 18, 0, ROOT_SX, ROOT_SY), CLOVER_ROOTS.map(d =>
        `<path d="${d}" fill="none" stroke="#fff6c8" stroke-width="8" stroke-linecap="round" pathLength="100" stroke-dasharray="${f2(tr * 100)} 100" opacity="${f2(Math.sin(tr * Math.PI))}"/>`).join(''));
    }
    // one N2 pair falls from the sky into the nodule on "pull"
    {
      const fixT = at('fix', 'pull'), d0 = fixT - 0.7, d1 = fixT - 0.05;
      if (t > d0 && t < d1 + 0.25) {
        const [nx, ny] = NODULE_WORLD();
        const p = ease.inQuad(inv(d0, d1, t));
        world += n2(lerp(nx + 70, nx, p), lerp(GROUND - 640, ny, p), 0.85 * (1 - inv(d1, d1 + 0.2, t)), p * 160);
        if (t > d1) world += circle(nx, ny, 18 + (t - d1) * 120, 'none', 5, '#fff', `opacity="${f2(1 - inv(d1, d1 + 0.25, t))}"`);
      }
    }
    // ammonia travelling up the roots into the clover
    if (t > yumT - 0.2 && t < yumT + 1.3) {
      const [nx, ny] = NODULE_WORLD();
      for (let i = 0; i < 6; i++) {
        const p = inv(yumT - 0.15 + i * 0.08, yumT + 0.5 + i * 0.08, t);
        if (p <= 0 || p >= 1) continue;
        const x = lerp(nx + (i % 3 - 1) * 20, CLOVER_X, ease.inOutQuad(p)), y = lerp(ny + (i % 2) * 40, GROUND - 160, ease.inQuad(p));
        world += nDot(x, y, 0.42, 1 - inv(0.55, 0.85, p));
      }
    }
    // background clovers sprout as Mina throws seeds (left half only)
    const BG = [40, 170, 430, 500];
    let bgPlants = '';
    BG.forEach((x, i) => {
      const p = pop(t, B.throws[i % 3] + 0.45 + i * 0.12, 0.5);
      if (p.s > 0.01 && sinkP < 1) bgPlants += G(tf(x, 0, (rand(i + 71) - 0.5) * 8, 1), clover(0, { t, s: 0.42 * (0.82 + rand(i + 61) * 0.36) * p.s, seed: 10 + i, wilt, wind: D.wind(t, x), sink: sinkP * 120, face: false, mood: 'happy', sq: [p.sx / Math.max(p.s, 0.01), p.sy / Math.max(p.s, 0.01)] }));
      world += D.crumbs(t, B.throws[i % 3] + 0.45 + i * 0.12, x, GROUND + 6, { seed: 30 + i, n: 5, up: 300 });
    });
    world += `<g clip-path="url(#above)">${bgPlants}</g>`;
    if (sprout.s > 0.01 && sinkP < 1) {
      world += shadow(CLOVER_X, 70 * (1 - sinkP), 0.2);
      world += `<g clip-path="url(#above)">` + clover(CLOVER_X, {
        t, s: sprout.s * clGrow, wilt, sink: sinkP * 330, flower: inv(yumT - 0.05, feedsT, t), flowerAt: feedsT,
        mood: clMood, talk: talkOf('clover', f), lookX: t > B.lensClose ? 0.6 : 0.3, lookY: t > B.followT && t < B.lensClose ? 1 : 0, bl: blink(t, 1, 3.1), seed: 1,
        sq: [sprout.sx / Math.max(sprout.s, 0.01) * squash(t, yumT)[0], sprout.sy / Math.max(sprout.s, 0.01) * squash(t, yumT)[1]],
        wind: D.wind(t, CLOVER_X) * (1 - wilt), windLag: D.wind(t - 0.15, CLOVER_X) * (1 - wilt),
      }) + `</g>`;
    }
    world += D.crumbs(t, 0.12, CLOVER_X, GROUND + 6, { seed: 9, n: 8 });
    world += D.crumbs(t, B.dieT + 0.75, CLOVER_X, GROUND + 6, { seed: 19, n: 12, up: 380 });
    // tall corn on the clover side (spring)
    if (tallIn.s > 0.01) {
      world += shadow(TALL_X, lerp(40, 120, tg), 0.2);
      world += `<g clip-path="url(#above)">` + corn(TALL_X, {
        t, grow: tg, health: clamp(tg * 1.3), mood: t > B.growT + 0.5 ? (t > L.tall.end ? 'proud' : 'proud') : 'happy', s: tallIn.s * 1.3, bl: blink(t, 6, 3.3),
        wind: D.wind(t, TALL_X), lookX: 0.6, cob: pop(t, B.growT + 0.8, 0.5).s, sq: [tallIn.sx / Math.max(tallIn.s, 0.01), tallIn.sy / Math.max(tallIn.s, 0.01)],
      }) + `</g>`;
      world += D.crumbs(t, B.growT, TALL_X, GROUND + 6, { seed: 13, n: 12, up: 600 });
    }
    // Kernel
    world += shadow(CORN_X, 55, 0.2);
    world += `<g clip-path="url(#above)">` + corn(CORN_X, {
      t, grow: 0.12, health: t > B.growT ? 0.05 : 0, mood: kMood, talk: talkOf('kernel', f), flinch, s: kIn.s * 1.35, bl: blink(t, 2, 3.4),
      wind: D.wind(t, CORN_X), lookX: kLook[0], lookY: kLook[1], cob: 0,
    }) + `</g>`;
    // Mina: away during the rain, walks back in for spring
    const act2 = t > B.springOut - 0.36;
    const mx = act2 ? MINA_X2 : MINA_X - 420 * ease.inOutCubic(inv(B.followT + 0.4, B.followT + 1.6, t));
    const minaHere = (t < B.cardIn || act2) && toScreen(cam, mx, GROUND - 300)[0] > 30;
    if (minaHere) {
      const walk = act2 ? 0 : inv(B.followT + 0.4, B.followT + 1.6, t) > 0 && inv(B.followT + 0.4, B.followT + 1.6, t) < 1 ? 1 : 0;
      const throwArm = tt => { // a throw swings the arm up and over
        for (const th of tt) { const d = t - th; if (d > -0.25 && d < 0.35) return d < 0 ? 40 + (d + 0.25) / 0.25 * 100 : 140 - d / 0.35 * 90; }
        return 40;
      };
      let pose = { mood: 'happy', armL: { sh: 10, el: 10 }, armR: { sh: 10, el: 10 }, look: [0.4, 0], hand: {} };
      if (t < L.hungry.start) pose = { mood: 'annoyed', armL: { sh: 25, el: 50 }, armR: { sh: throwArm(B.throws), el: 25 }, look: [0.6, 0.2], hand: { l: 'pouch' } };
      else if (t < B.wigPop) pose = { mood: 'sad', armL: { sh: 25, el: 50 }, armR: { sh: 14, el: 10 }, look: [1, 0.1], hand: { l: 'pouch' } };
      else if (t < L.air.start) pose = { mood: 'surprised', armL: { sh: 35, el: 40 }, armR: { sh: 35, el: 40 }, look: [1, 0.3], hand: {} };
      else if (t < L.cant.start) pose = { mood: t < B.airT ? 'skeptical' : 'excited', armL: { sh: 15, el: 10 }, armR: { sh: lerp(20, 165, ease.outBack(inv(L.air.start, L.air.start + 0.4, t))), el: 5 }, look: [0.4, -1], hand: {} };
      else if (t < B.cardIn) pose = { mood: t > B.followT ? 'excited' : 'skeptical', armL: { sh: 35, el: 110 }, armR: { sh: 35, el: 110 }, look: [1, 0.4], hand: {} };
      else if (t < L.tall.start) pose = { mood: 'happy', armL: { sh: 25, el: 50 }, armR: { sh: throwArm([B.seedL, B.seedR]), el: 25 }, look: [t < B.seedR - 0.3 ? 0.6 : 1, 0.3], hand: { l: 'pouch' } };
      else if (t < L.fed.start) pose = { mood: 'happy', armL: { sh: 20, el: 120 }, armR: { sh: 20, el: 120 }, look: [1, -0.6], hand: {} };
      else if (t < L.rotate.start) pose = { mood: 'proud', armL: { sh: 15, el: 10 }, armR: { sh: lerp(20, 80, ease.outBack(inv(L.fed.start, L.fed.start + 0.4, t))), el: 10 }, look: [1, 0], hand: {} };
      else pose = { mood: 'excited', armL: { sh: 15, el: 10 }, armR: { sh: 150, el: 20 + Math.sin(t * 9) * 25 }, look: [1, 0], hand: {} };
      const k = Cast.kid(mx, GROUND + 8, { t, s: 1.0, talk: talkOf('mina', f), mood: pose.mood, lookX: pose.look[0], lookY: pose.look[1], bl: blink(t + 1.3, 8, 3.6),
        armL: pose.armL, armR: pose.armR, hand: pose.hand, lean: walk * 4 * Math.sin(t * 12) + (t < L.hungry.start ? 2 : 0) });
      world += shadow(mx, 90, 0.22) + k.svg;
      // seeds from her hand: clover seeds in the hook, corn seeds in spring
      const seedArc = (t0, tx, n, colr) => {
        let s = '';
        for (let i = 0; i < n; i++) {
          const p = inv(t0 + i * 0.03, t0 + 0.5 + i * 0.03, t);
          if (p <= 0 || p >= 1) continue;
          const [hx, hy] = k.hands[1];
          const x = lerp(hx, tx + (i - n / 2) * 26, p), y = lerp(hy, GROUND + 2, p) - Math.sin(p * Math.PI) * 140;
          s += D.sphere(x, y, 6, colr, { w: 2.5 });
        }
        return s;
      };
      B.throws.forEach((th, i) => { world += seedArc(th, [250, 380, 470][i], 4, '#c9a25a'); });
      world += seedArc(B.seedL, TALL_X, 1, '#ffd23f') + seedArc(B.seedR, CORN_X - 30, 1, '#ffd23f');
    }
    // Wiggs (the cut-away soil shows his whole body)
    {
      const sp = wiggsPose(t);
      const pts = Cast.spine(sp[0], sp[1], sp[2], sp[3], t, t < B.wigPop ? 1.5 : 4, 24);
      world += Cast.worm(pts, { t, talk: talkOf('wiggs', f), mood: wiggsMood(t), lookX: t > B.followT && t < B.cardIn ? -0.8 : -0.4, lookY: 0, bl: blink(t, 4, 2.9), wink: t > B.endWink && t < B.endWink + 0.45, headS: 1.5 });
      // a leaf umbrella in the rain
      if (storm > 0.01) {
        const [hx, hy] = pts[0];
        world += G(tf(hx + 4, hy - 46, -8 + noise(5, t) * 4, storm), D.shade('M-70 0 Q0 -70 70 0 Q35 -12 0 -4 Q-35 -12 -70 0 Z', '#6bb544', { depth: 8, light: 3, w: 4.5, ink: C.ink }) + tube('M0 -4 L0 40', '#4f9a33', 6, 3));
      }
      world += D.crumbs(t, B.wigPop + 0.1, DIV_X, GROUND + 6, { seed: 41, n: 12, up: 520 });
      world += D.crumbs(t, B.followT + 0.35, DIV_X, GROUND + 6, { seed: 43, n: 10, up: 420 });
      world += D.crumbs(t, L.rotate.start - 0.2, DIV_X, GROUND + 6, { seed: 47, n: 10, up: 460 });
    }
    // puddles while the ground is wet
    if (wet > 0.01) [[120, 70], [460, 90], [690, 60], [930, 80]].forEach(([px, pw], i) => {
      const s = ease.outCubic(clamp(wet * 1.4 - i * 0.1));
      world += `<ellipse cx="${px}" cy="${GROUND + 4}" rx="${f2(pw * s)}" ry="${f2(11 * s)}" fill="${D.linear([[0, '#a9c3dc'], [1, '#6f8daa']])}" stroke="${C.ink}" stroke-width="3" opacity="${f2(0.9 * s)}"/>` +
        `<ellipse cx="${px - pw * 0.3}" cy="${GROUND + 1}" rx="${f2(pw * 0.3 * s)}" ry="${f2(2.5 * s)}" fill="#fff" opacity="${f2(0.7 * s)}"/>`;
    });

    // nitrogen in the air on Mina's "air", and the bounce off Kernel on "can't"
    for (let i = 0; i < 9; i++) {
      const p = pop(t, B.airT - 0.15 + i * 0.07, 0.5);
      const out = 1 - ease.inCubic(inv(B.followT + i * 0.03, B.followT + 0.5 + i * 0.03, t));
      if (p.s * out <= 0.01) continue;
      const row = Math.floor(i / 3), colm = i % 3;
      const bx = 230 + colm * 240 + (row % 2) * 110 + (rand(i + 200) - 0.5) * 30, by = 340 + row * 145 + (rand(i + 300) - 0.5) * 24;
      world += n2(bx + noise(i + 400, t * 0.4) * 18 + t * 4, by + noise(i + 500, t * 0.35) * 14 - (1 - out) * 900, 1.15 * p.s, noise(i + 600, t * 0.3) * 40, i === 4 ? { tag: { t, at: B.airT + 0.3 } } : {});
    }
    {
      const t0 = B.cantT - 0.55, hit = B.cantT;
      if (t > t0 && t < hit + 1.4) {
        let x, y, r;
        if (t < hit) { const p = ease.inQuad(inv(t0, hit, t)); x = lerp(700, CORN_X - 6, p); y = lerp(500, GROUND - 230, p); r = p * 90; }
        else { const p = t - hit; x = CORN_X - 6 + p * 260; y = GROUND - 230 - 520 * p + 330 * p * p; r = 90 + p * 300; }
        world += G(`translate(${f2(x)} ${f2(y)}) scale(${t > hit && t < hit + 0.12 ? '1.25 0.75' : '1 1'})`, n2(0, 0, 0.95, r));
        if (t > hit && t < hit + 0.35) {
          const q = inv(hit, hit + 0.35, t);
          world += `<g opacity="${f2(1 - q)}">` + D.shock(CORN_X - 6, GROUND - 245, -Math.PI * 0.62, 1 + q * 0.4) + D.shock(CORN_X - 6, GROUND - 245, -Math.PI * 0.2, 0.8 + q * 0.4) + `</g>`;
        }
      }
    }
    // released nitrogen: spreads from the clover in the rain, then flows to the tall corn in spring
    let glowLayer = '';
    if (t > B.nitroT - 0.1 && t < L.rotate.start + 0.5) {
      for (let i = 0; i < 26; i++) {
        if (i % 3 === 2) continue;
        const a = rand(i + 700) * Math.PI * 2, d = 60 + rand(i + 800) * 200;
        const sx = CLOVER_X + 40 + Math.cos(a) * d * 0.8, sy = GROUND + 120 + Math.sin(a) * d * 0.35;
        const spread = ease.outCubic(inv(B.nitroT - 0.1 + i * 0.03, B.relT + 0.6 + i * 0.02, t));
        const toCorn = ease.inOutCubic(inv(B.growT - 0.3 + i * 0.025, B.growT + 0.6 + i * 0.02, t));
        const x0 = lerp(CLOVER_X, sx, spread), y0 = lerp(GROUND + 120, sy, spread);
        const tx = TALL_X + (rand(i + 900) - 0.5) * 100, ty = GROUND + 40 + rand(i + 950) * 90;
        const x = lerp(x0, tx, toCorn) + noise(i + 1000, t) * 6, y = lerp(y0, ty, toCorn) + noise(i + 1100, t) * 6;
        const op = spread * (1 - inv(B.growT + 0.5, B.growT + 1.2, t));
        const [, scrY] = toScreen(cam, x, y);
        const clear = 1 - inv(1300, 1345, scrY);
        if (op * clear > 0.01) glowLayer += nDot(x, y, 0.58, op * clear);
      }
    }
    // on "fed": the clover side's soil glows under the tall corn
    {
      const g = Math.sin(clamp(inv(at('fed', 'fed') - 0.1, at('fed', 'fed') + 1.6, t)) * Math.PI);
      if (g > 0.01) glowLayer += `<ellipse cx="${TALL_X}" cy="${GROUND + 120}" rx="${f2(210 * (0.8 + 0.2 * g))}" ry="80" fill="url(#glow)" opacity="${f2(0.55 * g)}"/>`;
    }

    // backdrop layers
    const sunY = keys(t, [[0, 290], [B.cardOut - 0.2, 290], [B.cardOut, 1080, 'linear'], [B.springIn + 0.4, 1080], [B.springOut - 0.36, 290, 'linear']]);
    const sunL = `<circle cx="880" cy="${f2(sunY)}" r="150" fill="${D.radial([[0, '#fff3b0', 0.7], [1, '#fff3b0', 0]], { cx: 0.5, cy: 0.5, r: 0.5 })}"/>` + D.sphere(880, sunY, 64, '#ffd75e', { w: 0, spec: false });
    let skyL = '';
    [[120, 220, 1.0, 1], [700, 160, 0.8, 2], [430, 420, 0.65, 3], [980, 380, 0.75, 4], [250, 120, 0.9, 5]].forEach(([x, y, s, sd], i) => {
      if (i === 4 && storm < 0.01) return;
      const xx = ((x + t * 16 * s + 300) % 1500) - 300;
      skyL += D.cloud(xx, y + storm * 30, s * (1 + storm * 0.35), sd, D.mix('#ffffff', '#8e98a6', storm), D.mix('#dceef8', '#6c7684', storm));
    });
    const farL = hills(dusk, t), hedgeL = hedge(dusk);
    const fgL = D.fgGrass(1230, GROUND + 40, 560, 7, t);

    const camT = `translate(${W / 2} ${H / 2}) scale(${f2(cam.z)}) translate(${f2(-cam.cx)} ${f2(-cam.cy)})`;
    const layerT = p => `translate(${W / 2} ${H / 2}) scale(${f2(1 + (cam.z - 1) * p)}) translate(${f2(-(540 + (cam.cx - 540) * p))} ${f2(-(960 + (cam.cy - 960) * p))})`;
    const dof = 1 + Math.max(0, cam.z - 1) * 1.4;
    let svg = sky(t, dusk);
    if (storm > 0.01) svg += `<rect width="${W}" height="${H}" fill="#8c97a6" opacity="${f2(storm * 0.55)}"/>`;
    svg += `<g transform="${layerT(0.15)}">${sunL}</g>`;
    svg += `<g filter="${D.blurFilter(3.5)}"><g transform="${layerT(0.15)}">${skyL}</g></g>`;
    svg += `<g filter="${D.blurFilter(5 * dof)}"><g transform="${layerT(0.45)}">${farL}</g></g>`;
    svg += `<g filter="${D.blurFilter(2.4 * dof)}"><g transform="${layerT(0.75)}">${hedgeL}</g></g>`;
    svg += `<g transform="${camT}">${world}</g>`;
    if (storm > 0.01) svg += `<rect width="${W}" height="${H}" fill="#56627a" opacity="${f2(storm * 0.3)}" style="mix-blend-mode:multiply"/>`;
    if (glowLayer) svg += `<g transform="${camT}">${glowLayer}</g>`;
    svg += `<g filter="${D.blurFilter(9)}"><g transform="${layerT(1.4)}">${fgL}</g></g>`;
    if (rainAmt > 0.01) svg += D.rain(t, { amount: rainAmt, groundY: toScreen(cam, 0, GROUND)[1] });
    svg += lens(t, cam);
    svg += captions(t);
    svg += title(t);
    svg += D.timeCard(t, B.cardIn, B.cardOut, { text: 'MONTHS LATER…' });
    svg += D.timeCard(t, B.springIn, B.springOut, { text: 'NEXT SPRING…', months: ['NOV', 'DEC', 'JAN', 'FEB', 'MAR', 'APR'] });
    return svg + D.defs();
  }

  // ---------- sound cues (read by engine/audio.py) ----------
  const cue = (t, type, gain = 1) => ({ t: +t.toFixed(3), type, gain });
  window.CUES = [
    ...B.throws.map(th => cue(th - 0.05, 'whoosh', 0.5)),
    ...[0, 1, 2, 3].map(i => cue(B.throws[i % 3] + 0.45 + i * 0.12, 'pop_small', 0.6)),
    cue(1.95, 'pop'),
    cue(L.hungry.start - 0.1, 'whoosh'),
    cue(B.wigPop + 0.1, 'pop'), cue(B.wigPop + 0.15, 'sink', 0.6),
    cue(B.airT - 0.15, 'twinkle'),
    cue(B.cantT, 'boing'),
    cue(B.followT + 0.3, 'whoosh'), cue(B.followT + 0.4, 'sink', 0.8),
    cue(at('nodules', 'bumps'), 'pop_small', 0.7),
    cue(B.lensOpen, 'lens_open'),
    cue(at('fix', 'pull') - 0.05, 'pop_small', 0.6), cue(at('fix', 'pull') + 0.6, 'chomp'),
    cue(at('fix', 'turn') + 0.15, 'sparkle'), cue(at('fix', 'ammonia'), 'sparkle'),
    cue(B.lensClose, 'lens_close'), cue(L.yum.start, 'grow'), cue(at('yum', 'feeds'), 'pop'),
    cue(B.cardIn, 'whoosh'), cue(B.cardIn + 0.5, 'flip'), cue(B.cardOut - 0.4, 'whoosh'),
    cue(B.cardOut - 0.2, 'rain'),
    cue(B.dieT, 'wilt'), cue(B.dieT + 0.75, 'sink'),
    cue(B.nitroT - 0.1, 'shimmer'),
    cue(B.springIn, 'whoosh'), cue(B.springIn + 0.45, 'flip'), cue(B.springOut - 0.4, 'whoosh'), cue(B.springOut - 0.1, 'chime', 0.7),
    cue(B.seedL - 0.05, 'whoosh', 0.5), cue(B.seedL + 0.5, 'pop_small', 0.7),
    cue(B.seedR - 0.05, 'whoosh', 0.5), cue(B.seedR + 0.5, 'pop_small', 0.7),
    cue(B.growT, 'grow_big'), cue(B.growT + 0.8, 'pop'),
    cue(L.rotate.start - 0.2, 'pop'),
    cue(L.rotate.start, 'chime'),
    cue(B.endWink, 'wink'),
  ].sort((a, b) => a.t - b.t);

  const stage = document.getElementById('stage');
  window.renderFrame = f => { stage.innerHTML = frame(f); };
  window.FILM = { width: W, height: H, fps: FPS, frames: Math.round(END * FPS), safe: SAFE, ready: false };
  document.fonts.load('700 40px Fredoka').then(() => { window.FILM.ready = true; });
})();
