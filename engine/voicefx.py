"""Voice character: re-voice the narration with the WORLD vocoder, changing
pitch, vocal-tract length (formants) and intonation range while keeping every
word exactly where it was, so timing.json and the picture stay in sync.

    python voicefx.py FILM_DIR

Reads script.json "voice_fx" (a preset name, or {"preset": ..., overrides}),
reads build/voice.wav and writes build/voice_fx.wav, which audio.py then uses.
"""
import json
import sys
import warnings
from pathlib import Path

import numpy as np
import soundfile as sf

warnings.filterwarnings('ignore', category=UserWarning)  # pyworld's pkg_resources notice
import pyworld as pw  # noqa: E402

PRESETS = {
    # pitch: F0 multiplier; formant: spectral-envelope stretch (shorter vocal
    # tract > 1); range: intonation exaggeration around the speaker's mean
    'child': {'pitch': 1.45, 'formant': 1.15, 'range': 1.15},
    'baby': {'pitch': 1.8, 'formant': 1.25, 'range': 1.35},
}
FRAME_MS = 5.0
# prosody direction (WP-13), per line ("delivery" in script.json), on top of the speaker's own fx: Kokoro and Piper take
# no SSML, so delivery is made from the voice itself: pitch and intonation range (WORLD), spectral tilt in dB per
# octave above 1 kHz (brighter for a shout, darker for sad), speaking rate (the TTS length scale), level, and a
# whisper resynthesised with no voicing at all (noise through the same vocal tract)
DELIVERY = {
    'whisper': {'pitch': 1.0, 'range': 1.0, 'tilt': 2.0, 'rate': 1.05, 'gain_db': -6.0, 'whisper': True},
    'shout': {'pitch': 1.25, 'range': 1.3, 'tilt': 4.0, 'rate': 0.95, 'gain_db': 0.0},
    'excited': {'pitch': 1.12, 'range': 1.6, 'tilt': 1.5, 'rate': 0.88, 'gain_db': 0.0},
    'calm': {'pitch': 0.96, 'range': 0.65, 'tilt': -1.0, 'rate': 1.08, 'gain_db': -2.0},
    'sad': {'pitch': 0.9, 'range': 0.55, 'tilt': -3.0, 'rate': 1.15, 'gain_db': -3.0},
}


def warp(env, alpha):
    """Stretch a spectral envelope up the frequency axis by alpha."""
    n = env.shape[1]
    src = np.arange(n) / alpha
    lo = np.clip(np.floor(src).astype(int), 0, n - 1)
    hi = np.clip(lo + 1, 0, n - 1)
    w = src - np.floor(src)
    out = env[:, lo] * (1 - w) + env[:, hi] * w
    out[:, src > n - 1] = env[:, -1:]  # above the old top: hold the last bin
    return np.ascontiguousarray(out)


def analyse(x, fs):
    f0, t = pw.harvest(x, fs, f0_floor=70, f0_ceil=600, frame_period=FRAME_MS)
    return f0, pw.cheaptrick(x, f0, t, fs), pw.d4c(x, f0, t, fs)


def tilt(env, fs, db_per_oct):
    """raise (or lower) the spectral envelope by db_per_oct for each octave above 1 kHz"""
    if not db_per_oct:
        return env
    f = np.linspace(0, fs / 2, env.shape[1])
    g = np.where(f > 1000, db_per_oct * np.log2(np.maximum(f, 1000) / 1000), 0.0)
    return np.ascontiguousarray(env * (10 ** (g / 10))[None, :])   # power spectrum: 10, not 20


def revoice(x, fs, pitch, formant, range_, tilt_db=0.0, whisper=False):
    f0, sp, ap = analyse(x, fs)
    v = f0 > 0
    f0n = f0.copy()
    if v.any():
        lf = np.log(f0[v])
        mean = lf.mean()
        f0n[v] = np.exp(mean + np.log(pitch) + (lf - mean) * range_)
    sp2, ap2 = tilt(warp(sp, formant), fs, tilt_db), warp(ap, formant)
    if whisper:   # no voicing: the vocal tract excited by noise alone
        f0n = np.zeros_like(f0n); ap2 = np.ones_like(ap2)
    y = pw.synthesize(f0n, sp2, ap2, fs, frame_period=FRAME_MS)
    return y[: len(x)] if len(y) >= len(x) else np.pad(y, (0, len(x) - len(y))), f0, f0n


def main():
    film = Path(sys.argv[1])
    cfg = json.loads((film / 'script.json').read_text()).get('voice_fx')
    if not cfg:
        print('no voice_fx in script.json; nothing to do')
        return
    if isinstance(cfg, str):
        cfg = {'preset': cfg}
    p = {**PRESETS[cfg['preset']], **{k: v for k, v in cfg.items() if k != 'preset'}}
    x, fs = sf.read(film / 'build' / 'voice.wav', dtype='float64')
    y, f0, f0n = revoice(x, fs, p['pitch'], p['formant'], p['range'])
    y *= 0.9 / (np.max(np.abs(y)) + 1e-9)
    sf.write(film / 'build' / 'voice_fx.wav', y.astype(np.float32), fs, subtype='PCM_24')
    print(json.dumps({'preset': cfg['preset'], **p,
                      'f0_median_hz': [round(float(np.median(f0[f0 > 0])), 1), round(float(np.median(f0n[f0n > 0])), 1)],
                      'f0_p10_p90_hz': [[round(float(q), 1) for q in np.percentile(f0[f0 > 0], [10, 90])],
                                        [round(float(q), 1) for q in np.percentile(f0n[f0n > 0], [10, 90])]]}))


if __name__ == '__main__':
    main()
