"""Assemble a cut's audio from master stems (plan 2.14). Run with DBE_PY:
    python dbe/cut_audio.py SPEC.json
SPEC: {"segments": [{"build": "films/x/build", "t0": s, "t1": s}], "out": "....wav", "xfade": 0.04}
Each segment takes voice, music and effects from build/stems at their mixed levels, so a segment sounds as it does
in the master. Joins crossfade (equal power, `xfade` s); the music fades in when the cut starts mid-score and out
over the last 0.9 s; the sum is levelled to -14 LUFS with the master limiter. Prints loudness and true peak.
"""
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "engine"))
import audio as A  # noqa: E402  (limit, true_peak_db, SR)
import pyloudnorm as pyln  # noqa: E402


def stem(build, name, cache={}):
    k = (build, name)
    if k not in cache:
        x, sr = sf.read(str(ROOT / build / "stems" / f"{name}.wav"), dtype="float64", always_2d=True)
        assert sr == A.SR, f"{build}: stems at {sr} Hz"
        cache[k] = x
    return cache[k]


def main():
    spec = json.loads(Path(sys.argv[1]).read_text())
    SR = A.SR; xf = int(spec.get("xfade", 0.04) * SR)
    parts = []
    for i, s in enumerate(spec["segments"]):
        a, b = int(round(s["t0"] * SR)), int(round(s["t1"] * SR))
        v, m, fx = (np.pad(y, ((0, max(0, b - len(y))), (0, 0)))[a:b] for y in (stem(s["build"], "voice"), stem(s["build"], "music"), stem(s["build"], "sfx")))
        if i == 0 and s["t0"] > 0.3:  # starts mid-score: let the music in gently
            k = min(len(m), int(0.35 * SR)); m[:k] *= (np.linspace(0, 1, k) ** 2)[:, None]
        parts.append(v + m + fx)
    out = parts[0]
    for p in parts[1:]:  # equal-power crossfade at each join (joins sit in pauses, on the grid)
        k = min(xf, len(out), len(p))
        if k:
            u = np.linspace(0, 1, k)[:, None]
            out = np.concatenate([out[:-k], out[-k:] * np.cos(u * np.pi / 2) + p[:k] * np.sin(u * np.pi / 2), p[k:]])
        else:
            out = np.concatenate([out, p])
    k = min(len(out), int(0.9 * SR)); out[-k:] *= (np.linspace(1, 0, k) ** 2)[:, None]
    meter = pyln.Meter(SR)
    for _ in range(4):
        out = A.limit(out * 10 ** ((-14 - meter.integrated_loudness(out)) / 20))
    sf.write(spec["out"], out.astype(np.float32), SR, subtype="PCM_24")
    print(json.dumps({"lufs": round(meter.integrated_loudness(out), 2), "true_peak_db": round(A.true_peak_db(out), 2), "length_s": round(len(out) / SR, 3)}))


if __name__ == "__main__":
    main()
