// Shot player: renders any frame of a shots.json film in the browser (the SVG renderer, background plates for the
// other renderers, and the interactive web export). Query: ?shot=<id> (render that shot) | ?bg=1 (set only) | none (whole film).
(function () {
  const S = window.SHOTS, T = window.TIMING || {}, PUP = window.PUPPETS || {}, LIB = (window.CLIPLIB || {}).humanoid || { clips: {}, presets: {} };
  const q = new URLSearchParams(location.search);
  const W = (S.size || [1080, 1920])[0], H = (S.size || [1080, 1920])[1], FPS = S.fps || 30;
  const stage = document.getElementById('stage');
  stage.setAttribute('viewBox', `0 0 ${W} ${H}`); stage.style.width = W + 'px'; stage.style.height = H + 'px';
  const words = (T.lines || []).flatMap(l => l.words.map(w => ({ ...w, speaker: l.speaker })));
  const shotAt = t => S.shots.reduce((a, s) => (t >= s.start ? s : a), S.shots[0]);
  const placeAt = (pl, t) => Array.isArray(pl) ? Acting.sampleKeys(pl.map(([k, v]) => [k, [v.x, v.y, v.s ?? 1, v.flip ?? 1]]), t) : [pl.x, pl.y, pl.s ?? 1, pl.flip ?? 1];

  function captions(t, style) {
    const w = words.filter(v => v.start <= t + 0.05 && v.end + 0.2 > t);
    if (!w.length) return '';
    const text = w.slice(-3).map(v => v.text.replace(/[.,?!]$/, '')).join(' ').toUpperCase();
    const size = 84, pw = Math.min(980, text.length * size * 0.58 + 80);
    return `<g transform="translate(${W / 2} ${H - 300})"><rect x="${-pw / 2}" y="${-size * 0.95}" width="${pw}" height="${size * 1.25}" rx="${size * 0.62}" fill="#1a0f08" fill-opacity="0.82"/>` +
      `<text x="0" y="0" font-size="${size}" font-weight="700" text-anchor="middle" fill="#fff" stroke="#24160e" stroke-width="12" paint-order="stroke" stroke-linejoin="round">${text}</text></g>`;
  }
  function frameAt(t, bgOnly) {
    const sh = shotAt(t);
    const set = (window.SETS || {})[sh.set || 'plain'] || window.SETS.plain;
    let world = set.draw(t, sh.set_opts || {});
    for (const c of sh.cast || []) {
      const p = PUP[c.puppet]; if (!p) continue;
      if (bgOnly) { // the set plate for other renderers keeps each character's ground shadow
        const [x, y, s] = placeAt(c.place || { x: W / 2, y: set.floor }, t);
        world += `<ellipse cx="${x}" cy="${y + 6}" rx="${120 * s}" ry="${14 * s}" fill="#000" opacity="0.12"/>`; continue;
      }
      const tl = { ...(c.timeline || {}) };
      if (tl.visemes_from) { tl.visemes = (T.visemes || {})[tl.visemes_from] || []; delete tl.visemes_from; }
      const pose = Acting.evaluate(p, tl, t, LIB.clips, LIB.presets);
      const [x, y, s, flip] = placeAt(c.place || { x: W / 2, y: set.floor }, t);
      world += `<ellipse cx="${x}" cy="${y + 6}" rx="${120 * s}" ry="${14 * s}" fill="#000" opacity="0.12"/>` + Puppet.render(p, x, y, { ...pose, s, flip });
    }
    let svg = world;
    if (sh.camera) { const [cx, cy, z] = Acting.sampleKeys(sh.camera, t) || [W / 2, H / 2, 1]; svg = `<g transform="translate(${W / 2} ${H / 2}) scale(${z}) translate(${-cx} ${-cy})">${world}</g>`; }
    // shot renders leave captions to the film-level pass (dbe/captions.py); the live web player draws them itself
    if (!bgOnly && !only && sh.captions !== false && S.captions !== false) svg += captions(t);
    return svg;
  }
  const only = q.get('shot') ? S.shots.find(s => s.id === q.get('shot')) : null;
  const bgOnly = q.get('bg') === '1';
  const t0 = only ? only.start : 0, t1 = only ? only.end : S.shots[S.shots.length - 1].end;
  window.FILMTIME = { start: t0, end: t1, fps: FPS };
  window.frameAtTime = t => { stage.innerHTML = frameAt(t, bgOnly); };
  window.renderFrame = f => window.frameAtTime(t0 + f / FPS);
  window.FRAMES = Math.round((t1 - t0) * FPS);
  window.FILM = { width: W, height: H, fps: FPS, frames: window.FRAMES, ready: false };
  (document.fonts ? document.fonts.load('700 40px Fredoka') : Promise.resolve()).then(() => { window.FILM.ready = true; window.ready = true; });
})();
