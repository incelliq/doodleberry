// Set templates (original designs): functions of time returning a 1080×1920 SVG background. Exposes `SETS`.
// Each set also names its floor line (`floor`), where puppets' feet go.
(function (root) {
  const INK = '#24160e';
  const f2 = n => (+n).toFixed(1);
  const SETS = {
    plain: { floor: 1500, draw: (t, o = {}) => `<rect width="1080" height="1920" fill="${o.color || '#e6eef3'}"/><rect y="1500" width="1080" height="420" fill="${o.floor || '#d5dde2'}"/>` },

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
  root.SETS = SETS;
})(typeof window !== 'undefined' ? window : globalThis);
