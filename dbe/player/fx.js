// Motion effects from the motion itself (plan 2.20): no hand placement. Enable per shot:
//   "fx": {"speed_lines": true | {"parts": ["hand_R", "hand_L", "head"], "min": 650, "color": "#181e26"},
//          "dust": true | {"min_drop": 14}, "impacts": true}
// - speed lines: three tapered strokes trailing a part whose speed (px/s in the frame) passes `min`
// - dust: puffs at the feet when a character lands (its hips stop after falling at least `min_drop` px)
// - impacts: a star burst where a prop arrives (caught or dropped at the end of its travel)
// Everything is computed from poses at this and earlier times, so any frame renders on its own.
(function () {
  const INK = '#181e26', f1 = n => (+n).toFixed(1), f3 = n => (+n).toFixed(3);
  const clamp = u => Math.min(1, Math.max(0, u));

  function speedLines(cfg, casts, pointAt, t) {
    const parts = cfg.parts || ['hand_R', 'hand_L'], min = cfg.min ?? 650, dt = 1 / 30;
    let out = '';
    casts.forEach((c, ci) => {
      for (const part of parts) {
        if (!c.p.parts[part]) continue;
        const pts = [0, 1, 2, 3, 4].map(k => pointAt(ci, part, t - k * dt)).filter(Boolean);
        if (pts.length < 4) continue;
        const v = Math.hypot(pts[0][0] - pts[1][0], pts[0][1] - pts[1][1]) / dt;
        if (v < min) continue;
        const k = clamp((v - min) / min), dx = pts[0][0] - pts[3][0], dy = pts[0][1] - pts[3][1], len = Math.hypot(dx, dy) || 1;
        const nx = -dy / len, ny = dx / len, gap = 14 * c.s;
        for (const off of [-1, 0, 1]) {
          const o = off * gap, a = [pts[1][0] + nx * o, pts[1][1] + ny * o], b = [pts[3][0] + nx * o - dx * 0.5, pts[3][1] + ny * o - dy * 0.5];
          out += `<path d="M${f1(a[0])} ${f1(a[1])} L${f1(b[0])} ${f1(b[1])}" stroke="${cfg.color || INK}" stroke-width="${f1((off ? 4 : 6) * c.s)}" stroke-linecap="round" opacity="${f3(0.25 + 0.5 * k)}"/>`;
        }
      }
    });
    return out;
  }

  function dust(cfg, casts, pointAt, t) {
    const dt = 1 / 30, minDrop = cfg.min_drop ?? 14, life = 0.45;
    let out = '';
    casts.forEach((c, ci) => {
      if (!c.p.parts.hip) return;
      const ys = []; for (let k = 0; k <= 22; k++) { const q = pointAt(ci, 'hip', t - k * dt); ys.push(q ? q[1] : null); }
      // the most recent landing: hips moving down (y up) then stopping, after a drop of minDrop
      for (let j = 1; j < 14; j++) {
        if (ys[j] == null || ys[j + 1] == null || ys[j - 1] == null) continue;
        const vin = ys[j] - ys[j + 1], vout = ys[j - 1] - ys[j];   // downward px per frame into and out of frame j
        const falling = vin > 3, stopped = vout < vin * 0.35;
        const high = Math.min(...ys.slice(j, j + 9).filter(v => v != null));
        if (falling && stopped && ys[j] - high >= minDrop) {
          const age = j * dt; if (age > life) break;
          const u = age / life, gx = c.x, gy = c.y + 4;
          for (const side of [-1, 1]) for (let i = 0; i < 3; i++) {
            const r = (10 + 26 * u) * c.s * (1 - i * 0.18), px = gx + side * (40 + i * 26 + 70 * u) * c.s, py = gy - (8 + i * 6) * c.s * u;
            out += `<ellipse cx="${f1(px)}" cy="${f1(py)}" rx="${f1(r * 1.4)}" ry="${f1(r)}" fill="${cfg.color || '#d8cdb8'}" stroke="${INK}" stroke-width="${f1(2.5 * c.s)}" opacity="${f3((1 - u) * 0.85)}"/>`;
          }
          break;
        }
      }
    });
    return out;
  }

  function impacts(cfg, props, propPos, t) {
    const life = 0.35;
    let out = '';
    for (const pr of props) {
      if (pr.impact === false) continue;
      const keys = pr.attach || [], travel = pr.travel ?? 0.35;
      for (let k = 1; k < keys.length; k++) {
        const age = t - (keys[k][0] + travel);
        if (age < 0 || age > life) continue;
        const pos = propPos(pr, t); if (!pos) continue;
        const u = age / life, R = (pr.r || 34) * (1.2 + 1.6 * u);
        for (let i = 0; i < 6; i++) {
          const a = i / 6 * Math.PI * 2 + 0.3, x = pos[0] + Math.cos(a) * R, y = pos[1] + Math.sin(a) * R, s = 9 * (1 - u * 0.6);
          out += `<path d="M${f1(x)} ${f1(y - s)} L${f1(x + s * 0.3)} ${f1(y - s * 0.3)} L${f1(x + s)} ${f1(y)} L${f1(x + s * 0.3)} ${f1(y + s * 0.3)} L${f1(x)} ${f1(y + s)} L${f1(x - s * 0.3)} ${f1(y + s * 0.3)} L${f1(x - s)} ${f1(y)} L${f1(x - s * 0.3)} ${f1(y - s * 0.3)}Z"` +
            ` fill="${cfg.color || '#f6c945'}" stroke="${INK}" stroke-width="2.5" opacity="${f3(1 - u)}"/>`;
        }
      }
    }
    return out;
  }

  function render(sh, t, ctx) {
    const fx = sh.fx || {}; let out = '';
    if (fx.speed_lines) out += speedLines(fx.speed_lines === true ? {} : fx.speed_lines, ctx.casts, ctx.pointAt, t);
    if (fx.dust) out += dust(fx.dust === true ? {} : fx.dust, ctx.casts, ctx.pointAt, t);
    if (fx.impacts) out += impacts(fx.impacts === true ? {} : fx.impacts, sh.props || [], ctx.propPos, t);
    return out;
  }
  window.FX = { render };
})();
