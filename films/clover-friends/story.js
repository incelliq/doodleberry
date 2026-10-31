  // ================= story: "Clover Friends" =================
  const SPK_COL = { mina: '#ff8a6e', kernel: '#ffd23f', wiggs: '#a77bf0', clover: '#86d957', narrator: '#ffffff' };
  const MOUTH = window.TIMING.mouth || {};
  const talkOf = (spk, f) => (MOUTH[spk] && MOUTH[spk][f]) || 0;
  const DIV_X = 560, MINA_X = -40, MINA_X2 = 60, TALL_X = 330;

  // ---------- title card ----------
  function title(t) {
    const t0 = L.rotate.start;
    if (t < t0 - 0.05) return '';
    const ps = 0.82 + 0.18 * spring(t - t0 + 0.05, { freq: 2.4, damping: 0.62 });
    const w2 = t0 + 0.3;
    let out = `<rect x="-404" y="-160" width="808" height="330" rx="44" fill="${C.ink}" opacity="0.25" transform="translate(8 10)"/>`;
    out += `<rect x="-404" y="-160" width="808" height="330" rx="44" fill="${C.cream}" stroke="${C.ink}" stroke-width="8"/>`;
    const a = 0.6 + 0.4 * spring(t - t0, { freq: 3, damping: 0.5 });
    out += G(tf(-250, -40, noise(81, t * 0.6) * 6, 0.5 * a), tube('M0 0 L0 40', '#4fa034', 12, 6) + leaflet(-62, 0.92, C.leaf, 0.75) + leaflet(62, 0.92, C.leaf, 0.75) + leaflet(0, 1, C.leafHi, 0.75));
    out += G(tf(60, -26, 0, a), `<text x="0" y="0" font-size="118" font-weight="700" fill="#4e9d31" text-anchor="middle" stroke="${C.ink}" stroke-width="10" paint-order="stroke" stroke-linejoin="round">CLOVER</text>`);
    if (t > w2 - 0.02) {
      const b = 0.6 + 0.4 * spring(t - w2 + 0.02, { freq: 3, damping: 0.5 });
      out += G(tf(0, 66, 0, b), `<text x="0" y="0" font-size="64" font-weight="700" fill="${C.ink}" text-anchor="middle">first. Then corn.</text>`);
    }
    out += `<text x="0" y="132" font-size="32" font-weight="600" fill="#6b5646" text-anchor="middle" opacity="${f2(inv(t0 + 0.6, t0 + 1.0, t))}">Source: Wikipedia, “Nitrogen fixation”</text>`;
    return G(tf(495, 330 + noise(77, t * 0.6) * 4, 0, ps, ps), out);
  }
  function squash(t, t0, amt = 0.14) {
    const d = t - t0;
    if (d < -0.12 || d > 0.9) return [1, 1];
    const k = d < 0 ? -Math.sin((d + 0.12) / 0.12 * Math.PI) * 0.35 : Math.exp(-d * 5) * Math.sin(d * 16);
    return [1 + amt * k, 1 - amt * k];
  }

  // ---------- beats ----------
  const B = {
    throws: [0.85, 1.65, 2.45],
    wigPop: L.need.start - 0.25,
    airT: at('air', 'air'),
    cantT: at('cant', "can't"),
    followT: at('cant', 'follow'),
    lensOpen: at('nodules', 'bacteria') - 0.25,
    lensClose: L.yum.start - 0.45,
    cardIn: L.later.start - 0.45, cardOut: L.release.start - 0.05,
    springIn: L.spring.start - 0.45, springOut: L.plant.start - 0.05,
    dieT: at('release', 'dies'), nitroT: at('release', 'nitrogen'), relT: at('release', 'released'),
    rainOff: L.spring.start - 0.1,
    seedL: at('plant', 'corn'), seedR: at('plant', 'sides'),
    growT: L.plant.end + 0.35,
    endWink: L.rotate.end + 0.6,
  };
  const END = L.rotate.end + 1.6;

  // ---------- camera ----------
  function camera(t) {
    const k = (cx, cy, z) => [cx, cy, z];
    const cam = keys(t, [
      [0, k(270, 930, 1.12)],
      [L.hungry.start - 0.25, k(270, 930, 1.12), 'linear'],
      [L.hungry.start + 0.4, k(720, 960, 1.3), 'inOutCubic'],
      [B.wigPop - 0.15, k(720, 960, 1.3), 'linear'],
      [B.wigPop + 0.45, k(640, 950, 1.14), 'inOutCubic'],
      [L.air.start - 0.3, k(640, 950, 1.14), 'linear'],
      [L.air.start + 0.4, k(360, 820, 1.0), 'inOutCubic'],
      [L.cant.start - 0.2, k(360, 820, 1.0), 'linear'],
      [L.cant.start + 0.35, k(640, 920, 1.2), 'inOutCubic'],
      [B.followT + 0.1, k(640, 920, 1.2), 'linear'],
      [B.followT + 1.3, k(420, 1150, 1.45), 'inOutCubic'],
      [B.lensOpen, k(420, 1150, 1.45), 'linear'],
      [B.lensOpen + 0.6, k(430, 1090, 1.6), 'inOutCubic'],
      [B.lensClose + 0.5, k(430, 1090, 1.6), 'linear'],
      [B.lensClose + 0.95, k(330, 900, 1.25), 'inOutCubic'],
      [B.cardOut, k(500, 960, 1.05), 'linear'],
      [L.plant.start - 0.3, k(500, 960, 1.05), 'linear'],
      [L.plant.start + 0.3, k(360, 930, 1.05), 'inOutCubic'],
      [B.growT - 0.1, k(360, 930, 1.05), 'linear'],
      [B.growT + 0.8, k(470, 780, 0.88), 'outCubic'],
      [L.rotate.start - 0.2, k(470, 780, 0.88), 'linear'],
      [L.rotate.start + 0.4, k(480, 650, 0.9), 'inOutCubic'],
      [END, k(480, 650, 0.9), 'linear'],
    ]);
    return { cx: cam[0], cy: cam[1], z: cam[2] };
  }
  const toScreen = (cam, x, y) => [W / 2 + (x - cam.cx) * cam.z, H / 2 + (y - cam.cy) * cam.z];

  // ---------- Wiggs: spine poses keyed in time ----------
  const GR = GROUND;
  const POSE = {
    sleep: [[600, GR + 150], [652, GR + 178], [642, GR + 252], [586, GR + 246]],
    peek: [[560, GR - 70], [563, GR + 10], [568, GR + 70], [596, GR + 140]],
    rise: [[565, GR + 40], [575, GR + 120], [600, GR + 190], [595, GR + 260]],
    out: [[560, GR - 175], [566, GR - 60], [562, GR + 40], [588, GR + 135]],
    wind: [[578, GR - 225], [560, GR - 105], [560, GR + 10], [575, GR + 110]],
    arc: [[522, GR + 40], [530, GR - 140], [585, GR - 150], [592, GR - 4]],
    slide: [[480, GR + 150], [520, GR + 60], [548, GR - 60], [562, GR + 18]],
    roots: [[452, GR + 192], [492, GR + 176], [536, GR + 122], [560, GR + 42]],
    watch: [[602, GR + 112], [636, GR + 150], [642, GR + 222], [592, GR + 252]],
  };
  function wiggsPose(t) {
    const P = n => POSE[n].flat();
    const seq = [
      [0, P('sleep')], [B.wigPop - 0.05, P('sleep')], [B.wigPop + 0.12, P('rise'), 'inQuad'], [B.wigPop + 0.4, P('out'), 'outBack'],
      [B.followT - 0.15, P('out')], [B.followT + 0.05, P('wind'), 'outCubic'], [B.followT + 0.35, P('arc'), 'inCubic'],
      [B.followT + 0.65, P('slide'), 'linear'], [B.followT + 1.2, P('roots'), 'outCubic'],
      [B.lensClose + 0.2, P('roots')], [B.lensClose + 1.0, P('peek'), 'inOutCubic'],
      [B.cardIn + 0.4, P('peek')], [B.cardOut - 0.01, P('out'), 'linear'],
      [B.springIn + 0.4, P('out')], [B.springOut, P('peek'), 'linear'],
      [L.rotate.start - 0.6, P('peek')], [L.rotate.start - 0.1, P('out'), 'outBack'],
    ];
    const v = keys(t, seq);
    return [[v[0], v[1]], [v[2], v[3]], [v[4], v[5]], [v[6], v[7]]];
  }
  function wiggsMood(t) {
    if (t < B.wigPop) return 'sleep';
    if (t < B.wigPop + 0.6) return 'surprised';
    if (t > B.endWink - 0.1 && t < B.endWink + 0.5) return 'happy';
    if (t > L.release.start && t < B.rainOff) return 'sad';
    if (t > B.springOut && t < L.rotate.start - 0.2) return 'happy';
    if (t > B.lensClose && t < B.cardIn) return 'excited';
    return 'smug';
  }

  // ---------- the film ----------
  function frame(f) {
    D.begin(f);
    const t = f / FPS;
    const cam = camera(t);
    const card = t > B.cardIn + 0.36 && t < B.cardOut - 0.36;
    // weather: autumn rain after the card, spring sun after the rain
    const storm = clamp(inv(B.cardOut - 0.4, B.cardOut, t) * (1 - inv(B.springIn + 0.36, B.springOut - 0.36, t)));
    const rainAmt = clamp(inv(B.cardOut - 0.3, B.cardOut + 0.3, t) * (1 - inv(B.springIn + 0.36, B.springOut - 0.36, t)));
    const wet = clamp(inv(B.cardOut, B.cardOut + 1.5, t) * (1 - inv(B.springIn + 0.3, B.springOut - 0.3, t)));
    const dusk = 0;

    // --- the clover ---
    const sprout = pop(t, 0.12, 0.6);
    const yumT = L.yum.start, feedsT = at('yum', 'feeds');
    const wilt = ease.inOutCubic(inv(B.dieT, B.dieT + 0.7, t));
    const sinkP = ease.inCubic(inv(B.dieT + 0.75, B.dieT + 1.25, t));
    const clGrow = 1 + 0.12 * spring(t - yumT, { freq: 1.8, damping: 0.4 });
    let clMood = t < L.hungry.start ? 'happy' : 'happy';
    if (t > B.lensClose - 0.2 && t < B.cardIn) clMood = 'excited';
    if (t > B.cardOut && t < B.dieT) clMood = 'sad';
    if (t > B.dieT + 0.2) clMood = 'sleep';

    // --- Kernel (the corn that never gets clover) ---
    const kIn = pop(t, 0, 0.5);
    const flinch = t > B.cantT ? Math.exp(-(t - B.cantT) * 3.5) * Math.sin((t - B.cantT) * 22) * 9 : 0;
    let kMood = 'hungry';
    if (t < L.hungry.start) kMood = 'skeptical';
    else if (t < L.hungry.end) kMood = 'sad';
    else if (t < B.wigPop + 0.6 && t > B.wigPop) kMood = 'surprised';
    else if (t > L.air.start && t < L.air.end) kMood = 'skeptical';
    if (t > B.cantT - 0.1 && t < B.cantT + 1.2) kMood = 'sad';
    if (t > B.cardOut && t < B.rainOff) kMood = 'sleep';
    if (t > B.growT + 0.3) kMood = 'envious';
    if (t > L.fed.start + 0.5) kMood = 'hungry';
    const kLook = t > B.growT + 0.3 && t < L.fed.end ? [-1, -1] : t < L.hungry.start ? [-1, 0] : t > B.wigPop && t < L.air.start ? [-1, 0.3] : [-0.6, 0.2];

    // --- the tall corn on the clover side (spring) ---
    const tg = spring(t - B.growT, { freq: 1.4, damping: 0.5 }) * (t > B.growT ? 1 : 0);
    const tallIn = pop(t, B.seedL + 0.55, 0.5);

    // --- world ---
    let world = ground(t, dusk);
    if (wet > 0.01) {
      world += `<rect x="-800" y="${GROUND - 4}" width="2700" height="96" fill="#2a1a0e" opacity="${f2(0.45 * wet)}"/>`;
    }
    // the dividing stake and string between the two halves of the field
    world += G(tf(DIV_X, GROUND + 4), D.shade('M-9 0 L-8 -96 L0 -112 L8 -96 L9 0 Z', '#b07a46', { depth: 6, light: 2, w: 4.5, ink: C.ink }));
    world += `<path d="M-800 ${GROUND - 70} Q${DIV_X - 200} ${GROUND - 58} ${DIV_X} ${GROUND - 78}" fill="none" stroke="#f3e2b8" stroke-width="3" opacity="0"/>`;
    // ground signs make the comparison readable: which side had clover (drawn behind the cast)
    [[472, ['AFTER', 'CLOVER'], '#4e9d31', B.seedL + 0.4], [652, ['NO', 'CLOVER'], '#9a6a45', B.seedR + 0.4]].forEach(([sx, label, colr, t0]) => {
      const p = pop(t, t0, 0.5);
      if (p.s < 0.01) return;
      world += G(`translate(${sx} ${GROUND + 6}) scale(${f2(p.sx)} ${f2(p.sy)})`,
        D.shade('M-7 0 L-7 -240 L7 -240 L7 0 Z', '#b07a46', { depth: 4, light: 2, w: 4, ink: C.ink }) +
        G(tf(0, -282, sx < DIV_X ? -3 : 3), D.shade('M-82 -48 H82 V48 H-82 Z', '#f6e7c8', { depth: 7, light: 3, w: 5, ink: C.ink }) +
          `<text x="0" y="-6" font-size="34" font-weight="700" fill="${colr}" text-anchor="middle">${label[0]}</text>` +
          `<text x="0" y="32" font-size="34" font-weight="700" fill="${colr}" text-anchor="middle">${label[1]}</text>`));
    });
    // Wiggs's tunnel from the hole to the clover roots, once he has dug it
    const tun = inv(B.followT + 0.3, B.followT + 1.2, t);
    if (tun > 0) {
      const pts = D.bez([DIV_X, GROUND + 14], [DIV_X, GROUND + 90], [520, GROUND + 160], [446, GROUND + 196], 16);
      const tunOp = 0.55 * (1 - inv(B.lensClose + 0.6, B.lensClose + 1.4, t));
      if (tunOp > 0.01) world += D.taper(pts.slice(0, Math.max(2, Math.round(pts.length * tun))), 62, 54, '#3f2817', `opacity="${f2(tunOp)}"`);
    }
    // roots
    if (t < B.growT + 1.5) world += roots(CLOVER_X, { t, nodulePop: at('nodules', 'bumps'), pulse: at('nodules', 'bumps'), fade: inv(B.dieT, B.dieT + 1, t), gone: Math.max(1 - sprout.s, 0.55 * inv(B.relT, B.relT + 0.8, t) + 0.45 * inv(L.plant.start, B.growT + 1.2, t)) });
    world += cornRoots(CORN_X, 0.15);
    if (t > B.seedL + 0.5) world += cornRoots(TALL_X, tg);
    {
      const bT = at('nodules', 'bumps'), rT = at('nodules', 'roots');
      const vis = 1 - inv(B.lensClose, B.lensClose + 0.4, t);
      if (t > bT - 0.05 && vis > 0) NODULES.forEach(([nx, ny, r], i) => {
        const d = t - bT - i * 0.05;
        if (d < 0) return;
        const rr = r + 8 + (d % 1.2) * 34, op = Math.max(0, 1 - (d % 1.2) / 1.2) * vis;
        world += G(tf(CLOVER_X, GROUND + 18, 0, ROOT_SX, ROOT_SY), circle(nx, ny, rr, 'none', 5, '#fff', `opacity="${f2(op)}"`));
      });
      const tr = inv(rT - 0.05, rT + 0.55, t);
      if (tr > 0 && tr < 1) world += G(tf(CLOVER_X, GROUND + 18, 0, ROOT_SX, ROOT_SY), CLOVER_ROOTS.map(d =>
        `<path d="${d}" fill="none" stroke="#fff6c8" stroke-width="8" stroke-linecap="round" pathLength="100" stroke-dasharray="${f2(tr * 100)} 100" opacity="${f2(Math.sin(tr * Math.PI))}"/>`).join(''));
    }
    // one N2 pair falls from the sky into the nodule on "pull"
    {
      const fixT = at('fix', 'pull'), d0 = fixT - 0.7, d1 = fixT - 0.05;
      if (t > d0 && t < d1 + 0.25) {
        const [nx, ny] = NODULE_WORLD();
        const p = ease.inQuad(inv(d0, d1, t));
        world += n2(lerp(nx + 70, nx, p), lerp(GROUND - 640, ny, p), 0.85 * (1 - inv(d1, d1 + 0.2, t)), p * 160);
        if (t > d1) world += circle(nx, ny, 18 + (t - d1) * 120, 'none', 5, '#fff', `opacity="${f2(1 - inv(d1, d1 + 0.25, t))}"`);
      }
    }
    // ammonia travelling up the roots into the clover
    if (t > yumT - 0.2 && t < yumT + 1.3) {
      const [nx, ny] = NODULE_WORLD();
      for (let i = 0; i < 6; i++) {
        const p = inv(yumT - 0.15 + i * 0.08, yumT + 0.5 + i * 0.08, t);
        if (p <= 0 || p >= 1) continue;
        const x = lerp(nx + (i % 3 - 1) * 20, CLOVER_X, ease.inOutQuad(p)), y = lerp(ny + (i % 2) * 40, GROUND - 160, ease.inQuad(p));
        world += nDot(x, y, 0.42, 1 - inv(0.55, 0.85, p));
      }
    }
    // background clovers sprout as Mina throws seeds (left half only)
    const BG = [40, 170, 430, 500];
    let bgPlants = '';
    BG.forEach((x, i) => {
      const p = pop(t, B.throws[i % 3] + 0.45 + i * 0.12, 0.5);
      if (p.s > 0.01 && sinkP < 1) bgPlants += G(tf(x, 0, (rand(i + 71) - 0.5) * 8, 1), clover(0, { t, s: 0.42 * (0.82 + rand(i + 61) * 0.36) * p.s, seed: 10 + i, wilt, wind: D.wind(t, x), sink: sinkP * 120, face: false, mood: 'happy', sq: [p.sx / Math.max(p.s, 0.01), p.sy / Math.max(p.s, 0.01)] }));
      world += D.crumbs(t, B.throws[i % 3] + 0.45 + i * 0.12, x, GROUND + 6, { seed: 30 + i, n: 5, up: 300 });
    });
    world += `<g clip-path="url(#above)">${bgPlants}</g>`;
    if (sprout.s > 0.01 && sinkP < 1) {
      world += shadow(CLOVER_X, 70 * (1 - sinkP), 0.2);
      world += `<g clip-path="url(#above)">` + clover(CLOVER_X, {
        t, s: sprout.s * clGrow, wilt, sink: sinkP * 330, flower: inv(yumT - 0.05, feedsT, t), flowerAt: feedsT,
        mood: clMood, talk: talkOf('clover', f), lookX: t > B.lensClose ? 0.6 : 0.3, lookY: t > B.followT && t < B.lensClose ? 1 : 0, bl: blink(t, 1, 3.1), seed: 1,
        sq: [sprout.sx / Math.max(sprout.s, 0.01) * squash(t, yumT)[0], sprout.sy / Math.max(sprout.s, 0.01) * squash(t, yumT)[1]],
        wind: D.wind(t, CLOVER_X) * (1 - wilt), windLag: D.wind(t - 0.15, CLOVER_X) * (1 - wilt),
      }) + `</g>`;
    }
    world += D.crumbs(t, 0.12, CLOVER_X, GROUND + 6, { seed: 9, n: 8 });
    world += D.crumbs(t, B.dieT + 0.75, CLOVER_X, GROUND + 6, { seed: 19, n: 12, up: 380 });
    // tall corn on the clover side (spring)
    if (tallIn.s > 0.01) {
      world += shadow(TALL_X, lerp(40, 120, tg), 0.2);
      world += `<g clip-path="url(#above)">` + corn(TALL_X, {
        t, grow: tg, health: clamp(tg * 1.3), mood: t > B.growT + 0.5 ? (t > L.tall.end ? 'proud' : 'proud') : 'happy', s: tallIn.s * 1.3, bl: blink(t, 6, 3.3),
        wind: D.wind(t, TALL_X), lookX: 0.6, cob: pop(t, B.growT + 0.8, 0.5).s, sq: [tallIn.sx / Math.max(tallIn.s, 0.01), tallIn.sy / Math.max(tallIn.s, 0.01)],
      }) + `</g>`;
      world += D.crumbs(t, B.growT, TALL_X, GROUND + 6, { seed: 13, n: 12, up: 600 });
    }
    // Kernel
    world += shadow(CORN_X, 55, 0.2);
    world += `<g clip-path="url(#above)">` + corn(CORN_X, {
      t, grow: 0.12, health: t > B.growT ? 0.05 : 0, mood: kMood, talk: talkOf('kernel', f), flinch, s: kIn.s * 1.35, bl: blink(t, 2, 3.4),
      wind: D.wind(t, CORN_X), lookX: kLook[0], lookY: kLook[1], cob: 0,
    }) + `</g>`;
    // Mina: away during the rain, walks back in for spring
    const act2 = t > B.springOut - 0.36;
    const mx = act2 ? MINA_X2 : MINA_X - 420 * ease.inOutCubic(inv(B.followT + 0.4, B.followT + 1.6, t));
    const minaHere = (t < B.cardIn || act2) && toScreen(cam, mx, GROUND - 300)[0] > 30;
    if (minaHere) {
      const walk = act2 ? 0 : inv(B.followT + 0.4, B.followT + 1.6, t) > 0 && inv(B.followT + 0.4, B.followT + 1.6, t) < 1 ? 1 : 0;
      const throwArm = tt => { // a throw swings the arm up and over
        for (const th of tt) { const d = t - th; if (d > -0.25 && d < 0.35) return d < 0 ? 40 + (d + 0.25) / 0.25 * 100 : 140 - d / 0.35 * 90; }
        return 40;
      };
      let pose = { mood: 'happy', armL: { sh: 10, el: 10 }, armR: { sh: 10, el: 10 }, look: [0.4, 0], hand: {} };
      if (t < L.hungry.start) pose = { mood: 'annoyed', armL: { sh: 25, el: 50 }, armR: { sh: throwArm(B.throws), el: 25 }, look: [0.6, 0.2], hand: { l: 'pouch' } };
      else if (t < B.wigPop) pose = { mood: 'sad', armL: { sh: 25, el: 50 }, armR: { sh: 14, el: 10 }, look: [1, 0.1], hand: { l: 'pouch' } };
      else if (t < L.air.start) pose = { mood: 'surprised', armL: { sh: 35, el: 40 }, armR: { sh: 35, el: 40 }, look: [1, 0.3], hand: {} };
      else if (t < L.cant.start) pose = { mood: t < B.airT ? 'skeptical' : 'excited', armL: { sh: 15, el: 10 }, armR: { sh: lerp(20, 165, ease.outBack(inv(L.air.start, L.air.start + 0.4, t))), el: 5 }, look: [0.4, -1], hand: {} };
      else if (t < B.cardIn) pose = { mood: t > B.followT ? 'excited' : 'skeptical', armL: { sh: 35, el: 110 }, armR: { sh: 35, el: 110 }, look: [1, 0.4], hand: {} };
      else if (t < L.tall.start) pose = { mood: 'happy', armL: { sh: 25, el: 50 }, armR: { sh: throwArm([B.seedL, B.seedR]), el: 25 }, look: [t < B.seedR - 0.3 ? 0.6 : 1, 0.3], hand: { l: 'pouch' } };
      else if (t < L.fed.start) pose = { mood: 'happy', armL: { sh: 20, el: 120 }, armR: { sh: 20, el: 120 }, look: [1, -0.6], hand: {} };
      else if (t < L.rotate.start) pose = { mood: 'proud', armL: { sh: 15, el: 10 }, armR: { sh: lerp(20, 80, ease.outBack(inv(L.fed.start, L.fed.start + 0.4, t))), el: 10 }, look: [1, 0], hand: {} };
      else pose = { mood: 'excited', armL: { sh: 15, el: 10 }, armR: { sh: 150, el: 20 + Math.sin(t * 9) * 25 }, look: [1, 0], hand: {} };
      const k = Cast.kid(mx, GROUND + 8, { t, s: 1.0, talk: talkOf('mina', f), mood: pose.mood, lookX: pose.look[0], lookY: pose.look[1], bl: blink(t + 1.3, 8, 3.6),
        armL: pose.armL, armR: pose.armR, hand: pose.hand, lean: walk * 4 * Math.sin(t * 12) + (t < L.hungry.start ? 2 : 0) });
      world += shadow(mx, 90, 0.22) + k.svg;
      // seeds from her hand: clover seeds in the hook, corn seeds in spring
      const seedArc = (t0, tx, n, colr) => {
        let s = '';
        for (let i = 0; i < n; i++) {
          const p = inv(t0 + i * 0.03, t0 + 0.5 + i * 0.03, t);
          if (p <= 0 || p >= 1) continue;
          const [hx, hy] = k.hands[1];
          const x = lerp(hx, tx + (i - n / 2) * 26, p), y = lerp(hy, GROUND + 2, p) - Math.sin(p * Math.PI) * 140;
          s += D.sphere(x, y, 6, colr, { w: 2.5 });
        }
        return s;
      };
      B.throws.forEach((th, i) => { world += seedArc(th, [250, 380, 470][i], 4, '#c9a25a'); });
      world += seedArc(B.seedL, TALL_X, 1, '#ffd23f') + seedArc(B.seedR, CORN_X - 30, 1, '#ffd23f');
    }
    // Wiggs (the cut-away soil shows his whole body)
    {
      const sp = wiggsPose(t);
      const pts = Cast.spine(sp[0], sp[1], sp[2], sp[3], t, t < B.wigPop ? 1.5 : 4, 24);
      world += Cast.worm(pts, { t, talk: talkOf('wiggs', f), mood: wiggsMood(t), lookX: t > B.followT && t < B.cardIn ? -0.8 : -0.4, lookY: 0, bl: blink(t, 4, 2.9), wink: t > B.endWink && t < B.endWink + 0.45, headS: 1.5 });
      // a leaf umbrella in the rain
      if (storm > 0.01) {
        const [hx, hy] = pts[0];
        world += G(tf(hx + 4, hy - 46, -8 + noise(5, t) * 4, storm), D.shade('M-70 0 Q0 -70 70 0 Q35 -12 0 -4 Q-35 -12 -70 0 Z', '#6bb544', { depth: 8, light: 3, w: 4.5, ink: C.ink }) + tube('M0 -4 L0 40', '#4f9a33', 6, 3));
      }
      world += D.crumbs(t, B.wigPop + 0.1, DIV_X, GROUND + 6, { seed: 41, n: 12, up: 520 });
      world += D.crumbs(t, B.followT + 0.35, DIV_X, GROUND + 6, { seed: 43, n: 10, up: 420 });
      world += D.crumbs(t, L.rotate.start - 0.2, DIV_X, GROUND + 6, { seed: 47, n: 10, up: 460 });
    }
    // puddles while the ground is wet
    if (wet > 0.01) [[120, 70], [460, 90], [690, 60], [930, 80]].forEach(([px, pw], i) => {
      const s = ease.outCubic(clamp(wet * 1.4 - i * 0.1));
      world += `<ellipse cx="${px}" cy="${GROUND + 4}" rx="${f2(pw * s)}" ry="${f2(11 * s)}" fill="${D.linear([[0, '#a9c3dc'], [1, '#6f8daa']])}" stroke="${C.ink}" stroke-width="3" opacity="${f2(0.9 * s)}"/>` +
        `<ellipse cx="${px - pw * 0.3}" cy="${GROUND + 1}" rx="${f2(pw * 0.3 * s)}" ry="${f2(2.5 * s)}" fill="#fff" opacity="${f2(0.7 * s)}"/>`;
    });

    // nitrogen in the air on Mina's "air", and the bounce off Kernel on "can't"
    for (let i = 0; i < 9; i++) {
      const p = pop(t, B.airT - 0.15 + i * 0.07, 0.5);
      const out = 1 - ease.inCubic(inv(B.followT + i * 0.03, B.followT + 0.5 + i * 0.03, t));
      if (p.s * out <= 0.01) continue;
      const row = Math.floor(i / 3), colm = i % 3;
      const bx = 230 + colm * 240 + (row % 2) * 110 + (rand(i + 200) - 0.5) * 30, by = 340 + row * 145 + (rand(i + 300) - 0.5) * 24;
      world += n2(bx + noise(i + 400, t * 0.4) * 18 + t * 4, by + noise(i + 500, t * 0.35) * 14 - (1 - out) * 900, 1.15 * p.s, noise(i + 600, t * 0.3) * 40, i === 4 ? { tag: { t, at: B.airT + 0.3 } } : {});
    }
    {
      const t0 = B.cantT - 0.55, hit = B.cantT;
      if (t > t0 && t < hit + 1.4) {
        let x, y, r;
        if (t < hit) { const p = ease.inQuad(inv(t0, hit, t)); x = lerp(700, CORN_X - 6, p); y = lerp(500, GROUND - 230, p); r = p * 90; }
        else { const p = t - hit; x = CORN_X - 6 + p * 260; y = GROUND - 230 - 520 * p + 330 * p * p; r = 90 + p * 300; }
        world += G(`translate(${f2(x)} ${f2(y)}) scale(${t > hit && t < hit + 0.12 ? '1.25 0.75' : '1 1'})`, n2(0, 0, 0.95, r));
        if (t > hit && t < hit + 0.35) {
          const q = inv(hit, hit + 0.35, t);
          world += `<g opacity="${f2(1 - q)}">` + D.shock(CORN_X - 6, GROUND - 245, -Math.PI * 0.62, 1 + q * 0.4) + D.shock(CORN_X - 6, GROUND - 245, -Math.PI * 0.2, 0.8 + q * 0.4) + `</g>`;
        }
      }
    }
    // released nitrogen: spreads from the clover in the rain, then flows to the tall corn in spring
    let glowLayer = '';
    if (t > B.nitroT - 0.1 && t < L.rotate.start + 0.5) {
      for (let i = 0; i < 26; i++) {
        if (i % 3 === 2) continue;
        const a = rand(i + 700) * Math.PI * 2, d = 60 + rand(i + 800) * 200;
        const sx = CLOVER_X + 40 + Math.cos(a) * d * 0.8, sy = GROUND + 120 + Math.sin(a) * d * 0.35;
        const spread = ease.outCubic(inv(B.nitroT - 0.1 + i * 0.03, B.relT + 0.6 + i * 0.02, t));
        const toCorn = ease.inOutCubic(inv(B.growT - 0.3 + i * 0.025, B.growT + 0.6 + i * 0.02, t));
        const x0 = lerp(CLOVER_X, sx, spread), y0 = lerp(GROUND + 120, sy, spread);
        const tx = TALL_X + (rand(i + 900) - 0.5) * 100, ty = GROUND + 40 + rand(i + 950) * 90;
        const x = lerp(x0, tx, toCorn) + noise(i + 1000, t) * 6, y = lerp(y0, ty, toCorn) + noise(i + 1100, t) * 6;
        const op = spread * (1 - inv(B.growT + 0.5, B.growT + 1.2, t));
        const [, scrY] = toScreen(cam, x, y);
        const clear = 1 - inv(1300, 1345, scrY);
        if (op * clear > 0.01) glowLayer += nDot(x, y, 0.58, op * clear);
      }
    }
    // on "fed": the clover side's soil glows under the tall corn
    {
      const g = Math.sin(clamp(inv(at('fed', 'fed') - 0.1, at('fed', 'fed') + 1.6, t)) * Math.PI);
      if (g > 0.01) glowLayer += `<ellipse cx="${TALL_X}" cy="${GROUND + 120}" rx="${f2(210 * (0.8 + 0.2 * g))}" ry="80" fill="url(#glow)" opacity="${f2(0.55 * g)}"/>`;
    }

    // backdrop layers
    const sunY = keys(t, [[0, 290], [B.cardOut - 0.2, 290], [B.cardOut, 1080, 'linear'], [B.springIn + 0.4, 1080], [B.springOut - 0.36, 290, 'linear']]);
    const sunL = `<circle cx="880" cy="${f2(sunY)}" r="150" fill="${D.radial([[0, '#fff3b0', 0.7], [1, '#fff3b0', 0]], { cx: 0.5, cy: 0.5, r: 0.5 })}"/>` + D.sphere(880, sunY, 64, '#ffd75e', { w: 0, spec: false });
    let skyL = '';
    [[120, 220, 1.0, 1], [700, 160, 0.8, 2], [430, 420, 0.65, 3], [980, 380, 0.75, 4], [250, 120, 0.9, 5]].forEach(([x, y, s, sd], i) => {
      if (i === 4 && storm < 0.01) return;
      const xx = ((x + t * 16 * s + 300) % 1500) - 300;
      skyL += D.cloud(xx, y + storm * 30, s * (1 + storm * 0.35), sd, D.mix('#ffffff', '#8e98a6', storm), D.mix('#dceef8', '#6c7684', storm));
    });
    const farL = hills(dusk, t), hedgeL = hedge(dusk);
    const fgL = D.fgGrass(1230, GROUND + 40, 560, 7, t);

    const camT = `translate(${W / 2} ${H / 2}) scale(${f2(cam.z)}) translate(${f2(-cam.cx)} ${f2(-cam.cy)})`;
    const layerT = p => `translate(${W / 2} ${H / 2}) scale(${f2(1 + (cam.z - 1) * p)}) translate(${f2(-(540 + (cam.cx - 540) * p))} ${f2(-(960 + (cam.cy - 960) * p))})`;
    const dof = 1 + Math.max(0, cam.z - 1) * 1.4;
    let svg = sky(t, dusk);
    if (storm > 0.01) svg += `<rect width="${W}" height="${H}" fill="#8c97a6" opacity="${f2(storm * 0.55)}"/>`;
    svg += `<g transform="${layerT(0.15)}">${sunL}</g>`;
    svg += `<g filter="${D.blurFilter(3.5)}"><g transform="${layerT(0.15)}">${skyL}</g></g>`;
    svg += `<g filter="${D.blurFilter(5 * dof)}"><g transform="${layerT(0.45)}">${farL}</g></g>`;
    svg += `<g filter="${D.blurFilter(2.4 * dof)}"><g transform="${layerT(0.75)}">${hedgeL}</g></g>`;
    svg += `<g transform="${camT}">${world}</g>`;
    if (storm > 0.01) svg += `<rect width="${W}" height="${H}" fill="#56627a" opacity="${f2(storm * 0.3)}" style="mix-blend-mode:multiply"/>`;
    if (glowLayer) svg += `<g transform="${camT}">${glowLayer}</g>`;
    svg += `<g filter="${D.blurFilter(9)}"><g transform="${layerT(1.4)}">${fgL}</g></g>`;
    if (rainAmt > 0.01) svg += D.rain(t, { amount: rainAmt, groundY: toScreen(cam, 0, GROUND)[1] });
    svg += lens(t, cam);
    svg += captions(t);
    svg += title(t);
    svg += D.timeCard(t, B.cardIn, B.cardOut, { text: 'MONTHS LATER…' });
    svg += D.timeCard(t, B.springIn, B.springOut, { text: 'NEXT SPRING…', months: ['NOV', 'DEC', 'JAN', 'FEB', 'MAR', 'APR'] });
    return svg + D.defs();
  }

  // ---------- sound cues (read by engine/audio.py) ----------
  const cue = (t, type, gain = 1) => ({ t: +t.toFixed(3), type, gain });
  window.CUES = [
    ...B.throws.map(th => cue(th - 0.05, 'whoosh', 0.5)),
    ...[0, 1, 2, 3].map(i => cue(B.throws[i % 3] + 0.45 + i * 0.12, 'pop_small', 0.6)),
    cue(1.95, 'pop'),
    cue(L.hungry.start - 0.1, 'whoosh'),
    cue(B.wigPop + 0.1, 'pop'), cue(B.wigPop + 0.15, 'sink', 0.6),
    cue(B.airT - 0.15, 'twinkle'),
    cue(B.cantT, 'boing'),
    cue(B.followT + 0.3, 'whoosh'), cue(B.followT + 0.4, 'sink', 0.8),
    cue(at('nodules', 'bumps'), 'pop_small', 0.7),
    cue(B.lensOpen, 'lens_open'),
    cue(at('fix', 'pull') - 0.05, 'pop_small', 0.6), cue(at('fix', 'pull') + 0.6, 'chomp'),
    cue(at('fix', 'turn') + 0.15, 'sparkle'), cue(at('fix', 'ammonia'), 'sparkle'),
    cue(B.lensClose, 'lens_close'), cue(L.yum.start, 'grow'), cue(at('yum', 'feeds'), 'pop'),
    cue(B.cardIn, 'whoosh'), cue(B.cardIn + 0.5, 'flip'), cue(B.cardOut - 0.4, 'whoosh'),
    cue(B.cardOut - 0.2, 'rain'),
    cue(B.dieT, 'wilt'), cue(B.dieT + 0.75, 'sink'),
    cue(B.nitroT - 0.1, 'shimmer'),
    cue(B.springIn, 'whoosh'), cue(B.springIn + 0.45, 'flip'), cue(B.springOut - 0.4, 'whoosh'), cue(B.springOut - 0.1, 'chime', 0.7),
    cue(B.seedL - 0.05, 'whoosh', 0.5), cue(B.seedL + 0.5, 'pop_small', 0.7),
    cue(B.seedR - 0.05, 'whoosh', 0.5), cue(B.seedR + 0.5, 'pop_small', 0.7),
    cue(B.growT, 'grow_big'), cue(B.growT + 0.8, 'pop'),
    cue(L.rotate.start - 0.2, 'pop'),
    cue(L.rotate.start, 'chime'),
    cue(B.endWink, 'wink'),
  ].sort((a, b) => a.t - b.t);

  const stage = document.getElementById('stage');
  window.renderFrame = f => { stage.innerHTML = frame(f); };
  window.FILM = { width: W, height: H, fps: FPS, frames: Math.round(END * FPS), safe: SAFE, ready: false };
  document.fonts.load('700 40px Fredoka').then(() => { window.FILM.ready = true; });
})();
