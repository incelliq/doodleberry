"""Measure a mix the way a mixer would listen to it, so audio changes can be
judged by numbers.

    python mixcheck.py FILM_DIR [--whisper]

Reads build/mix.wav and the stems audio.py writes to build/stems/ (voice,
music, sfx at their mixed levels) plus timing.json, and reports:
  - integrated loudness, loudness range, true peak, channel count
  - speech-to-background ratio while the narrator talks (broadband and in the
    300 Hz-4 kHz band where words live)
  - music level between lines, relative to the voice
  - effect loudness relative to the voice, and how evenly effects are levelled
  - voice loudness spread across lines
  - optionally, Whisper's word confidence on the full mix (intelligibility)
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pyloudnorm as pyln
import soundfile as sf
from scipy.signal import butter, sosfilt, resample_poly

SR = 48000


def mono(x):
    return x.mean(axis=1) if x.ndim == 2 else x


def band(x, lo, hi):
    return sosfilt(butter(4, [lo, hi], 'band', fs=SR, output='sos'), x)


def rms_db(x):
    return 10 * np.log10(np.mean(x ** 2) + 1e-20)


def mask(lines, n, pad=0.0):
    m = np.zeros(n, bool)
    for l in lines:
        m[max(0, int((l['start'] - pad) * SR)):min(n, int((l['end'] + pad) * SR))] = True
    return m


def short_term(x, meter, win=3.0, hop=0.5):
    out = []
    for i in range(0, max(1, len(x) - int(win * SR)), int(hop * SR)):
        seg = x[i:i + int(win * SR)]
        if rms_db(mono(seg)) > -70:
            out.append(meter.integrated_loudness(seg))
    return np.array(out)


def lra(x, meter):
    st = short_term(x, meter)
    st = st[st > -70]
    if len(st) == 0:
        return 0.0
    gated = st[st > (10 * np.log10(np.mean(10 ** (st / 10))) - 20)]
    return float(np.percentile(gated, 95) - np.percentile(gated, 10))


def true_peak_db(x):
    x = x if x.ndim == 2 else x[:, None]
    return float(max(20 * np.log10(np.max(np.abs(resample_poly(x[:, c], 4, 1))) + 1e-12) for c in range(x.shape[1])))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('film', type=Path)
    ap.add_argument('--whisper', action='store_true')
    a = ap.parse_args()
    b = a.film / 'build'
    timing = json.loads((a.film / 'timing.json').read_text())
    meter = pyln.Meter(SR)
    mix, _ = sf.read(b / 'mix.wav', dtype='float64')
    st = {k: mono(sf.read(b / 'stems' / f'{k}.wav', dtype='float64')[0]) for k in ('voice', 'music', 'sfx')}
    n = len(st['voice'])
    sp = mask(timing['lines'], n)
    gap = ~mask(timing['lines'], n, pad=0.25)
    gap[: int(0.3 * SR)] = False
    bg = st['music'] + st['sfx']

    def lufs(x, m):
        return meter.integrated_loudness(x[m]) if m.sum() > SR * 0.5 else float('nan')

    v_sp = lufs(st['voice'], sp)
    r = {
        'channels': 1 if mix.ndim == 1 else mix.shape[1],
        'integrated_lufs': round(meter.integrated_loudness(mix), 2),
        'loudness_range_lu': round(lra(mix, meter), 2),
        'true_peak_dbtp': round(true_peak_db(mix), 2),
        'voice_lufs_while_speaking': round(v_sp, 2),
        'speech_to_background_lu': round(v_sp - lufs(bg, sp), 2),
        'speech_to_music_db_300_4k': round(rms_db(band(st['voice'], 300, 4000)[sp]) - rms_db(band(st['music'], 300, 4000)[sp]), 2),
        'music_between_lines_vs_voice_lu': round(lufs(st['music'], gap) - v_sp, 2),
    }
    # each effect's momentary loudness (400 ms around its loudest point), relative to the voice
    cues = json.loads((b / 'cues.json').read_text())
    fx_l = []
    for c in cues:
        i = int(c['t'] * SR)
        seg = st['sfx'][i:i + int(0.8 * SR)]
        if len(seg) < int(0.4 * SR) or rms_db(seg) < -80:
            continue
        k = int(np.argmax(np.convolve(seg ** 2, np.ones(int(0.1 * SR)), 'same')))
        win = seg[max(0, k - int(0.2 * SR)): k + int(0.2 * SR)]
        fx_l.append(meter.integrated_loudness(np.pad(win, (0, max(0, int(0.4 * SR) - len(win))))) - v_sp)
    r['sfx_momentary_vs_voice_lu'] = {'median': round(float(np.median(fx_l)), 2), 'min': round(float(np.min(fx_l)), 2),
                                      'max': round(float(np.max(fx_l)), 2), 'spread': round(float(np.max(fx_l) - np.min(fx_l)), 2)}
    per_line = [meter.integrated_loudness(st['voice'][int(l['start'] * SR):int(l['end'] * SR)]) for l in timing['lines'] if l['end'] - l['start'] > 0.45]
    r['voice_line_loudness_spread_lu'] = round(float(np.max(per_line) - np.min(per_line)), 2)
    # how much the music occupies the voice's pitch band (fundamental of the baby voice)
    r['music_energy_in_voice_f0_band_pct'] = round(100 * float(np.sum(band(st['music'], 170, 540) ** 2) / (np.sum(st['music'] ** 2) + 1e-20)), 1)
    if a.whisper:
        from faster_whisper import WhisperModel
        m = WhisperModel('small.en', device='cpu', compute_type='int8')
        segs, _ = m.transcribe(resample_poly(mono(mix), 1, 3).astype('float32'), language='en', word_timestamps=True)
        ws = [w for s in segs for w in s.words]
        r['whisper_on_mix'] = {'words': len(ws), 'mean_conf': round(float(np.mean([w.probability for w in ws])), 3),
                               'min_conf': round(float(np.min([w.probability for w in ws])), 3)}
    print(json.dumps(r, indent=1))
    (b / 'mixcheck.json').write_text(json.dumps(r, indent=1))


if __name__ == '__main__':
    main()
