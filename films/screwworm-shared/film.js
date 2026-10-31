// Screwworm films: shot painters, sequencer, captions and sound cues.
// A film's scene.js sets window.CUT and window.SHOTS (shot list keyed to script lines), then loads this.
(function () {
  const { clamp, lerp, inv, ease, spring, keys, noise, rand, blink } = M;
  const { C, INK, G, tf, f2, ellD, sh, P, txt, textWidth } = SW;
  const T = M.bindTiming(window.TIMING), L = T.lines, FPS = 30, W = 1080, H = 1920;
  const CUT = window.CUT || 'full';
  const MOUTH = (window.TIMING.mouth || {}).nar || [];
  const LINES = window.TIMING.lines;
  const lastLine = LINES[LINES.length - 1];
  const END = lastLine.end + (CUT === 'hook' ? 1.6 : 2.4);
  const SAFE = { left: 70, right: 920, top: 230, bottom: 1520 };

  // ---------- small helpers ----------
  const norm = s => s.toLowerCase().replace(/[^a-z0-9']/g, '');
  function findWord(lineIds, word, nth = 0) {
    let k = 0;
    for (const id of lineIds) for (const w of L[id].words) if (norm(w.text) === norm(word)) { if (k++ === nth) return w.start; }
    return null;
  }
  const popS = (t, t0, freq = 2.6, damp = 0.5) => (t < t0 ? 0 : spring(t - t0, { freq, damping: damp }));
  const fadeIn = (t, t0, d = 0.25) => clamp((t - t0) / d);
  const shake = (t, t0, amp = 14, dur = 0.4) => {
    const d = t - t0;
    if (d < 0 || d > dur) return [0, 0];
    const k = amp * (1 - d / dur);
    return [Math.sin(d * 70) * k, Math.cos(d * 53) * k * 0.7];
  };
  const camT = (cx, cy, z) => `translate(${W / 2} ${H / 2}) scale(${f2(z)}) translate(${f2(-cx)} ${f2(-cy)})`;
  function chip(x, y, text, o = {}) {
    const { size = 44, fill = C.cream, color = INK, s = 1, rot = 0, sub = '', subSize = 28, stroke = INK } = o;
    if (s <= 0.01) return '';
    const w = Math.max(textWidth(text, size), sub ? textWidth(sub, subSize, 600) : 0) + size * 1.1;
    const h = size * 1.45 + (sub ? subSize * 1.25 : 0);
    let out = `<rect x="${f2(-w / 2 + 7)}" y="${f2(-h / 2 + 9)}" width="${f2(w)}" height="${f2(h)}" rx="${f2(Math.min(h / 2, 30))}" fill="${INK}" opacity="0.25"/>`;
    out += `<rect x="${f2(-w / 2)}" y="${f2(-h / 2)}" width="${f2(w)}" height="${f2(h)}" rx="${f2(Math.min(h / 2, 30))}" fill="${fill}" stroke="${stroke}" stroke-width="6"/>`;
    out += txt(0, (sub ? -h / 2 + size * 1.12 : size * 0.36), text, size, color);
    if (sub) out += txt(0, h / 2 - subSize * 0.62, sub, subSize, color, { weight: 600 });
    return G(tf(x, y, rot, s), out);
  }
  function stamp(x, y, text, t, t0, o = {}) {
    if (t < t0) return '';
    const { color = C.red, size = 84, rot = -8, sub = '' } = o;
    const d = t - t0, k = d < 0.12 ? lerp(1.8, 1, ease.inCubic(d / 0.12)) : 1 + Math.exp(-(d - 0.12) * 10) * 0.05 * Math.sin((d - 0.12) * 40);
    const w = Math.max(textWidth(text, size), sub ? textWidth(sub, size * 0.42) : 0) + 70, h = size * 1.3 + (sub ? size * 0.6 : 0);
    let out = `<rect x="${f2(-w / 2)}" y="${f2(-h / 2)}" width="${f2(w)}" height="${f2(h)}" rx="16" fill="${C.cream}" fill-opacity="0.85" stroke="${color}" stroke-width="12"/>`;
    out += `<rect x="${f2(-w / 2 + 14)}" y="${f2(-h / 2 + 14)}" width="${f2(w - 28)}" height="${f2(h - 28)}" rx="8" fill="none" stroke="${color}" stroke-width="4"/>`;
    out += txt(0, sub ? -h / 2 + size * 1.05 : size * 0.36, text, size, color);
    if (sub) out += txt(0, h / 2 - size * 0.32, sub, size * 0.42, color, { weight: 600 });
    return G(tf(x, y, rot, k), out, `opacity="${f2(clamp(d / 0.06))}"`);
  }
  const check = (x, y, s = 1, col = C.green) => G(tf(x, y, 0, s), `<circle r="30" fill="${col}" stroke="${INK}" stroke-width="5"/><path d="M-14 0 L-4 12 L16 -12" fill="none" stroke="#fff" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/>`);
  const cross = (x, y, s = 1, col = C.red) => G(tf(x, y, 0, s), `<circle r="30" fill="${col}" stroke="${INK}" stroke-width="5"/><path d="M-12 -12 L12 12 M12 -12 L-12 12" stroke="#fff" stroke-width="8" stroke-linecap="round"/>`);
  const vignette = (k = 0.35) => `<rect width="${W}" height="${H}" fill="${D.radial([[0.55, '#000', 0], [1, '#1a0e08', k]], { cx: 0.5, cy: 0.45, r: 0.75 })}"/>`;
  const sepia = (k = 0.3) => `<rect width="${W}" height="${H}" fill="#a0784f" opacity="${f2(k)}" style="mix-blend-mode:multiply"/>`;
  const plain = (a, b) => `<rect width="${W}" height="${H}" fill="${D.linear([[0, a], [1, b]])}"/>`;
  function swarm(t, n, o = {}) {
    const { x0 = 0, y0 = 0, x1 = W, y1 = H, seed = 3, col = C.flyBody, s = 1, speed = 1 } = o;
    let out = '';
    for (let i = 0; i < n; i++) {
      const bx = x0 + rand(seed + i) * (x1 - x0), by = y0 + rand(seed + i * 3) * (y1 - y0);
      const x = bx + noise(seed + i, t * 0.9 * speed) * 50, y = by + noise(seed + i + 50, t * 1.1 * speed) * 40;
      out += SW.fleck(x, y, s * (0.8 + rand(seed + i * 7) * 0.5), t, typeof col === 'function' ? col(i) : col);
    }
    return out;
  }
  // calendar badge counting up to n units
  function counterBadge(x, y, value, label, o = {}) {
    const { s = 1, fill = C.gold, size = 92 } = o;
    if (s <= 0.01) return '';
    const w = Math.max(textWidth(value, size), textWidth(label, 34)) + 80;
    return G(tf(x, y, -2, s), `<rect x="${f2(-w / 2 + 8)}" y="-74" width="${f2(w)}" height="168" rx="30" fill="${INK}" opacity="0.25"/>` +
      `<rect x="${f2(-w / 2)}" y="-82" width="${f2(w)}" height="168" rx="30" fill="${fill}" stroke="${INK}" stroke-width="7"/>` +
      txt(0, 10, value, size, INK) + txt(0, 62, label, 34, INK, { weight: 600 }));
  }

  // ---------- map ----------
  const MP = window.MAP, MAPX = 40, MAPY = 300;
  const mxy = (lon, lat) => { const [x, y] = MP.xy(lon, lat); return [MAPX + x, MAPY + y]; };
  const LAND = Object.values(MP.countries).join('');
  const BORDER = [[-117.1, 32.53], [-114.72, 32.72], [-111.07, 31.33], [-108.21, 31.33], [-108.21, 31.78], [-106.53, 31.78], [-104.9, 30.6], [-104.45, 29.6], [-103.1, 28.98], [-102.4, 29.78], [-101.4, 29.77], [-100.3, 28.3], [-99.5, 27.5], [-99.1, 26.4], [-97.15, 25.95]];
  const borderD = BORDER.map(([lo, la], i) => { const [x, y] = mxy(lo, la); return `${i ? 'L' : 'M'}${f2(x)} ${f2(y)}`; }).join('');
  const CENTRAL = ['guatemala', 'belize', 'salvador', 'honduras', 'nicaragua', 'costarica', 'panama'];
  const SE_STATES = ['Florida', 'Georgia', 'Alabama', 'South Carolina', 'Mississippi'];
  const SW_STATES = ['Texas', 'New Mexico', 'Arizona', 'California', 'Oklahoma', 'Louisiana', 'Arkansas', 'Nevada'];
  // st: {cam:{cx,cy,z} in screen px of the unzoomed map, red:{country|state:Name: opacity}, mx:{front lat, op}, barrier, crack,
  //      labels:[{lon,lat,text,s,size,color,dy}], dots:[{lon,lat,s,col}], border:0..1, pins:[{lon,lat,s,text}], planes:[{x,y,rot}]}
  function mapScene(t, st) {
    const cam = st.cam || { cx: 540, cy: 810, z: 1 };
    let bg = `<rect width="${W}" height="${H}" fill="${D.linear([[0, '#8fd0ee'], [1, '#4c9ccc']])}"/>`;
    for (let i = 0; i < 30; i++) {
      const wx = (rand(i) * 1300 + t * 12) % 1300 - 110, wy = 200 + rand(i + 5) * 1600;
      bg += `<path d="M${f2(wx)} ${f2(wy)} q12 -8 24 0 q12 8 24 0" fill="none" stroke="#e6f6ff" stroke-width="3" stroke-linecap="round" opacity="0.4"/>`;
    }
    const zs = 1 / cam.z; // keep strokes readable when zoomed
    let m = `<g transform="translate(${MAPX} ${MAPY})">`;
    m += `<path d="${LAND}" fill="#3a6f8f" opacity="0.25" transform="translate(10 12)"/>`;
    m += `<path d="${LAND}" fill="${C.land}" stroke="${INK}" stroke-width="${f2(3.2 * zs)}" stroke-linejoin="round"/>`;
    // US states (thin)
    m += `<path d="${Object.values(MP.states).join('')}" fill="none" stroke="#b49a6a" stroke-width="${f2(1.6 * zs)}"/>`;
    m += `<path d="${MP.countries.usa}" fill="none" stroke="${INK}" stroke-width="${f2(3.2 * zs)}"/>`;
    // infestation: red regions
    const red = st.red || {};
    for (const [k, op] of Object.entries(red)) {
      if (op <= 0.01) continue;
      const d = k.startsWith('state:') ? MP.states[k.slice(6)] : MP.countries[k];
      if (d) m += `<path d="${d}" fill="${C.red}" opacity="${f2(op * 0.78)}"/>`;
    }
    m += '</g>';
    // Mexico's moving front (red south of the front latitude, clipped to Mexico)
    if (st.mx && st.mx.op > 0.01) {
      const [, yF] = mxy(-100, st.mx.front);
      let d = `M0 ${f2(yF)}`;
      for (let x = 0; x <= W; x += 40) d += `L${x} ${f2(yF + noise(3, x * 0.01 + t * 0.4) * 14)}`;
      d += `L${W} ${H} L0 ${H} Z`;
      m += `<clipPath id="mxclip"><path d="${MP.countries.mexico}" transform="translate(${MAPX} ${MAPY})"/></clipPath>`;
      m += `<g clip-path="url(#mxclip)"><path d="${d}" fill="${C.red}" opacity="${f2(st.mx.op * 0.78)}"/></g>`;
    }
    m += `<path d="${LAND}" transform="translate(${MAPX} ${MAPY})" fill="none" stroke="${INK}" stroke-width="${f2(3.2 * zs)}" stroke-linejoin="round"/>`;
    // barrier at the Darién Gap
    if (st.barrier > 0.01) {
      const [bx, by] = mxy(-77.6, 8.2);
      const pulse = 0.8 + 0.2 * Math.sin(t * 4);
      m += `<circle cx="${f2(bx)}" cy="${f2(by)}" r="${f2(90 * zs * 1.6)}" fill="${D.radial([[0, '#9bf0c0', 0.8], [1, '#9bf0c0', 0]], { cx: 0.5, cy: 0.5, r: 0.5 })}" opacity="${f2(st.barrier * pulse)}"/>`;
      m += G(tf(bx, by, 50), `<rect x="${f2(-60 * zs)}" y="${f2(-9 * zs)}" width="${f2(120 * zs)}" height="${f2(18 * zs)}" rx="${f2(8 * zs)}" fill="#3fd08a" stroke="${INK}" stroke-width="${f2(3 * zs)}"/>`, `opacity="${f2(st.barrier)}"`);
      if (st.crack > 0.01) m += G(tf(bx, by, 50), `<path d="M${f2(-8 * zs)} ${f2(-12 * zs)} L${f2(4 * zs)} ${f2(-2 * zs)} L${f2(-6 * zs)} ${f2(4 * zs)} L${f2(6 * zs)} ${f2(14 * zs)}" stroke="${INK}" stroke-width="${f2(4 * zs)}" fill="none" opacity="${f2(st.crack)}"/>`);
    }
    // closed border
    if (st.border > 0.01) {
      m += `<path d="${borderD}" fill="none" stroke="${INK}" stroke-width="${f2(14 * zs)}" stroke-linecap="round" stroke-linejoin="round" opacity="${f2(st.border)}"/>`;
      m += `<path d="${borderD}" fill="none" stroke="${C.red}" stroke-width="${f2(8 * zs)}" stroke-dasharray="${f2(18 * zs)} ${f2(10 * zs)}" stroke-linecap="round" stroke-linejoin="round" opacity="${f2(st.border)}"/>`;
    }
    for (const dt of st.dots || []) {
      if (dt.s <= 0.01) continue;
      const [x, y] = mxy(dt.lon, dt.lat);
      m += `<circle cx="${f2(x)}" cy="${f2(y)}" r="${f2(10 * zs * dt.s)}" fill="${dt.col || C.red}" stroke="${INK}" stroke-width="${f2(2.2 * zs)}"/>`;
    }
    for (const pn of st.pins || []) {
      if (pn.s <= 0.01) continue;
      const [x, y] = mxy(pn.lon, pn.lat);
      m += G(tf(x, y, 0, zs * pn.s), `<path d="M0 0 C-10 -20 -26 -32 -26 -52 C-26 -68 -14 -80 0 -80 C14 -80 26 -68 26 -52 C26 -32 10 -20 0 0 Z" fill="${pn.col || C.red}" stroke="${INK}" stroke-width="5"/><circle cx="0" cy="-52" r="10" fill="#fff"/>` +
        (pn.ring ? `<circle cx="0" cy="0" r="${f2(30 + ((t * 1.2) % 1) * 60)}" fill="none" stroke="${C.red}" stroke-width="5" opacity="${f2(1 - ((t * 1.2) % 1))}"/>` : ''));
    }
    for (const lb of st.labels || []) {
      if ((lb.s ?? 1) <= 0.01) continue;
      const [x, y] = mxy(lb.lon, lb.lat);
      m += G(tf(x, y + (lb.dy || 0) * zs, 0, zs * (lb.s ?? 1)), txt(0, 0, lb.text, lb.size || 34, lb.color || INK, { stroke: lb.halo || C.cream, sw: 9 }));
    }
    for (const pl of st.planes || []) m += SW.plane(pl.x, pl.y, { t, s: (pl.s || 0.35) * zs, rot: pl.rot || 0 });
    return bg + `<g transform="${camT(cam.cx, cam.cy, cam.z)}">${m}</g>`;
  }
  // camera target from lon/lat
  const camAt = (lon, lat, z) => { const [x, y] = mxy(lon, lat); return { cx: x, cy: y, z }; };
  const lerpCam = (a, b, k) => ({ cx: lerp(a.cx, b.cx, k), cy: lerp(a.cy, b.cy, k), z: Math.exp(lerp(Math.log(a.z), Math.log(b.z), k)) });
  const MAP_FULL = { cx: 540, cy: 810, z: 1 };
  // south Texas / NM / AZ case dots (illustrative positions inside the affected regions)
  const CASES = (() => {
    const out = [];
    for (let i = 0; i < 71; i++) {
      let lon, lat;
      if (i === 70) { lon = -109.9; lat = 31.8; }               // Cochise County, Arizona
      else if (i % 9 === 4) { lon = -104.2 - rand(i) * 2.5; lat = 32.1 + rand(i + 3) * 1.2; } // New Mexico
      else if (i === 0) { lon = -99.76; lat = 28.87; }          // Zavala County, Texas
      else { lon = -100.6 + (rand(i + 11) - 0.3) * 2.8; lat = 27.4 + rand(i + 17) * 2.3; }
      out.push([lon, lat]);
    }
    return out;
  })();

  // ---------- shot painters ----------
  // c: {t0, t1, lines, w(word, frac), opt}; each returns SVG for the full frame (captions added later)
  const PAINT = {};
  const CUEF = {};

  // ranch open: wide on the herd, push to the calf, fly lands
  PAINT.ranch = (t, c) => {
    const tL = t - c.t0, tM = c.w('maggots', 0.7), tJ = c.w('june', 0.05);
    const z = keys(t, [[c.t0, 1.0], [tM - 0.6, 1.12, 'linear'], [tM + 0.2, 1.65, 'inOutCubic']]);
    const cx = lerp(560, 720, inv(tM - 0.6, tM + 0.2, t)), cy = lerp(1000, 1180, inv(tM - 0.6, tM + 0.2, t));
    let s = SW.ranch(t, { cx, cy, z, warm: 0.6 });
    let wld = '';
    const sad = t > tM;
    const mom = SW.cow(250, 1360, { t, s: 1.05, mood: sad ? 'surprised' : 'happy', lookX: 1, bl: blink(t, 2, 3.4), headTurn: -4 });
    const calf = SW.cow(900, 1360, { t, s: 0.9, kind: 'calf', flip: -1, mood: sad ? 'sad' : 'happy', lookX: 0.6, lookY: sad ? 0.8 : 0, bl: blink(t + 1, 4, 2.8) });
    wld += `<ellipse cx="250" cy="1366" rx="260" ry="26" fill="#6b4a2a" opacity="0.25"/><ellipse cx="900" cy="1366" rx="190" ry="22" fill="#6b4a2a" opacity="0.25"/>`;
    wld += mom.svg + calf.svg;
    // fly arrives on a looping path and settles on the navel
    const [nx, ny] = calf.navel;
    const fT0 = c.t0 + 0.8, fT1 = c.w('found', 0.55);
    const k = clamp((t - fT0) / (fT1 - fT0));
    if (t > fT0) {
      const e = ease.inOutCubic(k), loop = (1 - e) * 120;
      const fx = lerp(1150, nx + 10, e) + Math.sin(e * 9) * loop, fy = lerp(700, ny + 4, e) + Math.cos(e * 7) * loop * 0.6;
      if (k < 1) for (let i = 1; i < 6; i++) { const e2 = ease.inOutCubic(clamp(k - i * 0.03)); wld += `<circle cx="${f2(lerp(1150, nx + 10, e2) + Math.sin(e2 * 9) * (1 - e2) * 120)}" cy="${f2(lerp(700, ny + 4, e2) + Math.cos(e2 * 7) * (1 - e2) * 72)}" r="4" fill="#fff" opacity="${f2(0.6 - i * 0.1)}"/>`; }
      wld += SW.fly(fx, fy, { t, s: 0.28, wing: k < 1 ? 1 : 0.15, flip: -1, mood: 'smug' });
    }
    s += `<g transform="${camT(cx, cy, z)}">${wld}</g>`;
    s += chip(540, 300, 'JUNE 2026', { size: 64, s: popS(t, tJ), sub: 'ZAVALA COUNTY, TEXAS', subSize: 32 });
    return s + vignette(0.25);
  };
  CUEF.ranch = c => [[c.t0 + 0.8, 'buzz', 0.9], [c.w('june', 0.05), 'pop'], [c.w('maggots', 0.7) - 0.6, 'whoosh', 0.8]];

  // macro: the navel wound in a lens, maggots wriggling
  function woundSkin(t, R, n, o = {}) {
    const { depth = 0 } = o;
    let s = `<rect x="${-R}" y="${-R}" width="${2 * R}" height="${2 * R}" fill="${D.radial([[0, '#f0b0a0'], [1, '#c8806e']], { cx: 0.5, cy: 0.45, r: 0.7 })}"/>`;
    for (let i = 0; i < 60; i++) {
      const a = rand(i) * 6.28, r = R * (0.55 + rand(i + 4) * 0.5), x = Math.cos(a) * r, y = Math.sin(a) * r;
      s += D.taper([[x, y], [x + Math.cos(a) * 30, y + Math.sin(a) * 30 - 10]], 6, 1, '#b5532e', 'opacity="0.8"');
    }
    let wd = '';
    for (let i = 0; i <= 14; i++) { const a = (i / 14) * 6.28, r = 120 * (1 + (rand(i + 9) - 0.5) * 0.3); wd += `${i ? 'L' : 'M'}${f2(Math.cos(a) * r * 1.3)} ${f2(Math.sin(a) * r)}`; }
    s += `<path d="${wd}Z" fill="${C.wound}" stroke="${INK}" stroke-width="5"/><path d="${wd}Z" fill="#5e1a18" transform="scale(0.7)" opacity="0.6"/>`;
    for (let i = 0; i < n; i++) {
      const a = (i / Math.max(1, n)) * 6.28 + 0.4, r = 55 + (i % 2) * 30;
      s += SW.maggot(Math.cos(a) * r * 1.2, Math.sin(a) * r, { t: t + i, s: 0.7, rot: (a * 180) / Math.PI + 180 + Math.sin(t * 3 + i) * 10, wig: 1.2, screw: t * 1.5 + i * 0.3 });
    }
    return s;
  }
  PAINT.macro = (t, c) => {
    const tL = t - c.t0;
    let s = SW.ranch(t, { cx: 720, cy: 1180, z: 1.65, warm: 0.6 });
    s += `<rect width="${W}" height="${H}" fill="#1a0e08" opacity="0.55"/>`;
    const r = 400 * ease.outBack(clamp(tL / 0.45), 1.2);
    const cid = 'lensC' + Math.round(t * 30);
    if (r > 2) {
      s += `<clipPath id="${cid}"><circle cx="540" cy="820" r="${f2(r)}"/></clipPath>`;
      s += `<g clip-path="url(#${cid})"><g transform="translate(540 820)">${woundSkin(t, 420, Math.min(6, Math.floor(tL * 8)))}</g></g>`;
      s += `<circle cx="540" cy="820" r="${f2(r)}" fill="none" stroke="${INK}" stroke-width="14"/><circle cx="540" cy="820" r="${f2(r - 9)}" fill="none" stroke="#fff" stroke-width="4" opacity="0.6"/>`;
    }
    const tA = c.w('living', c.opt.alive ? 0.6 : 0.85);
    s += chip(540, 1310, 'EATS LIVING FLESH', { size: 56, fill: C.red, color: '#fff', s: popS(t, tA), rot: -3 });
    return s;
  };
  CUEF.macro = c => [[c.t0, 'lens_open'], [c.t0 + 0.4, 'squirm', 0.8], [c.w('living', 0.6), 'stamp', 0.6]];

  // fly hero shot with name plate and the 1966/2026 stamps
  PAINT.flyHero = (t, c) => {
    const tB = c.w('back', 0.9), t66 = c.w('1966', 0.6), tN = c.w('new', 0.05);
    const [sx, sy] = shake(t, tB, 18);
    let s = `<rect width="${W}" height="${H}" fill="${D.radial([[0, '#2f6f78'], [1, '#0f2a33']], { cx: 0.5, cy: 0.4, r: 0.8 })}"/>`;
    for (let i = 0; i < 40; i++) s += `<circle cx="${f2((rand(i) * W + t * 8 * (1 + rand(i + 1))) % W)}" cy="${f2((rand(i + 2) * H - t * 14 * rand(i + 3) + H) % H)}" r="${f2(2 + rand(i + 4) * 4)}" fill="#bff3ff" opacity="${f2(0.15 + rand(i + 5) * 0.3)}"/>`;
    const ent = ease.outBack(clamp((t - c.t0) / 0.6), 1.3);
    const fx = lerp(1300, 560, ent) + noise(1, t * 0.8) * 16, fy = 760 + Math.sin(t * 2.2) * 18;
    const mood = t > tB ? 'smug' : t > t66 ? 'annoyed' : 'smug';
    s += G(`translate(${f2(sx)} ${f2(sy)})`, SW.fly(fx, fy, { t, s: 2.5, mood, lookX: -0.4, lookY: 0.4, bl: blink(t, 7, 3), rot: -6 + Math.sin(t * 1.3) * 3 }));
    const np = popS(t, tN);
    if (np > 0.01) s += G(tf(540, 1190, 0, np), `<rect x="-410" y="-70" width="820" height="150" rx="28" fill="${C.cream}" stroke="${INK}" stroke-width="7"/>` + txt(0, 4, 'NEW WORLD SCREWWORM', 62, INK) + txt(0, 54, 'Cochliomyia hominivorax', 34, '#6b5646', { weight: 600, extra: 'font-style="italic"' }));
    if (t > t66 && t < tB + 0.05) s += stamp(540, 430, 'ERADICATED', t, t66, { color: '#2f8f4a', sub: 'UNITED STATES · 1966' });
    if (t > tB) s += stamp(540, 430, "IT'S BACK", t, tB, { color: C.red, size: 104, rot: 6, sub: '2026' });
    return s;
  };
  CUEF.flyHero = c => [[c.t0, 'buzz', 0.8], [c.w('1966', 0.6), 'stamp'], [c.w('back', 0.9), 'stamp', 1.2], [c.w('back', 0.9) + 0.02, 'crack', 0.8]];

  // weapon: not poison — more flies, billions
  PAINT.weapon = (t, c) => {
    const tP = c.w('poison', 0.35), tF = c.w('flies', 0.6), tBn = c.w('billions', 0.85);
    let s = plain('#fdf3dc', '#f2dcb0');
    // spray can
    const cp = popS(t, c.t0 + 0.1);
    const fadeCan = 1 - clamp((t - tF + 0.2) / 0.3);
    if (cp > 0.01 && fadeCan > 0.01) {
      let can = sh('M-70 -150 L70 -150 L70 150 L-70 150 Z', '#8a9aa8', { depth: 12 }) + sh('M-40 -190 L40 -190 L40 -150 L-40 -150 Z', '#5a6a78', { depth: 5 }) + sh('M-12 -220 L20 -220 L20 -190 L-12 -190 Z', '#c0c8d0', { depth: 3 });
      can += `<rect x="-70" y="-60" width="140" height="110" fill="#f6e04a" stroke="${INK}" stroke-width="5"/>` + txt(0, 6, 'POISON', 34, INK) + `<path d="M-20 26 L20 26" stroke="${INK}" stroke-width="5"/>`;
      s += G(tf(540, 820, -8, cp), can, `opacity="${f2(fadeCan)}"`);
      if (t > tP) s += G('', cross(540, 820, 3.2 * popS(t, tP)), `opacity="${f2(fadeCan)}"`);
    }
    // flies multiply
    if (t > tF - 0.1) {
      const n = Math.round(Math.min(160, 6 * Math.pow(2, (t - tF) * 3.6)));
      s += swarm(t, n, { x0: 60, x1: 1020, y0: 260, y1: 1340, seed: 11, s: 2.2, col: i => (i % 7 === 0 ? C.flyBody : C.sterile) });
    }
    if (t > tBn) s += counterBadge(540, 820, 'BILLIONS', 'of flies', { s: popS(t, tBn), size: 120 });
    return s;
  };
  CUEF.weapon = c => [[c.w('poison', 0.35), 'stamp', findWord(c.lines, 'poison') !== null ? 0.6 : 0.3], [c.w('flies', 0.6), 'swarm', 1], [c.w('billions', 0.85), 'chime']];

  // title sting (full cut only): drawn over the end of the weapon shot
  function titleSting(t) {
    if (CUT !== 'full') return '';
    const t0 = L.weapon.end + 0.05, t1 = L.eggs.start + 0.15;
    if (t < t0 || t > t1) return '';
    const k = Math.min(popS(t, t0, 2.4, 0.55), 1 - clamp((t - t1 + 0.2) / 0.2));
    return `<rect width="${W}" height="${H}" fill="#1a0e08" opacity="${f2(0.55 * k)}"/>` + G(tf(540, 820, -3, k),
      `<rect x="-440" y="-150" width="880" height="300" rx="40" fill="${C.cream}" stroke="${INK}" stroke-width="9"/>` +
      txt(0, -30, 'THE FLY THAT', 90, INK) + txt(0, 80, 'CAME BACK', 120, C.red, { stroke: INK, sw: 8 }));
  }

  // eggs: a female lays an egg mass at a wound edge
  PAINT.eggs = (t, c) => {
    const tL = c.w('lays', 0.2), tE = c.w('eggs', 0.5), tN = c.w('navel', 0.9);
    let s = `<g transform="translate(540 900)">${woundSkin(t, 1200, 0)}</g>`;
    s += `<rect width="${W}" height="${H}" fill="#000" opacity="0.08"/>`;
    const n = Math.round(42 * clamp((t - tL) / Math.max(0.5, tE - tL + 0.8)));
    s += SW.eggMass(640, 760, n, { s: 2.2, rot: -14 });
    const land = ease.outCubic(clamp((t - c.t0) / 0.8));
    s += SW.fly(lerp(1200, 820, land), lerp(300, 610, land), { t, s: 1.35, wing: land < 1 ? 1 : 0.1, rot: 18, flip: -1, mood: 'smug', lookX: -0.6, lookY: 0.7 });
    const big = c.opt.upTo ? 'UP TO 500' : '250–500';
    const tC = c.opt.upTo ? c.w('five', 0.4) : c.w('two', 0.4);
    s += counterBadge(330, 420, big, 'eggs at a time', { s: popS(t, tC) });
    if (!c.opt.upTo && t > tN - 0.3) s += chip(330, 1180, "OR A NEWBORN'S NAVEL", { size: 40, s: popS(t, tN - 0.3) });
    return s + vignette(0.3);
  };
  CUEF.eggs = c => [[c.t0, 'buzz', 0.7], [c.opt.upTo ? c.w('five', 0.4) : c.w('two', 0.4), 'pop'], [c.w('navel', 0.9) - 0.3, 'pop_small']];

  // screw: cross-section of skin with maggots burrowing, screwing deeper when disturbed
  PAINT.screw = (t, c) => {
    const tD = c.w('disturb', 2), tN = c.w('name', 0.85);
    let s = plain('#fbe8d8', '#f4d4c0');
    // layers
    const top = 560;
    s += `<rect x="0" y="${top}" width="${W}" height="70" fill="#d98f7c"/><rect x="0" y="${top + 70}" width="${W}" height="260" fill="#efb8a6"/><rect x="0" y="${top + 330}" width="${W}" height="520" fill="#d4675e"/>`;
    for (let i = 0; i < 16; i++) s += `<path d="M${i * 70 - 20} ${top + 360} q35 30 0 60 q-35 30 0 60 q35 30 0 60 q-35 30 0 60" fill="none" stroke="#b84e48" stroke-width="5" opacity="0.6"/>`;
    for (let i = 0; i < 28; i++) s += D.taper([[i * 40 + 6, top], [i * 40 + 16, top - 60 - rand(i) * 30]], 10, 2, '#b5532e');
    s += `<path d="M0 ${top} L${W} ${top}" stroke="${INK}" stroke-width="6"/>`;
    // wound pit
    const dig = clamp((t - c.t0) / 3), deeper = ease.inOutCubic(clamp((t - tD) / 1.4));
    const pitD = 160 + dig * 120 + deeper * 220;
    s += `<path d="M380 ${top - 4} C410 ${top + pitD * 0.6} 470 ${top + pitD} 540 ${top + pitD} C610 ${top + pitD} 670 ${top + pitD * 0.6} 700 ${top - 4} Z" fill="${C.wound}" stroke="${INK}" stroke-width="6"/>`;
    for (let i = 0; i < 4; i++) {
      const bx = 450 + i * 60, by = top + 60 + dig * 90 + deeper * 200 + (i % 2) * 40;
      const spin = t * (1.2 + deeper * 5) + i;
      s += SW.maggot(bx, by, { t: t + i, s: 0.95, rot: 90 + Math.sin(t * 2 + i) * 8, wig: 0.6 + deeper, screw: spin, len: 130 });
      if (deeper > 0.05) s += `<path d="M${bx - 40} ${by - 20} q40 -24 80 0 M${bx - 40} ${by + 10} q40 -24 80 0" stroke="#fff" stroke-width="4" fill="none" opacity="${f2(0.7 * deeper * (0.6 + 0.4 * Math.sin(t * 20)))}"/>`;
    }
    // a poke on "disturb"
    if (t > tD - 0.3) {
      const pk = Math.sin(clamp((t - tD + 0.3) / 0.6) * Math.PI);
      s += G(tf(760 - pk * 60, top - 150 + pk * 60, -40), sh('M-12 -160 L12 -160 L10 40 L0 70 L-10 40 Z', '#c8955a', { depth: 4, w: 4.5 }));
      s += D.shock(700, top - 30, -2.4, 1.1 * pk);
    }
    if (t > tN - 0.2) {
      const k = popS(t, tN - 0.2);
      s += G(tf(540, 340, -4, k), `<rect x="-360" y="-80" width="720" height="160" rx="30" fill="${C.cream}" stroke="${INK}" stroke-width="7"/>` +
        txt(-120, 30, 'SCREW', 96, C.red, { stroke: INK, sw: 8 }) + txt(80, 30, '+', 80, INK) + txt(220, 30, 'WORM', 96, '#c9a65a', { stroke: INK, sw: 8 }));
    }
    return s;
  };
  CUEF.screw = c => [[c.t0, 'squirm', 0.8], [c.w('disturb', 2) - 0.2, 'boing', 0.7], [c.w('disturb', 2) + 0.2, 'drill', 0.8], [c.w('name', 0.85) - 0.2, 'pop']];

  // worse: the calf down, more flies circling
  PAINT.worse = (t, c) => {
    const tK = c.w('kill', 0.85), tM = c.w('flies', 0.3);
    let s = SW.ranch(t, { cx: 560, cy: 1150, z: 1.25, warm: 1, dusk: 0.25 });
    let wld = SW.cow(260, 1360, { t, s: 1.0, mood: 'sad', lookX: 1, lookY: 0.5, bl: blink(t, 3, 3) }).svg;
    const calf = SW.cow(760, 1380, { t, s: 0.9, kind: 'calf', flip: -1, mood: 'sad', lie: 1, lookY: 0.6, bl: blink(t, 5, 2.4) });
    wld += calf.svg;
    const [nx, ny] = calf.navel;
    const nF = 2 + Math.floor(clamp((t - tM + 0.4) / 1.5) * 6);
    for (let i = 0; i < nF; i++) {
      const a = t * (2 + i * 0.3) + i * 1.1, r = 70 + i * 22;
      wld += SW.fly(nx + Math.cos(a) * r, ny - 120 + Math.sin(a) * r * 0.45, { t: t + i, s: 0.22, flip: Math.cos(a) > 0 ? -1 : 1, mood: 'smug' });
    }
    s += `<g transform="${camT(560, 1150, 1.25)}">${wld}</g>`;
    if (t > tM - 0.3) s += chip(540, 340, '+ MORE FLIES', { size: 54, s: popS(t, tM - 0.3) });
    if (t > tK) s += stamp(540, 560, 'CAN KILL', t, tK, { color: C.redDk, size: 96 });
    return s + vignette(0.3);
  };
  CUEF.worse = c => [[c.t0, 'buzz', 0.9], [c.w('kill', 0.85), 'stamp']];

  // hosts: who it attacks
  PAINT.hosts = (t, c) => {
    let s = plain('#fdf0d6', '#f6d9a8');
    s += `<rect x="0" y="980" width="${W}" height="20" fill="#e6c48e"/><rect x="0" y="1360" width="${W}" height="20" fill="#e6c48e"/>`;
    const tc = c.w('cattle', 0.05), td = c.w('deer', 0.2), tg = c.w('dogs', 0.35), tct = c.w('cats', 0.5), tp = c.w('people', 0.85), tsm = c.w('sometimes', 0.7);
    const item = (t0, x, y, svg, label) => {
      const k = popS(t, t0);
      if (k <= 0.01) return '';
      return G(tf(x, y, 0, k), svg) + G(tf(x, y + 70, 0, k), txt(0, 0, label, 46, INK, { stroke: C.cream, sw: 8 }));
    };
    s += item(tc, 290, 980, SW.cow(-40, 0, { t, s: 0.62, mood: 'skeptical', bl: blink(t, 1) }).svg, 'CATTLE');
    s += item(td, 790, 980, SW.cow(-40, 0, { t, s: 0.66, kind: 'deer', antlers: true, mood: 'surprised', bl: blink(t, 2) }).svg, 'DEER');
    s += item(tg, 200, 1360, SW.dog(-40, 0, { t, s: 0.85, mood: 'sad', bl: blink(t, 3) }), 'DOGS');
    s += item(tct, 540, 1360, SW.cat(0, 0, { t, s: 0.9, bl: blink(t, 4) }), 'CATS');
    s += item(tp, 870, 1360, SW.adult(0, 0, { t, s: 0.42, coat: 'ranch', hat: true, mood: 'surprised', bl: blink(t, 5) }).svg, 'PEOPLE');
    if (t > tsm) s += chip(870, 1040, 'SOMETIMES', { size: 36, s: popS(t, tsm), fill: C.gold });
    s += txt(540, 330, 'WHO IT EATS', 76, INK, { stroke: C.cream, sw: 10 });
    return s;
  };
  CUEF.hosts = c => ['cattle', 'deer', 'dogs', 'cats', 'people'].map((w, i) => [c.w(w, 0.1 + i * 0.18), 'pop', 0.8]);

  // map shots
  PAINT.map = (t, c) => {
    const o = c.opt, mode = o.mode;
    const st = { cam: MAP_FULL, red: {}, labels: [], dots: [], pins: [], barrier: 0, crack: 0, border: 0 };
    const allRed = 1;
    const centralRed = v => CENTRAL.forEach(k => { st.red[k] = v; });
    const southAm = v => ['colombia', 'venezuela', 'ecuador'].forEach(k => { st.red[k] = v; });
    let over = '';
    if (mode === 'canada') {
      const pulse = 0.75 + 0.25 * Math.sin(t * 3);
      southAm(1); centralRed(1); st.red.mexico = 1; st.red.cuba = 1;
      const tU = c.w('canadian', 0.6);
      st.red.usa = clamp((t - c.t0) / 1.6) * pulse;
      st.labels.push({ lon: -97, lat: 50.6, text: 'CANADIAN BORDER', size: 40, s: popS(t, tU), color: C.redDk });
      over += chip(540, 260, 'BEFORE THE 1950s', { size: 46, s: popS(t, c.t0 + 0.2) });
    } else if (mode === 'scale') {
      southAm(1); centralRed(1); st.red.mexico = 1;
      const tF = c.w('florida', 0.3), tS = c.w('southwest', 0.85);
      SE_STATES.forEach(n => { st.red['state:' + n] = 1 - clamp((t - tF) / 1.4); });
      SW_STATES.forEach(n => { st.red['state:' + n] = 1 - clamp((t - tS) / 1.4); });
      st.cam = lerpCam(camAt(-92, 33, 1.7), camAt(-98, 32, 1.35), ease.inOutCubic(inv(tF + 0.6, tS, t)));
      const pk = clamp((t - tF) / 3);
      st.planes = [{ x: mxy(-84 + pk * 3, 28)[0], y: mxy(-84, 28.5 + pk * 2)[1], rot: -8, s: 0.3 }];
      if (t > tS) st.planes.push({ x: mxy(-104 + (t - tS) * 2, 31)[0], y: mxy(-100, 32.5)[1], rot: 6, s: 0.3 });
      over += chip(540, 260, t < tS ? 'FLORIDA · 1958' : 'THE SOUTHWEST', { size: 50, s: popS(t, tF - 0.1) });
    } else if (mode === 'gone') {
      southAm(1); centralRed(1); st.red.mexico = 1;
      const t66 = c.w('1966', 0.25), t94 = c.w('ninety', 0.6);
      st.cam = lerpCam(camAt(-98, 32, 1.35), MAP_FULL, ease.inOutCubic(inv(c.t0, c.t0 + 1.2, t)));
      over += stamp(540, 300, 'GONE FROM THE US', t, t66, { color: '#2f8f4a', size: 70, sub: '1966' });
      if (t > t94) over += counterBadge(540, 1210, '94 BILLION', 'sterile flies released, 1962–1975', { s: popS(t, t94), size: 96 });
    } else if (mode === 'south') {
      southAm(1);
      const t91 = c.w('1991', 0.3), tCA = c.w('central', 0.7);
      const kf = ease.inOutCubic(clamp((t - c.t0) / Math.max(0.5, t91 - c.t0)));
      st.mx = { front: lerp(33, 13.5, kf), op: 1 };
      CENTRAL.forEach((k, i) => { st.red[k] = 1 - clamp((t - tCA - i * 0.32) / 0.4); });
      over += chip(540, 260, t < t91 ? `${Math.round(lerp(1972, 1991, kf))}` : 'MEXICO FREE · 1991', { size: 50, s: popS(t, c.t0 + 0.1) });
    } else if (mode === 'wall') {
      southAm(1);
      const tP = c.w('panama', 0.2), tH = c.w('hundred', 0.5), tDG = c.w('darin', 0.85);
      st.cam = lerpCam(MAP_FULL, camAt(-79.3, 8.6, 4.2), ease.inOutCubic(inv(c.t0, tP + 0.6, t)));
      st.barrier = clamp((t - tP) / 0.6);
      st.labels.push({ lon: -80.4, lat: 9.75, text: 'PANAMA', size: 34, s: popS(t, tP) });
      st.labels.push({ lon: -77.4, lat: 7.15, text: 'DARIÉN GAP', size: 30, s: popS(t, tDG), color: '#1d7a4a' });
      if (t > tP) for (let i = 0; i < 14; i++) {
        const ph = (t * 0.6 + i / 14) % 1, [bx, by] = mxy(-77.6 + (rand(i) - 0.5) * 2.2, 8.2 + (rand(i + 3) - 0.5) * 1.6);
        st.dots.push({ lon: -77.6 + (rand(i) - 0.5) * 2.2 + ph * 0.3, lat: 8.2 + (rand(i + 3) - 0.5) * 1.6 + ph * 0.4, s: 0.7 * Math.sin(ph * Math.PI), col: C.sterile });
      }
      if (t > tH) over += counterBadge(540, 1210, 'UP TO 100 MILLION', 'sterile flies a week', { s: popS(t, tH), size: 80 });
    } else if (mode === 'breach') {
      const tBr = c.w('broke', 0.4), tS = c.w('southern', 0.6), tN = c.w('north', 0.9);
      southAm(1);
      st.barrier = 1 - clamp((t - tBr - 0.4) / 0.6) * 0.7;
      st.crack = clamp((t - tBr) / 0.2);
      st.cam = lerpCam(camAt(-80, 9, 2.4), MAP_FULL, ease.inOutCubic(inv(tBr + 0.5, tS + 0.4, t)));
      CENTRAL.slice().reverse().forEach((k, i) => { st.red[k] = clamp((t - tBr - 0.3 - i * 0.18) / 0.4); });
      st.mx = { front: lerp(14, 23, ease.inOutCubic(clamp((t - tS) / Math.max(1, tN - tS + 0.8)))), op: clamp((t - tS + 0.3) / 0.4) };
      over += chip(540, 260, 'LATE 2024', { size: 50, s: popS(t, c.t0 + 0.1) });
    } else if (mode === 'border' || mode === 'closer') {
      southAm(1); centralRed(1);
      const tC = mode === 'border' ? c.w('closed', 0.5) : c.t0 - 2;
      st.cam = mode === 'border' ? lerpCam(MAP_FULL, camAt(-102, 27.5, 2.6), ease.inOutCubic(inv(c.t0, c.t0 + 1.4, t))) : camAt(-102, 27.5, 2.6);
      st.mx = { front: mode === 'border' ? 24 : lerp(24, 28.6, ease.inOutCubic(clamp((t - c.t0) / 3.2))), op: 1 };
      st.border = clamp((t - tC) / 0.3);
      if (mode === 'border') over += chip(540, 260, 'JULY 2025', { size: 50, s: popS(t, c.t0 + 0.2) });
      if (t > tC) st.labels.push({ lon: -104.5, lat: 30.9, text: 'BORDER CLOSED', size: 30, s: popS(t, tC), color: C.redDk });
      if (mode === 'border' && t > tC + 0.3) over += chip(540, 1220, 'NO MEXICAN CATTLE IMPORTS', { size: 40, s: popS(t, tC + 0.3), fill: C.gold });
      if (mode === 'closer') {
        const t70 = c.w('seventy', 0.4), t31 = c.w('thirty', 0.8);
        st.pins.push({ lon: -100.18, lat: 26.5, s: popS(t, t70), ring: true });
        st.labels.push({ lon: -100.18, lat: 25.6, text: '70 MI', size: 34, s: popS(t, t70), color: C.redDk });
        st.pins.push({ lon: -101.0, lat: 28.95, s: popS(t, t31), ring: true });
        st.labels.push({ lon: -101.0, lat: 28.2, text: '31 MI', size: 34, s: popS(t, t31), color: C.redDk });
        over += chip(540, 260, t < t31 ? 'SEPT 2025' : 'MAY 2026', { size: 50, s: popS(t, t70 - 0.1) });
      }
    } else if (mode === 'june' || mode === 'cases') {
      southAm(1); centralRed(1); st.mx = { front: 29, op: 1 }; st.border = mode === 'june' ? 1 : 0.5;
      const zoom = mode === 'june' ? camAt(-99.8, 29.2, 3.2) : camAt(-104, 30.6, 2.2);
      st.cam = mode === 'june' ? lerpCam(camAt(-102, 27.5, 2.6), zoom, ease.inOutCubic(inv(c.t0, c.t0 + 1, t))) : lerpCam(camAt(-99.8, 29.2, 3.2), zoom, ease.inOutCubic(inv(c.t0, c.t0 + 1.2, t)));
      if (mode === 'june') {
        const tJ = c.w('june', 0.2), tT = c.w('texas', 0.8);
        st.pins.push({ lon: -99.76, lat: 28.87, s: popS(t, tT - 0.2), ring: true });
        st.labels.push({ lon: -99.76, lat: 28.3, text: 'ZAVALA COUNTY', size: 26, s: popS(t, tT) });
        over += stamp(540, 330, 'JUNE 3, 2026', t, tJ, { color: C.red, size: 80, sub: 'FIRST US CASE IN DECADES' });
      } else {
        const tO = c.w('october', 0.5), tTx = c.w('texas', 0.3), tNm = c.w('mexico', 0.4), tAz = c.w('arizona', 0.5);
        const tAnim = c.opt.hook ? [c.t0 + 0.3, c.w('arizona', 0.6)] : [c.t0 + 0.4, tAz + 0.2];
        const nShow = Math.round(71 * ease.inOutQuad(clamp((t - tAnim[0]) / (tAnim[1] - tAnim[0]))));
        CASES.forEach(([lon, lat], i) => st.dots.push({ lon, lat, s: i < nShow ? popS(t, tAnim[0] + (i / 71) * (tAnim[1] - tAnim[0])) : 0 }));
        st.red['state:Texas'] = 0.18 * fadeIn(t, tTx); st.red['state:New Mexico'] = 0.18 * fadeIn(t, tNm); st.red['state:Arizona'] = 0.18 * fadeIn(t, tAz);
        st.labels.push({ lon: -99.5, lat: 31.6, text: 'TEXAS', size: 32, s: popS(t, tTx) });
        st.labels.push({ lon: -106.1, lat: 34.3, text: 'NEW MEXICO', size: 28, s: popS(t, tNm) });
        st.labels.push({ lon: -111.7, lat: 34.3, text: 'ARIZONA', size: 28, s: popS(t, tAz) });
        over += counterBadge(540, 330, `${nShow}`, 'confirmed US cases', { s: popS(t, c.t0 + 0.2), size: 110 });
        const tCt = c.w('cattle', 0.8), tDg = c.w('dogs', 0.85), tCa = c.w('cat', 0.95);
        if (!c.opt.hook) {
          over += `<rect x="70" y="1150" width="940" height="230" rx="34" fill="${C.cream}" stroke="${INK}" stroke-width="6" opacity="${f2(fadeIn(t, tCt - 0.2))}"/>`;
          over += G(tf(250, 1340, 0, 0.42 * popS(t, tCt)), SW.cow(0, 0, { t, mood: 'sad', bl: blink(t, 1) }).svg);
          over += G(tf(560, 1350, 0, 0.62 * popS(t, tDg)), SW.dog(0, 0, { t, mood: 'sad', bl: blink(t, 2) }));
          over += G(tf(850, 1355, 0, 0.62 * popS(t, tCa)), SW.cat(0, 0, { t, mood: 'sad', bl: blink(t, 3) }));
        } else over += chip(540, 1230, 'FROM TEXAS TO ARIZONA', { size: 44, s: popS(t, c.w('arizona', 0.6)) });
      }
    }
    return mapScene(t, st) + over;
  };
  CUEF.map = c => {
    const m = c.opt.mode, out = [];
    if (m === 'canada') out.push([c.w('canadian', 0.6), 'pop']);
    if (m === 'scale') out.push([c.w('florida', 0.3), 'plane', 0.8], [c.w('southwest', 0.85), 'whoosh']);
    if (m === 'gone') out.push([c.w('1966', 0.25), 'stamp'], [c.w('ninety', 0.6), 'chime']);
    if (m === 'south') out.push([c.w('1991', 0.3), 'chime', 0.8], ...[0, 1, 2, 3, 4, 5, 6].map(i => [c.w('central', 0.7) + i * 0.32, 'pop_small', 0.5]));
    if (m === 'wall') out.push([c.w('panama', 0.2), 'shimmer'], [c.w('hundred', 0.5), 'chime', 0.8]);
    if (m === 'breach') out.push([c.w('broke', 0.4), 'crack', 1.1], [c.w('southern', 0.6), 'drone', 0.8]);
    if (m === 'border') out.push([c.w('closed', 0.5), 'stamp']);
    if (m === 'closer') out.push([c.w('seventy', 0.4), 'ping'], [c.w('thirty', 0.8), 'ping']);
    if (m === 'june') out.push([c.w('june', 0.2), 'stamp', 1.1]);
    if (m === 'cases') { const a = c.t0 + 0.4, b = c.opt.hook ? c.w('arizona', 0.6) : c.w('arizona', 0.5) + 0.2; for (let i = 0; i < 12; i++) out.push([a + (b - a) * (i / 12), 'tick', 0.5]); if (!c.opt.hook) out.push([c.w('cattle', 0.8), 'pop'], [c.w('dogs', 0.85), 'pop'], [c.w('cat', 0.95), 'pop']); }
    return out;
  };

  // lab: the two scientists
  PAINT.lab = (t, c) => {
    const tK = c.w('knipling', 0.45), tB = c.w('bushland', 0.6), tW = c.w('better', 0.85);
    let s = SW.lab(t);
    const k1 = popS(t, tK - 0.2), k2 = popS(t, tB - 0.2);
    s += G(`translate(0 ${f2((1 - k1) * 300)})`, SW.adult(320, 1640, { t, s: 1.15, coat: 'lab', glasses: true, hair: '#4a3020', tag: 'KNIPLING', mood: t > tW ? 'skeptical' : 'happy', lookX: 0.5, bl: blink(t, 1), armR: { sh: 30, el: 60 } }).svg);
    s += G(`translate(0 ${f2((1 - k2) * 300)})`, SW.adult(770, 1640, { t, s: 1.15, coat: 'lab', hair: '#7a5232', tag: 'BUSHLAND', skin: '#f0c49c', mood: t > tW ? 'skeptical' : 'happy', lookX: -0.5, bl: blink(t, 2), armL: { sh: 20, el: 40 } }).svg);
    // foreground bench with microscope and fly cage
    s += sh('M0 1500 L1080 1500 L1080 1920 L0 1920 Z', '#7a5a3a', { depth: 10, w: 6 });
    s += G(tf(540, 1500), sh('M-30 0 L30 0 L24 -40 L-24 -40 Z', '#4a5a6a', { depth: 4 }) + D.inkTaper([[0, -40], [-30, -160]], 30, 24, '#5a6a7a', INK, 4) + sh('M-60 -170 L0 -180 L0 -150 L-60 -140 Z', '#3a4a5a', { depth: 3 }));
    s += G(tf(850, 1500), sh('M-80 0 L80 0 L80 -140 L-80 -140 Z', '#e8f4f8', { depth: 6 }) + swarm(t, 6, { x0: -60, x1: 60, y0: -120, y1: -20, seed: 5, s: 0.7 }) + `<path d="M-80 -140 L80 0 M80 -140 L-80 0" stroke="${INK}" stroke-width="1" opacity="0.2"/>`);
    s += sepia(0.28);
    s += chip(540, 280, '1930s', { size: 60, s: popS(t, c.t0 + 0.1), fill: C.paper });
    if (t > tW) s += G(tf(540, 640, 0, popS(t, tW)), `<ellipse cx="0" cy="0" rx="150" ry="110" fill="#fff" stroke="${INK}" stroke-width="6"/><circle cx="-110" cy="120" r="18" fill="#fff" stroke="${INK}" stroke-width="5"/>` + txt(0, 34, '?', 110, C.red));
    return s;
  };
  CUEF.lab = c => [[c.w('knipling', 0.45) - 0.2, 'pop'], [c.w('bushland', 0.6) - 0.2, 'pop'], [c.w('better', 0.85), 'twinkle', 0.7]];

  // once: the weakness — she mates once
  PAINT.once = (t, c) => {
    const tW = c.w('weakness', 0.3), tO = c.w('once', 0.75), tLf = c.w('life', 0.95);
    let s = `<rect width="${W}" height="${H}" fill="${D.radial([[0, '#ffe3e8'], [1, '#f2b6c4']], { cx: 0.5, cy: 0.4, r: 0.8 })}"/>`;
    const mIn = ease.outCubic(clamp((t - c.t0) / 1.2));
    s += SW.fly(lerp(-200, 330, mIn), 820 + Math.sin(t * 3) * 10, { t, s: 1.25, mood: 'happy', lookX: 1 });
    s += SW.fly(760, 820 + Math.sin(t * 2.5 + 1) * 10, { t, s: 1.35, flip: -1, mood: t > tW ? 'happy' : 'smug', lookX: 1, bl: blink(t, 3) });
    if (t > tW) {
      const hp = popS(t, tW);
      s += G(tf(545, 590 - Math.sin(t * 3) * 8, 0, hp), sh('M0 30 C-60 -10 -50 -70 0 -40 C50 -70 60 -10 0 30 Z', '#ff5f7e', { depth: 8, w: 5 }));
    }
    if (t > tO) s += G(tf(540, 340, -4, popS(t, tO)), `<circle r="120" fill="${C.gold}" stroke="${INK}" stroke-width="8"/>` + txt(0, 48, '1', 150, INK));
    if (t > tLf) s += chip(540, 1180, 'MATES ONCE · FOR LIFE', { size: 56, s: popS(t, tLf), fill: C.cream });
    if (c.opt.weak && t > tW) s += chip(540, 1310, 'THE WEAKNESS', { size: 40, s: popS(t, tW), fill: C.gold });
    return s;
  };
  CUEF.once = c => [[c.t0, 'buzz', 0.6], [c.w('weakness', 0.3), 'twinkle'], [c.w('once', 0.75), 'pop'], [c.w('life', 0.95), 'chime', 0.7]];

  // logic: fertile vs sterile mate, then flood the land
  PAINT.logic = (t, c) => {
    const tS = c.w('sterile', 0.35), tF = c.w('flood', 0.6), tN = c.w('never', 0.9), tHatch = c.t0 + 0.6;
    let s = plain('#fdf3dc', '#f4e0b8');
    const row = (y, sterile, t0, tRes) => {
      const k = popS(t, t0);
      if (k <= 0.01) return '';
      let r = SW.fly(160, y, { t, s: 0.75, mood: 'happy' }) + txt(300, y + 24, '+', 80, INK) + SW.fly(450, y, { t, s: 0.75, sterile, mood: sterile ? 'skeptical' : 'smug', flip: -1 });
      r += `<path d="M560 ${y} L640 ${y}" stroke="${INK}" stroke-width="10" stroke-linecap="round"/><path d="M630 ${y - 20} L660 ${y} L630 ${y + 20}" fill="none" stroke="${INK}" stroke-width="10" stroke-linecap="round"/>`;
      r += SW.eggMass(780, y + 30, 21, { s: 1.4, sterile });
      if (t > tRes) {
        if (!sterile) for (let i = 0; i < 3; i++) r += SW.maggot(900 + i * 10, y - 40 + i * 40, { t: t + i, s: 0.45 * popS(t, tRes + i * 0.15), rot: -20 + i * 20 });
        r += sterile ? cross(980, y - 70, popS(t, tRes)) : check(980, y - 70, popS(t, tRes));
      }
      return G(`translate(0 0) scale(1)`, r, `opacity="${f2(clamp(k))}"`);
    };
    s += row(560, false, c.t0, tHatch);
    s += txt(540, 450, 'WILD MATE', 40, '#2a7f5a', { stroke: C.cream, sw: 8 }) ;
    s += row(1000, true, tS - 0.2, tN - 0.1);
    if (t > tS - 0.2) s += txt(540, 890, 'STERILE MATE', 40, '#59636e', { stroke: C.cream, sw: 8 });
    if (t > tN - 0.1) s += chip(800, 1200, 'NEVER HATCH', { size: 44, fill: C.red, color: '#fff', s: popS(t, tN - 0.1) });
    if (t > tF) {
      const n = Math.round(Math.min(160, 10 + (t - tF) * 90));
      s += swarm(t, n, { x0: 40, x1: 1040, y0: 240, y1: 1360, seed: 21, s: 1.6, col: i => (i % 10 === 0 ? C.flyBody : C.sterile) });
      s += chip(540, 330, 'FLOOD THE LAND', { size: 60, s: popS(t, tF), fill: C.gold });
    }
    return s;
  };
  CUEF.logic = c => [[c.t0 + 0.6, 'pop_small'], [c.w('sterile', 0.35) - 0.2, 'pop'], [c.w('flood', 0.6), 'swarm'], [c.w('never', 0.9) - 0.1, 'stamp', 0.6]];

  // how: the sterilization problem and Muller's book
  PAINT.how = (t, c) => {
    const tBk = c.w('book', 0.55), tNb = c.w('nobel', 0.65), tR = c.w('radiation', 0.85);
    let s = plain('#e9e1cf', '#d6c8a8');
    const qOut = clamp((t - tBk + 0.3) / 0.3);
    if (qOut < 1) s += G(tf(540, 820, -3, popS(t, c.t0 + 0.1) * (1 - qOut)), `<rect x="-420" y="-170" width="840" height="340" rx="40" fill="${C.cream}" stroke="${INK}" stroke-width="8"/>` +
      txt(0, -40, 'HOW DO YOU', 80, INK) + txt(0, 60, 'STERILIZE A FLY?', 80, C.red, { stroke: INK, sw: 7 }) + SW.fly(330, -150, { t, s: 0.6, mood: 'smug', flip: -1 }));
    if (t > tBk - 0.3) {
      const k = popS(t, tBk - 0.3);
      let bk = sh('M-260 -330 L260 -330 L260 330 L-260 330 Z', '#3f5f8f', { depth: 16, w: 7 }) + `<rect x="-238" y="-330" width="20" height="660" fill="#2f4870"/>`;
      bk += txt(10, -200, 'H. J. MULLER', 54, C.cream);
      // radiation trefoil
      const tre = [0, 120, 240].map(a => `<path d="M0 0 L${f2(Math.cos((a - 30) * Math.PI / 180) * 110)} ${f2(Math.sin((a - 30) * Math.PI / 180) * 110)} A110 110 0 0 1 ${f2(Math.cos((a + 30) * Math.PI / 180) * 110)} ${f2(Math.sin((a + 30) * Math.PI / 180) * 110)} Z" fill="${C.gold}"/>`).join('');
      bk += G(tf(10, 20, t * 20), tre + `<circle r="26" fill="#3f5f8f"/><circle r="16" fill="${C.gold}"/>`);
      bk += `<path d="M-120 220 Q-80 180 -40 220 Q0 260 40 220 Q80 180 120 220" fill="none" stroke="${C.cream}" stroke-width="8"/>`;
      s += G(tf(540, 800, 4, k), bk);
      if (t > tNb) s += chip(540, 1250, 'NOBEL LAUREATE', { size: 44, s: popS(t, tNb), fill: C.gold });
      if (t > tR) s += chip(540, 360, 'RADIATION CHANGES GENES', { size: 44, s: popS(t, tR) });
    }
    return s + vignette(0.25);
  };
  CUEF.how = c => [[c.t0 + 0.1, 'pop'], [c.w('book', 0.55) - 0.3, 'flip', 0.7], [c.w('nobel', 0.65), 'chime', 0.6]];

  // xray: Bushland and the army X-ray machine
  PAINT.xray = (t, c) => {
    const tX = c.w('xray', 0.3), tK = c.w('kerrville', 0.55), tS = c.w('six', 0.7), tD = c.w('dose', 0.95);
    let s = SW.lab(t);
    // machine
    let mc = sh('M-140 0 L140 0 L140 -560 L-140 -560 Z', '#8fa0a8', { depth: 14, w: 6 });
    mc += `<rect x="-100" y="-520" width="200" height="120" rx="10" fill="#2a3a40" stroke="${INK}" stroke-width="5"/>`;
    for (let i = 0; i < 3; i++) mc += `<circle cx="${-60 + i * 60}" cy="-460" r="20" fill="#e8e0c0" stroke="${INK}" stroke-width="4"/><path d="M${-60 + i * 60} -460 l${f2(Math.cos(t * 2 + i) * 14)} ${f2(Math.sin(t * 2 + i) * 14)}" stroke="${C.red}" stroke-width="4"/>`;
    mc += D.inkTaper([[140, -420], [330, -420]], 40, 40, '#8fa0a8', INK, 5) + sh('M290 -420 L370 -420 L350 -320 L310 -320 Z', '#5a6a72', { depth: 5 });
    s += G(tf(330, 1400), mc);
    // pupae tray under the head
    const zapK = t > tX ? Math.max(0, Math.sin(((t - tX) % 0.9) / 0.9 * Math.PI)) * (t < tD + 0.6 ? 1 : 0) : 0;
    const grey = clamp((t - tX) / Math.max(1, tD - tX));
    s += sh('M520 1180 L800 1180 L790 1220 L530 1220 Z', '#c0c4c8', { depth: 4 });
    for (let i = 0; i < 12; i++) s += SW.ellD ? `<ellipse cx="${560 + (i % 6) * 40}" cy="${1168 - Math.floor(i / 6) * 18}" rx="18" ry="10" fill="${D.mix('#8a5a2a', '#a8aeb4', grey)}" stroke="${INK}" stroke-width="3"/>` : '';
    if (zapK > 0.02) s += `<path d="M660 1000 L640 1080 L680 1080 L650 1170" fill="none" stroke="#fff6a0" stroke-width="${f2(10 * zapK)}" stroke-linejoin="round"/><rect width="${W}" height="${H}" fill="#fff8d0" opacity="${f2(zapK * 0.25)}"/>`;
    s += SW.adult(860, 1700, { t, s: 1.0, coat: 'lab', hair: '#7a5232', tag: 'BUSHLAND', skin: '#f0c49c', mood: t > tD ? 'proud' : 'skeptical', lookX: -0.8, lookY: 0.4, bl: blink(t, 2), armL: { sh: 60, el: 30 } }).svg;
    s += sepia(0.22);
    if (t > tK) s += chip(540, 280, 'KERRVILLE, TEXAS', { size: 50, s: popS(t, tK), fill: C.paper });
    if (t > tS) {
      const mo = Math.min(6, 1 + Math.floor((t - tS) / 0.22));
      s += counterBadge(270, 600, `${mo} MONTH${mo > 1 ? 'S' : ''}`, 'of tests', { s: popS(t, tS), size: 64 });
    }
    if (t > tD) s += chip(540, 1330, 'STERILIZING DOSE FOUND', { size: 44, s: popS(t, tD), fill: C.green, color: '#fff' });
    return s;
  };
  CUEF.xray = c => { const a = c.w('xray', 0.3), d = c.w('dose', 0.95), out = [[c.w('kerrville', 0.55), 'pop']]; for (let x = a; x < d + 0.5; x += 0.9) out.push([x, 'zap', 0.7]); out.push([c.w('six', 0.7), 'flip', 0.6], [d, 'chime']); return out; };

  // paper cards: the publication trail
  const PAPERS = {
    1951: { a: 'Bushland & Hopkins', ti: ['Experiments with Screw-Worm', 'Flies Sterilized by X-Rays'] },
    k55: { a: 'Knipling', ti: ['Possibilities of Insect Control', 'or Eradication Through the Use', 'of Sexually Sterile Males'] },
    b55: { a: 'Baumhover, Graham, Bitter, Hopkins', ti: ['Screw-Worm Control Through', 'Release of Sterilized Flies'] },
  };
  function paperCard(x, y, key, year, s = 1, rot = 0) {
    if (s <= 0.01) return '';
    const p = PAPERS[key];
    let out = `<rect x="-300" y="-200" width="600" height="400" rx="14" fill="${INK}" opacity="0.25" transform="translate(10 12)"/>`;
    out += `<rect x="-300" y="-200" width="600" height="400" rx="14" fill="${C.paper}" stroke="${INK}" stroke-width="6"/>`;
    out += `<rect x="-300" y="-200" width="600" height="70" rx="14" fill="#8a4a3a"/><rect x="-300" y="-150" width="600" height="20" fill="#8a4a3a"/>`;
    out += txt(-270, -152, 'J. ECON. ENTOMOL.', 30, C.cream, { anchor: 'start' }) + txt(270, -152, `${year}`, 40, C.gold, { anchor: 'end' });
    p.ti.forEach((ln, i) => { out += txt(0, -60 + i * 50, ln, 36, INK); });
    out += txt(0, 150, p.a, 30, '#6b5646', { weight: 600 });
    for (let i = 0; i < 3; i++) out += `<path d="M-240 ${96 + i * 0} L240 ${96}" stroke="#d8c6a0" stroke-width="3"/>`;
    return G(tf(x, y, rot, s), out);
  }
  PAINT.paper = (t, c) => {
    let s = plain('#c89a68', '#a87a50');
    for (let i = 0; i < 14; i++) s += `<path d="M0 ${200 + i * 130} Q540 ${170 + i * 130} 1080 ${210 + i * 130}" stroke="#9a6e46" stroke-width="5" fill="none" opacity="0.5"/>`;
    const slide = (t0, x, y, key, yr, rot) => { const k = ease.outBack(clamp((t - t0) / 0.5), 1.1); return k > 0 ? paperCard(lerp(x + 900, x, k), y, key, yr, 1, rot) : ''; };
    if (c.opt.which === 51) s += slide(c.t0 + 0.05, 540, 800, 1951, 1951, -3);
    else {
      s += paperCard(540, 560, 1951, 1951, 0.7, -6);
      s += slide(c.t0 + 0.1, 540, 850, 'b55', 1955, 3);
      s += slide(c.w('theory', 0.5), 560, 1140, 'k55', 1955, -2);
    }
    return s + vignette(0.3);
  };
  CUEF.paper = c => (c.opt.which === 51 ? [[c.t0 + 0.05, 'flip', 0.7]] : [[c.t0 + 0.1, 'flip', 0.7], [c.w('theory', 0.5), 'flip', 0.7]]);

  // islands: Sanibel (too close), Curaçao (far out), egg masses going sterile
  PAINT.islands = (t, c) => {
    const ph = c.opt.phase;
    let s = SW.sea(t);
    let wld = '';
    const planePass = (t0, period, y, dir = 1) => {
      const p = ((t - t0) % period) / period;
      if (t < t0) return '';
      const x = dir > 0 ? lerp(-300, 1380, p) : lerp(1380, -300, p);
      let out = SW.plane(x, y + Math.sin(p * 6) * 10, { t, s: 0.55 * dir, rot: dir > 0 ? -2 : 2 });
      for (let i = 0; i < 4; i++) {
        const dp = p - 0.25 - i * 0.12;
        if (dp <= 0 || dp > 0.3) continue;
        const bx = dir > 0 ? lerp(-300, 1380, p - dp) : lerp(1380, -300, p - dp), by = y + 50 + dp * 1400;
        out += SW.dropBox(bx, by, { rot: dp * 400, open: clamp((dp - 0.12) / 0.06), s: 0.8 });
        if (dp > 0.15) out += swarm(t, 6, { x0: bx - 70, x1: bx + 70, y0: by - 40, y1: by + 60, seed: i * 13 + Math.floor((t - t0) / period) * 7, col: C.sterile, s: 0.7 });
      }
      return out;
    };
    if (ph === 'sanibel') {
      const tBk = c.w('backed', 0.5), tCo = c.w('coast', 0.6), tPr = c.w('proof', 0.9);
      wld += sh('M760 0 C720 400 820 700 780 1100 C760 1400 840 1700 800 1920 L1080 1920 L1080 0 Z', C.land, { depth: 14, w: 6 }) + txt(930, 560, 'FLORIDA', 44, C.ink, { stroke: C.cream, sw: 8 });
      wld += island(560, 980, 130, 50, 4, { label: 'SANIBEL', size: 44 });
      wld += planePass(c.t0 + 0.2, 3.4, 640, 1);
      if (t > tBk) wld += chip(560, 1180, 'IT WORKED', { size: 44, s: popS(t, tBk), fill: C.green, color: '#fff' });
      if (t > tCo - 0.4) {
        for (let i = 0; i < 9; i++) {
          const p = ((t - tCo) * 0.45 + i / 9) % 1;
          if (t < tCo - 0.4 + i * 0.1) continue;
          wld += SW.fleck(lerp(860, 600, p) + Math.sin(p * 9 + i) * 20, 880 + i * 26 + Math.sin(p * 7) * 30, 1.6, t);
        }
        wld += `<path d="M840 830 Q740 780 660 870" fill="none" stroke="${C.red}" stroke-width="10" stroke-dasharray="20 14" stroke-linecap="round" opacity="${f2(fadeIn(t, tCo - 0.4))}"/>`;
      }
      if (t > tPr) wld += stamp(540, 380, 'TOO CLOSE', t, tPr, { color: C.redDk, size: 80, sub: 'WILD FLIES CAN DRIFT IN' });
    } else if (ph === 'curacao') {
      const t54 = c.w('1954', 0.3), tC = c.w('curaao', 0.4), tWk = c.w('week', 0.6);
      wld += island(540, 980, 230, 90, 9, { label: 'CURAÇAO', size: 56 });
      wld += chip(540, 280, '1954', { size: 64, s: popS(t, t54), fill: C.paper });
      if (t > tC) wld += chip(540, 1240, 'OPEN CARIBBEAN SEA', { size: 38, s: popS(t, tC + 0.3) });
      wld += planePass(tWk - 0.6, 2.2, 600, 1);
      if (t > tWk) wld += counterBadge(820, 440, `WEEK ${Math.min(9, 1 + Math.floor((t - tWk) / 0.55))}`, 'sterile drops', { s: popS(t, tWk), size: 52, fill: C.cream });
    } else {
      // seventy: egg masses on the island going sterile
      const t3 = c.w('three', 0.3), t70 = c.w('seventy', 0.5), tMo = c.w('months', 0.75), tG = c.w('gone', 0.9);
      wld += island(540, 900, 380, 170, 9, { label: '', size: 0 });
      const nSt = t < t70 ? 0 : t < tMo ? 7 : 10;
      for (let i = 0; i < 10; i++) {
        const ex = 330 + (i % 5) * 105, ey = 860 + Math.floor(i / 5) * 90;
        const st = i < nSt;
        wld += SW.eggMass(ex, ey, 14, { s: 0.9, sterile: st });
        if (st) wld += cross(ex + 30, ey - 50, 0.55 * popS(t, i < 7 ? t70 + i * 0.08 : tMo + (i - 7) * 0.1));
      }
      if (t > t3) wld += chip(540, 280, 'AFTER 3 WEEKS', { size: 50, s: popS(t, t3), fill: C.paper });
      if (t > t70) wld += counterBadge(540, 1240, '≈70%', 'of egg masses sterile', { s: popS(t, t70), size: 100 });
      if (t > tG) wld += stamp(540, 520, 'FERTILE EGGS: GONE', t, tG, { color: '#2f8f4a', size: 66, sub: 'WITHIN ABOUT 2 MONTHS' });
    }
    return s + wld;
  };
  function island(x, y, w, h, seed, o) { return SW.island(x, y, w, h, seed, o); }
  CUEF.islands = c => {
    const ph = c.opt.phase;
    if (ph === 'sanibel') return [[c.t0 + 0.2, 'plane', 0.7], [c.w('backed', 0.5) + 0.45, 'chime', 0.5], [c.w('coast', 0.6) - 0.4, 'buzz', 0.6], [c.w('proof', 0.9), 'stamp']];
    if (ph === 'curacao') return [[c.w('1954', 0.3), 'pop'], [c.w('week', 0.6) - 0.6, 'plane', 0.8]];
    return [[c.w('three', 0.3), 'pop'], [c.w('seventy', 0.5), 'chime', 0.7], [c.w('months', 0.75), 'pop_small'], [c.w('gone', 0.9), 'stamp']];
  };

  // keys: Key deer in the Florida Keys, 2016 -> beaten 2017
  PAINT.keys = (t, c) => {
    const tK = c.w('keys', 0.35), tDe = c.w('deer', 0.65), tM = c.w('march', 0.92);
    let s = SW.sea(t);
    s += SW.island(540, 1300, 520, 160, 21, { label: '' });
    s += `<ellipse cx="540" cy="1290" rx="420" ry="90" fill="#cfe7a0" opacity="0.6"/>`;
    for (const mx of [180, 300, 820, 930]) s += G(tf(mx, 1240), D.inkTaper([[0, 0], [0, -120]], 16, 8, '#6b4a30', INK, 3) + sh(ellD(70, 44, 0, -140), '#4f8f3f', { depth: 7, w: 4 }));
    const deer = SW.cow(470, 1300, { t, s: 0.75, kind: 'deer', antlers: true, mood: t > tM ? 'happy' : 'sad', bl: blink(t, 6), lookX: 0.5 });
    s += deer.svg;
    if (t < tM) for (let i = 0; i < 4; i++) { const a = t * 2.4 + i * 1.6; s += SW.fly(deer.navel[0] + Math.cos(a) * 120, deer.navel[1] - 160 + Math.sin(a) * 50, { t: t + i, s: 0.22, flip: Math.cos(a) > 0 ? -1 : 1 }); }
    s += chip(540, 290, 'FLORIDA KEYS · 2016', { size: 50, s: popS(t, tK - 0.3), fill: C.paper });
    if (t > tDe) s += chip(540, 1500, 'ENDANGERED KEY DEER', { size: 40, s: popS(t, tDe), fill: C.gold });
    if (t > tM) s += stamp(540, 620, 'BEATEN', t, tM, { color: '#2f8f4a', size: 96, sub: 'MARCH 2017' });
    return s;
  };
  CUEF.keys = c => [[c.w('keys', 0.35) - 0.3, 'pop'], [c.w('deer', 0.65), 'pop_small'], [c.w('march', 0.92), 'stamp']];

  // again: planes dropping sterile flies over Texas brush
  PAINT.again = (t, c) => {
    let s = SW.ranch(t, { cx: 540, cy: 1000, z: 1, warm: 0.3 });
    let wld = '';
    const passes = [[c.t0 + 0.1, 520, 1], [c.t0 + 1.4, 380, -1]];
    for (const [t0, y, dir] of passes) {
      const p = clamp((t - t0) / 3.2);
      if (p <= 0 || p >= 1) continue;
      const x = dir > 0 ? lerp(-300, 1400, p) : lerp(1400, -300, p);
      wld += SW.plane(x, y, { t, s: 0.6 * dir, rot: 0, col: dir > 0 ? '#f2c23a' : '#e8eef2' });
      for (let i = 0; i < 5; i++) {
        const dp = p - 0.08 - i * 0.1;
        if (dp <= 0) continue;
        const bx = dir > 0 ? lerp(-300, 1400, p - dp) : lerp(1400, -300, p - dp), by = y + 60 + dp * 1500;
        if (by < 1100) wld += SW.dropBox(bx, by, { rot: dp * 300, open: clamp((dp - 0.1) / 0.05), s: 0.8 });
        if (dp > 0.12) wld += swarm(t, 8, { x0: bx - 100, x1: bx + 100, y0: Math.min(by, 1050) - 80, y1: Math.min(by, 1050) + 80, seed: i * 11 + (dir > 0 ? 0 : 50), col: C.sterile, s: 0.8 });
      }
    }
    s += wld;
    const tS = c.w('sterile', 0.4);
    s += chip(540, 300, c.opt.hook ? 'STERILIZED · DROPPED FROM PLANES' : 'STERILE FLIES', { size: c.opt.hook ? 40 : 56, s: popS(t, tS - 0.1), fill: C.cream });
    if (c.opt.hook) s += chip(540, 1240, '☢ RADIATION', { size: 46, s: popS(t, c.w('radiation', 0.4)), fill: C.gold });
    return s + vignette(0.2);
  };
  CUEF.again = c => [[c.t0 + 0.1, 'plane', 0.9], [c.t0 + 1.4, 'plane', 0.7], [c.w('sterile', 0.4) - 0.1, 'pop']];

  // plant: the new fly factory in Edinburg, Texas
  PAINT.plant = (t, c) => {
    const tF = c.w('factory', 0.3), t1 = c.w('hundred', 0.6), t3 = c.w('three', 0.85), t28 = c.w('2028', 0.95);
    const zk = 1 + 0.035 * (t - c.t0); // slow push so the finished building never sits still
    let s = SW.ranch(t, { cx: 540, cy: 1000, z: zk, warm: 0.2 });
    const built = ease.outCubic(clamp((t - c.t0 - 0.2) / 1.6));
    let fac = SW.factory(540, 1260, { built, sign: 'STERILE FLY FACILITY', sub: 'MOORE AIR BASE · EDINBURG, TX', t });
    if (built > 0.9) for (let i = 0; i < 3; i++) { const p = ((t - c.t0) * 0.5 + i / 3) % 1; fac += SW.dropBox(540 + (i - 1) * 140 + p * 20, 1200 - p * 40, { s: 0.6, rot: 0 }); }
    if (built > 0.9) fac += swarm(t, 10, { x0: 260, x1: 820, y0: 760, y1: 940, seed: 77, col: C.sterile, s: 1.1 });
    s += `<g transform="${camT(540, 1000, zk)}">${fac}</g>`;
    if (c.opt.hook) {
      s += counterBadge(540, 420, 'HUNDREDS OF MILLIONS', 'more sterile flies', { s: popS(t, c.w('hundreds', 0.8)), size: 64 });
    } else {
      if (t > t1 && t < t3) s += counterBadge(540, 430, '100 MILLION', 'flies at first', { s: popS(t, t1), size: 88 });
      if (t > t3) s += counterBadge(540, 430, '300 MILLION', 'by the end of 2028', { s: popS(t, t3), size: 96, fill: C.gold });
      s += chip(540, 1440, 'EXPECTED TO START BY END OF 2026', { size: 34, s: popS(t, c.w('year', 0.5)), fill: C.cream });
    }
    return s + vignette(0.2);
  };
  CUEF.plant = c => (c.opt.hook ? [[c.t0 + 0.2, 'grow_big', 0.8], [c.w('hundreds', 0.8), 'chime']] : [[c.t0 + 0.2, 'grow_big', 0.8], [c.w('hundred', 0.6), 'pop'], [c.w('three', 0.85), 'chime']]);

  // advice: check animals, report, beef is safe
  PAINT.advice = (t, c) => {
    const tC = c.w('check', 0.4), tR = c.w('report', 0.6), tB = c.w('beef', 0.9);
    let s = SW.ranch(t, { cx: 540, cy: 1000, z: 1, warm: 0.5 });
    s += SW.dog(330, 1500, { t, s: 1.1, mood: 'happy', bl: blink(t, 1), lookX: -0.4 });
    s += SW.adult(170, 1560, { t, s: 0.95, coat: 'ranch', hat: true, mood: 'happy', lookX: 0.8, lookY: 0.6, bl: blink(t, 2), armR: { sh: 60, el: 30 }, shirt: '#d97a5a' }).svg;
    const items = [[tC, 'CHECK WOUNDS'], [tR, 'REPORT MAGGOTS'], [tB, 'BEEF IS SAFE']];
    s += `<rect x="560" y="330" width="460" height="${f2(110 + 120 * items.filter(i => t > i[0] - 0.1).length)}" rx="30" fill="${C.cream}" stroke="${INK}" stroke-width="7" opacity="${f2(fadeIn(t, tC - 0.3))}"/>`;
    items.forEach(([t0, label], i) => { if (t > t0 - 0.1) { const k = popS(t, t0 - 0.1); s += check(620, 430 + i * 120, k) + G(tf(670, 446 + i * 120, 0, k), txt(0, 0, label, 38, INK, { anchor: 'start' })); } });
    s += chip(790, 1180, 'VET · STATE · USDA', { size: 38, s: popS(t, tR + 0.4), fill: C.gold });
    return s + vignette(0.2);
  };
  CUEF.advice = c => [[c.w('check', 0.4) - 0.1, 'pop'], [c.w('report', 0.6) - 0.1, 'pop'], [c.w('beef', 0.9) - 0.1, 'chime', 0.7]];

  // end: the fly, the title card, sources (full) or the CTA (hook)
  PAINT.end = (t, c) => {
    let s = `<rect width="${W}" height="${H}" fill="${D.radial([[0, '#2f6f78'], [1, '#0f2a33']], { cx: 0.5, cy: 0.4, r: 0.8 })}"/>`;
    if (c.opt.hook) {
      const k = popS(t, c.t0 + 0.1);
      s += SW.fly(540, 1180 + Math.sin(t * 2) * 12, { t, s: 1.4, mood: 'smug', bl: blink(t, 4), lookX: -0.2, lookY: -0.6 });
      s += G(tf(540, 640, -2, k), `<rect x="-440" y="-250" width="880" height="500" rx="40" fill="${C.cream}" stroke="${INK}" stroke-width="9"/>` +
        txt(0, -140, 'FULL STORY', 96, C.red, { stroke: INK, sw: 8 }) + txt(0, -40, 'How two scientists', 54, INK) + txt(0, 30, 'beat it with an', 54, INK) + txt(0, 100, 'X-ray machine', 54, INK) + txt(0, 196, 'Sources: USDA APHIS · USDA ARS · DTN', 28, '#6b5646', { weight: 600 }));
      return s;
    }
    const tS = c.w('strange', 0.6), tO = c.w('once', 0.6, 1), tA = c.w('again', 0.9);
    s += SW.fly(540, 760 + Math.sin(t * 2) * 12, { t, s: 2.0, mood: t > tA ? 'annoyed' : 'smug', bl: blink(t, 4), lookX: -0.2, lookY: 0.4 });
    if (t > tS) s += chip(540, 330, 'SHE MATES ONCE', { size: 60, s: popS(t, tS), fill: C.gold });
    if (t > tA - 0.2) {
      const k = popS(t, tA - 0.2, 2.4, 0.55);
      s += G(tf(540, 1250, -2, k), `<rect x="-440" y="-170" width="880" height="340" rx="40" fill="${C.cream}" stroke="${INK}" stroke-width="9"/>` +
        txt(0, -50, 'THE FLY THAT', 80, INK) + txt(0, 50, 'CAME BACK', 104, C.red, { stroke: INK, sw: 8 }) + txt(0, 130, 'Sources: USDA APHIS · USDA ARS · NAL · DTN · Wikipedia', 26, '#6b5646', { weight: 600 }));
    }
    return s;
  };
  // the closing chime waits for the last word so it never masks the call to action
  CUEF.end = c => (c.opt.hook ? [[lastLine.end + 0.05, 'chime']] : [[c.w('strange', 0.6), 'pop_small', 0.6], [lastLine.end + 0.05, 'chime']]);

  // ---------- sequence ----------
  const SHOTS = window.SHOTS.map((sp, i) => ({ ...sp, i }));
  SHOTS.forEach((sp, i) => {
    const ln = L[sp.line];
    let t0 = sp.word ? findWord([sp.line], sp.word) - 0.12 : ln.start - 0.22;
    sp.t0 = i === 0 ? 0 : t0;
  });
  SHOTS.forEach((sp, i) => { sp.t1 = i < SHOTS.length - 1 ? SHOTS[i + 1].t0 : END; });
  SHOTS.forEach(sp => {
    sp.lines = LINES.filter(l => l.start >= sp.t0 - 0.3 && l.start < sp.t1).map(l => l.id);
    if (!sp.lines.includes(sp.line)) sp.lines.unshift(sp.line);
    sp.opt = sp.opt || {};
    sp.w = (word, frac = 0.5, nth = 0) => { const r = findWord(sp.lines, word, nth); return r !== null ? r : lerp(sp.t0, sp.t1, frac); };
  });
  const shotAt = t => { let k = 0; for (let i = 0; i < SHOTS.length; i++) if (t >= SHOTS[i].t0) k = i; return SHOTS[k]; };
  // every shot drifts: a slow push plus a gentle sway, so map and card holds never sit still
  const paint = (sp, t) => {
    const d = Math.max(0, t - sp.t0), k = 1 + 0.011 * d + 0.006 * Math.sin(d * 0.9);
    const px = 540 + 10 * Math.sin(d * 0.55 + sp.i), py = 900 + 8 * Math.cos(d * 0.45 + sp.i);
    return `<g transform="translate(${f2(px)} ${f2(py)}) scale(${(k).toFixed(4)}) translate(-540 -900)">${PAINT[sp.shot](t, sp)}</g>`;
  };

  // ---------- captions (phrase chunks keyed to word times) ----------
  const LEAD = 2 / FPS;
  const KEY = new Set(['screwworm', 'maggots', 'sterile', 'billions', 'once', 'radiation', 'x-ray', '1966', '2026', 'texas', 'flies']);
  const CHUNKS = (() => {
    const out = [];
    for (const l of LINES) {
      const ws = l.words, n = ws.length;
      const until = i => (i < n ? ws[i].start : l.end + 0.3);
      const FN = /^(the|a|an|in|of|to|into|on|and|is|their|its|for|from|that|do|has|it|but|they|at|by|with|was|her|his)$/i;
      const bare = w => w.replace(/[^a-z0-9'éç-]/gi, '');
      const cost = (i, j) => {
        const k = j - i, d = until(j) - ws[i].start;
        const chars = ws.slice(i, j).map(w => bare(w.text)).join(' ').length;
        let c = Math.max(0, 0.7 - d) * 2 + Math.max(0, 0.3 * k - d);
        if (chars > 18) c += 5; else if (chars > 16) c += 0.4;
        if (FN.test(bare(ws[j - 1].text)) && j < n && !/[,.?!:]$/.test(ws[j - 1].text)) c += 0.3;
        if (ws.slice(i, j - 1).some(w => /[,]$/.test(w.text))) c += 0.35;
        if (ws.slice(i, j - 1).some(w => /[.?!:]$/.test(w.text))) c += 99;
        return c + 0.05;
      };
      const best = new Array(n + 1).fill(null);
      best[n] = { c: 0, cuts: [] };
      for (let i = n - 1; i >= 0; i--) for (let j = i + 1; j <= Math.min(n, i + 4); j++) {
        const cand = { c: best[j].c + cost(i, j), cuts: [j, ...best[j].cuts] };
        if (!best[i] || cand.c < best[i].c) best[i] = cand;
      }
      let i0 = 0;
      for (const j of best[0].cuts) { out.push({ words: ws.slice(i0, j).map(w => w.text), start: ws[i0].start, end: until(j) }); i0 = j; }
    }
    out[0].start = 0;
    return out;
  })();
  function captions(t) {
    const c = CHUNKS.find(c => t >= c.start - LEAD && t < c.end - LEAD);
    if (!c) return '';
    const words = c.words.map(w => w.replace(/[.,?!:]$/g, '').replace(/[.,?!]/g, ''));
    const text = words.join(' ').toUpperCase();
    const isKey = words.some(w => KEY.has(w.toLowerCase()));
    let size = isKey ? 112 : 96;
    const est = textWidth(text, size);
    if (est > 760) size *= 760 / est;
    const q = c.start === 0 && t < 0.4 ? 1 : 0.9 + 0.1 * spring(t - c.start + LEAD, { freq: 4, damping: 0.5 });
    const y = 1530 - (1 - Math.min(1, q)) * 14;
    const pw = Math.min(860, Math.min(est, 760) + 70), ph = size * 1.22;
    const fill = isKey ? '#ffe45c' : C.white;
    return G(`translate(540 ${f2(y)}) scale(${f2(q)})`,
      `<rect x="${f2(-pw / 2)}" y="${f2(-size * 0.92)}" width="${f2(pw)}" height="${f2(ph)}" rx="${f2(ph / 2)}" fill="#24160c" fill-opacity="0.86"/>` +
      `<text x="0" y="0" font-size="${f2(size)}" font-weight="700" text-anchor="middle" fill="${fill}" stroke="${INK}" stroke-width="14" stroke-linejoin="round" paint-order="stroke">${text}</text>`);
  }

  // ---------- frame ----------
  const WIPE = 0.32;
  function frame(f) {
    D.begin(f);
    const t = f / FPS;
    const sp = shotAt(t);
    let svg = paint(sp, t);
    // wipe from the previous shot: a slanted edge sweeps right-to-left over the old frame
    const prev = SHOTS[sp.i - 1];
    if (prev && t < sp.t0 + WIPE && sp.tr !== 'cut') {
      const k = ease.inOutCubic((t - sp.t0) / WIPE);
      const x = lerp(W + 300, -300, k);
      const id = `wipe${f}`;
      svg += `<clipPath id="${id}"><path d="M0 0 L${f2(x + 200)} 0 L${f2(x - 200)} ${H} L0 ${H} Z"/></clipPath>`;
      svg += `<g clip-path="url(#${id})">${paint(prev, t)}</g>`;
      svg += `<path d="M${f2(x + 200)} 0 L${f2(x - 200)} ${H}" stroke="${C.gold}" stroke-width="34"/><path d="M${f2(x + 200)} 0 L${f2(x - 200)} ${H}" stroke="${INK}" stroke-width="8" transform="translate(22 0)"/>`;
    }
    svg += titleSting(t);
    svg += captions(t);
    return svg + D.defs();
  }

  // ---------- sound cues ----------
  const cue = (t, type, gain = 1) => ({ t: +Math.max(0, t).toFixed(3), type, gain });
  const cues = [];
  SHOTS.forEach((sp, i) => {
    if (i > 0 && sp.tr !== 'cut') cues.push(cue(sp.t0, 'whoosh', 0.8));
    for (const [tt, type, g] of (CUEF[sp.shot] ? CUEF[sp.shot](sp) : [])) if (tt !== null && tt >= sp.t0 - 0.3 && tt < sp.t1 + 0.5) cues.push(cue(tt, type, g ?? 1));
  });
  if (CUT === 'full') cues.push(cue(L.weapon.end + 0.05, 'chime'));
  window.CUES = cues.sort((a, b) => a.t - b.t);

  const stage = document.getElementById('stage');
  window.renderFrame = f => { stage.innerHTML = frame(f); };
  window.FILM = { width: W, height: H, fps: FPS, frames: Math.round(END * FPS), safe: SAFE, ready: false };
  window.SHOT_TIMES = SHOTS.map(s => ({ shot: s.shot, line: s.line, t0: +s.t0.toFixed(2), t1: +s.t1.toFixed(2) }));
  document.fonts.load('700 40px Fredoka').then(() => { window.FILM.ready = true; });
})();
