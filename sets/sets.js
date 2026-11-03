// Set templates (original designs): functions of time returning an SVG background. Exposes `SETS`.
// draw(t, opts, W, H): portrait (1080x1920) is the original design; landscape (e.g. 1920x1080) has its own layout.
// floor: portrait floor line; floorAt(W, H): the floor for any frame size (where puppets' feet go).
(function (root) {
  const INK = '#24160e';
  const f2 = n => (+n).toFixed(1);
  const SETS = {
    plain: { floor: 1500, draw: (t, o = {}) => `<rect width="1080" height="1920" fill="${o.color || '#e6eef3'}"/><rect y="1500" width="1080" height="420" fill="${o.floor || '#d5dde2'}"/>` },
    none: { floor: 1500, draw: () => '' },   // transparent: the shot's depth planes (WP-36 comp) paint the world

    park: { floor: 1500, draw: (t) => {
      let s = `<rect width="1080" height="1920" fill="#dff0f7"/>`;
      for (const [x, y, r] of [[160, 300, 70], [700, 230, 90], [980, 420, 60]]) { const xx = ((x + t * 12) % 1300) - 110; s += `<g fill="#fff" opacity="0.9"><circle cx="${f2(xx)}" cy="${y}" r="${r}"/><circle cx="${f2(xx + r)}" cy="${y + 10}" r="${r * 0.8}"/><circle cx="${f2(xx - r)}" cy="${y + 14}" r="${r * 0.7}"/></g>`; }
      s += `<path d="M0 1260 C260 1200 520 1280 760 1230 C900 1205 1000 1220 1080 1210 L1080 1500 L0 1500 Z" fill="#b9d89a"/>`;
      for (const [x, h] of [[120, 300], [900, 360]]) s += `<rect x="${x - 14}" y="${1290 - h * 0.4}" width="28" height="${h * 0.45}" fill="#8a6040" stroke="${INK}" stroke-width="4"/><circle cx="${x}" cy="${1290 - h * 0.55}" r="${h * 0.32}" fill="#6fae4f" stroke="${INK}" stroke-width="5"/>`;
      s += `<rect y="1500" width="1080" height="420" fill="#cfe3b0"/><path d="M0 1500 L1080 1500" stroke="${INK}" stroke-width="5"/>`;
      for (let i = 0; i < 9; i++) s += `<ellipse cx="${(i * 170 + 40) % 1080}" cy="${1560 + (i % 3) * 90}" rx="40" ry="10" fill="#b9d394"/>`;
      return s; } },

    clinic: { floor: 1500, draw: (t) => {
      let s = `<rect width="1080" height="1920" fill="#c4d5e0"/>`;
      for (let i = 0; i < 7; i++) s += `<rect x="${i * 180 - 20}" y="0" width="176" height="1480" fill="none" stroke="#a9bccb" stroke-width="4"/>`;
      s += `<rect x="620" y="360" width="360" height="420" fill="#eef8ff" stroke="${INK}" stroke-width="6"/>`;
      for (let i = 0; i < 12; i++) s += `<rect x="628" y="${372 + i * 34}" width="344" height="20" rx="3" fill="#f8fcff" stroke="#9fb4c4" stroke-width="2"/>`;
      s += `<rect x="110" y="380" width="210" height="260" fill="#fffdf6" stroke="${INK}" stroke-width="5"/><circle cx="215" cy="460" r="48" fill="none" stroke="#e05a4f" stroke-width="7"/>`;
      s += `<rect y="1480" width="1080" height="26" fill="#eef2f5" stroke="${INK}" stroke-width="4"/><rect y="1500" width="1080" height="420" fill="#d8cfc2"/>`;
      for (let i = -4; i < 12; i++) s += `<path d="M${540 + i * 140} 1506 L${540 + i * 240} 1920" stroke="#bfb3a3" stroke-width="3"/>`;
      return s; } },

    // ruled notebook page (the Sheep & Pig look): rules every 78 px, a pink margin, fine grain, soft page shading
    paper: { floor: 1440, draw: (t, o = {}) => {
      let s = `<defs><filter id="grain"><feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="1" seed="3"/><feColorMatrix values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 0.06 0"/></filter>` +
        `<radialGradient id="pageshade" cx="50%" cy="50%" r="75%"><stop offset="0.6" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity="0.09"/></radialGradient></defs>`;
      s += `<rect width="1080" height="1920" fill="${o.color || '#f3f3ee'}"/>`;
      for (let y = 140; y < 1920; y += 78) s += `<rect x="0" y="${y}" width="1080" height="2" fill="#d6e0e8"/>`;
      if (o.margin !== false) s += `<rect x="86" y="0" width="2" height="1920" fill="#e2d0d0"/>`;
      return s + `<rect width="1080" height="1920" filter="url(#grain)"/><rect width="1080" height="1920" fill="url(#pageshade)"/>`; } },

    cutaway: { floor: 1100, draw: (t) => {
      let s = `<rect width="1080" height="1920" fill="#bfe3f2"/><rect y="1100" width="1080" height="820" fill="#8a5c3c"/><rect y="1100" width="1080" height="60" fill="#6fae4f"/>`;
      for (let i = 0; i < 40; i++) s += `<circle cx="${(i * 197) % 1080}" cy="${1200 + (i * 131) % 700}" r="${6 + (i % 4) * 3}" fill="#74492e"/>`;
      return s + `<path d="M0 1100 L1080 1100" stroke="${INK}" stroke-width="5"/>`; } },
  };
  // ---------- landscape layouts (16:9 and wider): composed for the frame, not cropped from portrait ----------
  const LAND = {
    plain: (t, o, W, H) => `<rect width="${W}" height="${H}" fill="${o.color || '#e6eef3'}"/><rect y="${H * 0.8}" width="${W}" height="${H * 0.2}" fill="${o.floor || '#d5dde2'}"/>`,
    none: () => '',
    park: (t, o, W, H) => {
      const fl = H * 0.8; let s = `<rect width="${W}" height="${H}" fill="#dff0f7"/>`;
      for (const [x, y, r] of [[200, 150, 60], [760, 110, 74], [1340, 170, 56], [1720, 120, 64]]) { const xx = ((x + t * 12) % (W + 240)) - 120; s += `<g fill="#fff" opacity="0.9"><circle cx="${f2(xx)}" cy="${y}" r="${r}"/><circle cx="${f2(xx + r)}" cy="${y + 10}" r="${r * 0.8}"/><circle cx="${f2(xx - r)}" cy="${y + 12}" r="${r * 0.7}"/></g>`; }
      s += `<path d="M0 ${fl - 200} C${W * 0.25} ${fl - 260} ${W * 0.5} ${fl - 170} ${W * 0.72} ${fl - 230} C${W * 0.86} ${fl - 255} ${W * 0.95} ${fl - 240} ${W} ${fl - 250} L${W} ${fl} L0 ${fl} Z" fill="#b9d89a"/>`;
      for (const [x, h] of [[150, 300], [560, 240], [1460, 330], [1800, 260]]) s += `<rect x="${x - 12}" y="${fl - 30 - h * 0.4}" width="24" height="${h * 0.42}" fill="#8a6040" stroke="${INK}" stroke-width="4"/><circle cx="${x}" cy="${fl - 30 - h * 0.55}" r="${h * 0.3}" fill="#6fae4f" stroke="${INK}" stroke-width="4"/>`;
      s += `<rect y="${fl}" width="${W}" height="${H - fl}" fill="#cfe3b0"/><path d="M0 ${fl} L${W} ${fl}" stroke="${INK}" stroke-width="5"/>`;
      for (let i = 0; i < 14; i++) s += `<ellipse cx="${(i * 157 + 40) % W}" cy="${fl + 40 + (i % 3) * 50}" rx="40" ry="9" fill="#b9d394"/>`;
      return s; },
    clinic: (t, o, W, H) => {
      const fl = H * 0.8; let s = `<rect width="${W}" height="${H}" fill="#c4d5e0"/>`;
      for (let i = 0; i < 12; i++) s += `<rect x="${i * 180 - 20}" y="0" width="176" height="${fl - 20}" fill="none" stroke="#a9bccb" stroke-width="4"/>`;
      s += `<rect x="${W - 520}" y="140" width="380" height="380" fill="#eef8ff" stroke="${INK}" stroke-width="6"/>`;
      for (let i = 0; i < 10; i++) s += `<rect x="${W - 512}" y="${152 + i * 36}" width="364" height="22" rx="3" fill="#f8fcff" stroke="#9fb4c4" stroke-width="2"/>`;
      s += `<rect x="140" y="160" width="230" height="270" fill="#fffdf6" stroke="${INK}" stroke-width="5"/><circle cx="255" cy="250" r="50" fill="none" stroke="#e05a4f" stroke-width="7"/>`;
      s += `<rect y="${fl - 20}" width="${W}" height="26" fill="#eef2f5" stroke="${INK}" stroke-width="4"/><rect y="${fl}" width="${W}" height="${H - fl}" fill="#d8cfc2"/>`;
      for (let i = -6; i < 16; i++) s += `<path d="M${W / 2 + i * 140} ${fl + 6} L${W / 2 + i * 200} ${H}" stroke="#bfb3a3" stroke-width="3"/>`;
      return s; },
    paper: (t, o, W, H) => {
      let s = `<defs><filter id="grain"><feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="1" seed="3"/><feColorMatrix values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 0.06 0"/></filter>` +
        `<radialGradient id="pageshade" cx="50%" cy="50%" r="75%"><stop offset="0.6" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity="0.09"/></radialGradient></defs>`;
      s += `<rect width="${W}" height="${H}" fill="${o.color || '#f3f3ee'}"/>`;
      for (let y = 90; y < H; y += 60) s += `<rect x="0" y="${y}" width="${W}" height="2" fill="#d6e0e8"/>`;
      if (o.margin !== false) s += `<rect x="120" y="0" width="2" height="${H}" fill="#e2d0d0"/>`;
      return s + `<rect width="${W}" height="${H}" filter="url(#grain)"/><rect width="${W}" height="${H}" fill="url(#pageshade)"/>`; },
    cutaway: (t, o, W, H) => {
      const fl = H * 0.55; let s = `<rect width="${W}" height="${H}" fill="#bfe3f2"/><rect y="${fl}" width="${W}" height="${H - fl}" fill="#8a5c3c"/><rect y="${fl}" width="${W}" height="40" fill="#6fae4f"/>`;
      for (let i = 0; i < 50; i++) s += `<circle cx="${(i * 197) % W}" cy="${fl + 70 + (i * 131) % (H - fl - 80)}" r="${6 + (i % 4) * 3}" fill="#74492e"/>`;
      return s + `<path d="M0 ${fl} L${W} ${fl}" stroke="${INK}" stroke-width="5"/>`; },
  };
  const FLOOR_FRAC = { plain: 0.8, none: 0.8, park: 0.8, clinic: 0.8, paper: 0.8, cutaway: 0.55 };
  for (const [k, set] of Object.entries(SETS)) {
    const portrait = set.draw;
    set.draw = (t, o = {}, W = 1080, H = 1920) => (H >= W ? portrait(t, o) : LAND[k](t, o, W, H));
    set.floorAt = (W = 1080, H = 1920) => (H >= W ? set.floor : Math.round(H * FLOOR_FRAC[k]));
  }
  root.SETS = SETS;
})(typeof window !== 'undefined' ? window : globalThis);
