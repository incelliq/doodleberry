// Human rig demo: a short clinic exchange with two voices and lip-sync. Original room and characters.
(function () {
  const { clamp, lerp, inv, ease, spring, keys, noise, blink } = M;
  const T = M.bindTiming(window.TIMING), L = T.lines, FPS = 30, W = 1080, H = 1920;
  const MOUTH = window.TIMING.mouth || {};
  const talkOf = (spk, f) => (MOUTH[spk] && MOUTH[spk][f]) || 0;
  const at = (line, word, frac = 0.5) => { try { return T.word(line, word).start; } catch (e) { return lerp(L[line].start, L[line].end, frac); } };
  const END = L.d2.end + 1.4;
  const INK = '#24160e';
  const f2 = n => (+n).toFixed(2);

  // ---------- the exam room (original layout) ----------
  function room(t) {
    let s = `<rect x="-600" y="-200" width="${W + 1200}" height="${H + 400}" fill="${D.linear([[0, '#c9d8e2'], [1, '#b7c9d6']])}"/>`;
    // wall panels and a window with blinds
    for (let i = -3; i < 9; i++) s += `<rect x="${i * 190 - 20}" y="0" width="186" height="1260" fill="none" stroke="#a9bccb" stroke-width="4"/>`;
    s += D.shade('M640 300 L1000 300 L1000 720 L640 720 Z', '#e9f6ff', { depth: 8, light: 3, w: 6, ink: INK });
    for (let i = 0; i < 12; i++) s += `<rect x="648" y="${312 + i * 34}" width="344" height="20" rx="3" fill="#f6fbff" stroke="#9fb4c4" stroke-width="2"/>`;
    s += `<rect x="630" y="716" width="380" height="18" rx="5" fill="#dfe6ec" stroke="${INK}" stroke-width="4"/>`;
    // wall chart and a hand-sanitiser box
    s += D.shade('M120 300 L330 300 L330 560 L120 560 Z', '#fffdf6', { depth: 6, light: 2, w: 5, ink: INK });
    s += `<circle cx="225" cy="380" r="48" fill="none" stroke="#e05a4f" stroke-width="7"/><path d="M190 470 L260 470 M170 500 L280 500 M180 530 L270 530" stroke="#9fb4c4" stroke-width="7" stroke-linecap="round"/>`;
    s += D.shade('M420 520 L480 520 L480 610 L420 610 Z', '#f3f6f8', { depth: 4, light: 2, w: 4, ink: INK }) + `<rect x="436" y="608" width="28" height="14" fill="#7fb6d9" stroke="${INK}" stroke-width="3"/>`;
    // floor tiles
    s += `<rect x="-600" y="1260" width="${W + 1200}" height="${H}" fill="#d8cfc2"/><path d="M-600 1260 L${W + 600} 1260" stroke="${INK}" stroke-width="5"/>`;
    for (let i = -6; i < 14; i++) s += `<path d="M${540 + i * 140} 1260 L${540 + i * 260} ${H}" stroke="#bfb3a3" stroke-width="3"/>`;
    for (const y of [1340, 1460, 1620, 1820, 2100]) s += `<path d="M-600 ${y} L${W + 600} ${y}" stroke="#bfb3a3" stroke-width="3"/>`;
    // skirting board
    s += `<rect x="-600" y="1236" width="${W + 1200}" height="26" fill="#eef2f5" stroke="${INK}" stroke-width="4"/>`;
    return s;
  }
  // exam chair the patient sits in (seat front at x, floor at y)
  function chair(x, y, sc) {
    const g = (d, c) => D.shade(d, c, { depth: 8, light: 3, w: 5, ink: INK });
    let s = '';
    s += g('M-40 -250 L60 -250 L80 -10 L-60 -10 Z', '#d6dce2');                // pedestal
    s += g('M-120 -20 L140 -20 L150 10 L-130 10 Z', '#c3cbd3');                 // base
    s += g('M-150 -300 L130 -300 Q150 -300 150 -275 L150 -250 L-160 -250 L-160 -280 Q-160 -300 -150 -300 Z', '#6fa8dc'); // seat
    s += g('M-170 -620 Q-170 -650 -140 -650 L-110 -650 Q-80 -650 -82 -620 L-60 -300 L-150 -300 Z', '#6fa8dc');           // back
    s += g('M-150 -720 Q-150 -750 -120 -750 L-80 -750 Q-50 -750 -55 -720 L-70 -660 L-150 -660 Z', '#6fa8dc');           // headrest
    s += g('M-120 -420 L60 -420 Q80 -420 80 -400 L80 -380 L-120 -380 Z', '#5f98cc');                                     // armrest
    return `<g transform="translate(${f2(x)} ${f2(y)}) scale(${f2(-sc)} ${f2(sc)})">${s}</g>`;
  }

  // ---------- captions ----------
  const CH = (() => { const out = []; for (const l of window.TIMING.lines) { const ws = l.words; let i = 0; while (i < ws.length) { let j = i + 1; while (j < ws.length && j - i < 3 && !/[,.?!]$/.test(ws[j - 1].text)) j++; out.push({ text: ws.slice(i, j).map(w => w.text.replace(/[.,?!]$/, '')).join(' ').toUpperCase(), s: ws[i].start, e: j < ws.length ? ws[j].start : l.end + 0.25, spk: l.speaker }); i = j; } } return out; })();
  function captions(t) {
    const c = CH.find(c => t >= c.s - 0.07 && t < c.e - 0.07);
    if (!c) return '';
    const size = 92, w = Math.min(900, c.text.length * size * 0.58 + 80);
    const col = c.spk === 'doctor' ? '#7fd0a8' : '#f39ab8';
    return `<g transform="translate(540 1640)"><rect x="${-w / 2}" y="${-size * 0.95}" width="${w}" height="${size * 1.25}" rx="${size * 0.62}" fill="#1a0f08" fill-opacity="0.82" stroke="${col}" stroke-width="6"/>` +
      `<text x="0" y="0" font-size="${size}" font-weight="700" fill="#fff" text-anchor="middle" stroke="${INK}" stroke-width="13" paint-order="stroke" stroke-linejoin="round">${c.text}</text></g>`;
  }

  // ---------- the film ----------
  function frame(f) {
    D.begin(f);
    const t = f / FPS;
    const tDoc = talkOf('doctor', f), tPat = talkOf('patient', f);
    // camera: gentle push, drifting toward whoever is speaking
    const speakerX = keys(t, [[0, 640], [L.d1.start - 0.3, 640], [L.d1.start + 0.3, 420, 'inOutCubic'], [L.p2.start - 0.3, 420], [L.p2.start + 0.3, 640, 'inOutCubic'], [L.d2.start - 0.3, 640], [L.d2.start + 0.3, 460, 'inOutCubic']]);
    const z = 1.42 + 0.08 * inv(0, END, t);
    const cx = lerp(520, speakerX, 0.35), cy = 1190;
    const camT = `translate(540 960) scale(${f2(z)}) translate(${f2(-cx)} ${f2(-cy)})`;
    let world = room(t);

    // patient: seated, facing left toward the doctor
    const breatheIn = ease.inOutCubic(inv(at('p2', 'like') - 0.2, at('p2', 'this') + 0.4, t)) * (1 - ease.inOutCubic(inv(at('d2', 'let') - 0.1, at('d2', 'out') + 0.6, t)));
    const cough = at('p1', 'cough');
    const handToChest = Math.sin(clamp((t - cough + 0.2) / 1.4) * Math.PI);
    world += chair(700, 1500, 0.92);
    const pat = Human.human(690, 1500, {
      t, s: 0.92, flip: -1, pose: 'sit', seatH: 276, lashes: true, skin: 'light', figure: 'curvy',
      hair: { style: 'bob', color: 'auburn' }, top: { type: 'tee', color: '#7fc8a9' }, bottom: { color: '#3a3f58' }, shoes: { color: '#f2f2f2' },
      acc: { watch: true },
      armL: { sh: 6, el: lerp(62, 118, handToChest) }, armR: { sh: 4, el: 64 },
      mood: t < L.d1.start ? 'worried' : t < L.p2.start ? 'neutral' : t < L.d2.start ? 'surprised' : 'smile',
      talk: tPat, lookX: 0.7, lookY: t > L.d1.start && t < L.p2.start ? 0.1 : -0.1, bl: blink(t + 0.4, 5, 3.1), turn: 0.45,
      lean: lerp(0, -3, breatheIn), headTilt: -2 + breatheIn * -3,
    });
    world += pat.svg;
    // doctor: standing, facing right toward the patient; gestures on his lines
    const g1 = Math.sin(clamp((t - at('d1', 'listen') + 0.3) / 1.6) * Math.PI), g2 = Math.sin(clamp((t - at('d2', 'out') + 0.6) / 1.4) * Math.PI);
    const doc = Human.human(330, 1560, {
      t, s: 1.02, flip: 1, age: 'old', skin: 'fair',
      hair: { style: 'swept', color: 'gray' }, top: { type: 'labcoat', shirt: '#36506e' }, bottom: { color: '#23262e' },
      acc: { glasses: true, stethoscope: true, tie: '#c0463c', badge: true, pen: true },
      armL: { sh: 6, el: 10 }, armR: { sh: lerp(8, 42, Math.max(g1, g2)), el: lerp(10, 58, Math.max(g1, g2)) },
      mood: t < L.d1.start ? 'neutral' : 'smile', talk: tDoc, lookX: 0.8, lookY: 0.15, bl: blink(t, 2, 3.4), turn: 0.4,
      headTilt: 2 + Math.max(g1, g2) * 2,
    });
    world += `<ellipse cx="330" cy="1566" rx="120" ry="16" fill="#000" opacity="0.12"/>` + doc.svg;
    let svg = `<g transform="${camT}">${world}</g>`;
    svg += captions(t);
    return svg + D.defs();
  }

  window.CUES = [];
  const stage = document.getElementById('stage');
  window.renderFrame = f => { stage.innerHTML = frame(f); };
  window.FILM = { width: W, height: H, fps: FPS, frames: Math.round(END * FPS), ready: false };
  document.fonts.load('700 40px Fredoka').then(() => { window.FILM.ready = true; });
})();
