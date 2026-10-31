// Screwworm films: shared rigs and backdrops (original designs), drawn with D (draw.js)
// and Cast (cast.js). Every function is a pure function of its arguments.
(function (root) {
  const { clamp, lerp, inv, ease, spring, noise, rand, blink } = root.M;
  const D = root.D, Cast = root.Cast;
  const f2 = n => (+n).toFixed(2);
  const INK = '#2a1a10';
  const G = (tr, inner, extra = '') => `<g transform="${tr}" ${extra}>${inner}</g>`;
  const tf = (x = 0, y = 0, r = 0, sx = 1, sy = sx) => `translate(${f2(x)} ${f2(y)}) rotate(${f2(r)}) scale(${f2(sx)} ${f2(sy)})`;
  const ellD = (rx, ry, cx = 0, cy = 0) => `M${f2(cx - rx)} ${f2(cy)} A${f2(rx)} ${f2(ry)} 0 1 0 ${f2(cx + rx)} ${f2(cy)} A${f2(rx)} ${f2(ry)} 0 1 0 ${f2(cx - rx)} ${f2(cy)} Z`;
  const sh = (d, c, o = {}) => D.shade(d, c, { ink: INK, w: 5, depth: 9, light: 3, ...o });
  const P = (d, fill, sw = 5, stroke = INK, extra = '') => `<path d="${d}" fill="${fill}" stroke="${stroke}" stroke-width="${sw}" stroke-linejoin="round" stroke-linecap="round" ${extra}/>`;
  const txt = (x, y, s, size, fill = INK, o = {}) => {
    const { anchor = 'middle', weight = 700, stroke = null, sw = 10, extra = '' } = o;
    return `<text x="${f2(x)}" y="${f2(y)}" font-size="${f2(size)}" font-weight="${weight}" fill="${fill}" text-anchor="${anchor}"` +
      (stroke ? ` stroke="${stroke}" stroke-width="${sw}" paint-order="stroke" stroke-linejoin="round"` : '') + ` ${extra}>${s}</text>`;
  };
  // rough text width for Fredoka bold (per char em widths)
  function textWidth(str, size, weight = 700) {
    let w = 0;
    for (const ch of String(str)) {
      if (ch === ' ') w += 0.26; else if ('il.,:;!|\''.includes(ch)) w += 0.27; else if ('MW'.includes(ch)) w += 0.86;
      else if (ch >= 'A' && ch <= 'Z') w += 0.66; else if (ch >= '0' && ch <= '9') w += 0.58; else w += 0.55;
    }
    return w * size * (weight >= 700 ? 1.02 : 0.97);
  }

  const C = {
    ink: INK, cream: '#fff8e8', white: '#ffffff',
    skyTop: '#6cb8e8', skyBot: '#fde6b8', mesa: '#c9825a', mesaFar: '#d9a785', dirt: '#d8b27a', grass: '#b9b45a', grassDk: '#8f8a3e',
    mesquite: '#6f9a45', cactus: '#7fae4f', post: '#8a6040',
    cow: '#b4552e', cowWhite: '#fbf3e6', muzzle: '#f1a99a', hoof: '#4a3428',
    flyBody: '#1f8fa0', flyHi: '#7fe3d6', flyDark: '#0f4e66', flyEye: '#e2552c', wing: '#dff3ff',
    maggot: '#f4e7c8', maggotRing: '#c9b285', skin: '#e7a08f', skinDeep: '#c4685c', wound: '#9e2f2c',
    red: '#e2463a', redDk: '#a52a24', gold: '#f6c445', green: '#5fbf4a', sterile: '#9aa6b2', teal: '#2a9d8f',
    sea: '#7cc4e4', seaDk: '#3f8fbf', land: '#f0dfb4', landDk: '#d8c08a', paper: '#fff4dc', sepia: '#a07850',
  };

  // ======================= the screwworm fly =======================
  // Metallic blue-green blowfly with orange-red eyes and three dark stripes on the thorax.
  // o: t, s, rot, wing (0..1 buzz amount), mood, lookX/lookY, talk, sterile (grey + band), flip, legs ('hang'|'stand')
  function fly(x, y, o = {}) {
    const { t = 0, s = 1, rot = 0, wing = 1, mood = 'smug', lookX = 0.3, lookY = 0.1, talk = 0, sterile = false, flip = 1, bl = 0, glow = 0 } = o;
    const body = sterile ? '#8e9aa6' : C.flyBody, hi = sterile ? '#d6dde4' : C.flyHi, dark = sterile ? '#59636e' : C.flyDark;
    const eyeC = sterile ? '#b9a29a' : C.flyEye;
    let out = '';
    // wings behind: buzz between two angles, with a ghost for speed
    const flap = wing > 0.02 ? Math.sin(t * 2 * Math.PI * 14) : 0;
    const wingD = 'M0 0 C30 -40 120 -70 170 -50 C200 -36 170 -6 120 6 C70 14 30 10 0 0 Z';
    const wingOne = (a, op) => G(tf(-6, -34, a), `<path d="${wingD}" fill="${C.wing}" fill-opacity="${f2(0.55 * op)}" stroke="${INK}" stroke-width="3.5" stroke-opacity="${f2(op)}"/>` +
      `<path d="M8 -2 C50 -20 100 -36 150 -40 M20 2 C60 -4 100 -12 140 -16" fill="none" stroke="${INK}" stroke-width="2" opacity="${f2(0.5 * op)}"/>`);
    const a0 = -18 + flap * 26 * wing, a1 = -18 - flap * 26 * wing;
    if (wing > 0.02) out += wingOne(a1 - 10, 0.35);
    out += wingOne(a0 - 10, 1);
    // legs
    for (let i = 0; i < 3; i++) {
      const lx = -30 + i * 30, sw = noise(i * 7 + 3, t * 3) * 6;
      const pts = [[lx, 30], [lx - 18 + i * 6, 62 + sw * 0.3], [lx - 26 + i * 14 + sw, 98]];
      out += D.inkTaper(D.bez(pts[0], pts[1], pts[1], pts[2], 6), 8, 4, dark, INK, 2.5);
    }
    // abdomen (rear, left) and thorax (middle)
    const abd = ellD(70, 52, -78, 12);
    out += sh(abd, body, { dir: [0.4, 0.9], depth: 14, light: 4, glint: { x: -96, y: -14, s: 1.0, r: -50 } });
    out += `<path d="M-120 -8 Q-80 -30 -40 -14 M-128 20 Q-82 4 -36 18" fill="none" stroke="${dark}" stroke-width="4" opacity="0.6"/>`;
    if (sterile) out += `<path d="M-100 -36 L-92 58" stroke="#ffd84a" stroke-width="14" opacity="0.95"/><path d="M-100 -36 L-92 58" stroke="${INK}" stroke-width="18" opacity="0.25"/>`;
    const tho = ellD(56, 50, 4, 0);
    out += sh(tho, body, { dir: [0.4, 0.9], depth: 12, light: 4 });
    for (const sx of [-20, 4, 28]) out += `<path d="M${sx - 4} -42 Q${sx} 0 ${sx - 4} 40" fill="none" stroke="${dark}" stroke-width="7" stroke-linecap="round" opacity="0.85"/>`;
    out += `<ellipse cx="-14" cy="-26" rx="26" ry="10" fill="${hi}" opacity="0.45" transform="rotate(-18 -14 -26)"/>`;
    // head with big compound eyes (cartoon pupils) and a mouthpart
    const hx = 66, hy = 4;
    let head = sh(ellD(40, 38, 0, 0), D.mix(body, '#d9a066', 0.25), { depth: 8 });
    head += P('M22 28 Q30 52 20 64', 'none', 7, INK) + P('M22 28 Q30 52 20 64', 'none', 4, '#5c3a2a');
    const eyeAt = (ex, ey, r) => {
      let e = `<circle cx="${ex}" cy="${ey}" r="${r}" fill="${D.radial([[0, D.lightOf(eyeC, 1.1)], [0.6, eyeC], [1, D.shadowOf(eyeC, 1.2)]], { cx: 0.38, cy: 0.32, r: 0.8 })}" stroke="${INK}" stroke-width="4.5"/>`;
      // facets
      e += `<g opacity="0.25">${[0, 1, 2].map(k => `<circle cx="${ex - r * 0.3 + k * r * 0.3}" cy="${ey + r * 0.35}" r="${r * 0.12}" fill="none" stroke="${INK}" stroke-width="1.5"/>`).join('')}</g>`;
      if (bl < 0.6) {
        const px = ex + lookX * r * 0.35, py = ey + lookY * r * 0.3;
        e += `<circle cx="${f2(px)}" cy="${f2(py)}" r="${f2(r * 0.38)}" fill="#1a0e08"/><circle cx="${f2(px + r * 0.14)}" cy="${f2(py - r * 0.15)}" r="${f2(r * 0.13)}" fill="#fff"/>`;
      }
      // attitude lid
      const lid = mood === 'smug' ? 0.42 : mood === 'annoyed' ? 0.5 : mood === 'sad' ? 0.35 : mood === 'sleep' ? 1 : 0;
      const ll = Math.max(lid, bl);
      if (ll > 0.02) {
        const yy = ey - r + 2 * r * Math.min(0.98, ll), tilt = mood === 'annoyed' ? 8 : mood === 'sad' ? -8 : 0;
        e += `<path d="M${ex - r - 2} ${ey - r - 4} L${ex + r + 2} ${ey - r - 4} L${ex + r + 2} ${f2(yy + tilt)} L${ex - r - 2} ${f2(yy - tilt)} Z" fill="${D.shadowOf(eyeC, 0.6)}" clip-path="none" opacity="0.97"/>`;
        e += `<path d="M${ex - r} ${f2(yy - tilt)} L${ex + r} ${f2(yy + tilt)}" stroke="${INK}" stroke-width="4"/>`;
        e += `<circle cx="${ex}" cy="${ey}" r="${r}" fill="none" stroke="${INK}" stroke-width="4.5"/>`;
      }
      return e;
    };
    // the lid path overflows the eye; clip each eye to its circle
    const eyeClip = (ex, ey, r, k) => {
      const id = `fe${k}_${Math.round(x)}_${Math.round(y)}_${Math.round(t * 30)}`;
      return `<clipPath id="${id}"><circle cx="${ex}" cy="${ey}" r="${r + 3}"/></clipPath><g clip-path="url(#${id})">${eyeAt(ex, ey, r)}</g>`;
    };
    head += eyeClip(-6, -18, 24, 0) + eyeClip(26, -10, 21, 1);
    // brow and mouth
    const browT = mood === 'annoyed' ? 10 : mood === 'smug' ? -4 : mood === 'surprised' ? -10 : 0;
    head += D.taper(D.bez([-26, -48 + browT * 0.3], [-14, -54], [4, -54], [16, -46 - browT * 0.3], 6), 7, 3, INK);
    const mo = clamp(talk);
    if (mo > 0.05 || mood === 'surprised') head += `<ellipse cx="10" cy="22" rx="${f2(8 + mo * 3)}" ry="${f2(4 + mo * 9)}" fill="#5e1a18" stroke="${INK}" stroke-width="3.5"/>`;
    else head += D.taper(D.bez(mood === 'sad' ? [-2, 26] : [-2, 18], [6, mood === 'sad' ? 18 : 26], [14, mood === 'sad' ? 18 : 26], [22, mood === 'smug' ? 14 : mood === 'sad' ? 26 : 18], 8), 3, 4.5, INK);
    out += G(tf(hx, hy, noise(5, t * 1.5) * 5), head);
    if (glow > 0.01) out = `<circle cx="0" cy="0" r="190" fill="${D.radial([[0, '#fff3b0', 0.8 * glow], [1, '#fff3b0', 0]], { cx: 0.5, cy: 0.5, r: 0.5 })}"/>` + out;
    return G(`translate(${f2(x)} ${f2(y)}) rotate(${f2(rot)}) scale(${f2(s * flip)} ${f2(s)})`, out);
  }
  // tiny flying fleck (crowds): body dot + wing blur
  function fleck(x, y, s = 1, t = 0, col = C.flyBody, wingOp = 0.6) {
    const fl = Math.sin(t * 90 + x) > 0 ? 1 : -1;
    return G(tf(x, y, 0, s), `<ellipse cx="-4" cy="${-10 * fl}" rx="10" ry="5" fill="${C.wing}" opacity="${wingOp}" stroke="${INK}" stroke-width="1.2"/>` +
      `<ellipse cx="0" cy="0" rx="9" ry="7" fill="${col}" stroke="${INK}" stroke-width="2.4"/><circle cx="8" cy="-1" r="4.2" fill="${col === C.flyBody ? C.flyEye : '#c4b3ab'}" stroke="${INK}" stroke-width="1.6"/>`);
  }

  // ======================= maggot =======================
  // Segmented cream larva; rings drawn slanted so it reads like a screw thread. o: t, s, rot, wig, screw (0..1 spin phase)
  function maggot(x, y, o = {}) {
    const { t = 0, s = 1, rot = 0, wig = 1, screw = 0, len = 110, wid = 34 } = o;
    const n = 9;
    const pts = [];
    for (let i = 0; i <= n; i++) {
      const u = i / n;
      pts.push([-len / 2 + u * len, Math.sin(u * 3.4 + t * 7 * wig) * 7 * wig]);
    }
    let out = D.inkTaper(pts, wid * 0.55, wid, C.maggot, INK, 3.5);
    for (let i = 1; i < n; i++) {
      const [px, py] = pts[i], w = lerp(wid * 0.55, wid, i / n) / 2;
      const ph = (screw * 2 + i * 0.0) % 1;
      out += `<path d="M${f2(px - 5 + ph * 8)} ${f2(py - w + 2)} L${f2(px + 5 + ph * 8)} ${f2(py + w - 2)}" stroke="${C.maggotRing}" stroke-width="3.2" stroke-linecap="round"/>`;
    }
    const [hx, hy] = pts[0];
    out += `<path d="M${f2(hx + 2)} ${f2(hy - 4)} l-9 -3 M${f2(hx + 2)} ${f2(hy + 4)} l-9 3" stroke="${INK}" stroke-width="3" stroke-linecap="round"/>`;
    out += `<ellipse cx="${f2(pts[5][0])}" cy="${f2(pts[5][1] - wid * 0.22)}" rx="${f2(len * 0.22)}" ry="4" fill="#fff" opacity="0.5"/>`;
    return G(tf(x, y, rot, s), out);
  }
  // egg mass: shingled rows of white rice-like eggs at a wound edge
  function eggMass(x, y, n, o = {}) {
    const { s = 1, rot = 0, sterile = false } = o;
    let out = '';
    for (let i = 0; i < n; i++) {
      const row = Math.floor(i / 7), col = i % 7;
      const ex = col * 13 - 40 + row * 5, ey = -row * 9;
      out += `<ellipse cx="${ex}" cy="${ey}" rx="5" ry="12" transform="rotate(${-20 + row * 4} ${ex} ${ey})" fill="${sterile ? '#d9dde2' : '#fffaf0'}" stroke="${INK}" stroke-width="2"/>`;
    }
    return G(tf(x, y, rot, s), out);
  }

  // ======================= cattle, deer, dog, cat =======================
  // Side-view quadruped facing right; head turned 3/4 with a Cast face. kind: 'cow' | 'calf' | 'deer'
  function cow(x, y, o = {}) {
    const { t = 0, s = 1, kind = 'cow', mood = 'happy', talk = 0, lookX = 0.4, lookY = 0, bl = 0, flip = 1, headTurn = 0, walk = 0, lie = 0 } = o;
    const calf = kind === 'calf', deer = kind === 'deer';
    const body = deer ? '#b07a48' : calf ? '#c56a3a' : C.cow, white = deer ? '#f3e6d0' : C.cowWhite;
    const bw = calf ? 150 : deer ? 170 : 210, bh = calf ? 82 : deer ? 86 : 118, legH = calf ? 120 : deer ? 140 : 110;
    const by = -legH - bh * 0.5 + lie * (legH * 0.85);
    let out = '';
    // tail
    const sw = Math.sin(t * 2.4) * 14 + noise(9, t) * 8;
    const tailEnd = [-bw - 30 + sw * 0.4, by + 60 + Math.abs(sw) * 0.2];
    if (!deer) out += D.inkTaper(D.bez([-bw + 6, by - bh * 0.3], [-bw - 30, by - 10], [-bw - 30 + sw * 0.3, by + 30], tailEnd, 10), 7, 5, body, INK, 3) +
      G(tf(tailEnd[0], tailEnd[1], sw * 0.5), sh('M0 -6 C10 4 10 24 0 34 C-10 24 -10 4 0 -6 Z', '#5a2c18', { depth: 4, w: 3.5 }));
    else out += G(tf(-bw + 2, by - bh * 0.35, -30 + sw * 0.3), sh('M0 0 C14 -16 30 -8 22 10 C14 20 4 14 0 0 Z', '#fffaf0', { depth: 4, w: 3.5 }));
    // legs (far pair darker, near pair over the body later)
    const leg = (lx, ph, far) => {
      const a = Math.sin(t * 6 + ph) * 16 * walk;
      const L1 = legH * (1 - lie * 0.75);
      const kneeX = lx + Math.sin((a * Math.PI) / 180) * L1 * 0.5, kneeY = by + bh * 0.3 + L1 * 0.5;
      const footX = lx + Math.sin((a * Math.PI) / 180) * L1 * (lie > 0.5 ? 0.9 : 1) + lie * 30, footY = by + bh * 0.3 + L1;
      const c = far ? D.shadowOf(body, 1.1) : body;
      let l = D.inkTaper([[lx, by + bh * 0.1], [kneeX, kneeY], [footX, footY - 10]], calf ? 30 : 36, calf ? 20 : 24, c, INK, 4);
      l += G(tf(footX, footY - 6), sh(`M-14 -10 L14 -10 L16 6 L-16 6 Z`, C.hoof, { depth: 3, light: 1, w: 3.5 }));
      return l;
    };
    out += leg(-bw * 0.65, 1.2, true) + leg(bw * 0.55, 0.0, true);
    // barrel
    const barrel = `M${-bw} ${by - bh * 0.15} C${-bw} ${by - bh * 0.95} ${-bw * 0.4} ${by - bh} ${bw * 0.2} ${by - bh * 0.92} C${bw * 0.85} ${by - bh * 0.85} ${bw} ${by - bh * 0.4} ${bw * 0.95} ${by + bh * 0.1} C${bw * 0.9} ${by + bh * 0.62} ${bw * 0.3} ${by + bh * 0.7} ${-bw * 0.2} ${by + bh * 0.62} C${-bw * 0.8} ${by + bh * 0.6} ${-bw} ${by + bh * 0.4} ${-bw} ${by - bh * 0.15} Z`;
    out += sh(barrel, body, { dir: [0.3, 0.95], depth: 16, light: 4 });
    // belly (white) and patches
    out += `<path d="M${-bw * 0.6} ${by + bh * 0.5} C${-bw * 0.2} ${by + bh * 0.75} ${bw * 0.4} ${by + bh * 0.75} ${bw * 0.75} ${by + bh * 0.45} C${bw * 0.4} ${by + bh * 0.3} ${-bw * 0.3} ${by + bh * 0.3} ${-bw * 0.6} ${by + bh * 0.5} Z" fill="${white}" opacity="0.95"/>`;
    if (!deer) out += `<path d="M${-bw * 0.2} ${by - bh * 0.9} C${-bw * 0.05} ${by - bh * 0.55} ${bw * 0.2} ${by - bh * 0.6} ${bw * 0.25} ${by - bh * 0.9} Z" fill="${white}" opacity="0.9"/>`;
    if (deer) for (let i = 0; i < 6; i++) out += `<circle cx="${f2(-bw * 0.5 + i * 34)}" cy="${f2(by - bh * 0.45 + (i % 2) * 18)}" r="6" fill="#fff6e6" opacity="0.8"/>`;
    out += barrel.length ? P(barrel, 'none', 5) : '';
    // navel marker point (calves): returned for the scene
    const navel = [bw * 0.05, by + bh * 0.62];
    // near legs
    out += leg(-bw * 0.5, 3.0, false) + leg(bw * 0.7, 2.1, false);
    // neck + head
    const hx = bw * 0.95 + (calf ? 40 : 52), hy = by - bh * 0.55 - (calf ? 30 : 20) + lie * 10;
    out += D.inkTaper(D.bez([bw * 0.6, by - bh * 0.3], [bw * 0.85, by - bh * 0.5], [hx - 30, hy + 10], [hx - 10, hy + 20], 8), calf ? 70 : 92, calf ? 56 : 70, body, INK, 4);
    let head = '';
    const hs = calf ? 1.12 : deer ? 0.95 : 1;
    // ears
    const ear = (side) => G(tf(side * 52, -34, side * (40 + Math.sin(t * 3 + side) * 8)), sh('M0 0 C20 -10 46 -8 56 4 C44 16 18 16 0 0 Z', deer ? '#a46d3e' : body, { depth: 5, w: 4 }) + `<path d="M10 2 C24 -2 38 0 46 4" stroke="#f3b6a8" stroke-width="6" fill="none" stroke-linecap="round"/>`);
    head += G('scale(-1 1)', ear(1)) + ear(1);
    if (!calf && !deer) for (const side of [-1, 1]) head += D.inkTaper(D.bez([side * 36, -52], [side * 52, -80], [side * 70, -86], [side * 82, -78], 8), 16, 6, '#efe2c4', INK, 3);
    if (deer && o.antlers) for (const side of [-1, 1]) {
      const a = D.bez([side * 24, -56], [side * 40, -110], [side * 70, -130], [side * 86, -150], 8);
      head += D.inkTaper(a, 9, 5, '#d8c29a', INK, 3) + D.inkTaper([[side * 46, -110], [side * 30, -150]], 7, 4, '#d8c29a', INK, 3);
    }
    head += sh(`M-48 -40 C-50 -70 50 -70 48 -40 C52 0 44 50 0 60 C-44 50 -52 0 -48 -40 Z`, deer ? '#b98451' : body, { dir: [0.4, 0.9], depth: 10, light: 4 });
    if (!deer) head += `<path d="M-22 -60 C-10 -40 10 -40 22 -60 C14 -10 12 30 0 40 C-12 30 -14 -10 -22 -60 Z" fill="${white}"/>`;
    head += sh(ellD(36, 24, 0, 46), deer ? '#3a2a20' : C.muzzle, { depth: 6, w: 4 });
    head += `<ellipse cx="-12" cy="46" rx="5" ry="7" fill="${INK}" opacity="0.75"/><ellipse cx="12" cy="46" rx="5" ry="7" fill="${INK}" opacity="0.75"/>`;
    head += Cast.face({ x: 0, y: -14, s: 0.9, mood, talk, lookX, lookY, bl, sep: 24, rx: 13, ry: 15, mouthY: 82, lid: deer ? '#b98451' : body, cheeks: false });
    out += G(tf(hx, hy, headTurn + noise(3, t * 0.8) * 3, hs * flip, hs), head);
    return { svg: G(`translate(${f2(x)} ${f2(y)}) scale(${f2(s * flip)} ${f2(s)})`, out), navel: [x + navel[0] * s * flip, y + navel[1] * s] };
  }
  function dog(x, y, o = {}) {
    const { t = 0, s = 1, mood = 'happy', flip = 1, bl = 0, wag = 1, lookX = 0.3, col = '#d79a52' } = o;
    let out = '';
    const tw = Math.sin(t * 12) * 22 * wag;
    out += D.inkTaper(D.bez([-92, -110], [-120, -150], [-130 + tw * 0.4, -180], [-120 + tw, -196], 8), 18, 8, col, INK, 4);
    for (const [lx, far] of [[-70, 1], [60, 1], [-50, 0], [80, 0]]) out += D.inkTaper([[lx, -90], [lx + 2, -40], [lx + 4, -6]], 26, 22, far ? D.shadowOf(col, 1) : col, INK, 4) + sh(ellD(16, 9, lx + 8, -4), D.shadowOf(col, 1.4), { depth: 2, w: 3.5 });
    out += sh('M-100 -110 C-100 -160 90 -170 100 -120 C106 -80 70 -60 0 -62 C-70 -60 -100 -70 -100 -110 Z', col, { dir: [0.3, 0.95], depth: 12 });
    out += `<path d="M-40 -66 C0 -56 50 -58 80 -70" stroke="#fbe7c6" stroke-width="16" fill="none" stroke-linecap="round" opacity="0.8"/>`;
    let head = sh(ellD(62, 56, 0, 0), col, { depth: 10 });
    head += G(tf(-50, -20, 20 + Math.sin(t * 4) * 6), sh('M0 0 C-30 10 -40 60 -20 80 C0 70 10 30 0 0 Z', D.shadowOf(col, 1.3), { depth: 5, w: 4 }));
    head += G(tf(50, -20, -20 - Math.sin(t * 4) * 6), sh('M0 0 C30 10 40 60 20 80 C0 70 -10 30 0 0 Z', D.shadowOf(col, 1.3), { depth: 5, w: 4 }));
    head += sh(ellD(34, 24, 6, 30), '#fbe7c6', { depth: 5, w: 4 }) + D.sphere(6, 18, 11, '#2a1a10', { w: 3 });
    head += Cast.face({ x: 0, y: -10, s: 0.8, mood, lookX, bl, sep: 26, rx: 12, ry: 14, mouthY: 62, lid: col, cheeks: false });
    out += G(tf(100, -150, noise(4, t) * 4), head);
    return G(`translate(${f2(x)} ${f2(y)}) scale(${f2(s * flip)} ${f2(s)})`, out);
  }
  function cat(x, y, o = {}) {
    const { t = 0, s = 1, mood = 'skeptical', flip = 1, bl = 0, col = '#8c8f99', lookX = 0.2 } = o;
    let out = '';
    const tw = Math.sin(t * 2) * 10;
    out += D.inkTaper(D.bez([50, -20], [130, -10], [120 + tw, -110], [80 + tw, -130], 10), 18, 10, col, INK, 4);
    out += sh('M-60 0 C-80 -80 -50 -170 0 -170 C50 -170 80 -80 60 0 Z', col, { dir: [0.3, 0.95], depth: 12 });
    out += `<path d="M-20 -10 C-24 -60 24 -60 20 -10 Z" fill="#e8e6ea" opacity="0.85"/>`;
    for (const k of [-1, 1]) out += sh(ellD(20, 12, k * 26, -4), D.shadowOf(col, 0.6), { depth: 3, w: 3.5 });
    let head = sh('M-60 10 C-66 -40 -46 -60 -40 -86 L-14 -56 C-4 -60 4 -60 14 -56 L40 -86 C46 -60 66 -40 60 10 C50 46 -50 46 -60 10 Z', col, { depth: 9 });
    head += `<path d="M-38 -72 L-26 -56 M38 -72 L26 -56" stroke="#f2a9b0" stroke-width="6"/>`;
    for (const [k, a] of [[-1, -6], [-1, 6], [1, -6], [1, 6]]) head += `<path d="M${k * 20} 14 L${k * 62} ${14 + a}" stroke="${INK}" stroke-width="2.5"/>`;
    head += `<path d="M-6 6 L6 6 L0 14 Z" fill="#f2a9b0" stroke="${INK}" stroke-width="2.5"/>`;
    head += Cast.face({ x: 0, y: -16, s: 0.75, mood, lookX, bl, sep: 26, rx: 12, ry: 15, mouthY: 46, lid: col, cheeks: false });
    out += G(tf(0, -190, noise(6, t * 0.7) * 4), head);
    return G(`translate(${f2(x)} ${f2(y)}) scale(${f2(s * flip)} ${f2(s)})`, out);
  }

  // ======================= adults =======================
  // Front-facing adult about 640 units tall. o: t, s, coat ('lab' | 'ranch' | 'vet'), hair, skin, glasses, hat,
  // armL/armR {sh, el} in degrees, mood, talk, look, bl, tie, tag (name tag text), sepia
  function adult(x, y, o = {}) {
    const { t = 0, s = 1, coat = 'lab', hair = '#5a3a26', skin = '#e8b48e', glasses = false, hat = false, mood = 'happy', talk = 0, lookX = 0, lookY = 0, bl = 0,
      tie = '#b8463a', tag = '', shirt = '#7fa7d6', pants = '#4b4f63', bald = 0, flip = 1 } = o;
    const armL = o.armL || { sh: 10, el: 10 }, armR = o.armR || { sh: 10, el: 10 };
    const coatC = coat === 'lab' ? '#f7f5ef' : coat === 'vet' ? '#5fb3a6' : shirt;
    let out = '';
    const bob = Math.sin(t * 2) * 2;
    for (const side of [-1, 1]) {
      out += sh(`M${side * 46 - 26} -150 L${side * 46 - 24} 0 L${side * 46 + 24} 0 L${side * 46 + 26} -150 Z`, pants, { depth: 9, w: 4.5 });
      out += sh(`M${side * 46 - 34} -6 L${side * 46 + 34} -6 Q${side * 46 + 40} 14 ${side * 46 + 30} 16 L${side * 46 - 30} 16 Q${side * 46 - 40} 14 ${side * 46 - 34} -6 Z`, '#3a2a20', { depth: 4, w: 4 });
    }
    const arm = (side, a) => {
      const ux = side * 82, uy = -404;
      const a1 = (a.sh * Math.PI) / 180, a2 = ((a.sh + a.el) * Math.PI) / 180;
      const ex = ux + side * Math.sin(a1) * 110, ey = uy + Math.cos(a1) * 110;
      const hx = ex + side * Math.sin(a2) * 100, hy = ey + Math.cos(a2) * 100;
      return { svg: D.inkTaper([[ex, ey], [hx, hy]], 34, 30, coatC, INK, 4.5) + D.inkTaper([[ux, uy], [ex, ey]], 44, 36, coatC, INK, 4.5) + D.sphere(hx, hy, 22, skin, { w: 4.5, spec: false }), hand: [hx, hy] };
    };
    const L = arm(-1, armL), R = arm(1, armR);
    out += L.svg;
    // torso
    out += sh('M-92 -150 Q-100 -330 -84 -420 Q0 -446 84 -420 Q100 -330 92 -150 Z', coatC, { dir: [0.4, 0.9], depth: 16, light: 4 });
    if (coat === 'lab') {
      out += `<path d="M-30 -428 L0 -340 L30 -428" fill="${shirt}" stroke="${INK}" stroke-width="4"/><path d="M-10 -400 L10 -400 L14 -330 L0 -310 L-14 -330 Z" fill="${tie}" stroke="${INK}" stroke-width="3.5"/>`;
      out += `<path d="M0 -340 L0 -150" stroke="${INK}" stroke-width="4"/><rect x="40" y="-330" width="34" height="40" rx="4" fill="none" stroke="${INK}" stroke-width="3.5"/><path d="M50 -334 L50 -306" stroke="#3a6ad0" stroke-width="5"/>`;
    } else if (coat === 'ranch') {
      out += `<path d="M-60 -400 L0 -360 L60 -400" fill="none" stroke="${INK}" stroke-width="4"/><path d="M0 -360 L0 -160" stroke="${INK}" stroke-width="3" stroke-dasharray="2 18" stroke-linecap="round"/>`;
      for (let i = -3; i <= 3; i++) out += `<path d="M${i * 26} -420 L${i * 26} -152" stroke="${D.shadowOf(coatC, 0.6)}" stroke-width="5" opacity="0.5"/>`;
      out += `<rect x="-92" y="-176" width="184" height="22" fill="#6b4428" stroke="${INK}" stroke-width="4"/><rect x="-18" y="-180" width="36" height="30" rx="4" fill="${C.gold}" stroke="${INK}" stroke-width="3.5"/>`;
    } else {
      out += `<path d="M-30 -428 L0 -380 L30 -428" fill="#fff" stroke="${INK}" stroke-width="4"/>`;
    }
    if (tag) out += `<g transform="translate(-50 -300) rotate(-4)"><rect x="-58" y="-20" width="116" height="40" rx="8" fill="#fff" stroke="${INK}" stroke-width="3.5"/>${txt(0, 9, tag, 22, INK)}</g>`;
    out += R.svg;
    // head
    let head = '';
    head += sh(ellD(16, 22, -84, 6), skin, { depth: 5, w: 4 }) + sh(ellD(16, 22, 84, 6), skin, { depth: 5, w: 4 });
    head += sh('M-80 -10 C-84 -110 84 -110 80 -10 C82 60 50 100 0 104 C-50 100 -82 60 -80 -10 Z', skin, { dir: [0.5, 0.85], depth: 12, light: 4 });
    head += Cast.face({ x: 0, y: 4, s: 1.0, mood, talk, lookX, lookY, bl, sep: 30, rx: 13, ry: 16, mouthY: 50, lid: skin, cheeks: false });
    if (glasses) head += `<g fill="none" stroke="${INK}" stroke-width="5"><rect x="-56" y="-14" width="44" height="34" rx="10"/><rect x="12" y="-14" width="44" height="34" rx="10"/><path d="M-12 0 L12 0 M-56 0 L-80 -6 M56 0 L80 -6"/></g>`;
    if (!hat) head += sh(bald > 0.5 ? 'M-84 -10 C-90 -40 -80 -60 -70 -40 L-66 -10 Z M84 -10 C90 -40 80 -60 70 -40 L66 -10 Z' : 'M-86 0 C-100 -96 -40 -126 10 -120 C70 -116 100 -80 86 0 C80 -40 60 -64 10 -70 C-30 -72 -70 -60 -86 0 Z', hair, { depth: 8, w: 4.5 });
    else head += sh('M-150 -40 Q0 -10 150 -40 Q140 -18 0 -4 Q-140 -18 -150 -40 Z', '#c8955a', { depth: 6, w: 4.5 }) + sh('M-76 -36 C-80 -120 -40 -136 0 -126 C40 -136 80 -120 76 -36 Q0 -22 -76 -36 Z', '#d6a466', { depth: 10, w: 4.5 }) + `<path d="M-74 -52 Q0 -38 74 -52" stroke="#7a4a2a" stroke-width="10" fill="none"/>`;
    out += G(tf(0, -520 + bob, noise(13, t * 0.8) * 2 + talk * 2 * Math.sin(t * 9)), head);
    return { svg: G(`translate(${f2(x)} ${f2(y)}) scale(${f2(s * flip)} ${f2(s)})`, out), hands: [L.hand, R.hand].map(([a, b]) => [x + a * s * flip, y + b * s]) };
  }

  // ======================= machines =======================
  // 1950s high-wing crop plane, side view facing right. o: t, s, rot, col
  function plane(x, y, o = {}) {
    const { t = 0, s = 1, rot = 0, col = '#f2c23a', door = 0 } = o;
    let out = '';
    out += sh('M-200 -10 C-160 -40 120 -46 170 -20 C200 -4 196 20 160 26 C80 34 -120 30 -200 10 Z', col, { dir: [0.3, 0.95], depth: 12 });
    out += sh('M-200 -10 L-250 -70 L-214 -70 L-170 -18 Z', col, { depth: 6, w: 4.5 });
    out += sh('M-230 0 L-170 -6 L-176 12 L-232 14 Z', D.shadowOf(col, 0.6), { depth: 4, w: 4 });
    out += sh('M40 -40 C60 -70 120 -60 140 -30 L60 -26 Z', '#bfe6ff', { depth: 4, w: 4.5 });
    out += sh('M-120 -66 L160 -66 L160 -50 L-120 -50 Z', D.shadowOf(col, 0.35), { depth: 4, w: 4.5 });
    out += `<path d="M-40 -50 L-10 -20 M110 -50 L90 -22" stroke="${INK}" stroke-width="5"/>`;
    out += `<path d="M-30 -10 L-30 10 L10 10 L10 -10 Z" fill="${door > 0.5 ? '#3a2a20' : D.shadowOf(col, 0.5)}" stroke="${INK}" stroke-width="3.5"/>`;
    out += `<text x="-110" y="12" font-size="22" font-weight="700" fill="${INK}">USDA</text>`;
    out += `<path d="M60 26 L40 64 M100 26 L120 64" stroke="${INK}" stroke-width="5"/>` + D.sphere(40, 70, 13, '#3a3a40', { w: 3.5 }) + D.sphere(120, 70, 13, '#3a3a40', { w: 3.5 });
    out += `<ellipse cx="200" cy="0" rx="10" ry="${f2(54 + Math.sin(t * 80) * 6)}" fill="#c9d4dc" opacity="0.45" stroke="${INK}" stroke-width="2" stroke-opacity="0.4"/>`;
    out += sh(ellD(16, 16, 192, 0), '#c0c4c8', { depth: 3, w: 4 });
    return G(tf(x, y, rot, s), out);
  }
  // cardboard release box falling and opening; flies spill out after `open`
  function dropBox(x, y, o = {}) {
    const { rot = 0, open = 0, s = 1 } = o;
    let out = sh('M-28 -22 L28 -22 L28 22 L-28 22 Z', '#d8b07a', { depth: 6, w: 4 });
    out += `<path d="M-28 -6 L28 -6" stroke="${INK}" stroke-width="3"/>`;
    if (open > 0) out += G(tf(-28, -22, -100 * open), sh('M0 0 L28 0 L28 -6 L0 -6 Z', '#c99f68', { depth: 2, w: 3 })) + G(tf(28, -22, 100 * open), sh('M0 0 L-28 0 L-28 -6 L0 -6 Z', '#c99f68', { depth: 2, w: 3 }));
    return G(tf(x, y, rot, s), out);
  }

  // ======================= backdrops =======================
  // South Texas brush country: sky, far mesas, mesquite, prickly pear, fence, dry grass.
  function ranch(t, o = {}) {
    const { cx = 540, cy = 960, z = 1, warm = 0.4, dusk = 0 } = o;
    const top = D.mix(D.mix(C.skyTop, '#5a62b0', dusk), '#f2b46a', warm * 0.25), bot = D.mix(C.skyBot, '#f4a26a', dusk * 0.6);
    let s = `<rect width="1080" height="1920" fill="${D.linear([[0, top], [0.62, bot], [1, bot]])}"/>`;
    const layer = (p, inner) => `<g transform="translate(540 960) scale(${f2(1 + (z - 1) * p)}) translate(${f2(-(540 + (cx - 540) * p))} ${f2(-(960 + (cy - 960) * p))})">${inner}</g>`;
    s += layer(0.08, `<circle cx="820" cy="420" r="170" fill="${D.radial([[0, '#fff4c0', 0.8], [1, '#fff4c0', 0]], { cx: 0.5, cy: 0.5, r: 0.5 })}"/>` + D.sphere(820, 420, 70, '#ffd56a', { w: 0, spec: false }));
    let clouds = '';
    [[160, 330, 0.9, 1], [600, 250, 0.7, 2], [980, 360, 0.6, 3]].forEach(([x, y, sc, sd]) => { clouds += D.cloud(((x + t * 10 * sc + 300) % 1500) - 300, y, sc, sd, '#fffaf0', '#f6dcc0'); });
    s += layer(0.12, clouds);
    s += layer(0.25, `<path d="M-200 900 L60 900 L110 820 L330 812 L380 900 L640 900 L700 760 L900 750 L960 900 L1300 900 L1300 1100 L-200 1100 Z" fill="${C.mesaFar}" stroke="${INK}" stroke-width="3" stroke-opacity="0.35"/>`);
    s += layer(0.45, sh('M-200 990 C100 950 400 1000 700 960 C900 935 1100 970 1300 950 L1300 1300 L-200 1300 Z', D.mix(C.grass, C.mesa, 0.3), { depth: 10, w: 3 }));
    // mesquite trees on the far rise
    let trees = '';
    for (const [tx, ty, sc] of [[110, 985, 0.9], [890, 960, 1.1], [1010, 975, 0.7]]) {
      const lean = D.wind(t, tx) * 0.6;
      trees += G(tf(tx, ty, lean, sc), D.inkTaper(D.bez([0, 0], [-6, -60], [10, -100], [20, -130], 8), 22, 8, '#6b4a30', INK, 3) +
        [[-60, -150, 70], [20, -170, 80], [80, -140, 60], [-10, -120, 60]].map(([bx, by, r]) => sh(ellD(r, r * 0.6, bx, by), C.mesquite, { depth: 8, w: 4 })).join(''));
    }
    s += layer(0.45, trees);
    // ground
    let ground = sh('M-300 1080 C100 1050 600 1090 1400 1060 L1400 2200 L-300 2200 Z', C.dirt, { depth: 12, w: 4 });
    for (let i = 0; i < 40; i++) {
      const gx = -200 + rand(i + 3) * 1500, gy = 1100 + rand(i + 7) * 700, h = 30 + rand(i) * 40;
      const lean = D.wind(t, gx) * 1.5;
      ground += D.taper(D.bez([gx, gy], [gx, gy - h * 0.5], [gx + lean, gy - h * 0.8], [gx + lean * 1.4, gy - h], 6), 9, 2, i % 2 ? C.grass : C.grassDk);
    }
    // fence posts and wire
    let fence = '';
    for (let i = 0; i < 8; i++) fence += sh(`M${-140 + i * 210} 1000 l14 0 l3 130 l-20 0 Z`, C.post, { depth: 3, light: 1, w: 3.5 });
    fence += `<path d="M-200 1030 Q300 1040 1400 1026 M-200 1070 Q300 1080 1400 1066" stroke="${INK}" stroke-width="2.5" fill="none" opacity="0.7"/>`;
    // prickly pear
    const cactus = (x0, y0, sc) => G(tf(x0, y0, 0, sc), [[0, -40, 0], [-40, -100, -20], [40, -110, 18], [0, -160, 0]].map(([px, py, r]) => G(tf(px, py, r), sh(ellD(34, 46), C.cactus, { depth: 7, w: 4 }) +
      [[-10, -10], [12, 6], [-4, 20], [14, -22]].map(([dx, dy]) => `<circle cx="${dx}" cy="${dy}" r="2.5" fill="#fff6c8"/>`).join(''))).join('') + `<circle cx="40" cy="-162" r="9" fill="#e45a7a" stroke="${INK}" stroke-width="3"/>`);
    s += layer(0.7, fence);
    s += layer(1, ground + cactus(940, 1250, 0.9) + cactus(80, 1330, 0.7));
    return s;
  }
  // 1950s lab: wall, window, shelves of jars, bench. Sepia-tinted by the caller.
  function lab(t, o = {}) {
    let s = `<rect width="1080" height="1920" fill="${D.linear([[0, '#e8dcc0'], [1, '#d4c3a0']])}"/>`;
    s += `<rect x="0" y="1180" width="1080" height="740" fill="#a98b64"/><path d="M0 1180 L1080 1180" stroke="${INK}" stroke-width="5"/>`;
    for (let i = 0; i < 12; i++) s += `<path d="M${i * 100} 1180 L${i * 100 - 120} 1920" stroke="#8c7050" stroke-width="3"/>`;
    s += sh('M640 300 L960 300 L960 640 L640 640 Z', '#bfe0ef', { depth: 8, w: 6 }) + `<path d="M800 300 L800 640 M640 470 L960 470" stroke="${INK}" stroke-width="7"/>`;
    s += `<rect x="620" y="636" width="360" height="22" rx="4" fill="#c8a878" stroke="${INK}" stroke-width="4"/>`;
    for (const sy of [380, 560]) {
      s += `<rect x="70" y="${sy}" width="440" height="16" fill="#8c6a44" stroke="${INK}" stroke-width="4"/>`;
      for (let k = 0; k < 6; k++) {
        const jx = 100 + k * 70, jc = ['#cfe8d8', '#f2e2b8', '#d8d0f0'][k % 3];
        s += sh(`M${jx} ${sy} L${jx} ${sy - 80} Q${jx} ${sy - 92} ${jx + 12} ${sy - 92} L${jx + 38} ${sy - 92} Q${jx + 50} ${sy - 92} ${jx + 50} ${sy - 80} L${jx + 50} ${sy} Z`, jc, { depth: 5, w: 3.5 });
        s += `<rect x="${jx + 6}" y="${sy - 104}" width="38" height="12" rx="3" fill="#6b5040" stroke="${INK}" stroke-width="3"/>`;
        if (k % 2 === 0) for (let m = 0; m < 3; m++) s += fleck(jx + 14 + m * 10, sy - 40 - m * 14 + Math.sin(t * 3 + k + m) * 6, 0.6, t);
      }
    }
    // bench
    s += sh('M40 1100 L1040 1100 L1040 1150 L40 1150 Z', '#8a6a48', { depth: 6, w: 5 }) + `<path d="M80 1150 L80 1400 M1000 1150 L1000 1400" stroke="${INK}" stroke-width="12"/>`;
    return s;
  }
  // full-frame sea, for islands
  function sea(t, o = {}) {
    let s = `<rect width="1080" height="1920" fill="${D.linear([[0, '#5fb0dc'], [1, '#2f7fb4']])}"/>`;
    for (let i = 0; i < 46; i++) {
      const wx = (rand(i) * 1300 + t * 18 * (0.5 + rand(i + 2))) % 1300 - 110, wy = 220 + rand(i + 5) * 1600;
      s += `<path d="M${f2(wx)} ${f2(wy)} q14 -10 28 0 q14 10 28 0" fill="none" stroke="#d8f0ff" stroke-width="4" stroke-linecap="round" opacity="0.45"/>`;
    }
    return s;
  }
  function island(x, y, w, h, seed, o = {}) {
    const { label = '', labelY = -h - 40, size = 46 } = o;
    let d = '';
    const n = 18;
    for (let i = 0; i <= n; i++) {
      const a = (i / n) * Math.PI * 2, r = 1 + (rand(seed + i) - 0.5) * 0.35;
      d += `${i ? 'L' : 'M'}${f2(Math.cos(a) * w * r)} ${f2(Math.sin(a) * h * r)}`;
    }
    d += 'Z';
    let s = `<path d="${d}" fill="#bfe6f2" transform="scale(1.18)" opacity="0.7"/>` + sh(d, C.land, { depth: 10, w: 5 });
    s += [[-0.3, -0.2], [0.2, 0.1], [0.4, -0.3]].map(([px, py], i) => G(tf(px * w, py * h), sh(ellD(18, 12), C.mesquite, { depth: 4, w: 3 }))).join('');
    if (label) s += txt(0, labelY, label, size, C.cream, { stroke: INK, sw: 10 });
    return G(tf(x, y), s);
  }
  // modern factory with a sign; o: sign, sub, t, built (0..1 rises from the ground)
  function factory(x, y, o = {}) {
    const { sign = '', sub = '', built = 1, t = 0, w = 640 } = o;
    const hh = 300 * built;
    let s = '';
    if (built > 0.02) {
      s += sh(`M${-w / 2} 0 L${-w / 2} ${-hh} L${w / 2} ${-hh} L${w / 2} 0 Z`, '#dfe6ea', { depth: 14, w: 5 });
      for (let k = 0; k < 4; k++) s += sh(`M${-w / 2 + k * w / 4} ${-hh} l${w / 8} -60 l${w / 8} 60 Z`, '#c4cfd6', { depth: 5, w: 4.5 });
      for (let k = 0; k < 6; k++) s += `<rect x="${f2(-w / 2 + 30 + k * (w - 60) / 6)}" y="${f2(-hh + 60)}" width="${f2((w - 60) / 6 - 20)}" height="60" rx="6" fill="#9fd0ea" stroke="${INK}" stroke-width="3.5"/>`;
      s += `<rect x="-60" y="-120" width="120" height="120" fill="#8a96a0" stroke="${INK}" stroke-width="4"/>`;
    }
    if (sign && built > 0.6) s += G(tf(0, -hh - 110), `<rect x="-300" y="-46" width="600" height="92" rx="16" fill="${C.cream}" stroke="${INK}" stroke-width="6"/>` + txt(0, -4, sign, 40, INK) + txt(0, 32, sub, 26, '#6b5646', { weight: 600 }));
    return G(tf(x, y), s);
  }

  root.SW = { C, INK, G, tf, f2, ellD, sh, P, txt, textWidth, fly, fleck, maggot, eggMass, cow, dog, cat, adult, plane, dropBox, ranch, lab, sea, island, factory };
})(typeof window !== 'undefined' ? window : globalThis);
