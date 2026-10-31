  // ================= story: "Not a Tree" =================
  const SPK_COL = { nana: '#f6d046', wiggs: '#a77bf0' };
  const MOUTH = window.TIMING.mouth || {};
  const talkOf = (spk, f) => (MOUTH[spk] && MOUTH[spk][f]) || 0;
  const NANA_X = 540, HOLE_X = 690;

  const B = {
    wigPop: L.stem.start - 0.25,
    sliceIn: at('stem', 'pseudostem') - 0.1, sliceOut: L.stem.end + 0.4,
    flowT: at('corm', 'everything'), cormT: at('corm', 'corm'),
    spikeA: L.coming.end, spikeB: at('spike', 'stops'), spikeC: L.spike.end + 0.2,
    bractT: at('bracts', 'bracts'), handsT: at('bracts', 'hands'),
    nineA: at('nine', 'nine') - 0.1, nineB: at('nine', 'bunch') + 0.4, twentyT: at('nine', 'twenty'),
    montA: L.nine.end + 0.1, montB: L.sucker.start - 0.1,
    suckT: at('sucker', 'sucker') - 0.2,
    endWink: L.herb.end + 0.55,
  };
  const END = L.herb.end + 1.5;

  // ---------- title card ----------
  function title(t) {
    const t0 = L.herb.start;
    if (t < t0 - 0.05) return '';
    const ps = 0.82 + 0.18 * spring(t - t0 + 0.05, { freq: 2.4, damping: 0.62 });
    const a = 0.6 + 0.4 * spring(t - t0, { freq: 3, damping: 0.5 });
    let out = `<rect x="-404" y="-160" width="808" height="330" rx="44" fill="${C.ink}" opacity="0.25" transform="translate(8 10)"/>`;
    out += `<rect x="-404" y="-160" width="808" height="330" rx="44" fill="${C.cream}" stroke="${C.ink}" stroke-width="8"/>`;
    out += G(tf(0, -26, 0, a), `<text x="0" y="0" font-size="118" font-weight="700" fill="#e0b324" text-anchor="middle" stroke="${C.ink}" stroke-width="10" paint-order="stroke" stroke-linejoin="round">BANANA</text>`);
    if (t > t0 + 0.3) {
      const b = 0.6 + 0.4 * spring(t - t0 - 0.3, { freq: 3, damping: 0.5 });
      out += G(tf(0, 66, 0, b), `<text x="0" y="0" font-size="58" font-weight="700" fill="${C.ink}" text-anchor="middle">Not a tree. A giant herb.</text>`);
    }
    out += `<text x="0" y="132" font-size="32" font-weight="600" fill="#6b5646" text-anchor="middle" opacity="${f2(inv(t0 + 0.6, t0 + 1.0, t))}">Source: Wikipedia, “Banana”</text>`;
    return G(tf(495, 330 + noise(77, t * 0.6) * 4, 0, ps, ps), out);
  }

  // ---------- camera ----------
  function camera(t) {
    const k = (cx, cy, z) => [cx, cy, z];
    const cam = keys(t, [
      [0, k(540, 700, 0.92)],
      [L.stem.start - 0.3, k(540, 700, 0.92), 'linear'],
      [L.stem.start + 0.4, k(580, 820, 1.25), 'inOutCubic'],
      [B.flowT - 0.1, k(580, 820, 1.25), 'linear'],
      [B.flowT + 0.5, k(560, 760, 1.0), 'inOutCubic'],
      [at('corm', 'this') - 0.2, k(560, 760, 1.0), 'linear'],
      [at('corm', 'this') + 0.5, k(540, 1080, 1.35), 'inOutCubic'],
      [L.coming.start - 0.3, k(540, 1080, 1.35), 'linear'],
      [L.coming.start + 0.4, k(500, 620, 1.0), 'inOutCubic'],
      [B.spikeB, k(500, 620, 1.0), 'linear'],
      [B.spikeC, k(420, 560, 1.08), 'inOutCubic'],
      [L.bracts.start - 0.2, k(420, 560, 1.08), 'linear'],
      [L.bracts.start + 0.5, k(360, 520, 1.42), 'inOutCubic'],
      [B.montA - 0.1, k(360, 520, 1.42), 'linear'],
      [B.montA + 0.6, k(540, 700, 0.92), 'inOutCubic'],
      [L.sucker.start - 0.1, k(540, 700, 0.92), 'linear'],
      [L.sucker.start + 0.5, k(610, 860, 1.12), 'inOutCubic'],
      [L.herb.start - 0.2, k(610, 860, 1.12), 'linear'],
      [L.herb.start + 0.5, k(540, 540, 0.85), 'inOutCubic'],
      [END, k(540, 540, 0.85), 'linear'],
    ]);
    return { cx: cam[0], cy: cam[1], z: cam[2] };
  }
  const toScreen = (cam, x, y) => [W / 2 + (x - cam.cx) * cam.z, H / 2 + (y - cam.cy) * cam.z];

  // ---------- Wiggs ----------
  const GR = GROUND;
  const POSE = {
    hide: [[HOLE_X + 10, GR + 150], [HOLE_X + 50, GR + 175], [HOLE_X + 40, GR + 250], [HOLE_X - 10, GR + 245]],
    rise: [[HOLE_X + 5, GR + 40], [HOLE_X + 15, GR + 110], [HOLE_X + 30, GR + 170], [HOLE_X + 20, GR + 230]],
    out: [[HOLE_X, GR - 175], [HOLE_X + 6, GR - 60], [HOLE_X + 2, GR + 40], [HOLE_X + 28, GR + 135]],
    point: [[HOLE_X - 30, GR + 60], [HOLE_X - 5, GR + 20], [HOLE_X + 10, GR + 70], [HOLE_X + 30, GR + 150]],
    peek: [[HOLE_X, GR - 70], [HOLE_X + 3, GR + 10], [HOLE_X + 8, GR + 70], [HOLE_X + 36, GR + 140]],
  };
  function wiggsPose(t) {
    const P = n => POSE[n].flat();
    const v = keys(t, [
      [0, P('hide')], [B.wigPop - 0.05, P('hide')], [B.wigPop + 0.12, P('rise'), 'inQuad'], [B.wigPop + 0.4, P('out'), 'outBack'],
      [at('corm', 'this') - 0.3, P('out')], [at('corm', 'this') + 0.3, P('point'), 'inOutCubic'],
      [L.coming.start, P('point')], [L.coming.start + 0.5, P('hide'), 'inOutCubic'],
      [B.montA, P('hide')], [B.montA + 0.6, P('peek'), 'outBack'],
      [L.herb.start - 0.5, P('peek')], [L.herb.start - 0.1, P('out'), 'outBack'],
    ]);
    return [[v[0], v[1]], [v[2], v[3]], [v[4], v[5]], [v[6], v[7]]];
  }

  // ---------- the film ----------
  function frame(f) {
    D.begin(f);
    const t = f / FPS;
    const cam = camera(t);
    // day/night cycles while the bunch ripens
    const mont = inv(B.montA, B.montB, t);
    const dusk = mont > 0 && mont < 1 ? 0.5 - 0.5 * Math.cos(mont * Math.PI * 4) : 0;
    const ripe = ease.inOutCubic(mont);

    // --- Big Nana ---
    const growth = lerp(0.94, 1, inv(at('spike', 'mature') - 0.2, at('spike', 'mature') + 0.4, t));
    const unfurl = 0.15 + 0.85 * ease.inOutCubic(inv(0.3, L.stem.end, t));
    const flower = 0.45 * ease.outCubic(inv(B.spikeA, B.spikeB, t)) + 0.55 * ease.inOutCubic(inv(B.spikeB, B.spikeC, t));
    const bracts = ease.outCubic(inv(B.bractT - 0.5, B.bractT + 0.6, t));
    const bunch = 0.34 * ease.outCubic(inv(B.handsT - 0.3, L.bracts.end, t)) + 0.66 * clamp(inv(B.nineA, B.nineB, t));
    const pup = ease.outBack(inv(B.suckT, B.suckT + 1.2, t), 1.2);
    let nMood = 'annoyed';
    if (t > L.hook.end) nMood = 'skeptical';
    if (t > B.sliceIn + 0.3) nMood = 'surprised';
    if (t > L.corm.start) nMood = 'excited';
    if (t > L.coming.start) nMood = 'surprised';
    if (t > L.spike.start) nMood = 'proud';
    if (t > L.bracts.start) nMood = 'happy';
    if (t > L.nine.start) nMood = 'proud';
    if (mont > 0 && mont < 1) nMood = dusk > 0.6 ? 'sleep' : 'happy';
    if (t > L.sucker.start) nMood = 'excited';
    if (t > L.herb.start) nMood = 'proud';
    const nLook = t > L.stem.start && t < L.coming.start ? [1, 0.6] : t > L.coming.start && t < B.montA ? [-0.8, -1] : t > L.sucker.start && t < L.herb.start ? [1, 0.7] : [0.3, 0];

    let world = ground(t, dusk);
    // light flowing up from the corm into everything above ground
    let glowW = '';
    if (t > B.flowT - 0.1 && t < B.cormT + 1.2) {
      const crownY = GROUND - lerp(110, 640, growth) + 8;
      for (let i = 0; i < 14; i++) {
        const p = ((t - B.flowT) * 0.9 + i / 14) % 1;
        const fade = Math.sin(clamp(inv(B.flowT - 0.1, B.flowT + 0.4, t)) * Math.PI / 2) * (1 - inv(B.cormT + 0.4, B.cormT + 1.2, t));
        const branch = i % 4, ang = [-150, -30, -110, -70][branch] * Math.PI / 180;
        let x, y;
        if (p < 0.6) { x = NANA_X + (i % 3 - 1) * 8; y = lerp(GROUND + 40, crownY, p / 0.6); }
        else { const q = (p - 0.6) / 0.4; x = NANA_X + Math.cos(ang) * 260 * q; y = crownY + Math.sin(ang) * 260 * q; }
        glowW += `<circle cx="${f2(x)}" cy="${f2(y)}" r="22" fill="url(#glow)" opacity="${f2(0.8 * fade)}"/><circle cx="${f2(x)}" cy="${f2(y)}" r="6" fill="#eaffb0" opacity="${f2(fade)}"/>`;
      }
    }
    // corm spotlight on "corm"
    {
      const g = Math.sin(clamp(inv(B.cormT - 0.15, B.cormT + 1.4, t)) * Math.PI);
      if (g > 0.01) {
        world += `<ellipse cx="${NANA_X}" cy="${GROUND + 44}" rx="${f2(150 + 20 * g)}" ry="${f2(90 + 12 * g)}" fill="url(#glow)" opacity="${f2(0.7 * g)}"/>`;
        world += `<ellipse cx="${NANA_X}" cy="${GROUND + 44}" rx="${f2(130 + 30 * (1 - g))}" ry="${f2(78 + 18 * (1 - g))}" fill="none" stroke="#fff" stroke-width="5" stroke-dasharray="16 12" opacity="${f2(0.9 * g)}"/>`;
      }
    }
    world += shadow(NANA_X, 130, 0.24);
    world += Cast.banana(NANA_X, GROUND + 6, {
      t, s: 1, growth, unfurl, flower, bunch, ripe, bracts, wind: D.wind(t, NANA_X) * 1.8, underground: true, pup, side: 1, spikeSide: -1, seed: 5,
      face: { mood: nMood, talk: talkOf('nana', f), lookX: nLook[0], lookY: nLook[1], bl: blink(t + 0.7, 3, 3.3), wink: t > B.endWink && t < B.endWink + 0.45 },
      colors: { blotch: '#4d3346' },
    });
    world += D.crumbs(t, B.wigPop + 0.1, HOLE_X, GROUND + 6, { seed: 41, n: 12, up: 520 });
    world += D.crumbs(t, B.suckT, NANA_X + 1.55 * 108, GROUND + 6, { seed: 23, n: 12, up: 480 });
    // Wiggs
    {
      const sp = wiggsPose(t);
      const pts = Cast.spine(sp[0], sp[1], sp[2], sp[3], t, t < B.wigPop ? 1.5 : 4, 24);
      let wm = t < B.wigPop ? 'sleep' : t < B.wigPop + 0.6 ? 'surprised' : 'smug';
      if (mont > 0 && mont < 1) wm = 'sleep';
      if (t > L.sucker.start) wm = 'happy';
      world += Cast.worm(pts, { t, talk: talkOf('wiggs', f), mood: wm, lookX: t > at('corm', 'this') && t < L.coming.start ? -1 : -0.6, lookY: t > at('corm', 'this') && t < L.coming.start ? 0.6 : 0,
        bl: blink(t, 4, 2.9), wink: t > B.endWink && t < B.endWink + 0.45, headS: 1.5 });
    }

    // backdrop layers
    const sunX = mont > 0 && mont < 1 ? lerp(-100, 1180, (mont * 2) % 1) : 880;
    const sunY = mont > 0 && mont < 1 ? 900 - Math.sin(((mont * 2) % 1) * Math.PI) * 700 : 290;
    const sunL = `<circle cx="${f2(sunX)}" cy="${f2(sunY)}" r="150" fill="${D.radial([[0, '#fff3b0', 0.7], [1, '#fff3b0', 0]], { cx: 0.5, cy: 0.5, r: 0.5 })}"/>` + D.sphere(sunX, sunY, 64, '#ffd75e', { w: 0, spec: false });
    let skyL = '';
    [[120, 220, 1.0, 1], [700, 160, 0.8, 2], [430, 420, 0.65, 3], [980, 380, 0.75, 4]].forEach(([x, y, s, sd]) => {
      const xx = ((x + t * (mont > 0 && mont < 1 ? 120 : 16) * s + 300) % 1500) - 300;
      skyL += D.cloud(xx, y, s, sd, D.mix('#ffffff', '#c9b6e6', dusk), D.mix('#dceef8', '#9f86c8', dusk));
    });
    const farL = hills(dusk, t), hedgeL = hedge(dusk);
    const fgL = D.fgGrass(1230, GROUND + 40, 560, 7, t);
    const camT = `translate(${W / 2} ${H / 2}) scale(${f2(cam.z)}) translate(${f2(-cam.cx)} ${f2(-cam.cy)})`;
    const layerT = p => `translate(${W / 2} ${H / 2}) scale(${f2(1 + (cam.z - 1) * p)}) translate(${f2(-(540 + (cam.cx - 540) * p))} ${f2(-(960 + (cam.cy - 960) * p))})`;
    const dof = 1 + Math.max(0, cam.z - 1) * 1.4;
    let svg = sky(t, dusk);
    svg += `<g transform="${layerT(0.15)}">${sunL}</g>`;
    svg += `<g filter="${D.blurFilter(3.5)}"><g transform="${layerT(0.15)}">${skyL}</g></g>`;
    svg += `<g filter="${D.blurFilter(5 * dof)}"><g transform="${layerT(0.45)}">${farL}</g></g>`;
    svg += `<g filter="${D.blurFilter(2.4 * dof)}"><g transform="${layerT(0.75)}">${hedgeL}</g></g>`;
    svg += `<g transform="${camT}">${world}</g>`;
    if (dusk > 0.01) svg += `<rect width="${W}" height="${H}" fill="#5a4a8a" opacity="${f2(dusk * 0.38)}" style="mix-blend-mode:multiply"/>`;
    if (glowW) svg += `<g transform="${camT}">${glowW}</g>`;
    svg += `<g filter="${D.blurFilter(9)}"><g transform="${layerT(1.4)}">${fgL}</g></g>`;

    // the pseudostem cut-away: a slice pops out of the trunk showing layer on layer of leaf stalks
    {
      const pin = ease.outBack(inv(B.sliceIn, B.sliceIn + 0.5, t), 1.3), pout = 1 - ease.inCubic(inv(B.sliceOut - 0.35, B.sliceOut, t));
      const k = Math.min(pin, pout);
      if (k > 0.01) {
        const [sx, sy] = toScreen(cam, NANA_X + 20, GROUND - 330);
        const cx = lerp(sx, 800, ease.outCubic(Math.min(1, pin))), cy = lerp(sy, 700, ease.outCubic(Math.min(1, pin))), r = 175 * k;
        let rings = '';
        const nR = 7;
        for (let i = 0; i < nR; i++) {
          const ri = r * (1 - i / nR), ox = -i * r * 0.035, oy = i * r * 0.02;
          const show = clamp((t - B.sliceIn - 0.25 - i * 0.08) / 0.2);
          if (show <= 0) continue;
          const colr = D.mix(i % 2 ? '#8cc456' : '#b5dd7a', '#e9f6c9', i / nR * 0.6);
          rings += `<circle cx="${f2(cx + ox)}" cy="${f2(cy + oy)}" r="${f2(ri * (0.9 + 0.1 * show))}" fill="${colr}" stroke="${C.ink}" stroke-width="4" opacity="${f2(show)}"/>`;
          // each layer is a leaf stalk wrapped around the next: show its seam
          rings += `<path d="M${f2(cx + ox + ri * 0.98)} ${f2(cy + oy)} L${f2(cx + ox + ri * 0.82)} ${f2(cy + oy - ri * 0.06)}" stroke="${C.ink}" stroke-width="4" opacity="${f2(show)}"/>`;
        }
        const ang = Math.atan2(cy - sy, cx - sx), dist = Math.hypot(cx - sx, cy - sy);
        if (dist > r) {
          const spn = Math.asin(Math.min(1, r / dist));
          const a1 = ang + Math.PI - (Math.PI / 2 - spn), a2 = ang + Math.PI + (Math.PI / 2 - spn);
          svg += `<path d="M${f2(sx)} ${f2(sy)} L${f2(cx + Math.cos(a1) * r)} ${f2(cy + Math.sin(a1) * r)} L${f2(cx + Math.cos(a2) * r)} ${f2(cy + Math.sin(a2) * r)} Z" fill="#fff" opacity="${f2(0.35 * k)}"/>`;
        }
        svg += circle(cx + 8, cy + 10, r, C.ink, 0, 'none', 'opacity="0.25"');
        svg += circle(cx, cy, r, '#6aa83f', 9, C.ink) + rings + circle(cx, cy, r, 'none', 9, C.ink);
        svg += circle(sx, sy, 22 * cam.z, 'none', 5, '#fff', `opacity="${f2(k)}"`);
      }
    }
    // hands counter, then "up to 20 each"
    {
      const hands = Math.floor(clamp(bunch) * 9 + 1e-6);
      const on = clamp(inv(B.nineA - 0.1, B.nineA + 0.2, t)) * (1 - inv(B.montA - 0.2, B.montA + 0.2, t));
      if (on > 0.01 && hands > 0) {
        const bump = 1 + 0.12 * Math.exp(-((t * 9 * 1.0) % 1) * 0) * 0;
        const lastStep = (B.nineA + (hands - 3) / 6 * (B.nineB - B.nineA));
        const pp = 1 + 0.18 * Math.exp(-Math.max(0, t - lastStep) * 9);
        svg += G(tf(300, 330, -3, on * pp * bump), `<rect x="-170" y="-58" width="340" height="116" rx="58" fill="#fff8e8" stroke="${C.ink}" stroke-width="7"/>` +
          `<text x="0" y="24" font-size="70" font-weight="700" fill="${C.ink}" text-anchor="middle">${hands} <tspan fill="#4e9d31">HANDS</tspan></text>`);
      }
      const on2 = clamp(inv(B.twentyT - 0.05, B.twentyT + 0.25, t)) * (1 - inv(B.montA - 0.2, B.montA + 0.2, t));
      if (on2 > 0.01) svg += G(tf(700, 470, 3, on2 * (0.7 + 0.3 * ease.outBack(clamp(inv(B.twentyT, B.twentyT + 0.35, t))))),
        `<rect x="-230" y="-52" width="460" height="104" rx="52" fill="#f6d046" stroke="${C.ink}" stroke-width="7"/>` +
        `<text x="0" y="-2" font-size="40" font-weight="700" fill="${C.ink}" text-anchor="middle">UP TO 20</text><text x="0" y="36" font-size="30" font-weight="600" fill="${C.ink}" text-anchor="middle">bananas per hand</text>`);
    }
    svg += captions(t);
    svg += title(t);
    return svg + D.defs();
  }

  // ---------- sound cues (read by engine/audio.py) ----------
  const cue = (t, type, gain = 1) => ({ t: +t.toFixed(3), type, gain });
  window.CUES = [
    cue(L.stem.start - 0.3, 'whoosh'), cue(B.wigPop + 0.1, 'pop'), cue(B.wigPop + 0.15, 'sink', 0.6),
    cue(B.sliceIn, 'lens_open'), cue(B.sliceOut - 0.35, 'lens_close'),
    cue(B.flowT - 0.1, 'shimmer'), cue(at('corm', 'this') - 0.2, 'whoosh'), cue(B.cormT, 'chime', 0.7),
    cue(L.coming.start - 0.3, 'whoosh'), cue(B.spikeA, 'grow'), cue(B.spikeB + 0.2, 'grow_big', 0.8),
    cue(L.bracts.start - 0.2, 'whoosh'), cue(B.bractT - 0.3, 'sparkle'),
    ...Array.from({ length: 9 }, (_, h) => cue(h < 3 ? B.handsT - 0.3 + h * 0.5 : B.nineA + (h - 3) / 6 * (B.nineB - B.nineA), 'pop_small', 0.6)),
    cue(B.twentyT, 'chime', 0.7),
    cue(B.montA, 'whoosh'), cue(B.montA + 0.7, 'twinkle', 0.7), cue(B.montA + 2.1, 'twinkle', 0.7),
    cue(L.sucker.start - 0.1, 'whoosh'), cue(B.suckT, 'pop'), cue(B.suckT + 0.1, 'grow'),
    cue(L.herb.start - 0.2, 'whoosh'), cue(L.herb.start, 'chime'),
    cue(B.endWink, 'wink'),
  ].sort((a, b) => a.t - b.t);

  const stage = document.getElementById('stage');
  window.renderFrame = f => { stage.innerHTML = frame(f); };
  window.FILM = { width: W, height: H, fps: FPS, frames: Math.round(END * FPS), safe: SAFE, ready: false };
  document.fonts.load('700 40px Fredoka').then(() => { window.FILM.ready = true; });
})();
