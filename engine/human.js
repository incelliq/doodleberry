// Richer 2D humans for explainer reels: adult/kid proportions, a wardrobe (tee, tank, shirt, sweater, lab coat,
// scrubs; pants, shorts, skirt; shoes), hairstyles, accessories (glasses, stethoscope, tie, badge, watch, mask,
// straw hat), an expressive face with lip-sync, posable arms and standing or seated legs. Original designs, drawn
// with D (draw.js). Origin at the feet (standing) or the seat front (seated); about 640 units tall at s=1.
// Loaded after timeline.js, draw.js; exposes `Human`.
(function (root) {
  const { clamp, lerp, noise } = root.M;
  const D = root.D;
  const f2 = n => (+n).toFixed(2);
  const INK = '#24160e';
  const G = (tr, inner, extra = '') => `<g transform="${tr}" ${extra}>${inner}</g>`;
  const tf = (x = 0, y = 0, r = 0, sx = 1, sy = sx) => `translate(${f2(x)} ${f2(y)}) rotate(${f2(r)}) scale(${f2(sx)} ${f2(sy)})`;
  const sh = (d, c, o = {}) => D.shade(d, c, { ink: INK, w: 4, depth: 8, light: 2.5, ...o });
  const ln = (d, w = 3, c = INK, extra = '') => `<path d="${d}" fill="none" stroke="${c}" stroke-width="${w}" stroke-linecap="round" stroke-linejoin="round" ${extra}/>`;
  const rad = a => (a * Math.PI) / 180;

  const SKIN = { light: '#f6d2b8', fair: '#eebd9a', tan: '#d89a6e', brown: '#a8693f', deep: '#6e4128' };
  const HAIR = { black: '#2b2220', brown: '#5a3a26', auburn: '#8a3f22', blonde: '#d9b26a', gray: '#b9b7b2', white: '#ecebe6' };

  // ---------- face ----------
  // mood: neutral | smile | worried | surprised | talk-happy | skeptical ; talk 0..1 ; look {x,y} -1..1 ; bl blink 0..1
  function face(o) {
    const { mood = 'neutral', talk = 0, lookX = 0, lookY = 0, bl = 0, skin, lashes = false, turn = 0, age = 'adult', glasses = false, mask = false } = o;
    const k = 1 - bl * 0.95;
    let s = '';
    const ex = 25, ey = -6, ox = turn * 9;
    const browY = { neutral: -30, smile: -31, worried: -33, surprised: -38, skeptical: -30, angry: -27 }[mood] ?? -30;
    const browTilt = { worried: -7, angry: 8, skeptical: 0 }[mood] || 0;
    for (const side of [-1, 1]) {
      const x = side * ex + ox * (side === Math.sign(turn) ? 1.25 : 0.75);
      const rx = 11.5 * (1 - side * turn * 0.18), ry = 13.5;
      s += `<ellipse cx="${f2(x)}" cy="${ey}" rx="${f2(rx)}" ry="${f2(ry * k)}" fill="#ffffff" stroke="${INK}" stroke-width="3"/>`;
      if (k > 0.3) {
        const px = x + lookX * rx * 0.42, py = ey + lookY * ry * 0.35 + 1;
        s += `<circle cx="${f2(px)}" cy="${f2(py)}" r="${f2(5.6 * Math.min(1, k + 0.2))}" fill="${INK}"/><circle cx="${f2(px + 2)}" cy="${f2(py - 2.2)}" r="1.8" fill="#fff"/>`;
      }
      if (mood === 'skeptical' && side > 0) s += `<path d="M${f2(x - rx - 2)} ${ey - 4} L${f2(x + rx + 2)} ${ey - 8} L${f2(x + rx + 2)} ${ey - 16} L${f2(x - rx - 2)} ${ey - 16} Z" fill="${skin}"/>`;
      if (bl > 0.15) s += `<path d="M${f2(x - rx)} ${ey} Q${f2(x)} ${f2(ey - ry * k * 1.2)} ${f2(x + rx)} ${ey}" fill="${skin}" stroke="${INK}" stroke-width="2.6"/>`;
      s += ln(`M${f2(x - rx - 1)} ${f2(ey - ry * k * 0.15)} Q${f2(x)} ${f2(ey - ry * k * 1.12)} ${f2(x + rx + 1)} ${f2(ey - ry * k * 0.2)}`, 3.2);
      if (lashes) s += ln(`M${f2(x + side * rx * 0.85)} ${f2(ey - ry * k * 0.55)} l${side * 5} -4`, 2.4);
      const bt = side * browTilt, by = browY + (mood === 'skeptical' && side > 0 ? -5 : 0);
      s += D.taper([[x - 12, by + bt * 0.5 + 2], [x - 4, by - 2 + bt * 0.2], [x + 5, by - 2 - bt * 0.2], [x + 13, by - bt * 0.5 + 2]], 5, 2.5, o.browCol || INK);
      if (age === 'old') s += ln(`M${f2(x + side * 15)} ${ey + 2} l${side * 6} 3 M${f2(x + side * 15)} ${ey + 7} l${side * 5} 1`, 1.8, INK, 'opacity="0.6"');
    }
    if (glasses) {
      for (const side of [-1, 1]) { const x = side * ex + ox; s += `<rect x="${f2(x - 16)}" y="${ey - 13}" width="32" height="25" rx="9" fill="#dff2ff" fill-opacity="0.18" stroke="${INK}" stroke-width="3.2"/>`; }
      s += ln(`M${f2(-ex + 16 + ox)} ${ey - 2} Q${f2(ox)} ${ey - 7} ${f2(ex - 16 + ox)} ${ey - 2}`, 3);
    }
    // nose
    s += ln(`M${f2(3 + turn * 10)} ${ey + 8} Q${f2(10 + turn * 12)} ${ey + 22} ${f2(1 + turn * 10)} ${ey + 25}`, 2.8);
    if (mask) {
      s += sh(`M-44 ${ey + 14} Q0 ${ey + 6} 44 ${ey + 14} L40 ${ey + 50} Q0 ${ey + 64} -40 ${ey + 50} Z`, '#3fb37a', { depth: 4, w: 3 });
      s += ln(`M-38 ${ey + 26} Q0 ${ey + 20} 38 ${ey + 26} M-36 ${ey + 38} Q0 ${ey + 33} 36 ${ey + 38}`, 1.8, '#2a7a52');
      return s;
    }
    // mouth
    const my = ey + 40, mx = turn * 7, open = clamp(talk);
    if (open > 0.08 || mood === 'surprised') {
      const w = mood === 'surprised' && open < 0.2 ? 7 : 11 + open * 4, h = (mood === 'surprised' ? 9 : 3) + open * 15;
      s += `<path d="M${f2(mx - w)} ${my} Q${f2(mx)} ${my - 4} ${f2(mx + w)} ${my} Q${f2(mx + w * 0.8)} ${f2(my + h)} ${f2(mx)} ${f2(my + h)} Q${f2(mx - w * 0.8)} ${f2(my + h)} ${f2(mx - w)} ${my} Z" fill="#6a2420" stroke="${INK}" stroke-width="3" stroke-linejoin="round"/>`;
      if (h > 8) s += `<path d="M${f2(mx - w * 0.7)} ${my + 1} L${f2(mx + w * 0.7)} ${my + 1} L${f2(mx + w * 0.55)} ${my + 4.5} L${f2(mx - w * 0.55)} ${my + 4.5} Z" fill="#fff"/>`;
      if (h > 12) s += `<ellipse cx="${f2(mx + 1)}" cy="${f2(my + h * 0.72)}" rx="${f2(w * 0.45)}" ry="${f2(h * 0.18)}" fill="#e27a76"/>`;
    } else {
      const c = { smile: [5, 6], 'talk-happy': [5, 6], worried: [-1, -4], neutral: [1, 1], skeptical: [3, -2], angry: [-2, -3] }[mood] || [1, 1];
      s += ln(`M${f2(mx - 10)} ${my + c[1] * -0.3} Q${f2(mx)} ${f2(my + c[0])} ${f2(mx + 11)} ${my - c[1] * 0.4}`, 3);
    }
    return s;
  }

  // ---------- hair ----------
  function hairBack(style, col) {
    if (style === 'long') return sh('M-62 -40 C-80 30 -70 110 -50 130 L50 130 C70 110 80 30 62 -40 Z', col, { depth: 10 });
    if (style === 'bob') return sh('M-62 -36 C-74 20 -66 50 -46 58 L46 58 C66 50 74 20 62 -36 Z', col, { depth: 9 });
    if (style === 'ponytail') return G(tf(52, -40, 18), sh('M0 0 C30 10 34 60 18 100 C10 110 -4 100 0 80 C6 50 -4 20 0 0 Z', col, { depth: 6 }));
    if (style === 'bun') return sh('M-26 -112 C-26 -142 26 -142 26 -112 C26 -96 -26 -96 -26 -112 Z', col, { depth: 6 });
    return '';
  }
  function hairFront(style, col) {
    const cap = (d) => sh(d, col, { dir: [0.4, 0.9], depth: 10, light: 4 });
    switch (style) {
      case 'short': return cap('M-60 -20 C-66 -84 -30 -110 4 -108 C44 -108 68 -82 62 -24 C56 -48 44 -62 18 -66 C-6 -60 -30 -66 -46 -56 C-54 -46 -58 -34 -60 -20 Z');
      case 'sidepart': return cap('M-61 -18 C-68 -86 -24 -112 10 -108 C48 -104 70 -76 61 -20 C58 -46 50 -60 34 -66 C6 -78 -20 -64 -40 -54 C-52 -44 -58 -32 -61 -18 Z') + ln('M-6 -106 C-12 -88 -24 -74 -40 -62', 2.2, D.shadowOf(col, 1.2));
      case 'swept': return cap('M-62 -10 C-74 -70 -50 -112 0 -112 C54 -114 76 -74 64 -10 C60 -40 54 -58 40 -64 C30 -50 10 -46 -10 -58 C-30 -50 -48 -52 -56 -40 Z') + ln('M-30 -96 C-10 -84 14 -86 40 -96 M-40 -80 C-20 -70 10 -70 34 -80', 2, D.shadowOf(col, 0.8));
      case 'buzz': return cap('M-60 -26 C-62 -84 -30 -106 0 -106 C34 -106 62 -86 60 -26 C52 -62 30 -76 0 -76 C-30 -76 -52 -62 -60 -26 Z');
      case 'bald': return cap('M-64 -10 C-70 -40 -62 -56 -54 -48 C-52 -34 -56 -22 -58 -6 Z') + cap('M64 -10 C70 -40 62 -56 54 -48 C52 -34 56 -22 58 -6 Z');
      case 'long': case 'bob': case 'ponytail': case 'bun':
        return cap('M-62 -14 C-70 -80 -34 -112 2 -110 C40 -110 70 -82 62 -14 C58 -38 46 -58 24 -64 C10 -48 -16 -40 -36 -46 C-50 -40 -58 -28 -62 -14 Z') +
          ln('M2 -108 C8 -90 18 -74 24 -64', 2, D.shadowOf(col, 1.2));
      default: return '';
    }
  }

  // ---------- body parts ----------
  // limb: tapered tube from a to b with ink; returns svg
  const limb = (a, b, w0, w1, col) => D.inkTaper(D.bez(a, [lerp(a[0], b[0], 0.33), lerp(a[1], b[1], 0.33)], [lerp(a[0], b[0], 0.66), lerp(a[1], b[1], 0.66)], b, 6), w0, w1, col, INK, 3.5);
  function hand(x, y, ang, skin, s = 1) {
    return G(tf(x, y, ang, s), sh('M-11 -4 C-12 10 -6 22 4 22 C14 20 16 8 13 -4 C10 -10 -8 -10 -11 -4 Z', skin, { depth: 4, light: 2, w: 3.2 }) +
      sh('M10 -2 C18 0 22 8 18 13 C14 14 10 8 8 4 Z', skin, { depth: 2, light: 1, w: 2.8 }) + ln('M-4 12 L-4 19 M2 13 L2 20', 1.6, INK, 'opacity="0.5"'));
  }

  // arm from the shoulder: sh = angle from hanging (deg, + = outward), el = extra elbow bend (deg, + = forward/up)
  function arm(side, a, o) {
    const { U = 112, F = 104, sleeve = 'long', skin, cloth, cuff, coat } = o;
    const sx = side * 70, sy = o.shY + 8;
    const a1 = rad(a.sh), a2 = rad(a.sh + a.el);
    const ex = sx + side * Math.sin(a1) * U, ey = sy + Math.cos(a1) * U;
    const hx = ex + side * Math.sin(a2) * F, hy = ey + Math.cos(a2) * F;
    let s = '';
    const foreCol = sleeve === 'long' ? cloth : skin, upperCol = sleeve === 'none' ? skin : cloth;
    s += limb([ex, ey], [hx, hy], 35, 27, foreCol);

    s += limb([sx, sy], [ex, ey], sleeve === 'none' ? 36 : 46, sleeve === 'none' ? 31 : 38, upperCol);
    if (sleeve === 'short') s += limb([sx, sy], [lerp(sx, ex, 0.72), lerp(sy, ey, 0.72)], 48, 43, cloth);
    if (sleeve === 'long' && cuff) s += limb([lerp(ex, hx, 0.88), lerp(ey, hy, 0.88)], [hx, hy], 25, 24, cuff);
    if (a.hidden) return { svg: s, hand: [hx, hy] };
    s += hand(hx, hy, -side * (a.sh + a.el) * 0.9, skin, 1.35);
    if (o.watch && side < 0) s += G(tf(lerp(ex, hx, 0.86), lerp(ey, hy, 0.86), -side * (a.sh + a.el)), `<rect x="-14" y="-5" width="28" height="10" rx="4" fill="#2a2a30" stroke="${INK}" stroke-width="2"/><circle r="5" fill="#9fd8ff" stroke="${INK}" stroke-width="1.6"/>`);
    return { svg: s, hand: [hx, hy] };
  }

  // ---------- the human ----------
  // o: t, s, flip, kid, skin, hair {style, color}, top {type, color, accent}, bottom {type, color}, shoes {color},
  //    pose: 'stand' | 'sit', armL/armR {sh, el, hidden}, lean, headTilt, turn (-1..1), mood, talk, lookX/Y, bl,
  //    acc: {glasses, stethoscope, tie, badge, watch, mask, hat: 'straw'|'cap', pen}
  function human(x, y, o = {}) {
    const { t = 0, s = 1, flip = 1, kid = false, pose = 'stand', lean = 0, headTilt = 0, turn = 0, mood = 'neutral', talk = 0, lookX = 0, lookY = 0, bl = 0, lashes = false, age = 'adult' } = o;
    const skin = SKIN[o.skin] || o.skin || SKIN.fair;
    const hair = { style: 'short', color: 'brown', ...(o.hair || {}) };
    const hcol = HAIR[hair.color] || hair.color;
    const top = { type: 'tee', accent: '#ffffff', ...(o.top || {}) };
    if (!top.color) top.color = top.type === 'labcoat' ? '#f6f7f9' : '#3f7fd0';
    const bottom = { type: 'pants', color: '#2c2f3a', ...(o.bottom || {}) };
    const shoes = { color: '#3a2a20', ...(o.shoes || {}) };
    const acc = o.acc || {};
    const k = kid ? 0.82 : 1;                      // body height factor (kids: shorter torso and legs, same-size head)
    const breathe = Math.sin(t * 2.1) * 2 + talk * 2.5 * Math.sin(t * 17);
    const armL = o.armL || { sh: 8, el: 8 }, armR = o.armR || { sh: 8, el: 8 };
    const coat = top.type === 'labcoat';
    const shirtCol = coat ? (top.shirt || '#4f86c6') : top.color;
    let out = '';

    // legs
    const hipY = pose === 'sit' ? (-(o.seatH || 230) - 30) : -270 * k;
    if (pose === 'stand') {
      for (const side of [-1, 1]) {
        const hx = side * 30, fx = side * (34 + (side > 0 ? 4 : 0));
        const legCol = bottom.type === 'skirt' || bottom.type === 'shorts' ? skin : bottom.color;
        out += limb([hx, hipY], [fx, -26], 56, 40, legCol);
        if (bottom.type === 'shorts') out += limb([hx, hipY], [lerp(hx, fx, 0.45), lerp(hipY, -26, 0.45)], 62, 56, bottom.color);
        if (bottom.type === 'pants') out += ln(`M${f2(hx + side * 4)} ${f2(hipY + 40)} L${f2(fx + side * 2)} -40`, 2, D.shadowOf(bottom.color, 0.7), 'opacity="0.7"');
        out += G(tf(fx + side * 6, -12), sh(`M-24 -16 C-26 -2 -22 12 -10 14 L${side > 0 ? 34 : 22} 14 C${side > 0 ? 40 : 28} 12 ${side > 0 ? 38 : 26} 0 ${side > 0 ? 26 : 18} -6 L14 -18 Z`, shoes.color, { depth: 4, light: 2, w: 3.2 }));
      }
    } else {
      // seated, 3/4: thighs come forward (foreshortened), shins drop to the floor
      // seated: origin is the floor below the seat front; thighs run forward (toward +x), shins drop to the floor
      const seatY = -o.seatH || -230;
      for (const side of [1, -1]) { // far leg first
        const off = side < 0 ? 16 : 0, hx = -40 + off, kx = 110 + off, ky = seatY - 6 + off * 0.3, fx = 116 + off + (side < 0 ? 8 : -4), fy = -14;
        const legCol = bottom.type === 'skirt' || bottom.type === 'shorts' ? skin : (side > 0 ? D.shadowOf(bottom.color, 0.5) : bottom.color);
        out += limb([kx, ky], [fx, fy], 40, 32, legCol);
        out += limb([hx, seatY - 30], [kx, ky], 66, 52, bottom.type === 'shorts' || bottom.type === 'skirt' ? bottom.color : legCol);
        out += G(tf(fx + 4, fy + 2), sh('M-22 -12 C-24 0 -20 10 -8 12 L34 12 C40 10 38 -2 26 -6 L12 -14 Z', side > 0 ? D.shadowOf(shoes.color, 0.5) : shoes.color, { depth: 4, light: 2, w: 3.2 }));
      }
    }

    // torso (with lean)
    let body = '';
    const shY = pose === 'sit' ? hipY - 170 : -440 * k, waist = hipY + 10;
    const wst = o.figure === 'curvy' ? 50 : 58;
    const torso = `M-70 ${shY - 2} C-86 ${shY + 6} -84 ${shY + 50} -78 ${shY + 80} C-70 ${shY + 120} -${wst} ${waist - 50} -60 ${waist} L60 ${waist} C${wst} ${waist - 50} 70 ${shY + 120} 78 ${shY + 80} C84 ${shY + 50} 86 ${shY + 6} 70 ${shY - 2} C44 ${shY - 14} -44 ${shY - 14} -70 ${shY - 2} Z`;
    // hips/bottom garment top
    body += sh(`M-60 ${waist - 6} L60 ${waist - 6} L64 ${hipY + 36} L-64 ${hipY + 36} Z`, bottom.type === 'skirt' ? bottom.color : bottom.color, { depth: 6, w: 3.6 });
    if (bottom.type === 'skirt') body += sh(`M-62 ${hipY + 10} L62 ${hipY + 10} L84 ${hipY + (pose === 'sit' ? 70 : 120)} L-84 ${hipY + (pose === 'sit' ? 70 : 120)} Z`, bottom.color, { depth: 8, w: 3.6 });
    body += `<rect x="-62" y="${f2(waist - 12)}" width="124" height="14" rx="4" fill="${D.shadowOf(bottom.color, 1.3)}" stroke="${INK}" stroke-width="3"/>`;
    // shirt / top
    const topCol = top.type === 'tank' ? top.color : shirtCol;
    body += sh(torso, topCol, { dir: [0.35, 0.94], depth: 14, light: 4 });
    if (top.type === 'tank') body += sh(`M-40 ${shY - 2} C-30 ${shY + 40} 30 ${shY + 40} 40 ${shY - 2} Z`, skin, { depth: 4, light: 1, w: 3 });
    if (top.type === 'tee' || top.type === 'scrubs') body += sh(`M-26 ${shY - 6} C-16 ${shY + 22} 16 ${shY + 22} 26 ${shY - 6} Z`, skin, { depth: 3, light: 1, w: 3 });
    if (top.type === 'scrubs') body += ln(`M-26 ${shY - 6} L0 ${shY + 40} L26 ${shY - 6}`, 3) + `<rect x="22" y="${shY + 70}" width="34" height="30" rx="4" fill="none" stroke="${INK}" stroke-width="2.6"/>`;
    if (top.type === 'sweater') body += sh(`M-34 ${shY - 6} L0 ${shY + 30} L34 ${shY - 6} L22 ${shY - 12} L0 ${shY + 12} L-22 ${shY - 12} Z`, top.accent, { depth: 3, light: 1, w: 3 }) +
      ln(`M-56 ${waist - 18} L56 ${waist - 18}`, 2.5, D.shadowOf(top.color, 0.7));
    if (top.type === 'shirt' || coat) {
      body += sh(`M-30 ${shY - 8} L0 ${shY + 22} L30 ${shY - 8} L20 ${shY - 16} L0 ${shY + 4} L-20 ${shY - 16} Z`, coat ? '#f4f6fa' : top.accent, { depth: 3, light: 1, w: 3 });
      if (!coat) for (let i = 0; i < 4; i++) body += `<circle cx="0" cy="${f2(shY + 40 + i * 38)}" r="3" fill="${D.shadowOf(topCol, 1)}"/>`;
    }
    if (acc.tie) body += sh(`M-8 ${shY + 18} L8 ${shY + 18} L12 ${shY + 120} L0 ${shY + 140} L-12 ${shY + 120} Z`, acc.tie, { depth: 4, light: 2, w: 3 }) + sh(`M-9 ${shY + 8} L9 ${shY + 8} L7 ${shY + 22} L-7 ${shY + 22} Z`, acc.tie, { depth: 2, light: 1, w: 3 });
    if (coat) {
      const cc = top.color || '#f6f7f9', hem = pose === 'sit' ? hipY + 50 : hipY + 120;
      for (const side of [-1, 1]) {
        body += sh(`M${side * 18} ${shY - 6} L${side * 78} ${shY + 6} C${side * 86} ${shY + 80} ${side * 80} ${hem - 60} ${side * 76} ${hem} L${side * 24} ${hem} L${side * 30} ${shY + 150} Z`, cc, { dir: [side * 0.3, 0.95], depth: 10, light: 3, w: 3.6 });
        body += ln(`M${side * 18} ${shY - 6} L${side * 46} ${shY + 70} L${side * 30} ${shY + 150}`, 3);
        body += `<path d="M${side * 34} ${f2(hipY - 24)} L${side * 70} ${f2(hipY - 24)} L${side * 68} ${f2(hipY + 18)} L${side * 36} ${f2(hipY + 18)} Z" fill="none" stroke="${INK}" stroke-width="2.6"/>`;
      }
      body += `<path d="M38 ${shY + 64} L66 ${shY + 64} L66 ${shY + 92} L38 ${shY + 92} Z" fill="none" stroke="${INK}" stroke-width="2.6"/>`;
      if (acc.pen) body += `<rect x="44" y="${shY + 50}" width="5" height="26" rx="2" fill="#2f5fbf" stroke="${INK}" stroke-width="1.6"/><rect x="54" y="${shY + 54}" width="5" height="22" rx="2" fill="#d23c3c" stroke="${INK}" stroke-width="1.6"/>`;
    }
    if (acc.badge) body += G(tf(coat ? -52 : -40, shY + 92, -4), `<rect x="-17" y="-22" width="34" height="44" rx="5" fill="#fff" stroke="${INK}" stroke-width="2.6"/><rect x="-11" y="-14" width="22" height="16" rx="2" fill="#9fc6e8"/><path d="M-11 8 L11 8 M-11 14 L6 14" stroke="${INK}" stroke-width="2"/>`);
    if (acc.stethoscope) {
      body += ln(`M-30 ${shY - 2} C-50 ${shY + 60} -40 ${shY + 120} -24 ${shY + 150} M30 ${shY - 2} C48 ${shY + 50} 40 ${shY + 90} 30 ${shY + 110}`, 7, INK) +
        ln(`M-30 ${shY - 2} C-50 ${shY + 60} -40 ${shY + 120} -24 ${shY + 150} M30 ${shY - 2} C48 ${shY + 50} 40 ${shY + 90} 30 ${shY + 110}`, 4, '#4a5560');
      body += `<circle cx="30" cy="${shY + 120}" r="11" fill="#c8ced6" stroke="${INK}" stroke-width="3"/><circle cx="30" cy="${shY + 120}" r="5" fill="#8a96a2"/>`;
    }
    // arms: back arm first, then torso, then front arm
    const sleeve = top.type === 'tank' ? 'none' : (top.type === 'tee' || top.type === 'scrubs') ? 'short' : 'long';
    const armCol = coat ? (top.color || '#f6f7f9') : top.color;
    const A = arm(-1, armL, { k, shY, sleeve, skin, cloth: armCol, cuff: coat ? null : null, watch: acc.watch });
    const B = arm(1, armR, { k, shY, sleeve, skin, cloth: armCol, watch: false });
    // neck + head
    const headY = shY - 92;
    let head = '';
    for (const side of [-1, 1]) head += sh(`M${side * 58} -14 C${side * 74} -22 ${side * 76} 10 ${side * 60} 18 Z`, skin, { depth: 3, light: 1, w: 3 });
    head += sh('M-60 -30 C-64 -84 -30 -104 0 -104 C32 -104 64 -84 60 -30 C60 10 46 50 0 56 C-46 50 -60 10 -60 -30 Z', skin, { dir: [0.5, 0.86], depth: 10, light: 3.5, w: 4 });
    if (age === 'old' || acc.beard) head += acc.beard ? sh('M-56 0 C-50 40 -24 62 0 62 C24 62 50 40 56 0 C44 30 24 36 0 36 C-24 36 -44 30 -56 0 Z', hcol, { depth: 4, w: 3 }) : '';
    head += face({ mood, talk, lookX, lookY, bl, skin, lashes, turn, age, glasses: acc.glasses, mask: acc.mask, browCol: age === 'old' ? D.shadowOf(hcol, 0.6) : INK });
    head += hairFront(hair.style, hcol);
    if (acc.hat === 'straw') head += sh('M-108 -64 Q0 -40 108 -64 Q100 -40 0 -30 Q-100 -40 -108 -64 Z', '#e9a73a', { depth: 6, w: 3.6 }) + sh('M-62 -62 C-64 -128 -30 -142 0 -140 C30 -142 64 -128 62 -62 Q0 -48 -62 -62 Z', '#f2b445', { depth: 9, w: 3.6 }) + ln('M-60 -78 Q0 -64 60 -78', 9, '#a8642a');
    if (acc.hat === 'cap') head += sh('M-62 -50 C-64 -112 62 -112 62 -50 Q0 -40 -62 -50 Z', acc.capColor || '#d23c3c', { depth: 8, w: 3.6 }) + sh('M-20 -54 Q40 -60 96 -44 Q60 -30 -10 -44 Z', D.shadowOf(acc.capColor || '#d23c3c', 0.6), { depth: 3, w: 3.2 });
    const neck = sh(`M-20 ${headY + 44} L20 ${headY + 44} L24 ${shY + 6} L-24 ${shY + 6} Z`, skin, { depth: 5, light: 1, w: 3.2 });

    const hb = hairBack(hair.style, hcol);
    const headT = tf(0, headY + breathe * 0.5, headTilt + noise(31, t * 0.7) * 2 + talk * 1.8 * Math.sin(t * 8));
    const torsoG = G(tf(0, breathe * 0.3, lean * 0.4), (hb ? G(headT, hb) : '') + A.svg + body + neck + G(headT, head) + B.svg, `transform-origin="0 ${hipY}"`);
    out += torsoG;
    return { svg: G(`translate(${f2(x)} ${f2(y)}) scale(${f2(s * flip)} ${f2(s)})`, out), hands: [A.hand, B.hand].map(([a, b]) => [x + a * s * flip, y + b * s]), headY: y + headY * s };
  }

  root.Human = { human, face, SKIN, HAIR };
})(typeof window !== 'undefined' ? window : globalThis);
