// Lineup of the human rig's wardrobe and hair options (a test sheet, not a film).
(function () {
  const H = window.Human, { blink } = M;
  const CAST = [
    { x: 200, y: 900, s: 0.62, o: { skin: 'fair', age: 'old', hair: { style: 'swept', color: 'white' }, top: { type: 'labcoat', shirt: '#2f6f5a' }, bottom: { color: '#23262e' }, acc: { glasses: true, stethoscope: true, tie: '#1f9a5a', badge: true, pen: true }, armL: { sh: 6, el: 10 }, armR: { sh: 10, el: 30 }, mood: 'smile', turn: 0.3 } },
    { x: 540, y: 900, s: 0.62, o: { skin: 'light', lashes: true, hair: { style: 'long', color: 'brown' }, top: { type: 'tank', color: '#f39ab8' }, bottom: { color: '#2b2b33' }, shoes: { color: '#f08aa8' }, acc: { watch: true }, pose: 'sit', armL: { sh: 4, el: 50 }, armR: { sh: 6, el: 55 }, mood: 'worried', turn: -0.3, lookX: -0.6 } },
    { x: 880, y: 900, s: 0.62, o: { skin: 'tan', kid: true, hair: { style: 'sidepart', color: 'black' }, top: { type: 'sweater', color: '#2f7fd6', accent: '#ffffff' }, bottom: { type: 'shorts', color: '#1e1e24' }, shoes: { color: '#e9e9ee' }, mood: 'surprised', armL: { sh: 12, el: 4 }, armR: { sh: 30, el: 40 } } },
    { x: 200, y: 1720, s: 0.62, o: { skin: 'brown', hair: { style: 'buzz', color: 'black' }, top: { type: 'shirt', color: '#5a9be0', accent: '#eaf2ff' }, bottom: { color: '#3c5a8a' }, acc: { hat: 'straw', beard: true }, mood: 'talk-happy', talk: 0.6, armL: { sh: 8, el: 6 }, armR: { sh: 40, el: 60 } } },
    { x: 540, y: 1720, s: 0.62, o: { skin: 'deep', lashes: true, hair: { style: 'bun', color: 'black' }, top: { type: 'scrubs', color: '#4fb0b8' }, bottom: { color: '#4fb0b8' }, shoes: { color: '#f2f2f2' }, acc: { mask: true, badge: true }, mood: 'neutral', armL: { sh: 10, el: 8 }, armR: { sh: 10, el: 8 } } },
    { x: 880, y: 1720, s: 0.62, o: { skin: 'fair', lashes: true, hair: { style: 'ponytail', color: 'auburn' }, top: { type: 'labcoat', shirt: '#8a5fc0' }, bottom: { type: 'skirt', color: '#3a3550' }, acc: { glasses: true, badge: true }, mood: 'skeptical', armL: { sh: 20, el: 70 }, armR: { sh: 8, el: 8 } } },
  ];
  function frame(f) {
    D.begin(f);
    const t = f / 30;
    let s = `<rect width="1080" height="1920" fill="#dfe8ee"/><rect y="900" width="1080" height="20" fill="#b8c4cc"/><rect y="1720" width="1080" height="20" fill="#b8c4cc"/>`;
    for (const c of CAST) {
      if (c.o.pose === 'sit') s += `<g transform="translate(${c.x} ${c.y}) scale(${c.s})"><rect x="-110" y="-262" width="200" height="40" rx="14" fill="#6fa8dc" stroke="#24160e" stroke-width="5"/><rect x="-30" y="-222" width="50" height="222" fill="#c9ced4" stroke="#24160e" stroke-width="5"/><rect x="-130" y="-560" width="48" height="320" rx="18" fill="#6fa8dc" stroke="#24160e" stroke-width="5"/></g>`;
      const y = c.y;
      s += H.human(c.x, y, { t, s: c.s, bl: blink(t, c.x), ...c.o }).svg;
    }
    return s + D.defs();
  }
  const stage = document.getElementById('stage');
  window.renderFrame = f => { stage.innerHTML = frame(f); };
  window.FILM = { width: 1080, height: 1920, fps: 30, frames: 30, ready: false };
  document.fonts.load('700 40px Fredoka').then(() => { window.FILM.ready = true; });
})();
