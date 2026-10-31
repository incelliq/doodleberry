"""Score, effects and mix, all synthesized in code (seeded, so every build is
identical).

    python audio.py FILM_DIR

Reads FILM_DIR/score.json (tempo, offset, sections), FILM_DIR/timing.json
(voice lines) and FILM_DIR/build/cues.json (on-screen events, dumped from
the scene by `render.mjs --dump-cues`). Writes build/music.wav (music only),
build/sfx.wav, build/mix.wav and adds the beat grid to timing.json.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pyloudnorm as pyln
import soundfile as sf
from scipy.signal import butter, sosfilt, resample_poly

SR = 48000
RNG = np.random.default_rng(7)


def note_hz(n):  # MIDI note -> Hz
    return 440.0 * 2 ** ((n - 69) / 12)


def env(n, a, d, sustain=0.0, r=0.0):
    t = np.arange(n) / SR
    e = np.minimum(1, t / max(a, 1e-4)) * (sustain + (1 - sustain) * np.exp(-t / max(d, 1e-4)))
    if r > 0:
        tail = int(r * SR)
        if tail < n:
            e[-tail:] *= np.linspace(1, 0, tail)
    return e


def lp(x, hz, order=2):
    return sosfilt(butter(order, hz, 'low', fs=SR, output='sos'), x)


def hp(x, hz, order=2):
    return sosfilt(butter(order, hz, 'high', fs=SR, output='sos'), x)


def bp(x, lo, hi, order=2):
    return sosfilt(butter(order, [lo, hi], 'band', fs=SR, output='sos'), x)


def add(buf, x, t, gain=1.0):
    i = int(round(t * SR))
    if i >= len(buf):
        return
    j = min(len(buf), i + len(x))
    buf[i:j] += x[: j - i] * gain


def pan_gains(p):
    """Constant-power pan, p in -1 (left) .. 1 (right)."""
    a = (p + 1) * np.pi / 4
    return np.cos(a), np.sin(a)


def add_st(buf, x, t, gain=1.0, pan=0.0):
    i = int(round(t * SR))
    if i >= len(buf):
        return
    j = min(len(buf), i + len(x))
    l, r = pan_gains(pan)
    seg = x[: j - i] * gain
    buf[i:j, 0] += seg * l
    buf[i:j, 1] += seg * r


def declick(x, ms=3):
    k = min(len(x) // 2, int(ms * SR / 1000))
    if k > 0:
        x = x.copy()
        x[:k] *= np.linspace(0, 1, k)
        x[-k:] *= np.linspace(1, 0, k)
    return x


# ---------------- instruments ----------------
def pluck(hz, dur, bright=0.5):
    """Karplus-Strong string, a soft ukulele-ish pluck."""
    n = int(dur * SR)
    p = max(2, int(SR / hz))
    buf = RNG.uniform(-1, 1, p)
    buf = lp(buf, 1500 + 5000 * bright)
    out = np.zeros(n)
    for i in range(n):
        out[i] = buf[i % p]
        buf[i % p] = 0.5 * (buf[i % p] + buf[(i + 1) % p]) * 0.996
    return out * env(n, 0.002, dur, 0.0, 0.05)


def marimba(hz, dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = np.sin(2 * np.pi * hz * t) + 0.35 * np.sin(2 * np.pi * hz * 4 * t) * np.exp(-t * 30)
    return x * env(n, 0.003, 0.35, 0.0, 0.05)


def bass(hz, dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = np.sin(2 * np.pi * hz * t) + 0.25 * np.sin(2 * np.pi * hz * 2 * t)
    return lp(x, 600) * env(n, 0.01, 0.5, 0.35, 0.08)


def pad(hzs, dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = sum(np.sin(2 * np.pi * h * t + 0.3 * np.sin(2 * np.pi * 0.3 * t)) for h in hzs) / len(hzs)
    a = np.minimum(1, t / 0.4) * np.minimum(1, (dur - t) / 0.5).clip(0)
    return lp(x, 1800) * a


def shaker(dur=0.06):
    n = int(dur * SR)
    return bp(RNG.normal(0, 1, n), 5000, 11000) * env(n, 0.004, 0.02)


def thump():
    n = int(0.25 * SR)
    t = np.arange(n) / SR
    f = 55 + 70 * np.exp(-t * 30)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, 0.002, 0.12)


# ---------------- score ----------------
CHORDS = {  # root MIDI and triad, F major palette
    'F': (41, [65, 69, 72]), 'Dm': (38, [62, 65, 69]), 'Bb': (46, [62, 65, 70]),
    'C': (36, [64, 67, 72]), 'Gm': (43, [62, 67, 70]), 'Am': (45, [64, 69, 72]),
}
MELODY = [0, 2, 1, 2, 0, 1, 2, 1]  # index into chord tones, one per 8th


def music(score, total, speaking=lambda t: False):
    """Stereo score. The melody sits an octave above the narrator's pitch band and
    drops to quarter notes while the narrator speaks, eighths between lines."""
    bpm, off = score['bpm'], score['offset_s']
    beat = 60 / bpm
    out = np.zeros((int(total * SR) + SR * 4, 2))
    beats = []
    for sec in score['sections']:
        b0, b1 = sec['from_beat'], sec['to_beat']
        prog = sec['chords']
        for b in range(b0, b1):
            t = off + b * beat
            if t < 0 or t > total:
                continue
            beats.append(round(t, 3))
            bar_beat = (b - b0) % 4
            ch = prog[((b - b0) // 4) % len(prog)]
            root, tri = CHORDS[ch]
            kind = sec['kind']
            if kind in ('main', 'finale', 'intro'):
                for half in range(2):
                    tt = t + half * beat / 2
                    if half and speaking(tt):
                        continue  # leave room for the words
                    k = (bar_beat * 2 + half)
                    hz = note_hz(tri[MELODY[k % 8]] + 12 + (12 if kind == 'finale' and k % 4 == 3 else 0))
                    vel = (0.11 if kind == 'intro' else 0.13) * (1.0 if half == 0 else 0.7) * (1.15 if bar_beat == 0 and half == 0 else 1)
                    add_st(out, pluck(hz, 0.55, 0.28), tt, vel, -0.3)
            if kind in ('main', 'finale') and bar_beat in (0, 2):
                add_st(out, bass(note_hz(root), beat * 1.8), t, 0.3)
            if kind == 'intro' and bar_beat == 0:
                add_st(out, bass(note_hz(root), beat * 3.5), t, 0.2)
            if kind in ('main', 'finale'):
                for half in range(2):
                    add_st(out, shaker(), t + half * beat / 2, 0.045 if half else 0.065, 0.45 if half else -0.45)
                if bar_beat == 0:
                    add_st(out, thump(), t, 0.28)
            if kind == 'reflect' and bar_beat == 0:
                hz = [note_hz(h) for h in tri]
                add_st(out, pad([h * 0.9983 for h in hz], beat * 4.2), t, 0.2, -0.6)   # slight detune L/R for width
                add_st(out, pad([h * 1.0017 for h in hz], beat * 4.2), t, 0.2, 0.6)
                add_st(out, bass(note_hz(root), beat * 4), t, 0.16)
            if kind == 'reflect' and bar_beat in (1, 3):
                add_st(out, marimba(note_hz(tri[bar_beat // 2 + 1] + 12), 0.6), t, 0.07, 0.35)
            if kind == 'finale' and bar_beat == 0:
                hz = [note_hz(h) for h in tri]
                add_st(out, pad([h * 0.9983 for h in hz], beat * 4.2), t, 0.1, -0.6)
                add_st(out, pad([h * 1.0017 for h in hz], beat * 4.2), t, 0.1, 0.6)
        if sec.get('end_chord'):
            t = off + b1 * beat
            root, tri = CHORDS[sec['end_chord']]
            hz = [note_hz(h) for h in tri] + [note_hz(tri[0] + 12)]
            add_st(out, pad([h * 0.9983 for h in hz], 3.4), t, 0.22, -0.6)
            add_st(out, pad([h * 1.0017 for h in hz], 3.4), t, 0.22, 0.6)
            add_st(out, bass(note_hz(root), 3.0), t, 0.28)
            for i, nn in enumerate(tri + [tri[0] + 12]):
                add_st(out, marimba(note_hz(nn + 12), 1.2), t + i * 0.07, 0.11, -0.4 + i * 0.27)
            beats.append(round(t, 3))
    out = hp(out.T, 40).T
    return out[: int(total * SR)], beats


# ---------------- effects ----------------
def sweep(f0, f1, dur, shape='exp'):
    n = int(dur * SR)
    t = np.linspace(0, 1, n)
    f = f0 * (f1 / f0) ** t if shape == 'exp' else f0 + (f1 - f0) * t
    return np.sin(2 * np.pi * np.cumsum(f) / SR)


def bell(hz, dur, amp=1.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = np.sin(2 * np.pi * hz * t) + 0.22 * np.sin(2 * np.pi * hz * 2.76 * t) * np.exp(-t * 9)
    return amp * lp(x * np.minimum(1, t / 0.003) * np.exp(-t * 6), 9000)


def sfx(kind):
    if kind in ('pop', 'pop_small'):
        hi = 1.5 if kind == 'pop_small' else 1.0
        x = sweep(900 * hi, 320 * hi, 0.09) * env(int(0.09 * SR), 0.001, 0.035)
        return hp(x, 300)
    if kind == 'whoosh':
        n = int(0.45 * SR)
        x = RNG.normal(0, 1, n)
        t = np.linspace(0, 1, n)
        y = np.zeros(n)
        for k in range(0, n, 2048):  # moving band
            c = 900 + 2600 * np.sin(np.pi * t[k])
            seg = x[k:k + 2048]
            y[k:k + len(seg)] = bp(seg, c * 0.7, c * 1.3)
        return y * np.sin(np.pi * t) ** 2 * 0.5
    if kind == 'twinkle':
        out = np.zeros(int(0.9 * SR))
        for i, n in enumerate([84, 88, 91, 96, 93]):
            add(out, bell(note_hz(n), 0.5, 0.5), i * 0.07)
        return out
    if kind == 'boing':
        n = int(0.55 * SR)
        t = np.arange(n) / SR
        f = 260 + 160 * np.sin(2 * np.pi * 9 * t) * np.exp(-t * 5) + 120 * t
        x = np.sin(2 * np.pi * np.cumsum(f) / SR)
        return x * env(n, 0.003, 0.25) * 0.9
    if kind == 'wink':
        return bell(note_hz(96), 0.35, 0.6)
    if kind == 'lens_open':
        n = int(0.4 * SR)
        x = sweep(300, 1100, 0.4) * np.sin(np.linspace(0, np.pi, n)) ** 0.6
        return x * 0.6 + np.pad(bell(note_hz(91), 0.3, 0.3), (int(0.25 * SR), 0))[:n]
    if kind == 'lens_close':
        n = int(0.3 * SR)
        return sweep(1000, 320, 0.3) * np.sin(np.linspace(0, np.pi, n)) ** 0.6 * 0.5
    if kind == 'chomp':
        n = int(0.16 * SR)
        x = bp(RNG.normal(0, 1, n), 600, 2500) * env(n, 0.002, 0.04)
        return x * 0.7 + sweep(420, 180, 0.16) * env(n, 0.002, 0.06) * 0.6
    if kind == 'sparkle':
        out = np.zeros(int(0.8 * SR))
        for i, n in enumerate([89, 93, 96, 101]):
            add(out, bell(note_hz(n), 0.6, 0.45), i * 0.045)
        return out
    if kind == 'grow':
        n = int(0.55 * SR)
        x = sweep(440, 880, 0.55) * (0.7 + 0.3 * np.sin(2 * np.pi * 14 * np.arange(n) / SR))
        return x * np.sin(np.linspace(0, np.pi, n)) * 0.45
    if kind == 'grow_big':
        n = int(0.9 * SR)
        x = sweep(330, 1320, 0.9) * (0.7 + 0.3 * np.sin(2 * np.pi * 16 * np.arange(n) / SR))
        out = x * np.sin(np.linspace(0, np.pi, n)) ** 0.8 * 0.45
        add(out, bell(note_hz(96), 0.4, 0.35), 0.75)
        return out
    if kind == 'wilt':
        n = int(0.7 * SR)
        return sweep(820, 300, 0.7) * np.sin(np.linspace(0, np.pi, n)) * 0.4
    if kind == 'sink':
        n = int(0.5 * SR)
        x = lp(RNG.normal(0, 1, n), 900) * env(n, 0.01, 0.2) * 0.6
        return x + sweep(160, 70, 0.5) * env(n, 0.003, 0.15) * 0.5
    if kind == 'shimmer':
        out = np.zeros(int(1.8 * SR))
        for i in range(12):
            add(out, bell(note_hz(84 + (i * 5) % 17), 0.5, 0.22), i * 0.12)
        return out
    if kind == 'chime':
        out = np.zeros(int(1.5 * SR))
        add(out, bell(note_hz(84), 1.2, 0.5), 0)
        add(out, bell(note_hz(89), 1.2, 0.5), 0.14)
        return out
    if kind == 'rain':
        n = int(5.0 * SR)
        hiss = bp(RNG.normal(0, 1, n), 1500, 9000) * 0.5 + lp(RNG.normal(0, 1, n), 700) * 0.35
        out = hiss * np.minimum(1, np.arange(n) / (0.6 * SR)) * np.minimum(1, (n - np.arange(n)) / (0.8 * SR))
        for i in range(160):  # droplets
            add(out, bell(2400 + RNG.uniform(0, 3000), 0.05, 0.25), RNG.uniform(0.1, 4.8))
        return out
    if kind == 'flip':
        out = np.zeros(int(1.4 * SR))
        for i in range(6):
            m = int(0.06 * SR)
            add(out, bp(RNG.normal(0, 1, m), 1200, 6000) * env(m, 0.003, 0.02), 0.08 + i * 0.2)
        return out
    raise ValueError(kind)


# ---------------- mix ----------------
# each effect type's loudness relative to the narrator (LU); cue gains add on top,
# and the effects bus is carved in the speech band while the narrator talks
SFX_LEVEL = {'pop': -7, 'pop_small': -10, 'whoosh': -13, 'twinkle': -9, 'boing': -6, 'wink': -10,
             'lens_open': -8, 'lens_close': -11, 'chomp': -7, 'sparkle': -8, 'grow': -9, 'grow_big': -7,
             'wilt': -9, 'sink': -9, 'shimmer': -10, 'chime': -7, 'rain': -13, 'flip': -11}


def presence(voice, n, attack=0.04, release=0.35):
    """0..1 control: how much the narrator is talking right now (10 ms frames)."""
    hop = int(0.01 * SR)
    fr = np.sqrt(np.convolve(voice ** 2, np.ones(hop) / hop, 'same')[::hop] + 1e-12)
    db = 20 * np.log10(fr)
    on = (db > db.max() - 35).astype(float)
    p, out = 0.0, np.zeros(len(on))
    ka, kr = 1 - np.exp(-0.01 / attack), 1 - np.exp(-0.01 / release)
    for i, x in enumerate(on):
        p += (x - p) * (ka if x > p else kr)
        out[i] = p
    return np.interp(np.arange(n), np.arange(len(out)) * hop, out)


def multiband_duck(x, pres, low_db=-5, mid_db=-12, high_db=-6):
    """Duck a stereo signal under the voice, hardest where words live (200 Hz-5 kHz)."""
    low = lp(x.T, 200, 4).T
    high = hp(x.T, 5000, 4).T
    mid = x - low - high
    g = lambda d: (10 ** (d * pres / 20))[:, None]
    return low * g(low_db) + mid * g(mid_db) + high * g(high_db)


def level_lines(voice, lines, meter, max_db=5):
    """Even out line-to-line loudness with short ramps between lines."""
    Ls = [meter.integrated_loudness(voice[int(l['start'] * SR):int(l['end'] * SR)]) if l['end'] - l['start'] > 0.45 else None for l in lines]
    ref = np.median([L for L in Ls if L is not None])
    g = np.ones(len(voice))
    for l, L in zip(lines, Ls):
        if L is None:
            continue
        a, b = int((l['start'] - 0.08) * SR), int((l['end'] + 0.08) * SR)
        g[max(0, a):b] = 10 ** (np.clip(ref - L, -max_db, max_db) / 20)
    k = int(0.04 * SR)
    return voice * np.convolve(g, np.ones(k) / k, 'same')


def compress(x, ratio=2.5, knee_db=-14, attack=0.006, release=0.09):
    """Gentle RMS compressor, threshold relative to the signal's own peak level."""
    hop = int(0.001 * SR)
    lvl = 20 * np.log10(np.sqrt(np.convolve(x ** 2, np.ones(hop * 5) / (hop * 5), 'same')[::hop]) + 1e-9)
    thr = lvl.max() + knee_db
    target = np.where(lvl > thr, (thr - lvl) * (1 - 1 / ratio), 0.0)
    g, out = 0.0, np.zeros(len(target))
    ka, kr = 1 - np.exp(-0.001 / attack), 1 - np.exp(-0.001 / release)
    for i, d in enumerate(target):
        g += (d - g) * (ka if d < g else kr)
        out[i] = g
    gain = 10 ** (np.interp(np.arange(len(x)), np.arange(len(out)) * hop, out) / 20)
    return x * gain


def reverb_ir(rt60=1.1, length=1.6, predelay=0.018):
    """Seeded stereo room: decorrelated noise with an exponential, darkening tail."""
    n = int(length * SR)
    t = np.arange(n) / SR
    rng = np.random.default_rng(11)
    ir = np.zeros((n + int(predelay * SR), 2))
    for c in range(2):
        noise = rng.normal(0, 1, n) * 10 ** (-3 * t / rt60)
        dark = lp(noise, 3500)
        mixw = np.minimum(1, t / 0.5)  # tail darkens over the first half second
        ir[int(predelay * SR):, c] = noise * (1 - mixw) * 0.6 + dark * mixw
    return ir / np.sqrt(np.sum(ir ** 2) / 2)


def reverb(x, ir, wet):
    from scipy.signal import fftconvolve
    send = x.mean(axis=1) if x.ndim == 2 else x
    out = np.stack([fftconvolve(send, ir[:, c])[: len(send)] for c in range(2)], axis=1)
    return out * wet


def to_st(x, pan=0.0):
    l, r = pan_gains(pan)
    return np.stack([x * l, x * r], axis=1)


def true_peak_db(x):
    up = resample_poly(x, 4, 1, axis=0)
    return 20 * np.log10(np.max(np.abs(up)) + 1e-12)


def limit(x, ceiling_db=-1.6):  # leaves headroom for AAC overshoot (checked after encode)
    """Linked-stereo gain-reduction limiter on a 4x-oversampled envelope, 5 ms lookahead."""
    from scipy.ndimage import minimum_filter1d
    c = 10 ** (ceiling_db / 20)
    x2 = x if x.ndim == 2 else x[:, None]
    up = np.abs(resample_poly(x2, 4, 1, axis=0)).max(axis=1)
    pk = np.pad(up, (0, max(0, 4 * len(x2) - len(up))))[: 4 * len(x2)].reshape(-1, 4).max(axis=1)
    g = minimum_filter1d(np.minimum(1, c / (pk + 1e-12)), size=2 * int(0.005 * SR) + 1)
    k = int(0.004 * SR)
    g = np.convolve(g, np.ones(k) / k, mode='same')
    return x * (g[:, None] if x.ndim == 2 else g)


def main():
    film = Path(sys.argv[1])
    b = film / 'build'
    score = json.loads((film / 'score.json').read_text())
    timing = json.loads((film / 'timing.json').read_text())
    cues = json.loads((b / 'cues.json').read_text())
    total = score['length_s']
    n = int(total * SR)
    meter = pyln.Meter(SR)

    # ---- narrator: clean ends, even lines, gentle compression
    # a re-voiced narration (voicefx.py) replaces the raw one when the script asks for it
    fx_on = json.loads((film / 'script.json').read_text()).get('voice_fx')
    voice, vsr = sf.read(b / ('voice_fx.wav' if fx_on else 'voice.wav'), dtype='float64')
    assert vsr == SR
    voice = np.pad(voice, (0, max(0, n - len(voice))))[:n]
    voice = lp(hp(voice, 90, 2), 11000, 2)
    voice = compress(level_lines(voice, timing['lines'], meter))
    voice *= 10 ** ((-16 - meter.integrated_loudness(voice)) / 20)
    V = -16.0
    pres = presence(voice, n)
    speaking = lambda t: pres[min(n - 1, int(t * SR))] > 0.5

    # ---- score: bed sits 8 LU under the voice between lines, ducked by band under words
    mus, beats = music(score, total, speaking)
    mus = np.pad(mus, ((0, n - len(mus)), (0, 0)))
    mus *= 10 ** ((V - 9 - meter.integrated_loudness(mus)) / 20)
    ir = reverb_ir()
    mus = mus + reverb(mus, ir, 0.22)
    mus_d = multiband_duck(mus, pres)

    # ---- effects: each levelled to its type's target, dipped a little under speech
    fx = np.zeros((n + SR * 2, 2))
    for c in cues:
        x = declick(hp(sfx(c['type']), 250))
        L = max((meter.integrated_loudness(np.pad(x[i:i + int(0.4 * SR)], (0, max(0, int(0.4 * SR) - len(x[i:i + int(0.4 * SR)])))))
                 for i in range(0, max(1, len(x) - int(0.2 * SR)), int(0.05 * SR))), default=-70)
        g = 10 ** ((V + SFX_LEVEL[c['type']] + 20 * np.log10(c.get('gain', 1.0)) - L) / 20)
        if c['type'] == 'whoosh':  # sweeps left to right
            p = np.linspace(-0.6, 0.6, len(x))
            i = int(round(c['t'] * SR)); j = min(len(fx), i + len(x))
            fx[i:j, 0] += (x * g * np.cos((p + 1) * np.pi / 4))[: j - i]
            fx[i:j, 1] += (x * g * np.sin((p + 1) * np.pi / 4))[: j - i]
        else:
            add_st(fx, x, c['t'], g, 0.12 * np.sin(c['t'] * 2.3))
    fx = fx[:n]
    fx = fx + reverb(fx, ir, 0.16)
    # keep the effects' punch and sparkle, clear their speech band under words
    fx = multiband_duck(fx, pres, low_db=-2, mid_db=-8, high_db=-3)

    vo = to_st(voice) + reverb(voice, ir, 0.035)
    mix = vo + mus_d + fx
    fade = int(score.get('fade_out_s', 0.6) * SR)
    mix[-fade:] *= (np.linspace(1, 0, fade) ** 2)[:, None]
    gain = 1.0
    for _ in range(4):
        g = 10 ** ((-14 - meter.integrated_loudness(mix)) / 20)
        gain *= g
        mix = limit(mix * g)
    sf.write(b / 'mix.wav', mix.astype(np.float32), SR, subtype='PCM_24')
    # stems at their mixed level, for mixcheck.py
    (b / 'stems').mkdir(exist_ok=True)
    for name, x in (('voice', vo), ('music', mus_d), ('sfx', fx)):
        sf.write(b / 'stems' / f'{name}.wav', (x * gain).astype(np.float32), SR, subtype='PCM_24')
    sf.write(b / 'sfx.wav', (fx * gain).astype(np.float32), SR, subtype='PCM_24')
    # music-only version, undocked, at programme loudness
    mo = mus.copy()
    mo[-fade:] *= (np.linspace(1, 0, fade) ** 2)[:, None]
    for _ in range(3):
        mo = limit(mo * 10 ** ((-14 - meter.integrated_loudness(mo)) / 20))
    sf.write(b / 'music.wav', mo.astype(np.float32), SR, subtype='PCM_24')

    timing['beats'] = beats
    timing['bpm'] = score['bpm']
    timing['sections'] = [{'kind': s['kind'], 'start': round(score['offset_s'] + s['from_beat'] * 60 / score['bpm'], 3)} for s in score['sections']]
    (film / 'timing.json').write_text(json.dumps(timing, indent=1))
    print(json.dumps({
        'mix_lufs': round(meter.integrated_loudness(mix), 2),
        'mix_true_peak_db': round(true_peak_db(mix), 2),
        'music_lufs': round(meter.integrated_loudness(mo), 2),
        'beats': len(beats), 'cues': len(cues),
    }))


if __name__ == '__main__':
    main()
