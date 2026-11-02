// More sets (plan 1.6), original designs drawn in code. Each is aspect-independent: draw(t, opts, W, H) composes the
// set for the frame (portrait 1080x1920, landscape 1920x1080, square), floorAt(W, H) gives the floor line.
// Mostly static, with a little life so holds never freeze (clouds, stars, steam, water). Registers into SETS.
(function (root) {
  const INK = '#24160e', f1 = n => (+n).toFixed(1);
  const rng = seed => { let a = (seed | 0) * 2654435761 >>> 0 || 1; return () => { a ^= a << 13; a >>>= 0; a ^= a >> 17; a ^= a << 5; a >>>= 0; return a / 4294967296; }; };
  const R = (x, y, w, h, fill, extra = '') => `<rect x="${f1(x)}" y="${f1(y)}" width="${f1(w)}" height="${f1(h)}" fill="${fill}" ${extra}/>`;
  const RS = (x, y, w, h, fill, sw = 4, rx = 0) => R(x, y, w, h, fill, `stroke="${INK}" stroke-width="${sw}" rx="${rx}"`);
  const line = (x0, y0, x1, y1, c = INK, w = 4, op = 1) => `<path d="M${f1(x0)} ${f1(y0)} L${f1(x1)} ${f1(y1)}" stroke="${c}" stroke-width="${w}" opacity="${op}"/>`;
  const sky = (W, H, c1, c2) => `<defs><linearGradient id="skyg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${c1}"/><stop offset="1" stop-color="${c2}"/></linearGradient></defs>${R(0, 0, W, H, 'url(#skyg)')}`;
  const clouds = (t, W, H, n = 4, y0 = 0.08) => { const r = rng(5); let s = ''; for (let i = 0; i < n; i++) { const x = ((r() * W + t * (8 + r() * 10)) % (W + 300)) - 150, y = H * (y0 + r() * 0.12), k = 0.7 + r() * 0.6;
    s += `<g fill="#fff" opacity="0.92"><ellipse cx="${f1(x)}" cy="${f1(y)}" rx="${f1(70 * k)}" ry="${f1(34 * k)}"/><ellipse cx="${f1(x + 50 * k)}" cy="${f1(y - 18 * k)}" rx="${f1(50 * k)}" ry="${f1(32 * k)}"/><ellipse cx="${f1(x - 45 * k)}" cy="${f1(y + 4)}" rx="${f1(44 * k)}" ry="${f1(24 * k)}"/></g>`; } return s; };
  const floorBand = (W, H, fl, fill, stroke = true) => R(0, fl, W, H - fl, fill) + (stroke ? line(0, fl, W, fl, INK, 5) : '');
  const windowFrame = (x, y, w, h, view) => RS(x, y, w, h, '#cfe9f6', 6) + view + line(x + w / 2, y, x + w / 2, y + h, INK, 5) + line(x, y + h / 2, x + w, y + h / 2, INK, 5) + RS(x - 12, y + h, w + 24, 16, '#e9dfcf', 4);
  const pot = (x, y, s = 1) => `<path d="M${f1(x - 26 * s)} ${f1(y - 50 * s)} L${f1(x + 26 * s)} ${f1(y - 50 * s)} L${f1(x + 20 * s)} ${f1(y)} L${f1(x - 20 * s)} ${f1(y)} Z" fill="#c8693f" stroke="${INK}" stroke-width="4"/>` +
    [[-30, -110], [0, -130], [28, -105], [-14, -90], [16, -84]].map(([dx, dy]) => `<ellipse cx="${f1(x + dx * s)}" cy="${f1(y + dy * s)}" rx="${f1(16 * s)}" ry="${f1(30 * s)}" fill="#5d9e52" stroke="${INK}" stroke-width="3" transform="rotate(${dx * 0.8} ${f1(x + dx * s)} ${f1(y + dy * s)})"/>`).join('');

  const MORE = {
    kitchen: { frac: 0.78, draw: (t, o, W, H, fl) => {
      let s = R(0, 0, W, fl, o.wall || '#f2e6cf');
      for (let y = fl * 0.42; y < fl * 0.62; y += 46) for (let x = 0; x < W; x += 46) s += R(x + 2, y + 2, 42, 42, (Math.round(x / 46 + y / 46) % 2) ? '#e3efe9' : '#f7fbf9');
      s += windowFrame(W * 0.58, fl * 0.12, Math.min(W * 0.3, 340), fl * 0.26, clouds(t, W, H, 2, 0.06));
      const cw = W, ch = fl * 0.24, cy = fl - ch;
      s += RS(-10, cy - 22, cw + 20, 26, '#cfc4b3', 5) + R(0, cy + 4, W, ch, '#b97a4c');
      for (let x = 20; x < W - 120; x += 180) s += RS(x, cy + 24, 160, ch - 40, '#c98a5a', 4, 6) + `<circle cx="${f1(x + 140)}" cy="${f1(cy + ch / 2)}" r="7" fill="${INK}"/>`;
      s += RS(W * 0.06, fl * 0.24, 230, fl * 0.5 - fl * 0.24 + cy - fl * 0.5 - 20, '#eef3f6', 5, 16) + line(W * 0.06, fl * 0.44, W * 0.06 + 230, fl * 0.44);
      s += RS(W * 0.3, fl * 0.3, 240, 18, '#a8714a', 4) + [0, 1, 2].map(i => RS(W * 0.3 + 20 + i * 76, fl * 0.3 - 70, 52, 70, ['#f2c14e', '#d9534f', '#7fb069'][i], 4, 8)).join('');
      // steam from a kettle on the counter
      const kx = W * 0.72, ky = cy - 22;
      s += `<path d="M${f1(kx - 50)} ${f1(ky)} Q${f1(kx - 50)} ${f1(ky - 90)} ${f1(kx)} ${f1(ky - 90)} Q${f1(kx + 50)} ${f1(ky - 90)} ${f1(kx + 50)} ${f1(ky)} Z" fill="#7aa6c2" stroke="${INK}" stroke-width="5"/>`;
      for (let i = 0; i < 3; i++) { const u = ((t * 0.6 + i / 3) % 1); s += `<circle cx="${f1(kx + 60 + Math.sin(u * 6 + i) * 10)}" cy="${f1(ky - 90 - u * 120)}" r="${f1(10 + u * 14)}" fill="#fff" opacity="${f1(0.7 * (1 - u))}"/>`; }
      s += floorBand(W, H, fl, '#d7c3a4');
      for (let x = -200; x < W + 200; x += 120) s += line(x, fl, x - (x - W / 2) * 0.6, H, '#c2ad8d', 3);
      return s; } },

    classroom: { frac: 0.8, draw: (t, o, W, H, fl) => {
      let s = R(0, 0, W, fl, o.wall || '#e9e2c9');
      const bw = Math.min(W * 0.86, 1300), bh = fl * 0.34, bx = (W - bw) / 2, by = fl * 0.12;
      s += RS(bx - 16, by - 16, bw + 32, bh + 32, '#9b6b43', 6) + R(bx, by, bw, bh, '#2f4f3e');
      (o.board || []).forEach((txt, i) => { s += `<text x="${f1(bx + 40)}" y="${f1(by + 150 + i * 66)}" font-family="'Patrick Hand','Noto Sans Sinhala',sans-serif" font-size="56" fill="#f2f2e8" opacity="0.92">${String(txt).replace(/[<&]/g, '')}</text>`; });
      s += RS(bx, by + bh + 16, bw, 14, '#b88a5f', 3);
      const cx = W - 110, cy = by + bh + 120; s += `<circle cx="${cx}" cy="${cy}" r="56" fill="#fff" stroke="${INK}" stroke-width="5"/>` + line(cx, cy, cx, cy - 36) + line(cx, cy, cx + 28 * Math.cos(t * 0.5), cy + 28 * Math.sin(t * 0.5), '#c0392b', 4);
      s += floorBand(W, H, fl, '#c9b08d');
      for (let row = 0; row < 2; row++) for (let x = W * 0.08; x < W - 160; x += Math.max(260, W / 4)) {
        const y = fl + 60 + row * (H - fl) * 0.38; s += RS(x, y, 200, 26, '#c98a5a', 4, 4) + line(x + 20, y + 26, x + 20, y + 90) + line(x + 180, y + 26, x + 180, y + 90); }
      return s; } },

    office: { frac: 0.8, draw: (t, o, W, H, fl) => {
      let s = R(0, 0, W, fl, o.wall || '#dfe6ec');
      const ww = Math.min(W * 0.5, 820), wh = fl * 0.42, wx = W - ww - W * 0.06, wy = fl * 0.1, r = rng(9);
      let city = R(wx, wy, ww, wh, '#bfe0f2') + clouds(t, W, H, 2, 0.05);
      for (let x = wx; x < wx + ww; x += 70) { const bh = wh * (0.3 + r() * 0.5); city += R(x, wy + wh - bh, 62, bh, '#8ea9bb'); for (let yy = wy + wh - bh + 14; yy < wy + wh - 10; yy += 26) city += R(x + 10, yy, 14, 12, '#f6e7a8') + R(x + 36, yy, 14, 12, '#f6e7a8'); }
      s += RS(wx, wy, ww, wh, 'none', 7) + city;
      for (let y = wy; y < wy + wh * 0.3; y += 16) s += line(wx, y, wx + ww, y, '#9fb1bf', 3, 0.7);
      s += RS(W * 0.05, fl * 0.18, 220, fl * 0.62, '#b08a64', 5) + [0, 1, 2, 3].map(i => line(W * 0.05, fl * 0.18 + (i + 1) * fl * 0.124, W * 0.05 + 220, fl * 0.18 + (i + 1) * fl * 0.124)).join('');
      for (let i = 0; i < 4; i++) for (let j = 0; j < 5; j++) s += R(W * 0.05 + 14 + j * 40, fl * 0.18 + i * fl * 0.124 + 18, 30, fl * 0.124 - 22, ['#d9534f', '#5b8def', '#f2c14e', '#7fb069', '#a57fc2'][(i + j) % 5], `stroke="${INK}" stroke-width="2"`);
      s += floorBand(W, H, fl, '#9aa7b0') + pot(W * 0.38, fl, 1.2);
      return s; } },

    street: { frac: 0.82, draw: (t, o, W, H, fl) => {
      let s = sky(W, H, '#bfe6f7', '#eaf6fb') + clouds(t, W, H, 4, 0.05);
      const r = rng(21); let x = -20;
      while (x < W + 20) { const bw = 160 + r() * 140, bh = fl * (0.35 + r() * 0.35), col = ['#e8b77a', '#d98e73', '#a9c4a0', '#9fb8d6', '#e3d2a8'][Math.floor(r() * 5)];
        s += RS(x, fl - 120 - bh, bw, bh + 120, col, 5);
        for (let yy = fl - bh - 90; yy < fl - 170; yy += 90) for (let xx = x + 24; xx < x + bw - 50; xx += 64) s += RS(xx, yy, 38, 52, '#f4f1de', 3);
        s += RS(x + bw / 2 - 26, fl - 110, 52, 110, '#7a5236', 4); x += bw; }
      s += R(0, fl - 10, W, 30, '#c9c9c4') + line(0, fl - 10, W, fl - 10, INK, 4);
      s += R(0, fl + 20, W, H - fl - 20, '#6b6f75');
      for (let xx = -((t * 0) % 160); xx < W; xx += 160) s += R(xx, fl + 20 + (H - fl - 20) / 2 - 6, 90, 12, '#f2f2ea');
      for (const lx of [W * 0.15, W * 0.85]) s += line(lx, fl - 10, lx, fl - 330, INK, 8) + `<circle cx="${f1(lx)}" cy="${f1(fl - 340)}" r="22" fill="#f6e7a8" stroke="${INK}" stroke-width="4"/>`;
      return s; } },

    farm: { frac: 0.74, draw: (t, o, W, H, fl) => {
      let s = sky(W, H, '#bfe6f7', '#f2f8e8') + `<circle cx="${f1(W * 0.82)}" cy="${f1(H * 0.1)}" r="70" fill="#f9d65c"/>` + clouds(t, W, H, 3, 0.06);
      s += `<path d="M0 ${f1(fl - 160)} C${f1(W * 0.3)} ${f1(fl - 260)} ${f1(W * 0.6)} ${f1(fl - 120)} ${f1(W)} ${f1(fl - 210)} L${f1(W)} ${f1(fl)} L0 ${f1(fl)} Z" fill="#a8cf86"/>`;
      const bx = W * 0.08, bw = Math.min(300, W * 0.28), bh = 230, by = fl - bh;
      s += `<path d="M${f1(bx - 20)} ${f1(by)} L${f1(bx + bw / 2)} ${f1(by - 120)} L${f1(bx + bw + 20)} ${f1(by)} Z" fill="#8c2f24" stroke="${INK}" stroke-width="5"/>` + RS(bx, by, bw, bh, '#c0392b', 5) + RS(bx + bw / 2 - 50, by + 80, 100, 150, '#f4ead5', 4) + line(bx + bw / 2 - 50, by + 80, bx + bw / 2 + 50, by + 230, INK, 4) + line(bx + bw / 2 + 50, by + 80, bx + bw / 2 - 50, by + 230, INK, 4);
      for (let x = 0; x < W; x += 70) s += line(x, fl - 70, x, fl, '#8a6040', 8) ; s += line(0, fl - 56, W, fl - 56, '#8a6040', 7) + line(0, fl - 26, W, fl - 26, '#8a6040', 7);
      s += floorBand(W, H, fl, '#b98c5a');
      for (let y = fl + 50; y < H; y += 90) { s += line(0, y, W, y, '#9d7146', 10); for (let x = 30; x < W; x += 110) s += `<path d="M${f1(x)} ${f1(y - 6)} q-14 -30 0 -44 q14 14 0 44" fill="#6fae4f" stroke="${INK}" stroke-width="2"/>`; }
      return s; } },

    bedroom: { frac: 0.8, draw: (t, o, W, H, fl) => {
      const night = o.night ?? true;
      let s = R(0, 0, W, fl, o.wall || (night ? '#3d4a6b' : '#e8dff0'));
      const view = night ? R(W * 0.12, fl * 0.12, Math.min(W * 0.3, 360), fl * 0.3, '#1e2a4a') + `<circle cx="${f1(W * 0.12 + 80)}" cy="${f1(fl * 0.12 + 80)}" r="34" fill="#f4f1c9"/>` : clouds(t, W, H, 2, 0.07);
      s += windowFrame(W * 0.12, fl * 0.12, Math.min(W * 0.3, 360), fl * 0.3, view);
      const bx = W * 0.45, bw = Math.min(W * 0.5, 700);
      s += RS(bx, fl - 260, 40, 260, '#8a6040', 4) + RS(bx + 30, fl - 140, bw, 100, '#f1ece2', 4, 10) + RS(bx + 30, fl - 120, bw, 90, night ? '#6c7fb8' : '#e39ac0', 4, 10) + RS(bx + 50, fl - 170, 180, 50, '#fff', 4, 20);
      const lx = W * 0.08, ly = fl - 220; s += line(lx + 40, ly + 30, lx + 40, fl - 10, INK, 6) + `<path d="M${f1(lx)} ${f1(ly + 30)} L${f1(lx + 80)} ${f1(ly + 30)} L${f1(lx + 60)} ${f1(ly - 30)} L${f1(lx + 20)} ${f1(ly - 30)} Z" fill="#f6d77a" stroke="${INK}" stroke-width="4"/>`;
      if (night) s += `<circle cx="${f1(lx + 40)}" cy="${f1(ly + 10)}" r="${f1(180 + 6 * Math.sin(t * 2))}" fill="#f6e7a8" opacity="0.12"/>`;
      s += floorBand(W, H, fl, night ? '#5a4a3f' : '#c9a98a') + `<ellipse cx="${f1(W / 2)}" cy="${f1(fl + (H - fl) * 0.4)}" rx="${f1(W * 0.3)}" ry="${f1((H - fl) * 0.22)}" fill="${night ? '#7b5f8f' : '#d98e73'}" stroke="${INK}" stroke-width="4"/>`;
      return s; } },

    forest: { frac: 0.8, draw: (t, o, W, H, fl) => {
      let s = sky(W, H, '#cfe8e0', '#eef6ee');
      for (const [depth, col, n] of [[0.55, '#9cc8a6', 9], [0.7, '#6fae7f', 7], [0.85, '#4f8f5f', 6]]) { const r = rng(depth * 100);
        for (let i = 0; i < n; i++) { const x = r() * W, h = fl * depth * (0.5 + r() * 0.4), w = h * 0.38, base = fl - (1 - depth) * 120;
          s += `<path d="M${f1(x)} ${f1(base - h)} L${f1(x + w / 2)} ${f1(base)} L${f1(x - w / 2)} ${f1(base)} Z" fill="${col}" stroke="${INK}" stroke-width="${depth > 0.8 ? 4 : 0}"/>` + R(x - 8, base, 16, 30, '#7a5236'); } }
      s += floorBand(W, H, fl, '#8fbf6a') + `<path d="M${f1(W * 0.45)} ${f1(fl)} C${f1(W * 0.4)} ${f1(fl + (H - fl) * 0.5)} ${f1(W * 0.2)} ${f1(H * 0.98)} ${f1(W * 0.1)} ${f1(H)} L${f1(W * 0.9)} ${f1(H)} C${f1(W * 0.75)} ${f1(H * 0.98)} ${f1(W * 0.6)} ${f1(fl + (H - fl) * 0.5)} ${f1(W * 0.55)} ${f1(fl)} Z" fill="#d9c59a"/>`;
      return s; } },

    lab: { frac: 0.8, draw: (t, o, W, H, fl) => {
      let s = R(0, 0, W, fl, o.wall || '#dbe8ee');
      for (let x = 0; x < W; x += 120) s += line(x, 0, x, fl, '#c6d6de', 3);
      const by = fl - 200; s += RS(-10, by, W + 20, 30, '#e9eef1', 5) + R(0, by + 30, W, 170, '#a8b8c2') ;
      [[0.15, '#5bc0de'], [0.3, '#f0ad4e'], [0.62, '#5cb85c'], [0.78, '#d9534f']].forEach(([fx, c], i) => { const x = W * fx, y = by;
        s += `<path d="M${f1(x - 18)} ${f1(y - 120)} L${f1(x - 18)} ${f1(y - 70)} L${f1(x - 55)} ${f1(y)} L${f1(x + 55)} ${f1(y)} L${f1(x + 18)} ${f1(y - 70)} L${f1(x + 18)} ${f1(y - 120)} Z" fill="#eef7fb" stroke="${INK}" stroke-width="4"/>` +
          `<path d="M${f1(x - 42)} ${f1(y - 22)} L${f1(x + 42)} ${f1(y - 22)} L${f1(x + 55)} ${f1(y)} L${f1(x - 55)} ${f1(y)} Z" fill="${c}"/>`;
        const u = (t * 0.8 + i * 0.37) % 1; s += `<circle cx="${f1(x + Math.sin(u * 9) * 6)}" cy="${f1(y - 20 - u * 130)}" r="${f1(5 + u * 4)}" fill="${c}" opacity="${f1(0.8 * (1 - u))}"/>`; });
      s += RS(W * 0.4, fl * 0.12, Math.min(W * 0.4, 520), fl * 0.32, '#203040', 6, 10);
      for (let i = 0; i < 6; i++) s += line(W * 0.42, fl * 0.16 + i * 34, W * 0.42 + (120 + ((i * 97 + Math.floor(t * 2) * 13) % 260)), fl * 0.16 + i * 34, '#6ee7b7', 6, 0.9);
      s += floorBand(W, H, fl, '#c7d3da');
      return s; } },

    night: { frac: 0.82, draw: (t, o, W, H, fl) => {
      let s = sky(W, H, '#0e1633', '#2a3a6b'); const r = rng(33);
      for (let i = 0; i < 120; i++) { const x = r() * W, y = r() * fl * 0.9, b = 0.4 + 0.6 * Math.abs(Math.sin(t * (0.6 + r()) + i)); s += `<circle cx="${f1(x)}" cy="${f1(y)}" r="${f1(1.2 + r() * 2.2)}" fill="#fff" opacity="${f1(b)}"/>`; }
      s += `<circle cx="${f1(W * 0.75)}" cy="${f1(H * 0.15)}" r="80" fill="#f4f1c9"/><circle cx="${f1(W * 0.75 + 30)}" cy="${f1(H * 0.15 - 14)}" r="70" fill="#1b2650"/>`;
      s += `<path d="M0 ${f1(fl - 140)} C${f1(W * 0.3)} ${f1(fl - 220)} ${f1(W * 0.7)} ${f1(fl - 90)} ${f1(W)} ${f1(fl - 170)} L${f1(W)} ${f1(fl)} L0 ${f1(fl)} Z" fill="#1f2b44"/>`;
      return s + floorBand(W, H, fl, '#18233a', false); } },

    // reservoir in cross-section: water held behind an earthen embankment (bund); opts.level 0..1, opts.side 'left'|'right'
    reservoir: { frac: 0.82, draw: (t, o, W, H, fl) => {
      let s = sky(W, H, o.paper ? '#efe7d6' : '#cfe8f3', o.paper ? '#f4eedf' : '#eef6f8') + (o.paper ? '' : clouds(t, W, H, 2, 0.06));
      const crest = fl - (H > W ? 560 : 420), bundL = W * 0.42, bundR = W * 0.72, top = 90;
      const lvl = crest + (1 - (o.level ?? 0.75)) * (fl - crest - 40);
      const toe = bundL - 260, slopeX = y => toe + 260 * (fl - y) / (fl - crest);   // upstream face of the bund
      const ph = t * 2, xEnd = slopeX(lvl), wave = []; for (let i = 0; i <= 16; i++) { const x = xEnd * i / 16; wave.push([x, lvl + Math.sin(x * 0.02 + ph) * 5]); }
      s += `<path d="M0 ${f1(fl)} L${wave.map(p => f1(p[0]) + ' ' + f1(p[1])).join(' L')} L${f1(xEnd)} ${f1(lvl)} L${f1(toe)} ${f1(fl)} Z" fill="${o.water || '#5aa7d6'}" opacity="0.9"/>`;
      s += `<path d="M${f1(bundL - 260)} ${f1(fl)} L${f1(bundL)} ${f1(crest)} L${f1(bundL + top)} ${f1(crest)} L${f1(bundR + 200)} ${f1(fl)} Z" fill="${o.earth || '#b38b5d'}" stroke="${INK}" stroke-width="5"/>`;
      const r = rng(4); for (let i = 0; i < 30; i++) { const u = r(), v = r(); const y = crest + v * (fl - crest), xl = bundL - 260 * v, xr = bundL + top + (bundR + 200 - bundL - top) * v; s += `<ellipse cx="${f1(xl + u * (xr - xl))}" cy="${f1(y)}" rx="${f1(5 + r() * 8)}" ry="${f1(4 + r() * 5)}" fill="#00000022"/>`; }
      s += floorBand(W, H, fl, o.ground || '#8f6a45');
      return s; } },

    stage: { frac: 0.8, draw: (t, o, W, H, fl) => {
      const L = o.light || '#fff3cf', cx = W / 2, top = W * 0.06, bot = Math.min(W, H) * 0.36, flick = 0.82 + 0.05 * Math.sin(t * 1.3);
      let s = `<defs><linearGradient id="beam" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${L}" stop-opacity="0.55"/><stop offset="1" stop-color="${L}" stop-opacity="0.12"/></linearGradient>` +
        `<radialGradient id="pool" cx="50%" cy="50%" r="50%"><stop offset="0" stop-color="${L}" stop-opacity="0.55"/><stop offset="1" stop-color="${L}" stop-opacity="0"/></radialGradient></defs>`;
      s += R(0, 0, W, H, o.color || '#2b2f45') + floorBand(W, H, fl, '#3a3f5c', false);
      s += `<path d="M${f1(cx - top)} 0 L${f1(cx + top)} 0 L${f1(cx + bot)} ${f1(fl)} L${f1(cx - bot)} ${f1(fl)} Z" fill="url(#beam)" opacity="${f1(flick)}"/>`;
      return s + `<ellipse cx="${f1(cx)}" cy="${f1(fl + 20)}" rx="${f1(bot * 1.15)}" ry="${f1(Math.max(40, (H - fl) * 0.22))}" fill="url(#pool)"/>`; } },
  };

  const SETS = root.SETS = root.SETS || {};
  for (const [k, v] of Object.entries(MORE)) {
    SETS[k] = { floor: Math.round(1920 * v.frac), frac: v.frac,
      draw: (t, o = {}, W = 1080, H = 1920) => v.draw(t, o || {}, W, H, Math.round(H * v.frac)),
      floorAt: (W = 1080, H = 1920) => Math.round(H * v.frac) };
  }
})(typeof window !== 'undefined' ? window : globalThis);
