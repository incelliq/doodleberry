// Model sheet (plan 1.4): one page showing a puppet in key poses and views, and every expression close up.
// Used by the Rig Canvas (Sheet button) and by `python -m dbe puppet.sheet` (tools/sheet.mjs). Exposes `Sheet`.
//   Sheet.build(puppet, clipLib) -> SVG string (1800 x 1100)
(function (root) {
  const W = 1800, H = 1100, esc = s => String(s).replace(/[<&]/g, '');
  function figure(p, pose, cx, baseY, s) { return Puppet.render(p, cx, baseY, { s, ...pose }); }
  function headCell(p, pose, x, y, w, h, label) {
    const hp = (p.parts.head && p.parts.head.pivot) || [p.artboard[0] / 2, 300];
    const hip = (p.parts.hip && p.parts.hip.pivot) || [p.artboard[0] / 2, p.ground];
    // render the puppet at its artboard origin and window the head region
    const vb = [hp[0] - 120, hp[1] - 190, 240, 230];
    return `<g><rect x="${x}" y="${y}" width="${w}" height="${h}" rx="10" fill="#fffdf7" stroke="#d8cfc0"/>` +
      `<svg x="${x + 4}" y="${y + 4}" width="${w - 8}" height="${h - 30}" viewBox="${vb.join(' ')}">${Puppet.render(p, hip[0], p.ground ?? p.artboard[1], { s: 1, ...pose })}</svg>` +
      `<text x="${x + w / 2}" y="${y + h - 9}" text-anchor="middle" font-family="Fredoka,sans-serif" font-size="15" fill="#5a4a3a">${esc(label)}</text></g>`;
  }
  function build(p, lib) {
    const L = lib || { clips: {}, presets: {} };
    let s = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}"><rect width="${W}" height="${H}" fill="#f6f1e6"/>`;
    s += `<text x="40" y="58" font-family="Fredoka,sans-serif" font-size="40" font-weight="700" fill="#24160e">${esc(p.name || 'Character')}</text>` +
      `<text x="40" y="88" font-family="Fredoka,sans-serif" font-size="18" fill="#7a6a5a">model sheet · template ${esc(p.template)} · ${Object.keys(p.parts).length} parts</text>`;
    // row 1: poses and views
    const poses = [['rest', {}]];
    if (L.clips.wave_R) poses.push(['wave', Acting.evaluate(p, { clips: [{ clip: 'wave_R', start: 0 }] }, 0.6, L.clips, L.presets)]);
    else if (L.clips.wave_L) poses.push(['wave', Acting.evaluate(p, { clips: [{ clip: 'wave_L', start: 0 }] }, 0.6, L.clips, L.presets)]);
    if (p.controls && p.controls.turn) { poses.push(['turn left', Acting.evaluate(p, { controls: { turn: [[0, -1]] }, blink: false }, 0, L.clips, L.presets)]);
      poses.push(['turn right', Acting.evaluate(p, { controls: { turn: [[0, 1]] }, blink: false }, 0, L.clips, L.presets)]); }
    for (const v of Object.keys(p.views || {})) poses.push([v + ' view', { view: v }]);
    const n = Math.min(poses.length, 5), colW = (W - 80) / Math.max(4, n), sc = Math.min(0.62, 560 / p.artboard[1]);
    poses.slice(0, 5).forEach(([label, pose], i) => {
      const cx = 40 + colW * (i + 0.5), base = 120 + p.artboard[1] * sc;
      s += `<line x1="${cx - colW * 0.4}" y1="${base}" x2="${cx + colW * 0.4}" y2="${base}" stroke="#d8cfc0" stroke-width="2"/>` + figure(p, { blink: 0, ...pose }, cx, base, sc) +
        `<text x="${cx}" y="${base + 30}" text-anchor="middle" font-family="Fredoka,sans-serif" font-size="18" fill="#5a4a3a">${esc(label)}</text>`;
    });
    // rows 2-3: expressions
    const cells = [];
    const sw = p.swaps || {};
    for (const k of Object.keys((sw.mouth || {}).shapes || {})) cells.push(['mouth ' + k, { mouth: k }]);
    for (const k of Object.keys((sw.brows || {}).shapes || {})) if (k !== 'neutral') cells.push(['brows ' + k, { brows: k }]);
    for (const k of ['half', 'closed']) if (sw.eyes && sw.eyes.shapes[k]) cells.push(['eyes ' + k, { eyes: k }]);
    if (sw.pupils) cells.push(['look left', { look: [-1, 0] }], ['look up', { look: [0.3, -1] }]);
    const cw = 160, ch = 170, perRow = Math.floor((W - 80) / (cw + 12)), y0 = H - 2 * (ch + 14) - 20;
    cells.slice(0, perRow * 2).forEach(([label, pose], i) => { const r = Math.floor(i / perRow), c = i % perRow; s += headCell(p, { blink: 0, ...pose }, 40 + c * (cw + 12), y0 + r * (ch + 14), cw, ch, label); });
    return s + '</svg>';
  }
  root.Sheet = { build };
})(typeof window !== 'undefined' ? window : globalThis);
