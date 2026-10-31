"""Narration: synthesize each script line with Piper, lay lines on a timeline,
and recover word timings with faster-whisper so captions and animation can
snap to the voice.

    python voice.py FILM_DIR --voices-dir DIR [--audition]

Writes FILM_DIR/build/voice.wav and FILM_DIR/timing.json. With --audition,
renders the whole script once per voice found in --voices-dir and reports
speaking rate so a voice can be chosen; script.json picks the final one.
"""
import argparse
import difflib
import json
import re
from pathlib import Path

import numpy as np
import soundfile as sf
from piper import PiperVoice
from piper.config import SynthesisConfig

SR_OUT = 48000


def synth_line(voice, text, length_scale, noise_scale=0.5, noise_w=0.6):
    cfg = SynthesisConfig(length_scale=length_scale, noise_scale=noise_scale,
                          noise_w_scale=noise_w, normalize_audio=True)
    chunks = list(voice.synthesize(text, syn_config=cfg))
    audio = np.concatenate([c.audio_float_array for c in chunks])
    sr = chunks[0].sample_rate
    return resample(audio, sr, SR_OUT)


def resample(x, sr_in, sr_out):
    from scipy.signal import resample_poly
    from math import gcd
    g = gcd(sr_in, sr_out)
    return resample_poly(x, sr_out // g, sr_in // g).astype(np.float32)


def trim(x, thresh=0.01, pad=0.03):
    idx = np.where(np.abs(x) > thresh)[0]
    if len(idx) == 0:
        return x
    p = int(pad * SR_OUT)
    return x[max(0, idx[0] - p): idx[-1] + p]


def norm_word(w):
    return re.sub(r"[^a-z0-9']", "", w.lower())


def align_words(model, audio, text):
    """Word timings for `text` inside `audio` (seconds, relative to audio start).
    Recognised words are mapped back onto the script's own words so captions
    always show the script text; unmatched script words are interpolated."""
    from scipy.signal import resample_poly
    a16 = resample_poly(audio, 1, 3).astype(np.float32)
    segs, _ = model.transcribe(a16, language="en", word_timestamps=True,
                               initial_prompt=text, beam_size=5)
    rec = [w for s in segs for w in s.words]
    script = text.split()
    a = [norm_word(w) for w in script]
    b = [norm_word(w.word) for w in rec]
    times = [None] * len(script)
    sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op in ("equal", "replace") and (i2 - i1) == (j2 - j1):
            for k in range(i2 - i1):
                times[i1 + k] = (rec[j1 + k].start, rec[j1 + k].end)
    dur = len(audio) / SR_OUT
    # fill gaps linearly between known neighbours
    for i, t in enumerate(times):
        if t is None:
            prev = next((times[j][1] for j in range(i - 1, -1, -1) if times[j]), 0.0)
            nxt_i = next((j for j in range(i + 1, len(times)) if times[j]), None)
            nxt = times[nxt_i][0] if nxt_i is not None else dur
            span = (nxt_i if nxt_i is not None else len(times)) - i
            step = (nxt - prev) / max(span, 1)
            times[i] = (prev, prev + step)
    return [{"text": w, "start": round(s, 3), "end": round(e, 3)}
            for w, (s, e) in zip(script, times)]


def mouth_track(audio, fps, floor_db=-38.0):
    """0..1 mouth openness per video frame from a line's loudness, for lip-sync:
    quick to open, a little slower to close, with a flutter so long vowels don't freeze."""
    hop = SR_OUT // fps
    n = int(np.ceil(len(audio) / hop))
    rms = np.array([np.sqrt(np.mean(audio[i * hop:(i + 1) * hop] ** 2) + 1e-12) for i in range(n)])
    db = 20 * np.log10(rms)
    top = np.percentile(db, 95)
    o = np.clip((db - max(floor_db, top - 30)) / max(6.0, top - max(floor_db, top - 30)), 0, 1)
    out, m = np.zeros(n), 0.0
    for i, x in enumerate(o):
        m += (x - m) * (0.75 if x > m else 0.45)
        out[i] = m
    return out


def load_fx():
    import importlib.util
    spec = importlib.util.spec_from_file_location("voicefx", Path(__file__).with_name("voicefx.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def build(film, voices_dir, voice_name=None, out_name="voice.wav"):
    """Single-voice scripts use script["voice"]; multi-speaker scripts define
    script["speakers"] = {id: {"voice": ..., "fx": preset name or {pitch, formant, range}}}
    and give each line a "speaker". Per-line "pause" adds silence after a line."""
    script = json.loads((film / "script.json").read_text())
    speakers = script.get("speakers") or {"narrator": {"voice": voice_name or script["voice"]}}
    default = next(iter(speakers))
    voices = {}
    fxmod = load_fx() if any(sp.get("fx") for sp in speakers.values()) else None
    from faster_whisper import WhisperModel
    model = WhisperModel("small.en", device="cpu", compute_type="int8")
    fps = script.get("fps", 30)

    gap = script.get("gap_s", 0.3)
    t = script.get("lead_in_s", 0.3)
    pieces, lines = [np.zeros(int(t * SR_OUT), np.float32)], []
    mouths = []  # (speaker, start_s, track)
    for ln in script["lines"]:
        spk = ln.get("speaker", default)
        cfg = speakers[spk]
        if cfg["voice"] not in voices:
            voices[cfg["voice"]] = PiperVoice.load(str(voices_dir / f"{cfg['voice']}.onnx"))
        a = trim(synth_line(voices[cfg["voice"]], ln["text"], ln.get("length_scale", script.get("length_scale", 1.0))))
        if cfg.get("fx") and fxmod:
            fx = cfg["fx"] if isinstance(cfg["fx"], dict) else {"preset": cfg["fx"]}
            p = {**fxmod.PRESETS.get(fx.get("preset"), {"pitch": 1.0, "formant": 1.0, "range": 1.0}),
                 **{k: v for k, v in fx.items() if k != "preset"}}
            y, _, _ = fxmod.revoice(a.astype(np.float64), SR_OUT, p["pitch"], p["formant"], p["range"])
            a = (y * (0.9 / (np.max(np.abs(y)) + 1e-9))).astype(np.float32)
        words = align_words(model, a, ln["text"])
        d = len(a) / SR_OUT
        lines.append({"id": ln["id"], "speaker": spk, "fact": ln.get("fact"), "text": ln["text"],
                      "start": round(t, 3), "end": round(t + d, 3),
                      "words": [{**w, "start": round(t + w["start"], 3),
                                 "end": round(t + w["end"], 3)} for w in words]})
        mouths.append((spk, t, mouth_track(a, fps)))
        pause = gap + ln.get("pause", 0.0)
        pieces += [a, np.zeros(int(pause * SR_OUT), np.float32)]
        t += d + pause
    audio = np.concatenate(pieces)
    out = film / "build"
    out.mkdir(exist_ok=True)
    sf.write(out / out_name, audio, SR_OUT, subtype="PCM_24")
    # per-speaker mouth tracks on the film's frame grid
    nfr = int(np.ceil(len(audio) / SR_OUT * fps)) + 1
    mouth = {spk: np.zeros(nfr) for spk in speakers}
    for spk, start, tr in mouths:
        i0 = int(round(start * fps))
        seg = tr[: max(0, nfr - i0)]
        mouth[spk][i0:i0 + len(seg)] = np.maximum(mouth[spk][i0:i0 + len(seg)], seg)
    n_words = sum(len(l["words"]) for l in lines)
    speech = sum(l["end"] - l["start"] for l in lines)
    return {"voice": ",".join(sorted({c["voice"] for c in speakers.values()})), "duration": round(len(audio) / SR_OUT, 3),
            "wpm": round(60 * n_words / (len(audio) / SR_OUT), 1),
            "wpm_speech_only": round(60 * n_words / speech, 1), "lines": lines,
            "mouth": {k: [round(float(v), 2) for v in tr] for k, tr in mouth.items() if tr.any()}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("film", type=Path)
    ap.add_argument("--voices-dir", type=Path, required=True)
    ap.add_argument("--audition", action="store_true")
    args = ap.parse_args()
    if args.audition:
        for onnx in sorted(args.voices_dir.glob("*.onnx")):
            r = build(args.film, args.voices_dir, onnx.stem, f"audition-{onnx.stem}.wav")
            print(f"{r['voice']}: {r['duration']} s, {r['wpm']} wpm overall, "
                  f"{r['wpm_speech_only']} wpm while speaking")
        return
    r = build(args.film, args.voices_dir)
    timing = {"fps": 30, "voice": r["voice"], "duration": r["duration"],
              "wpm": r["wpm"], "lines": r["lines"], "mouth": r["mouth"]}
    (args.film / "timing.json").write_text(json.dumps(timing, indent=1))
    # file:// pages can't fetch JSON, so the scene loads timing as a script
    (args.film / "build" / "timing.js").write_text(f"window.TIMING = {json.dumps(timing)};\n")
    print(json.dumps({k: v for k, v in r.items() if k not in ("lines", "mouth")}))


if __name__ == "__main__":
    main()
