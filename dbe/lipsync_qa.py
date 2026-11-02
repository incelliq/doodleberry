"""Lip-sync QA cross-check (plan 2.2).

Two independent readings of the same voice are compared per speaker, frame by frame:
- our mouth track: the visemes in timing.json (from the voice model's phone timings, or phonemes spread over words);
- the audio: how open the jaw should be, read from build/voice.wav as first-formant band energy (300-1200 Hz) inside
  that speaker's own lines.
Visemes are turned into openness (closed 0 ... wide 1) and cross-correlated with the audio track within the
speaker's lines. The best lag says whether the mouths lead or trail the voice; the correlation at that lag says
whether they move with it. With Rhubarb Lip Sync installed (DBE_RHUBARB=/path/to/rhubarb, MIT), each line is
also read by Rhubarb from the audio and text, and its Preston Blair cues (A-H, X) are compared shape class by class.

    report = check(film_dir)  ->  {"speakers": {...}, "ok": bool, "lag_ms": worst, "corr": worst}
Pass: every speaker within +-2 frames of the voice and correlation >= 0.2 (and Rhubarb agreement >= 0.5 when it ran).
Tested by fault injection on dialogue-demo: visemes 200 ms late or 150 ms early, speakers swapped and a mouth stuck
open all fail; the built track passes at 0 ms.
"""
import json
import os
import subprocess
import tempfile
from pathlib import Path

OPEN = {"closed": 0.0, "FV": 0.2, "small": 0.35, "smile": 0.45, "mid": 0.65, "O": 0.6, "wide": 1.0}
# Preston Blair (Rhubarb) -> our shape classes
RHUBARB = {"A": "closed", "B": "small", "C": "mid", "D": "wide", "E": "O", "F": "O", "G": "FV", "H": "small", "X": "closed"}
CLASS = {"closed": "closed", "FV": "closed", "small": "narrow", "smile": "narrow", "mid": "open", "wide": "open", "O": "round"}
MAX_LAG, MIN_CORR, MIN_RHUBARB = 2, 0.2, 0.5


def _shape_at(cues, t):
    s = "closed"
    for ct, sh in cues:
        if ct > t + 1e-9:
            break
        s = sh
    return s


def _corr(a, b):
    n = len(a)
    if n < 3:
        return 0.0
    ma, mb = sum(a) / n, sum(b) / n
    va = sum((x - ma) ** 2 for x in a); vb = sum((y - mb) ** 2 for y in b)
    if va <= 1e-12 or vb <= 1e-12:
        return 0.0
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (va * vb) ** 0.5


def _rhubarb(film_dir, lines, fps):
    exe = os.environ.get("DBE_RHUBARB")
    wav = Path(film_dir) / "build" / "voice.wav"
    if not exe or not Path(exe).exists() or not wav.exists():
        return None
    import soundfile as sf
    x, sr = sf.read(str(wav), dtype="float32")
    cues = {}
    with tempfile.TemporaryDirectory() as td:
        for ln in lines:
            a, b = int(ln["start"] * sr), int(ln["end"] * sr)
            w = Path(td) / f"{ln['id']}.wav"; t = Path(td) / f"{ln['id']}.txt"
            sf.write(str(w), x[a:b], sr); t.write_text(ln["text"])
            r = subprocess.run([exe, "-f", "json", "--dialogFile", str(t), "-q", str(w)], capture_output=True, text=True, timeout=600)
            if r.returncode != 0:
                return None
            for c in json.loads(r.stdout).get("mouthCues", []):
                cues.setdefault(ln["speaker"], []).append([ln["start"] + c["start"], RHUBARB.get(c["value"], "small")])
    return cues


def jaw_track(wav, n_frames, fps):
    """0..1 jaw opening per video frame read from the voice alone: energy in the first-formant band (300-1200 Hz),
    which rises with the jaw on vowels and stays low for nasal hums (m, n) and hiss (s, f), unlike plain loudness"""
    import numpy as np
    import soundfile as sf
    x, sr = sf.read(str(wav), dtype="float64")
    if x.ndim > 1:
        x = x.mean(1)
    hop = sr // fps; win = 2 * hop; w = np.hanning(win)
    fr = np.fft.rfftfreq(win, 1 / sr); band = (fr >= 300) & (fr <= 1200)
    out = np.zeros(n_frames)
    for i in range(n_frames):
        seg = x[max(0, i * hop - hop // 2): max(0, i * hop - hop // 2) + win]
        if len(seg) < win:
            seg = np.pad(seg, (0, win - len(seg)))
        out[i] = np.sum(np.abs(np.fft.rfft(seg * w))[band] ** 2)
    db = 10 * np.log10(out + 1e-12); top = np.percentile(db, 97)
    return list(np.clip((db - (top - 35)) / 35, 0, 1))


def check(film_dir):
    d = Path(film_dir)
    tm = json.loads((d / "timing.json").read_text())
    fps = tm.get("fps", 30); vis = tm.get("visemes") or {}
    lines = tm.get("lines", [])
    if not vis or not lines or not (d / "build" / "voice.wav").exists():
        return {"ok": True, "skipped": "no visemes or voice (voice.build makes both)"}
    jaw = jaw_track(d / "build" / "voice.wav", int(max(l["end"] for l in lines) * fps) + 20, fps)
    mouth = {spk: jaw for spk in vis}   # speakers never overlap: each one is read only inside their own lines
    rh = _rhubarb(d, lines, fps)
    out, ok = {}, True
    for spk, cues in vis.items():
        track = mouth.get(spk)
        if not track:
            continue
        frames = sorted({f for l in lines if l["speaker"] == spk for f in range(int(l["start"] * fps), int(l["end"] * fps) + 1)})
        frames = [f for f in frames if MAX_LAG + 1 <= f < len(track) - MAX_LAG - 1]
        if len(frames) < 10:
            continue
        ours = {f: OPEN.get(_shape_at(cues, f / fps), 0.35) for f in range(frames[0] - 12, frames[-1] + 12)}
        best = max(range(-10, 11), key=lambda L: _corr([ours[f + L] for f in frames], [track[f] for f in frames]))
        corr = _corr([ours[f + best] for f in frames], [track[f] for f in frames])
        r = {"frames": len(frames), "lag_frames": int(best), "lag_ms": int(round(1000 * best / fps)), "corr": round(float(corr), 3)}
        # positive lag: our mouths move after the voice
        good = abs(best) <= MAX_LAG and corr >= MIN_CORR
        if rh and rh.get(spk):
            agree = sum(CLASS[_shape_at(cues, f / fps)] == CLASS[_shape_at(rh[spk], f / fps)] for f in frames) / len(frames)
            r["rhubarb_agreement"] = round(agree, 3); good = good and agree >= MIN_RHUBARB
        r["ok"] = bool(good); ok = bool(ok and good); out[spk] = r
    worst = max(out.values(), key=lambda r: (abs(r["lag_frames"]), -r["corr"]), default=None)
    return {"ok": ok, "speakers": out, "rhubarb": bool(rh), "thresholds": {"max_lag_frames": MAX_LAG, "min_corr": MIN_CORR, "min_rhubarb": MIN_RHUBARB},
            **({"worst_lag_ms": worst["lag_ms"], "worst_corr": min(r["corr"] for r in out.values())} if worst else {})}


if __name__ == "__main__":
    import sys
    print(json.dumps(check(sys.argv[1]), indent=1))
