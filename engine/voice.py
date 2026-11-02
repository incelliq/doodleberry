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
    if hasattr(voice, "synth"):  # Kokoro backend
        audio, sr = voice.synth(text, length_scale)
        return resample(audio, sr, SR_OUT)
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


def trim(x, thresh=0.01, pad=0.03, offset=False):
    """drop silence at both ends; offset=True also returns the seconds removed from the start"""
    idx = np.where(np.abs(x) > thresh)[0]
    if len(idx) == 0:
        return (x, 0.0) if offset else x
    p = int(pad * SR_OUT); a = max(0, idx[0] - p)
    return (x[a: idx[-1] + p], a / SR_OUT) if offset else x[a: idx[-1] + p]


def norm_word(w):
    return re.sub(r"[^\w']", "", w.lower()).replace("_", "")


def align_words(model, audio, text, lang="en"):
    """Word timings for `text` inside `audio` (seconds, relative to audio start).
    Recognised words are mapped back onto the script's own words so captions
    always show the script text; unmatched script words are interpolated."""
    from scipy.signal import resample_poly
    a16 = resample_poly(audio, 1, 3).astype(np.float32)
    segs, _ = model.transcribe(a16, language=lang, word_timestamps=True,
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
    # a word Whisper missed can inherit its neighbour's start; keep starts at least 0.16 s apart
    for i in range(1, len(times)):
        if times[i][0] < times[i - 1][0] + 0.16:
            times[i] = (min(times[i - 1][0] + 0.16, dur), max(times[i][1], times[i - 1][0] + 0.3))
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
    # language: script["lang"], else the first voice's prefix (es_ES-carlfm-x_low -> es)
    v0 = next(iter(speakers.values()))["voice"]
    _kl = {"a": "en", "b": "en", "e": "es", "f": "fr", "h": "hi", "i": "it", "j": "ja", "p": "pt", "z": "zh"}
    lang = script.get("lang") or (_kl.get(v0.split(":", 1)[1][:1], "en") if v0.startswith("kokoro:") else v0.split("_")[0])
    model = WhisperModel("small.en" if lang == "en" else "small", device="cpu", compute_type="int8")
    fps = script.get("fps", 30)

    gap = script.get("gap_s", 0.3)
    t = script.get("lead_in_s", 0.3)
    pieces, lines = [np.zeros(int(t * SR_OUT), np.float32)], []
    mouths = []  # (speaker, start_s, track)
    vis = {}  # speaker -> [[t, shape], ...]
    for ln in script["lines"]:
        spk = ln.get("speaker", default)
        cfg = speakers[spk]
        if cfg["voice"] not in voices:
            if cfg["voice"].startswith("kokoro:"):
                _ku = __import__("importlib.util").util; _ks = _ku.spec_from_file_location("kokoro_voice", Path(__file__).with_name("kokoro_voice.py"))
                _km = _ku.module_from_spec(_ks); _ks.loader.exec_module(_km)
                voices[cfg["voice"]] = _km.KokoroVoice(cfg["voice"], voices_dir)
            else:
                voices[cfg["voice"]] = PiperVoice.load(str(voices_dir / f"{cfg['voice']}.onnx"))
        def make(text, ls):
            """synthesize, trim, phone timings on the trimmed clock (plan 2.1), voice fx"""
            a_, cut0 = trim(synth_line(voices[cfg["voice"]], text, ls), offset=True)
            ph_ = [(ph, s0 - cut0, s1 - cut0) for ph, s0, s1 in (getattr(voices[cfg["voice"]], "last_phones", None) or [])]
            if cfg.get("fx") and fxmod:
                fx = cfg["fx"] if isinstance(cfg["fx"], dict) else {"preset": cfg["fx"]}
                p = {**fxmod.PRESETS.get(fx.get("preset"), {"pitch": 1.0, "formant": 1.0, "range": 1.0}),
                     **{k: v for k, v in fx.items() if k != "preset"}}
                y, _, _ = fxmod.revoice(a_.astype(np.float64), SR_OUT, p["pitch"], p["formant"], p["range"])
                a_ = (y * (0.9 / (np.max(np.abs(y)) + 1e-9))).astype(np.float32)
            return a_, ph_
        ls0 = ln.get("length_scale", script.get("length_scale", 1.0)); spoken = ln["text"]
        a, phones = make(spoken, ls0)
        slot = ln.get("slot")   # plan 2.16: [start_s, max_s] fixed before any voice; the picture is cut on slots
        fit = None
        if slot:
            if len(a) / SR_OUT > slot[1] and ln.get("alt"):   # the short alternate first
                a2, ph2 = make(ln["alt"], ls0)
                if len(a2) < len(a):
                    a, phones, spoken, fit = a2, ph2, ln["alt"], "alt"
            if len(a) / SR_OUT > slot[1]:   # then a little faster (at most 15%)
                k = max(0.85, slot[1] / (len(a) / SR_OUT) * 0.98)
                a, phones = make(spoken, ls0 * k); fit = (fit + "+" if fit else "") + f"speed x{1 / k:.2f}"
            if t < slot[0]:
                pieces.append(np.zeros(int(round((slot[0] - t) * SR_OUT)), np.float32)); t = slot[0]
            elif t > slot[0] + 0.01:   # the previous line ran past this slot's start: say so, never move the slot
                print(f"slot collision: line {ln['id']} starts {t - slot[0]:.2f} s late (the line before overflowed)")
        import importlib.util as _u
        _spec = _u.spec_from_file_location("visemes", Path(__file__).with_name("visemes.py")); _vm = _u.module_from_spec(_spec); _spec.loader.exec_module(_vm)
        words = _vm.phone_words(phones, spoken.split(), voices[cfg["voice"]].phonemize) if phones else None
        align = "model" if words else "whisper"
        words = words or align_words(model, a, spoken, lang)
        d = len(a) / SR_OUT
        slot_extra = {}
        if slot:   # the line keeps its slot: start at the slot, end at the slot's end, so nothing in the picture moves
            slot_extra = {"slot": slot, "voice_end": round(t + d, 3), **({"fit": fit} if fit else {}),
                          **({"overflow_s": round(d - slot[1], 3)} if d > slot[1] + 0.01 else {}), **({"spoken": spoken} if spoken != ln["text"] else {})}
        lines.append({"id": ln["id"], "speaker": spk, "fact": ln.get("fact"), "text": spoken,
                      "start": round(t, 3), "end": round(t + (slot[1] if slot else d), 3), "align": align, **slot_extra,
                      "words": [{**w, "start": round(t + w["start"], 3),
                                 "end": round(t + w["end"], 3)} for w in words]})
        mouths.append((spk, t, mouth_track(a, fps)))
        try:  # lip-sync cues (visemes): the model's own phone timings when it has them, else phonemes spread over words
            if phones:
                vis.setdefault(spk, []).extend(_vm.phone_visemes(phones, t))
            else:
                vis.setdefault(spk, []).extend(_vm.line_visemes(voices[cfg["voice"]], lines[-1]["words"]))
        except Exception as e:  # lip-sync falls back to loudness
            print("visemes skipped:", e)
        if slot:
            pieces.append(a); t += d
        else:
            pause = gap + ln.get("pause", 0.0)
            pieces += [a, np.zeros(int(pause * SR_OUT), np.float32)]
            t += d + pause
    if script["lines"] and script["lines"][-1].get("slot"):   # a tail after the last slot, like the unslotted gap
        sl = script["lines"][-1]["slot"]; tail = max(0.0, sl[0] + sl[1] + gap - t)
        pieces.append(np.zeros(int(tail * SR_OUT), np.float32))
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
            "mouth": {k: [round(float(v), 2) for v in tr] for k, tr in mouth.items() if tr.any()},
            "visemes": vis}


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
              "wpm": r["wpm"], "lines": r["lines"], "mouth": r["mouth"], "visemes": r.get("visemes", {})}
    (args.film / "timing.json").write_text(json.dumps(timing, indent=1))
    # file:// pages can't fetch JSON, so the scene loads timing as a script
    (args.film / "build" / "timing.js").write_text(f"window.TIMING = {json.dumps(timing)};\n")
    print(json.dumps({k: v for k, v in r.items() if k not in ("lines", "mouth")}))


if __name__ == "__main__":
    main()
