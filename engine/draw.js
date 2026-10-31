// Richer drawing primitives for code-drawn cartoons: cel shading, tapered
// strokes, glossy eyes and spheres, branching roots, soft clouds, depth blur,
// wind and soil crumbs. Pure functions of their arguments (seeded, no clocks).
// Loaded after timeline.js; exposes `D`. Call D.begin() at the start of each
// frame and include D.defs() once in the frame's SVG.
(function (root) {
  const { clamp, lerp, noise, rand } = root.M;
  const f2 = n => (+n).toFixed(2);
  let uid = 0;
  const filters = new Set();
  const gradients = new Map();

  // ---------- colour ----------
  const hex = h => [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16));
  const mix = (a, b, t) => {
    const A = hex(a), B = hex(b);
    return '#' + A.map((v, i) => Math.round(lerp(v, B[i], clamp(t))).toString(16).padStart(2, '0')).join('');
  };
  // hue-shifted shading: shadows lean cool, light leans warm (reads richer than darker/lighter)
  const shadowOf = (c, k = 1) => mix(mix(c, '#2a3270', 0.22 * k), '#000000', 0.12 * k);
  const lightOf = (c, k = 1) => mix(c, '#fff6cf', 0.45 * k);

  // per-frame ids restart each frame; art built once (cached) uses its own namespace so ids never collide
  let ns = 'f';
  // frame tag goes into filter ids: the browser caches a filter's result by id, so an id reused
  // across frames freezes the filtered layer until the id changes, then it jumps
  let ftag = '';
  function begin(tag = '') { uid = 0; ftag = String(tag); filters.clear(); gradients.clear(); }
  const id = p => `${ns}${p}${++uid}`;
  function prebuilt(name, fn) {
    const [pns, puid] = [ns, uid];
    ns = `p${name}`; uid = 0;
    try { return fn(); } finally { ns = pns; uid = puid; }
  }

  // ---------- defs ----------
  function blurFilter(sd) {
    const k = `blur${ftag}_${Math.round(sd * 100)}`;
    filters.add(`<filter id="${k}" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="${f2(sd)}"/></filter>`);
    return `url(#${k})`;
  }
  function radial(stops, { cx = 0.38, cy = 0.32, r = 0.75 } = {}) {
    const key = JSON.stringify([stops, cx, cy, r]);
    if (!gradients.has(key)) {
      const k = `rg${gradients.size}`;
      gradients.set(key, { k, svg: `<radialGradient id="${k}" cx="${cx}" cy="${cy}" r="${r}">${stops.map(([o, c, a = 1]) => `<stop offset="${o}" stop-color="${c}" stop-opacity="${a}"/>`).join('')}</radialGradient>` });
    }
    return `url(#${gradients.get(key).k})`;
  }
  function linear(stops, { x1 = 0, y1 = 0, x2 = 0, y2 = 1 } = {}) {
    const key = JSON.stringify(['l', stops, x1, y1, x2, y2]);
    if (!gradients.has(key)) {
      const k = `lg${gradients.size}`;
      gradients.set(key, { k, svg: `<linearGradient id="${k}" x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}">${stops.map(([o, c, a = 1]) => `<stop offset="${o}" stop-color="${c}" stop-opacity="${a}"/>`).join('')}</linearGradient>` });
    }
    return `url(#${gradients.get(key).k})`;
  }
  const defs = () => `<defs>${[...filters].join('')}${[...gradients.values()].map(g => g.svg).join('')}</defs>`;

  // ---------- shading ----------
  // Cel-shade a closed path: base fill, a cool shadow crescent on the side away
  // from the light, a warm rim light on the lit edge, then the ink outline.
  // dir: unit vector pointing away from the light (default: light from top-left).
  function shade(d, base, o = {}) {
    const { dir = [0.6, 0.8], depth = 10, light = 4, ink = '#3a2618', w = 5, shadow = shadowOf(base), lit = lightOf(base), glint = 0 } = o;
    const c = id('cs');
    let s = `<clipPath id="${c}"><path d="${d}"/></clipPath>`;
    s += `<path d="${d}" fill="${shadow}"/>`;
    s += `<g clip-path="url(#${c})"><path d="${d}" fill="${base}" transform="translate(${f2(-dir[0] * depth)} ${f2(-dir[1] * depth)})"/>`;
    if (light > 0) s += `<path d="${d}" fill="none" stroke="${lit}" stroke-width="${f2(light * 2)}" transform="translate(${f2(dir[0] * light)} ${f2(dir[1] * light)})" opacity="0.85"/>`;
    s += `</g>`;
    if (w > 0) s += `<path d="${d}" fill="none" stroke="${ink}" stroke-width="${w}" stroke-linejoin="round" stroke-linecap="round"/>`;
    if (glint) s += glintMark(glint.x, glint.y, glint.s || 1, glint.r || -30);
    return s;
  }
  // small specular glint: two rounded white dashes
  function glintMark(x, y, s = 1, r = -30) {
    return `<g transform="translate(${f2(x)} ${f2(y)}) rotate(${f2(r)}) scale(${f2(s)})">` +
      `<rect x="-3" y="-11" width="6" height="16" rx="3" fill="#fff" opacity="0.9"/><circle cx="0" cy="11" r="3" fill="#fff" opacity="0.9"/></g>`;
  }

  // ---------- strokes ----------
  function bez(p0, p1, p2, p3, n = 16) {
    const out = [];
    for (let i = 0; i <= n; i++) {
      const t = i / n, u = 1 - t;
      out.push([u * u * u * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t * t * t * p3[0],
        u * u * u * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t * t * t * p3[1]]);
    }
    return out;
  }
  // A filled stroke whose width runs from w0 to w1 along the points: veins,
  // root hairs, grass blades, brows, motion marks.
  function taperPath(pts, w0, w1, wfn = t => t) {
    const n = pts.length;
    const L = [0];
    for (let i = 1; i < n; i++) L.push(L[i - 1] + Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]));
    const tot = L[n - 1] || 1;
    const left = [], right = [];
    for (let i = 0; i < n; i++) {
      const a = pts[Math.max(0, i - 1)], b = pts[Math.min(n - 1, i + 1)];
      let nx = -(b[1] - a[1]), ny = b[0] - a[0];
      const m = Math.hypot(nx, ny) || 1;
      nx /= m; ny /= m;
      const w = lerp(w0, w1, wfn(L[i] / tot)) / 2;
      left.push([pts[i][0] + nx * w, pts[i][1] + ny * w]);
      right.push([pts[i][0] - nx * w, pts[i][1] - ny * w]);
    }
    const p = left.map(([x, y], i) => `${i ? 'L' : 'M'}${f2(x)} ${f2(y)}`).join('') +
      right.reverse().map(([x, y]) => `L${f2(x)} ${f2(y)}`).join('') + 'Z';
    return p;
  }
  const taper = (pts, w0, w1, fill, extra = '') => `<path d="${taperPath(pts, w0, w1)}" fill="${fill}" ${extra}/>`;
  // ink-outlined taper: ink underlay a little wider, colour on top
  const inkTaper = (pts, w0, w1, fill, ink = '#3a2618', iw = 3) =>
    taper(pts, w0 + iw * 2, Math.max(0.5, w1 + iw * 1.2), ink) + taper(pts, w0, w1, fill);

  // ---------- eyes, spheres ----------
  // Glossy cartoon eye. bl = blink 0..1, look in -1..1.
  function eye(x, y, o = {}) {
    const { rx = 14, ry = 17, lookX = 0, lookY = 0, bl = 0, ink = '#2a1a10', lid = '#5fb33d', w = 3.6, lidUp = 0, lidTilt = 0, lidLow = 0 } = o;
    const k = 1 - bl * 0.94;
    let s = `<g transform="translate(${f2(x)} ${f2(y)})">`;
    s += `<ellipse cx="0" cy="0" rx="${rx}" ry="${f2(ry * k)}" fill="${radial([[0, '#ffffff'], [0.62, '#ffffff'], [1, '#d6deea']], { cx: 0.42, cy: 0.38, r: 0.7 })}" stroke="${ink}" stroke-width="${w}"/>`;
    if (k > 0.35) {
      const px = lookX * rx * 0.42, py = lookY * ry * 0.38 + 1;
      const pr = rx * 0.56;
      s += `<circle cx="${f2(px)}" cy="${f2(py)}" r="${f2(pr)}" fill="${radial([[0, '#3a2a22'], [1, '#0d0806']], { cx: 0.4, cy: 0.35, r: 0.8 })}"/>`;
      s += `<circle cx="${f2(px + pr * 0.35)}" cy="${f2(py - pr * 0.38)}" r="${f2(pr * 0.34)}" fill="#fff"/>`;
      s += `<circle cx="${f2(px - pr * 0.35)}" cy="${f2(py + pr * 0.4)}" r="${f2(pr * 0.14)}" fill="#fff" opacity="0.85"/>`;
      // upper-lid shadow on the eyeball
      s += `<path d="M${-rx * 0.86} ${f2(-ry * k * 0.45)} Q0 ${f2(-ry * k * 1.05)} ${rx * 0.86} ${f2(-ry * k * 0.45)}" fill="none" stroke="#b9c6da" stroke-width="3" opacity="0.6"/>`;
    }
    if (bl > 0.05) s += `<path d="M${-rx} 0 Q0 ${f2(-ry * k * 1.3)} ${rx} 0" fill="${lid}" stroke="${ink}" stroke-width="${w * 0.8}" opacity="${f2(clamp(bl * 2))}"/>`;
    // attitude lids: upper lid comes down (tilted for angry/worried), lower lid rises for a smug squint
    if ((lidUp > 0.02 || lidLow > 0.02) && k > 0.35) {
      const c = id('el');
      const ty = Math.tan((lidTilt * Math.PI) / 180) * rx;
      const yU = -ry * k + 2 * ry * k * clamp(lidUp, 0, 0.95);
      const yLo = ry * k - 2 * ry * k * clamp(lidLow, 0, 0.6);
      s += `<clipPath id="${c}"><ellipse cx="0" cy="0" rx="${rx}" ry="${f2(ry * k)}"/></clipPath><g clip-path="url(#${c})">`;
      if (lidUp > 0.02) s += `<path d="M${-rx - 3} ${-ry - 6} L${rx + 3} ${-ry - 6} L${rx + 3} ${f2(yU + ty)} L${-rx - 3} ${f2(yU - ty)} Z" fill="${lid}"/>` +
        `<path d="M${-rx - 3} ${f2(yU - ty)} L${rx + 3} ${f2(yU + ty)}" stroke="${ink}" stroke-width="${w}"/>`;
      if (lidLow > 0.02) s += `<path d="M${-rx - 3} ${ry + 6} L${rx + 3} ${ry + 6} L${rx + 3} ${f2(yLo)} Q0 ${f2(yLo - 4)} ${-rx - 3} ${f2(yLo)} Z" fill="${lid}"/>` +
        `<path d="M${-rx - 3} ${f2(yLo)} Q0 ${f2(yLo - 4)} ${rx + 3} ${f2(yLo)}" fill="none" stroke="${ink}" stroke-width="${w * 0.8}"/>`;
      s += `</g><ellipse cx="0" cy="0" rx="${rx}" ry="${f2(ry * k)}" fill="none" stroke="${ink}" stroke-width="${w}"/>`;
    }
    return s + '</g>';
  }
  // shaded sphere (atoms, droplets, nodules)
  function sphere(x, y, r, base, o = {}) {
    const { ink = '#2a1a10', w = 4.5, spec = true } = o;
    let s = `<circle cx="${f2(x)}" cy="${f2(y)}" r="${f2(r)}" fill="${radial([[0, lightOf(base, 1.3)], [0.45, base], [1, shadowOf(base, 1.2)]], { cx: 0.36, cy: 0.32, r: 0.8 })}" stroke="${ink}" stroke-width="${w}"/>`;
    if (spec) s += `<ellipse cx="${f2(x - r * 0.36)}" cy="${f2(y - r * 0.4)}" rx="${f2(r * 0.26)}" ry="${f2(r * 0.17)}" transform="rotate(-30 ${f2(x - r * 0.36)} ${f2(y - r * 0.4)})" fill="#fff" opacity="0.85"/>`;
    return s;
  }

  // ---------- organic forms ----------
  // Fine rootlets branching off a main root (points), seeded. Returns ink+fill SVG.
  function rootlets(pts, seed, o = {}) {
    const { count = 7, len = 46, w = 3.2, fill = '#f3e6c4', ink = '#3a2618', depth = 2 } = o;
    let inkS = '', fillS = '';
    const grow = (x, y, ang, l, ww, d, sd) => {
      const p = [[x, y]];
      let a = ang, cx = x, cy = y;
      for (let i = 0; i < 6; i++) {
        a += (rand(sd + i * 3.7) - 0.5) * 0.5 + (Math.PI / 2 - a) * 0.08; // wander, bend downward
        cx += Math.cos(a) * l / 6; cy += Math.sin(a) * l / 6;
        p.push([cx, cy]);
      }
      inkS += taper(p, ww + 3.4, 1.2, ink);
      fillS += taper(p, ww, 0.4, fill);
      if (d > 0) for (let k = 0; k < 2; k++) {
        const at = p[2 + k * 2];
        grow(at[0], at[1], a + (k ? 0.9 : -0.9) * (0.6 + rand(sd + k) * 0.6), l * 0.5, ww * 0.6, d - 1, sd * 1.7 + k + 3);
      }
    };
    for (let i = 0; i < count; i++) {
      const j = 1 + Math.floor(rand(seed + i * 13) * (pts.length - 2));
      const [x, y] = pts[j], [px, py] = pts[j - 1];
      const along = Math.atan2(y - py, x - px);
      const side = rand(seed + i * 5) > 0.5 ? 1 : -1;
      grow(x, y, along + side * (0.7 + rand(seed + i) * 0.6), len * (0.6 + rand(seed + i * 2) * 0.7), w, depth, seed + i * 31);
    }
    return { ink: inkS, fill: fillS };
  }
  // Points of an SVG cubic path "M x y C x y x y x y [C ...]"
  function pathPts(d, n = 10) {
    const nums = d.match(/-?\d*\.?\d+/g).map(Number);
    const pts = [];
    let p0 = [nums[0], nums[1]];
    for (let i = 2; i + 5 < nums.length + 1; i += 6) {
      const seg = bez(p0, [nums[i], nums[i + 1]], [nums[i + 2], nums[i + 3]], [nums[i + 4], nums[i + 5]], n);
      pts.push(...(pts.length ? seg.slice(1) : seg));
      p0 = [nums[i + 4], nums[i + 5]];
    }
    return pts;
  }

  // Soft, slightly blurred cloud (blob union with a darker belly)
  function cloud(x, y, s, seed = 1, bodyCol = '#ffffff', bellyCol = '#dceef8') {
    const blobs = [[0, 0, 60], [-66, 16, 44], [64, 14, 48], [-26, -30, 44], [30, -34, 40], [100, 26, 30], [-100, 28, 28]];
    let body = '', belly = '';
    blobs.forEach(([bx, by, r], i) => {
      const rr = r * (0.9 + rand(seed + i) * 0.25);
      body += `<circle cx="${bx}" cy="${by}" r="${f2(rr)}" fill="${bodyCol}"/>`;
      belly += `<circle cx="${bx}" cy="${by + rr * 0.35}" r="${f2(rr * 0.8)}" fill="${bellyCol}"/>`;
    });
    // soften with a blur applied in screen space by the caller: a filter inside a group whose
    // scale animates is re-rasterised in steps and twitches
    return `<g transform="translate(${f2(x)} ${f2(y)}) scale(${f2(s)})">${belly}<g transform="translate(0 -8)">${body}</g></g>`;
  }

  // Wind: a gentle constant breeze plus gusts that travel left→right across the
  // field. Returns a lean in degrees for something at x (world) at time t.
  function wind(t, x, o = {}) {
    const { base = 1.2, gust = 4.5, every = 5.5, speed = 900 } = o;
    let g = 0;
    for (let k = -1; k <= 1; k++) {
      const t0 = (Math.floor(t / every) + k) * every + rand(Math.floor(t / every) + k) * 1.5;
      const d = t - t0 - (x + 400) / speed; // arrives later further right
      if (d > 0 && d < 1.6) g += Math.sin((d / 1.6) * Math.PI) ** 2;
    }
    return base * noise(x * 0.01, t * 0.7) + gust * g;
  }

  // Soil crumbs bursting from a point at t0 (ballistic, seeded)
  function crumbs(t, t0, x, y, o = {}) {
    const { n = 10, spread = 1, color = '#6b4428', seed = 3, up = 520 } = o;
    const d = t - t0;
    if (d < 0 || d > 1.1) return '';
    let s = '';
    for (let i = 0; i < n; i++) {
      const a = -Math.PI / 2 + (rand(seed + i) - 0.5) * 2.1 * spread;
      const v = up * (0.45 + rand(seed + i * 3) * 0.6);
      const px = x + Math.cos(a) * v * d, py = y + Math.sin(a) * v * d + 1100 * d * d;
      if (py > y + 6) continue;
      const r = 4 + rand(seed + i * 7) * 6;
      s += `<ellipse cx="${f2(px)}" cy="${f2(py)}" rx="${f2(r)}" ry="${f2(r * 0.8)}" fill="${color}" stroke="#3a2618" stroke-width="2" opacity="${f2(1 - d / 1.1)}"/>`;
    }
    return s;
  }
  // Emphasis "shock" marks: three short tapered strokes fanning out from a point
  function shock(x, y, ang, s = 1, color = '#ffd84a', ink = '#3a2618') {
    let out = '';
    [-0.5, 0, 0.5].forEach((da, i) => {
      const a = ang + da, r0 = 18, r1 = 46 + (i === 1 ? 10 : 0);
      const pts = [[Math.cos(a) * r0, Math.sin(a) * r0], [Math.cos(a) * r1, Math.sin(a) * r1]];
      out += taper(pts, 12, 6, ink) + taper(pts, 7, 3, color);
    });
    return `<g transform="translate(${f2(x)} ${f2(y)}) scale(${f2(s)})">${out}</g>`;
  }

  // Screen-space rain: seeded streaks falling at an angle, with splash ticks at groundY (screen).
  function rain(t, o = {}) {
    const { n = 90, speed = 2200, angle = 12, len = 70, alpha = 0.55, w = 1080, h = 1920, groundY = null, seed = 5, amount = 1 } = o;
    if (amount <= 0.01) return '';
    const dx = Math.tan((angle * Math.PI) / 180);
    let s = '';
    for (let i = 0; i < Math.round(n * amount); i++) {
      const sp = speed * (0.8 + rand(seed + i) * 0.4);
      const y0 = rand(seed + i * 3) * (h + 400), x0 = rand(seed + i * 7) * (w + 300) - 150;
      const y = ((y0 + t * sp) % (h + 400)) - 200;
      if (groundY !== null && y > groundY) {
        const k = (y - groundY) / 220;
        if (k < 1) s += `<ellipse cx="${f2(x0 + y * dx)}" cy="${f2(groundY + 4)}" rx="${f2(6 + k * 18)}" ry="${f2(2 + k * 4)}" fill="none" stroke="#dfeeff" stroke-width="2" opacity="${f2(alpha * (1 - k))}"/>`;
        continue;
      }
      const x = x0 + y * dx, l = len * (0.7 + rand(seed + i * 5) * 0.6);
      s += `<line x1="${f2(x)}" y1="${f2(y)}" x2="${f2(x - l * dx)}" y2="${f2(y - l)}" stroke="#e6f1ff" stroke-width="${f2(2 + rand(i) * 1.5)}" stroke-linecap="round" opacity="${f2(alpha * amount)}"/>`;
    }
    return s;
  }
  // Time-skip card: an iris opens onto a calendar flipping through months, then closes.
  function timeCard(t, t0, t1, o = {}) {
    if (t < t0 || t > t1) return '';
    const { text = 'MONTHS LATER…', months = ['JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV'], w = 1080, h = 1920, ink = '#2a1a10' } = o;
    const R = Math.hypot(w, h) / 2 + 20;
    const pin = clamp((t - t0) / 0.35), pout = clamp((t1 - t) / 0.35);
    const r = R * Math.min(root.M.ease.inOutCubic(pin), root.M.ease.inOutCubic(pout));
    const c = id('tc');
    let s = `<clipPath id="${c}"><circle cx="${w / 2}" cy="${h / 2}" r="${f2(r)}"/></clipPath><g clip-path="url(#${c})">`;
    s += `<rect width="${w}" height="${h}" fill="${linear([[0, '#1d5f63'], [1, '#2c2a6b']])}"/>`;
    // drifting leaves on a slow swirl
    for (let i = 0; i < 14; i++) {
      const a = rand(i + 3) * 6.28 + (t - t0) * (0.6 + rand(i) * 0.6), rr = 260 + rand(i + 9) * 520;
      const x = w / 2 + Math.cos(a) * rr, y = h / 2 + Math.sin(a) * rr * 1.3;
      const col = ['#f2a33a', '#e0603a', '#f7d04a', '#9bcf53'][i % 4];
      s += `<g transform="translate(${f2(x)} ${f2(y)}) rotate(${f2(a * 57 + i * 40)}) scale(${f2(0.8 + rand(i + 5) * 0.8)})">` +
        shade('M0 -30 C18 -18 18 14 0 30 C-18 14 -18 -18 0 -30 Z', col, { depth: 6, light: 2, w: 3, ink }) + '</g>';
    }
    // calendar: pages flip (squash to the hinge, swap the month, open again)
    const dur = t1 - t0, ph = clamp((t - t0 - 0.25) / Math.max(0.3, dur - 0.6)) * (months.length - 1);
    const i0 = Math.min(months.length - 1, Math.floor(ph)), fr = ph - i0;
    const flip = i0 < months.length - 1 ? Math.abs(Math.cos(fr * Math.PI)) : 1;
    const mon = fr < 0.5 || i0 === months.length - 1 ? months[i0] : months[i0 + 1];
    const cy = h / 2 - 120;
    s += `<g transform="translate(${w / 2} ${cy})">` + shade('M-200 -150 H200 V190 H-200 Z', '#fff7e6', { depth: 14, light: 4, w: 7, ink }) +
      shade('M-200 -150 H200 V-60 H-200 Z', '#e0603a', { depth: 8, light: 3, w: 7, ink }) +
      `<circle cx="-110" cy="-150" r="14" fill="${ink}"/><circle cx="110" cy="-150" r="14" fill="${ink}"/>` +
      `<g transform="translate(0 70) scale(1 ${f2(Math.max(0.05, flip))})"><text x="0" y="40" font-size="130" font-weight="700" fill="${ink}" text-anchor="middle">${mon}</text></g></g>`;
    s += `<text x="${w / 2}" y="${cy + 420}" font-size="96" font-weight="700" fill="#fff4c8" text-anchor="middle" stroke="${ink}" stroke-width="14" paint-order="stroke" stroke-linejoin="round">${text}</text>`;
    return s + '</g>' + (r < R - 2 ? `<circle cx="${w / 2}" cy="${h / 2}" r="${f2(r)}" fill="none" stroke="${ink}" stroke-width="16"/>` : '');
  }
  // Tall out-of-focus grass clumps for a foreground layer (draw inside a blurred wrapper).
  function fgGrass(x, baseY, hgt, seed, t = 0, colr = '#5d9f3a') {
    let s = '';
    for (let k = 0; k < 7; k++) {
      const bx = x + (rand(seed + k) - 0.5) * 120, hh = hgt * (0.6 + rand(seed + k * 3) * 0.5);
      const lean = (rand(seed + k * 5) - 0.5) * 60 + noise(seed + k, t * 0.8) * 14;
      const pts = bez([bx, baseY], [bx, baseY - hh * 0.4], [bx + lean * 0.5, baseY - hh * 0.8], [bx + lean, baseY - hh], 10);
      s += taper(pts, 38, 4, mix(colr, k % 2 ? '#2f5a20' : '#8fcf5a', 0.3));
    }
    return s;
  }
  root.D = { begin, prebuilt, defs, rain, timeCard, fgGrass, blurFilter, radial, linear, mix, shadowOf, lightOf, shade, glintMark, bez, taperPath, taper, inkTaper,
    eye, sphere, rootlets, pathPts, cloud, wind, crumbs, shock };
})(typeof window !== 'undefined' ? window : globalThis);
