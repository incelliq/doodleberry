// Reusable character rigs drawn with D (draw.js): an expressive face, a kid, an
// earthworm. Every pose is a plain object of numbers, so scenes animate them as
// functions of time. Loaded after timeline.js and draw.js; exposes `Cast`.
(function (root) {
  const { clamp, lerp, noise } = root.M;
  const D = root.D;
  const f2 = n => (+n).toFixed(2);
  const INK = '#2a1a10';
  const G = (tr, inner, extra = '') => `<g transform="${tr}" ${extra}>${inner}</g>`;
  const tf = (x = 0, y = 0, r = 0, sx = 1, sy = sx) => `translate(${f2(x)} ${f2(y)}) rotate(${f2(r)}) scale(${f2(sx)} ${f2(sy)})`;
  const ellD = (rx, ry) => `M${-rx} 0 A${rx} ${ry} 0 1 0 ${rx} 0 A${rx} ${ry} 0 1 0 ${-rx} 0 Z`;

  // Attitude presets: eyelids and brows do the acting
  const MOODS = {
    happy: { lidUp: 0, tilt: 0, brow: -2, browTilt: 0, mouth: 'smile' },
    excited: { lidUp: 0, tilt: 0, brow: -7, browTilt: 0, mouth: 'grin' },
    smug: { lidUp: 0.42, tilt: 0, lidLow: 0.18, brow: -1, browTilt: -2, mouth: 'smirk' },
    hungry: { lidUp: 0.38, tilt: 9, brow: 1, browTilt: 7, mouth: 'frown' },
    sad: { lidUp: 0.3, tilt: 12, brow: 0, browTilt: 9, mouth: 'frown' },
    skeptical: { lidUp: 0.28, tilt: -4, brow: -2, browTilt: -5, mouth: 'flat', asym: true },
    annoyed: { lidUp: 0.34, tilt: -8, brow: 2, browTilt: -8, mouth: 'flat' },
    surprised: { lidUp: 0, tilt: 0, brow: -10, browTilt: 0, mouth: 'o' },
    envious: { lidUp: 0.22, tilt: 6, brow: -6, browTilt: 6, mouth: 'o' },
    proud: { lidUp: 0.3, tilt: 0, brow: -4, browTilt: -2, mouth: 'grin' },
    sleep: { lidUp: 1, tilt: 0, brow: 0, browTilt: 0, mouth: 'smile' },
  };

  // Face centred on the eye line. talk = 0..1 mouth openness from the lip-sync track.
  function face(o) {
    const { x = 0, y = 0, s = 1, mood = 'happy', talk = 0, lookX = 0, lookY = 0, bl = 0, sep = 22, lid = '#f3c6a0',
      rx = 15, ry = 18, mouthY = 34, cheeks = true, wink = false } = o;
    const m = MOODS[mood] || MOODS.happy;
    let out = '';
    for (const side of [-1, 1]) {
      const ex = side * sep;
      if (m.lidUp >= 0.99 || (wink && side > 0)) {
        out += D.inkTaper(D.bez([ex - 12, 2], [ex - 5, 10], [ex + 5, 10], [ex + 12, 2], 8), 5, 3, INK, INK, 0);
        continue;
      }
      const up = m.asym && side < 0 ? m.lidUp * 0.3 : m.lidUp;
      out += D.eye(ex, 0, { rx, ry, lookX, lookY, bl, lid, lidUp: up, lidTilt: -side * m.tilt, lidLow: m.lidLow || 0 });
      const by = -ry - 9 + m.brow + (m.asym && side < 0 ? -5 : 0), bt = side * m.browTilt;
      out += D.taper(D.bez([ex - 13, by + bt], [ex - 5, by - 5 + bt * 0.3], [ex + 5, by - 5 - bt * 0.3], [ex + 13, by - bt], 6), 5.5, 2.5, INK);
    }
    // mouth: shape from the mood, opened by speech
    const my = mouthY, open = clamp(talk);
    if (open > 0.06 || m.mouth === 'o') {
      const ow = m.mouth === 'o' ? 9 + open * 6 : 14 + open * 4, oh = (m.mouth === 'o' ? 10 : 3) + open * 20;
      const md = `M${-ow} ${my} Q0 ${my - 5} ${ow} ${my} Q${ow * 0.75} ${f2(my + oh)} 0 ${f2(my + oh)} Q${-ow * 0.75} ${f2(my + oh)} ${-ow} ${my} Z`;
      out += `<path d="${md}" fill="${D.linear([[0, '#5e1a18'], [1, '#9c3530']])}" stroke="${INK}" stroke-width="4.5" stroke-linejoin="round"/>`;
      if (oh > 12) out += `<ellipse cx="2" cy="${f2(my + oh * 0.72)}" rx="${f2(ow * 0.5)}" ry="${f2(oh * 0.22)}" fill="#ff8a8a"/>`;
      if (oh > 9) out += `<path d="M${-ow * 0.6} ${my + 1} L${ow * 0.6} ${my + 1} L${ow * 0.5} ${my + 5} L${-ow * 0.5} ${my + 5} Z" fill="#fff"/>`;
    } else {
      const shapes = {
        smile: [[-15, my - 3], [-6, my + 9], [6, my + 9], [15, my - 3]],
        grin: [[-18, my - 4], [-7, my + 12], [7, my + 12], [18, my - 4]],
        smirk: [[-12, my + 2], [-4, my + 5], [6, my + 3], [15, my - 5]],
        frown: [[-13, my + 6], [-5, my - 4], [5, my - 4], [13, my + 6]],
        flat: [[-11, my + 1], [-4, my + 2], [4, my + 2], [11, my + 1]],
      };
      out += D.taper(D.bez(...shapes[m.mouth] || shapes.smile, 10), 3, 5.5, INK);
    }
    if (cheeks && mood !== 'sad' && mood !== 'hungry') {
      const blush = D.radial([[0, '#ff7f7a', 0.7], [1, '#ff7f7a', 0]], { cx: 0.5, cy: 0.5, r: 0.5 });
      out += `<ellipse cx="${-sep - 15}" cy="22" rx="13" ry="8" fill="${blush}"/><ellipse cx="${sep + 15}" cy="22" rx="13" ry="8" fill="${blush}"/>`;
    }
    return G(tf(x, y, 0, s), out);
  }

  // ---------- Kid farmer ----------
  // Origin at the feet; about 600 units tall at s=1.
  // o: t, s, talk, mood, look, bl, armL/armR {sh, el} (degrees; 0 = hanging), lean, bob, crouch (0..1),
  //    hand: {l, r} props ('pouch' | 'seed' | null), flip
  const KID = { skin: '#f3c6a0', hair: '#5a3622', shirt: '#ff8a6e', denim: '#4a78c2', boot: '#ffcc33', band: '#ffd84a' };
  function arm(side, sh, el, c, holding, t) {
    // sh: shoulder swing from hanging (0) outward/up (90 = horizontal); el: extra bend at the elbow
    const ux = side * 84, uy = -362;
    const a1 = (sh * Math.PI) / 180, a2 = ((sh + el) * Math.PI) / 180;
    const ex = ux + side * Math.sin(a1) * 92, ey = uy + Math.cos(a1) * 92;
    const hx = ex + side * Math.sin(a2) * 88, hy = ey + Math.cos(a2) * 88;
    let s = '';
    const up = D.bez([ux, uy], [lerp(ux, ex, 0.33), lerp(uy, ey, 0.33)], [lerp(ux, ex, 0.66), lerp(uy, ey, 0.66)], [ex, ey], 6);
    const lo = D.bez([ex, ey], [lerp(ex, hx, 0.33), lerp(ey, hy, 0.33)], [lerp(ex, hx, 0.66), lerp(ey, hy, 0.66)], [hx, hy], 6);
    s += D.inkTaper(lo, 32, 27, c.skin, INK, 5);
    s += D.inkTaper(up, 46, 36, c.shirt, INK, 5);
    s += D.taper(up.map(([px, py]) => [px - side * 5, py]), 8, 4, D.lightOf(c.shirt), 'opacity="0.7"');
    s += D.sphere(hx, hy, 25, c.skin, { w: 5, spec: false });
    if (holding === 'pouch') {
      s += G(tf(hx + side * 6, hy + 30, side * 8), D.shade('M-26 -16 Q0 -30 26 -16 L22 26 Q0 36 -22 26 Z', '#c8955a', { depth: 7, light: 3, w: 4.5, ink: INK }) +
        `<path d="M-20 -14 Q0 -4 20 -14" fill="none" stroke="${INK}" stroke-width="3"/>`);
    }
    return { svg: s, hand: [hx, hy] };
  }
  function kid(x, y, o = {}) {
    const { t = 0, s = 1, talk = 0, mood = 'happy', lookX = 0, lookY = 0, bl = 0, lean = 0, crouch = 0, flip = 1 } = o;
    const c = { ...KID, ...(o.colors || {}) };
    const armL = o.armL || { sh: 8, el: 6 }, armR = o.armR || { sh: 8, el: 6 };
    const bob = Math.sin(t * 2.2) * 2 + talk * 4 * Math.sin(t * 18);
    const cr = crouch * 70;
    let out = '';
    // boots and legs
    for (const side of [-1, 1]) {
      const bx = side * 34;
      out += G(tf(bx, 0), D.shade(`M-28 0 L-26 -62 L26 -62 L28 0 Q30 8 22 8 L-24 8 Q-32 8 -28 0 Z`, c.boot, { depth: 9, light: 3, w: 5, ink: INK }) +
        `<rect x="-30" y="-2" width="60" height="10" rx="5" fill="${D.shadowOf(c.boot, 1.4)}"/>`);
      out += G(tf(bx, -58), D.shade(`M-26 0 L-24 ${-150 + cr} L24 ${-150 + cr} L26 0 Z`, c.denim, { depth: 10, light: 3, w: 5, ink: INK }));
    }
    // torso: shirt, overalls, straps, buttons
    const tor = G(tf(0, cr, lean * 0.4),
      D.shade('M-86 -200 Q-92 -330 -70 -372 Q0 -392 70 -372 Q92 -330 86 -200 Z', c.shirt, { depth: 16, light: 4, w: 5.5, ink: INK }) +
      D.shade('M-82 -200 L-80 -298 L-50 -298 L-50 -350 L50 -350 L50 -298 L80 -298 L82 -200 Z', c.denim, { depth: 14, light: 3, w: 5, ink: INK }) +
      D.inkTaper([[-50, -346], [-62, -372]], 16, 16, c.denim, INK, 4) + D.inkTaper([[50, -346], [62, -372]], 16, 16, c.denim, INK, 4) +
      D.sphere(-38, -336, 7, c.band, { w: 3 }) + D.sphere(38, -336, 7, c.band, { w: 3 }) +
      D.shade('M-26 -318 L26 -318 L22 -284 L-22 -284 Z', D.mix(c.denim, '#ffffff', 0.12), { depth: 4, light: 2, w: 3.5, ink: INK }) +
      `<path d="M-60 -250 Q0 -240 60 -250" fill="none" stroke="${D.lightOf(c.denim)}" stroke-width="3" stroke-dasharray="7 6" opacity="0.8"/>`);
    const L = arm(-1, armL.sh, armL.el, c, (o.hand || {}).l, t), R = arm(1, armR.sh, armR.el, c, (o.hand || {}).r, t);
    // head: braids behind, face, hair cap with bangs, headband
    const hx = 0, hy = -482;
    let head = '';
    for (const side of [-1, 1]) {
      const sway = noise(side * 3 + 11, t * 1.3) * 5 + lean * 0.3;
      for (let k = 0; k < 5; k++) {
        const bx = side * (82 + k * 3) + sway * k * 0.4, by = 10 + k * 34;
        head += G(tf(bx, by, side * (8 + k * 2)), D.shade(ellD(19 - k, 22), c.hair, { depth: 6, light: 2, w: 4, ink: INK }));
      }
      head += G(tf(side * (96 + sway * 1.6), 186, side * 12), D.shade('M0 0 L-18 -14 L-18 14 Z M0 0 L18 -14 L18 14 Z', c.band, { depth: 3, light: 2, w: 3.5, ink: INK }));
    }
    head += G(tf(-92, 6), D.shade(ellD(16, 20), c.skin, { depth: 5, light: 2, w: 4.5, ink: INK })) + G(tf(92, 6), D.shade(ellD(16, 20), c.skin, { depth: 5, light: 2, w: 4.5, ink: INK }));
    head += D.shade(ellD(94, 90), c.skin, { dir: [0.5, 0.85], depth: 14, light: 4, w: 6, ink: INK });
    for (const [fx, fy] of [[-50, 28], [-60, 20], [-42, 18], [50, 28], [60, 20], [42, 18]]) head += `<circle cx="${fx}" cy="${fy}" r="2.6" fill="#c97b52" opacity="0.8"/>`;
    head += face({ x: 0, y: -2, s: 1.15, mood, talk, lookX, lookY, bl, sep: 26, lid: c.skin, mouthY: 36 });
    // hair cap with a scalloped fringe
    // fuller hair cap: crown, side locks framing the face, scalloped fringe
    let fringe = 'M-106 18 C-116 -86 -66 -134 0 -134 C66 -134 116 -86 106 18 L92 18 L92 -26';
    for (let k = 0; k < 6; k++) { const x0 = 92 - k * 30.7, x1 = x0 - 30.7; fringe += ` Q${f2(x0 - 15)} ${k % 2 ? -12 : -2} ${f2(x1)} -30`; }
    fringe += ' L-92 18 Z';
    head += D.shade(fringe, c.hair, { dir: [0.4, 0.9], depth: 14, light: 5, w: 5.5, ink: INK });
    head += `<path d="M-100 -60 C-70 -124 70 -124 100 -60" fill="none" stroke="${INK}" stroke-width="24" stroke-linecap="round"/><path d="M-100 -60 C-70 -124 70 -124 100 -60" fill="none" stroke="${c.band}" stroke-width="15" stroke-linecap="round"/>`;
    head += D.glintMark(-46, -104, 0.7, -60);
    const headG = G(tf(hx, hy + cr + bob, lean + noise(21, t * 0.9) * 2 + talk * 2 * Math.sin(t * 9)), head);
    out += L.svg.replace(/^/, '') ; // back arm under the torso
    out += tor.replace(/^/, '');
    out += headG + R.svg;
    return { svg: G(`translate(${f2(x)} ${f2(y)}) scale(${f2(s * flip)} ${f2(s)})`, out), hands: [L.hand, R.hand].map(([a, b]) => [x + a * s * flip, y + (b + cr) * s]) };
  }

  // ---------- Earthworm ----------
  // pts: spine points from head to tail (world units). o: t, talk, mood, look, bl, glasses, bow
  const WORM = { body: '#e8918a', band: '#f4b3a6', ring: '#b8605c' };
  function worm(pts, o = {}) {
    const { t = 0, talk = 0, mood = 'smug', lookX = 0.3, lookY = 0, bl = 0, glasses = true, bow = true, s = 1 } = o;
    const c = { ...WORM, ...(o.colors || {}) };
    let out = D.inkTaper(pts.slice().reverse(), 30 * s, 54 * s, c.body, INK, 5);
    out += D.taper(pts.slice().reverse().map(([x, y]) => [x - 4 * s, y - 5 * s]), 8 * s, 14 * s, D.lightOf(c.body), 'opacity="0.55"');
    // segment rings, and the lighter clitellum band a third of the way down
    for (let i = 3; i < pts.length - 1; i += 2) {
      const [ax, ay] = pts[i - 1], [bx, by] = pts[i + 1], [px, py] = pts[i];
      let nx = -(by - ay), ny = bx - ax; const m = Math.hypot(nx, ny) || 1; nx /= m; ny /= m;
      const w = lerp(26, 15, i / pts.length) * s;
      const band = i > pts.length * 0.22 && i < pts.length * 0.34;
      out += `<path d="M${f2(px + nx * w)} ${f2(py + ny * w)} Q${f2(px + (bx - ax) * 0.15)} ${f2(py + (by - ay) * 0.15)} ${f2(px - nx * w)} ${f2(py - ny * w)}" fill="none" stroke="${band ? c.band : c.ring}" stroke-width="${f2((band ? 9 : 3) * s)}" stroke-linecap="round" opacity="${band ? 0.95 : 0.7}"/>`;
    }
    // head
    const [hx, hy] = pts[0], [nx2, ny2] = pts[2];
    const ang = (Math.atan2(hy - ny2, hx - nx2) * 180) / Math.PI + 90; // head points along the spine
    let head = D.shade(ellD(34, 36), c.body, { depth: 9, light: 4, w: 5.5, ink: INK });
    head += face({ x: 0, y: -6, s: 0.72, mood, talk, lookX, lookY, bl, sep: 21, lid: c.body, mouthY: 34, cheeks: true });
    if (glasses) {
      head += `<g transform="translate(0 -6) scale(0.72)">` +
        [-21, 21].map(gx => `<circle cx="${gx}" cy="0" r="23" fill="#dff1ff" fill-opacity="0.18" stroke="${INK}" stroke-width="5"/>` +
          `<path d="M${gx - 12} -10 Q${gx - 6} -16 ${gx + 2} -16" fill="none" stroke="#fff" stroke-width="4" stroke-linecap="round" opacity="0.8"/>`).join('') +
        `<path d="M-2 -2 Q0 -6 2 -2" fill="none" stroke="${INK}" stroke-width="5"/></g>`;
    }
    out += G(`translate(${f2(hx)} ${f2(hy)}) rotate(${f2(clamp(ang, -40, 40))}) scale(${f2(s)})`, head);
    if (bow && pts.length > 5) {
      const [bx, by] = pts[3];
      out += G(tf(bx, by, 0, s), D.shade('M0 0 L-20 -13 L-20 13 Z M0 0 L20 -13 L20 13 Z', '#d6453d', { depth: 4, light: 2, w: 3.5, ink: INK }) + D.sphere(0, 0, 6, '#d6453d', { w: 3 }));
    }
    return out;
  }
  // Spine through four control points, head first, with a travelling wiggle.
  function spine(p0, p1, p2, p3, t = 0, wig = 6, n = 22) {
    const pts = D.bez(p0, p1, p2, p3, n);
    return pts.map(([x, y], i) => {
      const a = pts[Math.max(0, i - 1)], b = pts[Math.min(n, i + 1)];
      let nx = -(b[1] - a[1]), ny = b[0] - a[0]; const m = Math.hypot(nx, ny) || 1;
      const k = Math.sin(t * 6 - i * 0.55) * wig * Math.min(1, i / 4);
      return [x + (nx / m) * k, y + (ny / m) * k];
    });
  }

  root.Cast = { face, MOODS, kid, worm, spine, KID, WORM };
})(typeof window !== 'undefined' ? window : globalThis);
