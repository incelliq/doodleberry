// Acting demo: one puppet, every acting feature, driven by a timeline (no hand-set angles per frame).
(function () {
  const P = window.PIP, LIB = window.CLIPLIB.humanoid, CLIPS = LIB.clips, PRE = LIB.presets;
  const T = window.TIMING, L = Object.fromEntries(T.lines.map(l => [l.id, l]));
  const at = (id, w) => { const x = L[id].words.find(v => v.text.toLowerCase().replace(/[^a-z']/g, '') === w); return x ? x.start : L[id].start; };
  const S = 0.95, WALK_END = 3.4, X0 = -60, X1 = 470, SPEED = (X1 - X0) / WALK_END; // scene px/s
  const tReach = at('point', 'grab'), tGot = L.yay.start;
  const TL = {
    clips: [
      { clip: 'idle', start: 0, weight: 1, fadeIn: 0 },
      { clip: 'walk', start: 0, end: WALK_END, weight: 1.6, fadeIn: 0, fadeOut: 0.3 },
      { clip: 'wave_R', start: at('hi', 'hi') - 0.3, end: at('hi', 'pip') + 0.3, weight: 2 },
      { clip: 'talk_beat', start: at('hi', 'walk') - 0.2, additive: true },
      { clip: 'talk_beat', start: at('hi', 'talk') - 0.2, additive: true },
      { clip: 'point_R', start: at('point', 'balloon') - 0.35, end: at('point', 'watch'), weight: 2 },
      { clip: 'nod', start: tGot + 0.3, additive: true },
    ],
    poses: [[0, 'neutral'], [tGot - 0.1, 'pip_cheer']],
    visemes: (T.visemes || {}).pip || [],
    look: [[0, [1, 0]], [at('point', 'balloon') - 0.3, [1, -0.8]], [tGot, [0, 0]]],
    ik: { arm_R: [[tReach - 0.6, null], [tReach, [520, 250]], [tGot - 0.15, [520, 250]]] },
    pins: { foot_L: true, foot_R: true }, travel: SPEED / S, springs: true,
  };
  // IK keys with null = off: strip them outside the reach window
  const ikAt = t => (t > tReach - 0.6 && t < tGot - 0.1) ? { arm_R: [[0, [lerpN(470, 520, (t - tReach + 0.6) / 0.6), lerpN(560, 250, (t - tReach + 0.6) / 0.6)]]] } : {};
  function lerpN(a, b, k) { k = Math.max(0, Math.min(1, k)); k = k * k * (3 - 2 * k); return a + (b - a) * k; }
  const END = L.yay.end + 1.6;
  function frame(f) {
    const t = f / 30;
    const x = t < WALK_END ? X0 + SPEED * t : X1, y = 1500;
    const pose = Acting.evaluate(P, { ...TL, ik: ikAt(t), pins: t < WALK_END ? TL.pins : null }, t, CLIPS, PRE);
    let s = `<rect width="1080" height="1920" fill="#dff0f7"/><rect y="1500" width="1080" height="420" fill="#cfe3b0"/><path d="M0 1500 L1080 1500" stroke="#24160e" stroke-width="5"/>`;
    for (let i = 0; i < 9; i++) s += `<ellipse cx="${(i * 170 + 40) % 1080}" cy="${1560 + (i % 3) * 90}" rx="40" ry="10" fill="#b9d394"/>`;
    // the balloon: floats until grabbed, then follows the hand
    const hand = Puppet.pointOf(P, 'hand_R', null, x, y, { ...pose, s: S });
    const got = t >= tReach;
    const bx = got ? hand[0] : 990 + Math.sin(t * 1.3) * 8, by = got ? hand[1] - 230 : 540 + Math.sin(t * 1.7) * 14;
    const sx = got ? hand[0] : 990, sy = got ? hand[1] : 900;
    s += `<path d="M${bx} ${by + 95} Q${(bx + sx) / 2 + 20} ${(by + sy) / 2} ${sx} ${sy}" fill="none" stroke="#24160e" stroke-width="3"/>`;
    s += `<ellipse cx="${bx}" cy="${by}" rx="70" ry="92" fill="#e2463a" stroke="#24160e" stroke-width="6"/><ellipse cx="${bx - 24}" cy="${by - 34}" rx="14" ry="22" fill="#fff" opacity="0.6"/>`;
    s += `<ellipse cx="${x}" cy="${y + 6}" rx="130" ry="16" fill="#000" opacity="0.12"/>`;
    s += Puppet.render(P, x, y, { ...pose, s: S });
    // caption: current viseme (debug strip) and words
    const w = T.lines.flatMap(l => l.words).filter(v => v.start <= t + 0.05 && v.end + 0.25 > t).map(v => v.text).slice(-3).join(' ').toUpperCase();
    if (w) s += `<g transform="translate(540 1720)"><rect x="-430" y="-80" width="860" height="110" rx="55" fill="#1a0f08" fill-opacity="0.82"/><text x="0" y="0" font-size="76" font-weight="700" fill="#fff" text-anchor="middle">${w}</text></g>`;
    s += `<text x="40" y="80" font-size="34" font-weight="600" fill="#24160e" opacity="0.6">mouth: ${pose.mouth || 'closed'}</text>`;
    return s;
  }
  const stage = document.getElementById('stage');
  window.renderFrame = f => { stage.innerHTML = frame(f); };
  window.CUES = [{ t: +(tReach).toFixed(3), type: 'pop', gain: 0.8 }, { t: +(tGot).toFixed(3), type: 'chime', gain: 0.7 }];
  window.FILM = { width: 1080, height: 1920, fps: 30, frames: Math.round(END * 30), ready: false };
  document.fonts.load('700 40px Fredoka').then(() => { window.FILM.ready = true; });
})();
