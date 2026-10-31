// Frame-function motion library. Every value is a pure function of the frame
// number: no timers, no Math.random. Loaded as a plain <script>; exposes `M`.
(function (root) {
  const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
  const lerp = (a, b, t) => a + (b - a) * t;
  const inv = (a, b, x) => (b === a ? (x >= b ? 1 : 0) : clamp((x - a) / (b - a)));
  const mix = (a, b, t) => (typeof a === 'number' ? lerp(a, b, t) : a.map((v, i) => lerp(v, b[i], t)));

  const ease = {
    linear: t => t,
    inQuad: t => t * t,
    outQuad: t => 1 - (1 - t) * (1 - t),
    inOutQuad: t => (t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2),
    inCubic: t => t * t * t,
    outCubic: t => 1 - Math.pow(1 - t, 3),
    inOutCubic: t => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2),
    outQuart: t => 1 - Math.pow(1 - t, 4),
    inOutQuart: t => (t < 0.5 ? 8 * t ** 4 : 1 - Math.pow(-2 * t + 2, 4) / 2),
    outExpo: t => (t === 1 ? 1 : 1 - Math.pow(2, -10 * t)),
    inOutExpo: t => t === 0 ? 0 : t === 1 ? 1 : t < 0.5 ? Math.pow(2, 20 * t - 10) / 2 : (2 - Math.pow(2, -20 * t + 10)) / 2,
    // anticipation: dips below 0 before travelling
    inBack: (t, s = 1.70158) => (s + 1) * t * t * t - s * t * t,
    outBack: (t, s = 1.70158) => 1 + (s + 1) * Math.pow(t - 1, 3) + s * Math.pow(t - 1, 2),
    inOutBack: (t, s = 1.70158 * 1.525) => t < 0.5
      ? (Math.pow(2 * t, 2) * ((s + 1) * 2 * t - s)) / 2
      : (Math.pow(2 * t - 2, 2) * ((s + 1) * (t * 2 - 2) + s) + 2) / 2,
  };

  // Damped spring from 0 to 1, t in seconds. Closed form, so it can be sampled
  // at any frame. Underdamped by default for follow-through.
  function spring(t, { freq = 2.2, damping = 0.45 } = {}) {
    if (t <= 0) return 0;
    const w = 2 * Math.PI * freq, z = damping;
    if (z >= 1) return 1 - (1 + w * t) * Math.exp(-w * t);
    const wd = w * Math.sqrt(1 - z * z);
    return 1 - Math.exp(-z * w * t) * (Math.cos(wd * t) + (z * w / wd) * Math.sin(wd * t));
  }

  // Piecewise keyframes: [[time, value, easeIntoThisKey?], ...] sorted by time.
  function keys(t, ks) {
    if (t <= ks[0][0]) return ks[0][1];
    for (let i = 1; i < ks.length; i++) {
      const [t1, v1, e] = ks[i];
      if (t <= t1) {
        const [t0, v0] = ks[i - 1];
        const fn = typeof e === 'function' ? e : ease[e || 'inOutCubic'];
        return mix(v0, v1, fn(inv(t0, t1, t)));
      }
    }
    return ks[ks.length - 1][1];
  }

  // Deterministic smooth noise (seeded value noise, cosine-interpolated).
  function hash(n) {
    const s = Math.sin(n * 127.1 + 311.7) * 43758.5453123;
    return s - Math.floor(s);
  }
  function noise(seed, t) {
    const i = Math.floor(t), f = t - i;
    const a = hash(i + seed * 101.3), b = hash(i + 1 + seed * 101.3);
    const u = (1 - Math.cos(f * Math.PI)) / 2;
    return lerp(a, b, u) * 2 - 1;
  }
  const rand = (seed) => hash(seed * 9.13 + 0.71);

  // Blink: returns eyelid closure 0..1. Irregular but seeded.
  function blink(t, seed = 0, every = 3.2) {
    const k = Math.floor((t + rand(seed) * every) / every);
    const start = k * every - rand(seed) * every + rand(seed + k) * every * 0.6;
    const d = t - start;
    if (d < 0 || d > 0.16) return 0;
    return Math.sin((d / 0.16) * Math.PI);
  }

  // Pop-in envelope with squash & stretch: returns {s, sx, sy}.
  function pop(t, t0, dur = 0.45) {
    const p = (t - t0) / dur;
    if (p <= 0) return { s: 0, sx: 0, sy: 0 };
    const s = spring(t - t0, { freq: 2.6, damping: 0.42 });
    const wob = Math.exp(-p * 3) * Math.sin(p * 14);
    return { s, sx: s * (1 + 0.12 * wob), sy: s * (1 - 0.12 * wob) };
  }

  // Timing helpers bound to a parsed timing.json
  function bindTiming(timing) {
    const lines = Object.fromEntries(timing.lines.map(l => [l.id, l]));
    const words = timing.lines.flatMap(l => l.words.map(w => ({ ...w, line: l.id })));
    const word = (lineId, text, nth = 0) => {
      const ws = lines[lineId].words.filter(w => w.text.toLowerCase().replace(/[^a-z']/g, '') === text.toLowerCase());
      if (!ws[nth]) throw new Error(`word ${text} not in ${lineId}`);
      return ws[nth];
    };
    return { lines, words, word, fps: timing.fps };
  }

  // SVG helpers
  const tf = (x = 0, y = 0, r = 0, sx = 1, sy = sx) =>
    `translate(${x.toFixed(2)} ${y.toFixed(2)}) rotate(${r.toFixed(2)}) scale(${sx.toFixed(4)} ${sy.toFixed(4)})`;
  const g = (attrs, inner) => `<g ${attrs}>${inner}</g>`;

  root.M = { clamp, lerp, inv, mix, ease, spring, keys, noise, rand, blink, pop, bindTiming, tf, g };
})(typeof window !== 'undefined' ? window : globalThis);
