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
            if ch not in CHORDS:
                raise SystemExit(f"score.json: chord {ch!r} is not in the palette ({', '.join(CHORDS)})")
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


def step(surface=None):
    """a footstep on a surface (WP-13): grass swishes, tile clicks and rings, wood knocks hollow, concrete scuffs,
    carpet is a muffled thump; no surface is the original soft shoe"""
    n = int(0.16 * SR); t = np.arange(n) / SR; r = RNG.random()
    if surface == 'grass':   # blades brushing: soft-onset band of noise, almost no thump
        x = bp(RNG.normal(0, 1, n), 1800, 7000) * np.minimum(1, t / 0.012) * np.exp(-t * 26) * 0.9
        return x + 0.12 * np.sin(2 * np.pi * (80 + 15 * r) * t) * np.exp(-t * 45)
    if surface == 'tile':    # hard heel click with a ringing tile body
        click = hp(RNG.normal(0, 1, n), 2500) * np.exp(-t * 260)
        ring = np.sin(2 * np.pi * (2300 + 200 * r) * t) * np.exp(-t * 60) * 0.35 + np.sin(2 * np.pi * (3400 + 300 * r) * t) * np.exp(-t * 80) * 0.2
        return click + ring + 0.35 * np.sin(2 * np.pi * 110 * t) * np.exp(-t * 50)
    if surface == 'wood':    # hollow knock: a resonant board around 250 Hz and a click
        return np.sin(2 * np.pi * (240 + 30 * r) * t) * np.exp(-t * 30) * 0.8 + 0.3 * hp(RNG.normal(0, 1, n), 1500) * np.exp(-t * 180)
    if surface == 'concrete':   # dull thump and a gritty scuff
        return np.sin(2 * np.pi * (90 + 20 * r) * t) * np.exp(-t * 40) + 0.3 * bp(RNG.normal(0, 1, n), 800, 4000) * np.exp(-t * 35)
    if surface == 'carpet':  # muffled: only the low thump
        return lp(np.sin(2 * np.pi * (85 + 15 * r) * t) * np.exp(-t * 32) + 0.1 * RNG.normal(0, 1, n) * np.exp(-t * 60), 600)
    n = int(0.12 * SR); t = np.arange(n) / SR   # soft shoe on a floor: low thump plus a little scuff (as before)
    return np.sin(2 * np.pi * (95 + 25 * RNG.random()) * t) * np.exp(-t * 38) + 0.18 * lp(RNG.normal(0, 1, n), 2500) * np.exp(-t * 55)


def sfx(kind, dur=None, surface=None):
    if kind == 'scratch':  # pen on paper while a drawing draws itself: short strokes of bright, gritty noise
        d = max(0.15, min(8.0, dur or 1.0)); n = int(d * SR); t = np.arange(n) / SR
        strokes = 0.55 + 0.45 * np.sin(2 * np.pi * (6.5 + 1.5 * np.sin(2 * np.pi * 0.7 * t)) * t) ** 2
        grit = bp(RNG.normal(0, 1, n), 2200, 7500) * (1 + 0.6 * (RNG.random(n) > 0.97))
        edge = np.minimum(1, np.minimum(t / 0.04, (d - t) / 0.08))
        return grit * strokes * edge * 0.6
    if kind == 'step':
        return step(surface)
    if kind == 'thud':  # landing: deeper body thump
        n = int(0.22 * SR); t = np.arange(n) / SR
        return np.sin(2 * np.pi * 62 * t * (1 - 0.3 * t)) * np.exp(-t * 18) + 0.25 * lp(RNG.normal(0, 1, n), 900) * np.exp(-t * 30)
    if kind == 'swish':  # quick air movement
        n = int(0.16 * SR); t = np.linspace(0, 1, n)
        return bp(RNG.normal(0, 1, n), 1200, 5200) * np.sin(np.pi * t) ** 2
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
    if kind == 'buzz':  # a fly passing: buzzy saw tone with wobbling pitch and a fade in/out
        n = int(1.4 * SR)
        t = np.arange(n) / SR
        f = 210 + 25 * np.sin(2 * np.pi * 5.5 * t) + 12 * np.sin(2 * np.pi * 13 * t)
        ph = np.cumsum(f) / SR
        x = 2 * (ph % 1) - 1
        x = bp(x, 180, 3500) * (0.6 + 0.4 * np.sin(2 * np.pi * 31 * t))
        return x * np.sin(np.linspace(0, np.pi, n)) ** 1.5 * 0.5
    if kind == 'swarm':  # many detuned buzzes swelling
        n = int(2.4 * SR)
        t = np.arange(n) / SR
        out = np.zeros(n)
        for k in range(7):
            f = 190 + 22 * k + 15 * np.sin(2 * np.pi * (3 + k) * t + k)
            ph = np.cumsum(f) / SR
            out += bp(2 * (ph % 1) - 1, 160, 3000) / 7
        return out * np.minimum(1, t / 1.2) * np.minimum(1, (2.4 - t) / 0.6) * 0.8
    if kind == 'squirm':  # wet little squelches
        out = np.zeros(int(1.2 * SR))
        for i in range(6):
            m = int(0.08 * SR)
            add(out, lp(RNG.normal(0, 1, m), 900) * env(m, 0.005, 0.03) * 0.6 + sweep(300, 180, 0.08) * env(m, 0.004, 0.03) * 0.4, 0.05 + i * 0.17 + RNG.uniform(0, 0.05))
        return out
    if kind == 'stamp':  # rubber stamp thud with a paper slap
        n = int(0.35 * SR)
        x = thump()[:n] if len(thump()) >= n else np.pad(thump(), (0, n - len(thump())))
        return x * 0.9 + bp(RNG.normal(0, 1, n), 800, 5000) * env(n, 0.001, 0.03) * 0.5
    if kind == 'crack':
        n = int(0.5 * SR)
        out = np.zeros(n)
        for i in range(9):
            m = int(0.02 * SR)
            add(out, hp(RNG.normal(0, 1, m), 1500) * env(m, 0.001, 0.006), i * 0.035 + RNG.uniform(0, 0.02))
        return out * 0.8
    if kind == 'drill':  # rising screw whine
        n = int(1.0 * SR)
        x = sweep(220, 520, 1.0) * (0.6 + 0.4 * np.sign(np.sin(2 * np.pi * 24 * np.arange(n) / SR)))
        return bp(x, 150, 3000) * np.sin(np.linspace(0, np.pi, n)) * 0.4
    if kind == 'plane':  # prop drone passing (doppler-ish pitch drop)
        n = int(3.2 * SR)
        t = np.arange(n) / SR
        f = 92 - 14 * np.tanh((t - 1.6) * 2)
        ph = np.cumsum(f) / SR
        x = sum(np.sin(2 * np.pi * ph * h) / h for h in (1, 2, 3, 4, 6))
        x = lp(x * (0.75 + 0.25 * np.sin(2 * np.pi * 2 * f * t)), 1400)
        return x * np.exp(-((t - 1.6) / 1.0) ** 2) * 0.6
    if kind == 'drone':  # low ominous swell
        n = int(2.5 * SR)
        t = np.arange(n) / SR
        x = np.sin(2 * np.pi * 55 * t) + 0.5 * np.sin(2 * np.pi * 82.4 * t + 0.4) + 0.3 * np.sin(2 * np.pi * 110 * t * (1 + 0.003 * np.sin(2 * np.pi * 0.7 * t)))
        return lp(x, 600) * np.sin(np.linspace(0, np.pi, n)) ** 1.2 * 0.6
    if kind == 'ping':  # map marker
        out = bell(note_hz(88), 0.6, 0.6)
        add(out, bell(note_hz(76), 0.4, 0.3), 0.0)
        return out
    if kind == 'tick':
        m = int(0.03 * SR)
        return bp(RNG.normal(0, 1, m), 2500, 7000) * env(m, 0.001, 0.008)
    if kind == 'zap':  # x-ray hum burst with a crackle
        n = int(0.6 * SR)
        t = np.arange(n) / SR
        x = np.sign(np.sin(2 * np.pi * 120 * t)) * 0.4 + bp(RNG.normal(0, 1, n), 2000, 8000) * 0.5
        return lp(x, 6000) * env(n, 0.01, 0.25) * 0.6
    raise ValueError(kind)


# ---------------- mix ----------------
# each effect type's loudness relative to the narrator (LU); cue gains add on top,
# and the effects bus is carved in the speech band while the narrator talks
ROOT = Path(__file__).resolve().parents[1]


def sample_library():
    """assets/sounds.json (WP-13): recorded sample packs (files under assets/external/sounds/<pack>/, not in git, each
    pinned by sha256) and which cue (type, or type/surface) each group of samples can stand in for"""
    p = ROOT / 'assets' / 'sounds.json'
    return json.loads(p.read_text()) if p.exists() else {'packs': {}, 'map': {}}


def sample_for(cue, lib, packs=None, turns=None):
    """the recorded sample a cue plays, or None (then it is synthesized). A group's variants (footstep_grass_000..004)
    take turns in cue order (`turns` counts each group's cues so far), so the choice is a pure function of the cue
    list; the file must match its sha256. -> (path, name) or None"""
    import hashlib
    key = f"{cue['type']}/{cue['surface']}" if cue.get('surface') else cue['type']
    ref = cue.get('sample') or lib['map'].get(key) or (lib['map'].get(cue['type']) if not cue.get('surface') else None)
    if not ref:
        return None
    pack, group = ref.split(':', 1)
    pk = lib['packs'].get(pack)
    if not pk or (packs is not None and pack not in packs):
        return None
    names = sorted(n for n in pk['files'] if n.rsplit('.', 1)[0].rstrip('0123456789').rstrip('_') == group or n.rsplit('.', 1)[0] == group)
    if not names:
        return None
    k = 0
    if turns is not None:
        k = turns.get(ref, 0); turns[ref] = k + 1
    name = names[k % len(names)]
    f = ROOT / pk['dir'] / name
    if not f.exists() or hashlib.sha256(f.read_bytes()).hexdigest() != pk['files'][name]:
        return None
    return f, f"{pack}:{name}"


def load_sample(path):
    """a sample file as mono float64 at SR, its leading silence (under -50 dB of its peak) trimmed"""
    from math import gcd
    x, sr = sf.read(str(path), dtype='float64', always_2d=True)
    x = x.mean(axis=1)
    if sr != SR:
        g = gcd(SR, sr); x = resample_poly(x, SR // g, sr // g)
    pk = np.abs(x).max() or 1.0
    on = int(np.argmax(np.abs(x) > pk * 10 ** (-50 / 20)))
    return x[max(0, on - int(0.002 * SR)):]


SFX_LEVEL = {'scratch': -19, 'step': -16, 'thud': -10, 'swish': -15, 'pop': -7, 'pop_small': -10, 'whoosh': -13, 'twinkle': -9, 'boing': -6, 'wink': -10,
             'lens_open': -8, 'lens_close': -11, 'chomp': -7, 'sparkle': -8, 'grow': -9, 'grow_big': -7,
             'wilt': -9, 'sink': -9, 'shimmer': -10, 'chime': -7, 'rain': -13, 'flip': -11,
             'buzz': -12, 'swarm': -13, 'squirm': -12, 'stamp': -8, 'crack': -10, 'drill': -13, 'plane': -13,
             'drone': -12, 'ping': -9, 'tick': -14, 'zap': -11}


def presence(voice, n, attack=0.04, release=0.35):
    """0..1 control: how much the narrator is talking right now (10 ms frames)."""
    hop = int(0.01 * SR)
    if not np.any(voice):   # no narrator (sound-off cut)
        return np.zeros(n)
    fr = np.sqrt(np.convolve(voice ** 2, np.ones(hop) / hop, 'same')[::hop] + 1e-12)
    db = 20 * np.log10(fr)
    on = (db > db.max() - 35).astype(float)
    p, out = 0.0, np.zeros(len(on))
    ka, kr = 1 - np.exp(-0.01 / attack), 1 - np.exp(-0.01 / release)
    for i, x in enumerate(on):
        p += (x - p) * (ka if x > p else kr)
        out[i] = p
    return np.interp(np.arange(n), np.arange(len(out)) * hop, out)


def multiband_duck(x, pres, low_db=-5, mid_db=-12, high_db=-6, block=1 << 20):
    """Duck a stereo signal under the voice, hardest where words live (200 Hz-5 kHz). The bands are combined block by
    block into the low band's buffer: per sample the same arithmetic as low * gl + (x - low - high) * gm + high * gh
    on whole arrays, without five more full-length temporaries (WP-38)."""
    low = lp(x.T, 200, 4).T
    high = hp(x.T, 5000, 4).T
    g = lambda d, a, b: (10 ** (d * pres[a:b] / 20))[:, None]
    for a in range(0, len(x), block):
        b = min(len(x), a + block)
        mid = x[a:b] - low[a:b] - high[a:b]
        low[a:b] = low[a:b] * g(low_db, a, b) + mid * g(mid_db, a, b) + high[a:b] * g(high_db, a, b)
    return low


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
    # overlap-add (block by block): the same convolution as one FFT of the whole film, in a fraction of the memory
    # (a 20-minute film's single FFT took gigabytes; WP-38 long-form)
    from scipy.signal import oaconvolve
    send = x.mean(axis=1) if x.ndim == 2 else x
    out = np.empty((len(send), 2))
    for c in range(2):
        out[:, c] = oaconvolve(send, ir[:, c])[: len(send)]
    return out * wet


def room_reverb(x, rooms, key, default_wet, default_ir):
    """reverb per stretch of the film (rooms: [{t0, t1, rt60, fx_wet, voice_wet}] from the shots' sets): each room's
    reverb is fed only the sound inside its stretch (0.05 s crossfades), so its tail rings on past a cut; no rooms is
    the single default room, as before"""
    if not rooms:
        return reverb(x, default_ir, default_wet)
    n = len(x); out = None; groups = {}
    for r in rooms:
        groups.setdefault((r['rt60'], r[key]), []).append((r['t0'], r['t1']))
    tt = np.arange(n) / SR
    for (rt60, wet), spans in groups.items():
        m = np.zeros(n)
        for a, b_ in spans:
            m = np.maximum(m, np.clip(np.minimum((tt - a) / 0.05 + 0.5, (b_ - tt) / 0.05 + 0.5), 0, 1))
        ir = default_ir if rt60 == 1.1 else reverb_ir(rt60, length=max(0.4, min(2.4, rt60 * 1.4)))
        y = reverb(x * (m[:, None] if x.ndim == 2 else m), ir, wet)
        out = y if out is None else out + y
    return out


def to_st(x, pan=0.0):
    l, r = pan_gains(pan)
    return np.stack([x * l, x * r], axis=1)


def _peak4(x2, chunk=1 << 20, pad=64):
    """per input sample, the largest magnitude of its 4x-oversampled values over all channels, computed in chunks
    (with `pad` samples of real neighbours either side, far more than the resampling filter reaches), so a long film
    is never upsampled whole: 4 times a 20-minute stereo mix did not fit in memory (WP-38 long-form). The maxima are
    taken channel by channel and over each sample's 4 values with np.maximum, not a strided max over an axis: the same
    values, about 8 times faster on a long mix (WP-38)."""
    n = len(x2); out = np.empty(n)
    for a in range(0, n, chunk):
        b = min(n, a + chunk); a0, b0 = max(0, a - pad), min(n, b + pad)
        up = resample_poly(x2[a0:b0], 4, 1, axis=0)
        m = np.abs(up[:, 0])
        for c in range(1, up.shape[1]):
            np.maximum(m, np.abs(up[:, c]), out=m)
        if len(m) < 4 * (b0 - a0):
            m = np.pad(m, (0, 4 * (b0 - a0) - len(m)))
        q = m[: 4 * (b0 - a0)].reshape(-1, 4)
        r = np.maximum(np.maximum(q[:, 0], q[:, 1]), np.maximum(q[:, 2], q[:, 3]))
        out[a:b] = r[a - a0: a - a0 + (b - a)]
    return out


def true_peak_db(x):
    x2 = x if x.ndim == 2 else x[:, None]
    return 20 * np.log10(float(_peak4(x2).max()) + 1e-12)


def limit(x, ceiling_db=-1.6, inplace=False):  # leaves headroom for AAC overshoot (checked after encode)
    """Linked-stereo gain-reduction limiter on a 4x-oversampled envelope, 5 ms lookahead. inplace: scale x itself
    (the same numbers, without a second full-length buffer)."""
    from scipy.ndimage import minimum_filter1d
    c = 10 ** (ceiling_db / 20)
    x2 = x if x.ndim == 2 else x[:, None]
    pk = _peak4(x2)
    g = minimum_filter1d(np.minimum(1, c / (pk + 1e-12)), size=2 * int(0.005 * SR) + 1)
    del pk
    k = int(0.004 * SR)
    g = np.convolve(g, np.ones(k) / k, mode='same')
    if inplace:
        x *= (g[:, None] if x.ndim == 2 else g)
        return x
    return x * (g[:, None] if x.ndim == 2 else g)


def _write(path, x, gain=None, block=1 << 20):
    """x (times gain) to a 24-bit WAV block by block: the same bytes as sf.write of the whole float32 array, without
    a full-length float32 (and scaled) copy of it"""
    with sf.SoundFile(path, 'w', SR, 1 if x.ndim == 1 else x.shape[1], 'PCM_24') as f:
        for a in range(0, len(x), block):
            y = x[a:a + block]
            f.write((y * gain if gain is not None else y).astype(np.float32))


def main():
    film = Path(sys.argv[1])
    b = film / 'build'
    # the score with a sound designer's music swaps (sound.json, WP-40), when film.render or sound.remix wrote it
    score = json.loads(((b / 'score_mix.json') if (b / 'score_mix.json').exists() else (film / 'score.json')).read_text())
    timing = json.loads((film / 'timing.json').read_text())
    cues = json.loads((b / 'cues.json').read_text())
    total = score['length_s']
    n = int(total * SR)
    meter = pyln.Meter(SR)

    # ---- narrator: clean ends, even lines, gentle compression
    # a re-voiced narration (voicefx.py) replaces the raw one when the script asks for it
    fx_on = json.loads((film / 'script.json').read_text()).get('voice_fx')
    V = -16.0
    if score.get('voice', True) is False:   # the sound-off cut (plan 2.13): music and effects only
        voice = np.zeros(n)
    else:
        voice, vsr = sf.read(b / ('voice_fx.wav' if fx_on else 'voice.wav'), dtype='float64')
        assert vsr == SR
        voice = np.pad(voice, (0, max(0, n - len(voice))))[:n]
        voice = lp(hp(voice, 90, 2), 11000, 2)
        voice = compress(level_lines(voice, timing['lines'], meter))
        voice *= 10 ** ((-16 - meter.integrated_loudness(voice)) / 20)
    pres = presence(voice, n)
    speaking = lambda t: pres[min(n - 1, int(t * SR))] > 0.5

    # ---- score: bed sits 8 LU under the voice between lines, ducked by band under words
    mus, beats = music(score, total, speaking)
    mus = np.pad(mus, ((0, n - len(mus)), (0, 0)))
    mus *= 10 ** ((V - 9 - meter.integrated_loudness(mus)) / 20)
    ir = reverb_ir()
    mus = mus + reverb(mus, ir, 0.22)
    mus_d = multiband_duck(mus, pres)
    # music-only version, undocked, at programme loudness: made now, so the undocked music need not be kept to the end
    # (each full-length stereo buffer of a 20-minute film is about 1 GB; WP-38 long-form)
    fade = int(score.get('fade_out_s', 0.6) * SR)
    mo = mus; del mus
    mo[-fade:] *= (np.linspace(1, 0, fade) ** 2)[:, None]
    for _ in range(3):
        mo *= 10 ** ((-14 - meter.integrated_loudness(mo)) / 20); limit(mo, inplace=True)
    _write(b / 'music.wav', mo)
    music_lufs = round(meter.integrated_loudness(mo), 2); del mo

    # ---- effects: each levelled to its type's target, dipped a little under speech
    fx = np.zeros((n + SR * 2, 2))
    # recorded samples stand in for mapped cues when the score asks (WP-13: "samples": true, or a list of pack ids);
    # otherwise every effect is synthesized exactly as before
    want = score.get('samples'); lib = sample_library() if want else None; used = []; turns = {}
    for c in cues:
        hit = sample_for(c, lib, None if want is True else want, turns) if want else None
        if hit:
            used.append({'t': c['t'], 'type': c['type'], **({'surface': c['surface']} if c.get('surface') else {}), 'sample': hit[1]})
        x = declick(hp(load_sample(hit[0]) if hit else sfx(c['type'], c.get('dur'), c.get('surface')), 250))
        L = max((meter.integrated_loudness(np.pad(x[i:i + int(0.4 * SR)], (0, max(0, int(0.4 * SR) - len(x[i:i + int(0.4 * SR)])))))
                 for i in range(0, max(1, len(x) - int(0.2 * SR)), int(0.05 * SR))), default=-70)
        g = 10 ** ((V + SFX_LEVEL[c['type']] + 20 * np.log10(c.get('gain', 1.0)) - L) / 20)
        if c['type'] == 'whoosh':  # sweeps left to right
            p = np.linspace(-0.6, 0.6, len(x))
            i = int(round(c['t'] * SR)); j = min(len(fx), i + len(x))
            fx[i:j, 0] += (x * g * np.cos((p + 1) * np.pi / 4))[: j - i]
            fx[i:j, 1] += (x * g * np.sin((p + 1) * np.pi / 4))[: j - i]
        else:
            add_st(fx, x, c['t'], g, c['pan'] if 'pan' in c else 0.12 * np.sin(c['t'] * 2.3))   # foley cues carry their screen position
    fx = fx[:n]
    if want:
        (b / 'samples_used.json').write_text(json.dumps(used, indent=1))
    rooms = json.loads((b / 'rooms.json').read_text()) if (b / 'rooms.json').exists() else []   # WP-13: each set's own room
    fx = fx + room_reverb(fx, rooms, 'fx_wet', 0.16, ir)
    # keep the effects' punch and sparkle, clear their speech band under words
    fx = multiband_duck(fx, pres, low_db=-2, mid_db=-8, high_db=-3)
    del pres

    vo = to_st(voice) + room_reverb(voice, rooms, 'voice_wet', 0.035, ir)
    del voice
    mix = vo + mus_d; mix += fx   # (vo + mus_d) + fx, as before, in one buffer
    mix[-fade:] *= (np.linspace(1, 0, fade) ** 2)[:, None]
    gain = 1.0
    for _ in range(4):
        g = 10 ** ((-14 - meter.integrated_loudness(mix)) / 20)
        gain *= g
        mix *= g; limit(mix, inplace=True)
    _write(b / 'mix.wav', mix)
    # stems at their mixed level, for mixcheck.py
    (b / 'stems').mkdir(exist_ok=True)
    for name, x in (('voice', vo), ('music', mus_d), ('sfx', fx)):
        _write(b / 'stems' / f'{name}.wav', x, gain)
    _write(b / 'sfx.wav', fx, gain)
    del vo, mus_d, fx

    timing['beats'] = beats
    timing['bpm'] = score['bpm']
    timing['sections'] = [{'kind': s['kind'], 'start': round(score['offset_s'] + s['from_beat'] * 60 / score['bpm'], 3)} for s in score['sections']]
    (film / 'timing.json').write_text(json.dumps(timing, indent=1))
    print(json.dumps({
        'mix_lufs': round(meter.integrated_loudness(mix), 2),
        'mix_true_peak_db': round(true_peak_db(mix), 2),
        'music_lufs': music_lufs,
        'beats': len(beats), 'cues': len(cues),
    }))


if __name__ == '__main__':
    main()
