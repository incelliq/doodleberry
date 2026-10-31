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


def revoice(x, fs, pitch, formant, range_):
    f0, sp, ap = analyse(x, fs)
    v = f0 > 0
    lf = np.log(f0[v])
    mean = lf.mean()
    f0n = f0.copy()
    f0n[v] = np.exp(mean + np.log(pitch) + (lf - mean) * range_)
    y = pw.synthesize(f0n, warp(sp, formant), warp(ap, formant), fs, frame_period=FRAME_MS)
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
