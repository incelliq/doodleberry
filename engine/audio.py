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


def music(score, total):
    bpm, off = score['bpm'], score['offset_s']
    beat = 60 / bpm
    out = np.zeros(int(total * SR) + SR * 2)
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
                    k = (bar_beat * 2 + half)
                    hz = note_hz(tri[MELODY[k % 8]] + (12 if kind == 'finale' and k % 4 == 3 else 0))
                    add(out, pluck(hz, 0.5, 0.35 if kind == 'intro' else 0.55), tt, 0.16 if kind == 'intro' else 0.2)
            if kind in ('main', 'finale') and bar_beat in (0, 2):
                add(out, bass(note_hz(root), beat * 1.8), t, 0.34)
            if kind == 'intro' and bar_beat == 0:
                add(out, bass(note_hz(root), beat * 3.5), t, 0.22)
            if kind in ('main', 'finale'):
                for half in range(2):
                    add(out, shaker(), t + half * beat / 2, 0.05 if half else 0.08)
                if bar_beat == 0:
                    add(out, thump(), t, 0.32)
            if kind == 'reflect' and bar_beat == 0:
                add(out, pad([note_hz(h) for h in tri], beat * 4.2), t, 0.22)
                add(out, bass(note_hz(root), beat * 4), t, 0.18)
            if kind == 'reflect' and bar_beat in (1, 3):
                add(out, marimba(note_hz(tri[bar_beat // 2 + 1] + 12), 0.6), t, 0.08)
            if kind == 'finale' and bar_beat == 0:
                add(out, pad([note_hz(h) for h in tri], beat * 4.2), t, 0.12)
        if sec.get('end_chord'):
            t = off + b1 * beat
            root, tri = CHORDS[sec['end_chord']]
            add(out, pad([note_hz(h) for h in tri] + [note_hz(tri[0] + 12)], 3.4), t, 0.26)
            add(out, bass(note_hz(root), 3.0), t, 0.3)
            for i, n in enumerate(tri + [tri[0] + 12]):
                add(out, marimba(note_hz(n + 12), 1.2), t + i * 0.07, 0.12)
            beats.append(round(t, 3))
    out = hp(out, 40)
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
    return amp * (np.sin(2 * np.pi * hz * t) + 0.4 * np.sin(2 * np.pi * hz * 2.76 * t)) * np.exp(-t * 6)


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
    raise ValueError(kind)


# ---------------- mix ----------------
def duck_curve(lines, n, depth_db=-9, attack=0.12, release=0.35):
    g = np.ones(n)
    target = 10 ** (depth_db / 20)
    for l in lines:
        a, b = int((l['start'] - attack) * SR), int((l['end'] + release) * SR)
        g[max(0, a):min(n, b)] = target
    k = int(0.15 * SR)
    return np.convolve(g, np.ones(k) / k, mode='same')


def true_peak_db(x):
    up = resample_poly(x, 4, 1)
    return 20 * np.log10(np.max(np.abs(up)) + 1e-12)


def limit(x, ceiling_db=-2.0):  # headroom for AAC overshoot
    """Gain-reduction limiter on a 4x-oversampled envelope, lookahead 5 ms."""
    c = 10 ** (ceiling_db / 20)
    up = np.abs(resample_poly(x, 4, 1))
    pk = up.reshape(-1, 4).max(axis=1)[: len(x)] if len(up) >= 4 * len(x) else np.pad(up[::4], (0, len(x)))[: len(x)]
    g = np.minimum(1, c / (pk + 1e-12))
    la = int(0.005 * SR)
    from scipy.ndimage import minimum_filter1d
    g = minimum_filter1d(g, size=2 * la + 1)
    k = int(0.004 * SR)
    g = np.convolve(g, np.ones(k) / k, mode='same')
    return x * g


def main():
    film = Path(sys.argv[1])
    b = film / 'build'
    score = json.loads((film / 'score.json').read_text())
    timing = json.loads((film / 'timing.json').read_text())
    cues = json.loads((b / 'cues.json').read_text())
    total = score['length_s']
    n = int(total * SR)

    # a re-voiced narration (voicefx.py) replaces the raw one when the script asks for it
    fx_on = json.loads((film / 'script.json').read_text()).get('voice_fx')
    voice, vsr = sf.read(b / ('voice_fx.wav' if fx_on else 'voice.wav'), dtype='float64')
    assert vsr == SR
    voice = np.pad(voice, (0, max(0, n - len(voice))))[:n]

    mus, beats = music(score, total)
    mus = np.pad(mus, (0, n - len(mus)))
    fx = np.zeros(n + SR * 2)
    for c in cues:
        add(fx, sfx(c['type']), c['t'], c.get('gain', 1.0))
    fx = hp(fx[:n], 250)  # effects sit just above the music's low end

    meter = pyln.Meter(SR)
    # level stems relative to the voice
    vL = meter.integrated_loudness(voice)
    voice *= 10 ** ((-16 - vL) / 20)
    mL = meter.integrated_loudness(mus)
    mus *= 10 ** ((-27 - mL) / 20)
    fx *= 10 ** ((-25 - meter.integrated_loudness(fx)) / 20)

    duck = duck_curve(timing['lines'], n)
    mix = voice + mus * duck + fx
    fade = int(score.get('fade_out_s', 0.6) * SR)
    mix[-fade:] *= np.linspace(1, 0, fade) ** 2
    for _ in range(3):
        L = meter.integrated_loudness(mix)
        mix *= 10 ** ((-14 - L) / 20)
        mix = limit(mix)
    sf.write(b / 'mix.wav', mix.astype(np.float32), SR, subtype='PCM_24')
    sf.write(b / 'sfx.wav', fx.astype(np.float32), SR, subtype='PCM_24')
    # music-only version, delivered at the same programme loudness
    mo = mus * 10 ** ((-14 - meter.integrated_loudness(mus)) / 20)
    sf.write(b / 'music.wav', limit(mo).astype(np.float32), SR, subtype='PCM_24')

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
