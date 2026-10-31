"""Measured half of the quality bar, plus contact sheets for the critic.

    python qa.py FILM_DIR [--video build/final.mp4]

Checks duration, size, frame rate, frozen stretches, loudness and true peak,
and narration-to-fact tracing; writes build/qa.json and contact sheets
(build/qa/sheet-2fps.jpg for the sound-off read, build/qa/dense-*.jpg every
0.2 s for the frame critic).
"""
import argparse
import json
import subprocess
from pathlib import Path

import numpy as np


def sh(*a):
    return subprocess.run(a, check=True, capture_output=True, text=True).stdout


def probe(v):
    j = json.loads(sh('ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(v)))
    vs = next(s for s in j['streams'] if s['codec_type'] == 'video')
    num, den = map(int, vs['r_frame_rate'].split('/'))
    return {'duration': float(j['format']['duration']), 'width': vs['width'], 'height': vs['height'],
            'fps': num / den, 'frames': int(vs.get('nb_frames', 0)),
            'audio': any(s['codec_type'] == 'audio' for s in j['streams'])}


def frame_diffs(v, w=108, h=192):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(v), '-vf', f'scale={w}:{h},format=gray',
                          '-f', 'rawvideo', '-'], check=True, capture_output=True).stdout
    fr = np.frombuffer(raw, np.uint8).reshape(-1, h, w).astype(np.float32)
    return np.abs(np.diff(fr, axis=0)).mean(axis=(1, 2))


def frozen_stretches(d, fps, thresh=0.05, min_s=0.5):
    out, run = [], 0
    for i, x in enumerate(list(d) + [1e9]):
        if x < thresh:
            run += 1
        else:
            if run / fps >= min_s:
                out.append({'start': round((i - run) / fps, 2), 'len': round(run / fps, 2)})
            run = 0
    return out


def loudness(v):
    o = subprocess.run(['ffmpeg', '-nostats', '-i', str(v), '-af', 'ebur128=peak=true', '-f', 'null', '-'],
                       capture_output=True, text=True).stderr
    tail = o[o.rfind('Summary:'):]
    I = float(tail.split('I:')[1].split('LUFS')[0])
    tp = float(tail.split('Peak:')[1].split('dBFS')[0])
    return I, tp


def sheets(v, out, dur):
    out.mkdir(exist_ok=True)
    sh('ffmpeg', '-v', 'error', '-y', '-i', str(v), '-vf', 'fps=2,scale=216:384,tile=10x7', '-frames:v', '1',
       str(out / 'sheet-2fps.jpg'))
    # every 0.2 s, 30 frames (6 s) per sheet
    per = 6
    for k in range(int(np.ceil(dur / per))):
        sh('ffmpeg', '-v', 'error', '-y', '-ss', str(k * per), '-t', str(per), '-i', str(v), '-vf',
           "fps=5,scale=216:384,drawtext=text='%{pts\\:hms\\:" + str(k * per) + "}':x=6:y=6:fontsize=18:fontcolor=white:box=1:boxcolor=black@0.6,tile=10x3",
           '-frames:v', '1', str(out / f'dense-{k:02d}.jpg'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('film', type=Path)
    ap.add_argument('--video', default='build/final.mp4')
    a = ap.parse_args()
    v = a.film / a.video
    p = probe(v)
    d = frame_diffs(v)
    frozen = frozen_stretches(d, p['fps'])
    I, tp = loudness(v)
    timing = json.loads((a.film / 'timing.json').read_text())
    facts = {f['id'] for f in json.loads((a.film / 'facts.json').read_text())['facts']}
    cites = lambda l: l.get('fact') if isinstance(l.get('fact'), list) else [l.get('fact')]
    untraced = [l['id'] for l in timing['lines'] if not cites(l) or any(c not in facts for c in cites(l))]
    frozen_total = sum(f['len'] for f in frozen)
    report = {
        **p,
        'frozen_stretches_over_0.5s': frozen,
        'frozen_s_per_30s': round(frozen_total * 30 / p['duration'], 2),
        'loudness_lufs': I, 'true_peak_dbtp': tp,
        'untraced_lines': untraced,
        'checks': {
            'size_1080x1920': (p['width'], p['height']) == (1080, 1920),
            'fps_30': abs(p['fps'] - 30) < 0.01,
            'no_still_over_0.5s': not frozen,
            'loudness_-14±1': abs(I + 14) <= 1,
            'true_peak_<=-1': tp <= -1.0,
            'every_line_traced': not untraced,
        },
    }
    sheets(v, a.film / 'build' / 'qa', p['duration'])
    (a.film / 'build' / 'qa.json').write_text(json.dumps(report, indent=1))
    print(json.dumps(report, indent=1))


if __name__ == '__main__':
    main()
