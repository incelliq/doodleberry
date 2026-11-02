"""Gesture planner (plan 2.3): characters act from the script and the voice, with no hand-placed clips.

    python dbe/gestures.py FILM_DIR          (run with DBE_PY: reads build/voice.wav for prosody)

For each shot and each cast member with a speaker:
- while speaking: beat gestures on emphasised words (loudness, pitch and length above the line's median), at most one
  every 0.9 s; a pointing word ("you", "this", "that", "look", "here", "there") gets a point; an exclamation gets open
  palms on its strongest word; a question ends with a shrug (humanoid) or a head tilt (doodle), brows raised;
- while listening: gaze on the speaker, a nod just after each of their lines, an occasional blink on their pauses;
- every line returns to idle, and nothing overlaps another gesture.
Generated clips are tagged "auto": true and replace earlier auto clips on each run, so hand-placed clips always survive.
Prints the plan per cast member as JSON.
"""
import json
import re
import sys
from pathlib import Path

import numpy as np

POINT_WORDS = {"you", "your", "this", "that", "these", "those", "look", "here", "there"}


def prosody(wav_path, words):
    """per word: loudness (RMS dB), pitch (median F0 Hz, 0 if unvoiced) and duration"""
    try:
        import soundfile as sf
        x, sr = sf.read(str(wav_path), dtype="float64")
        if x.ndim > 1:
            x = x.mean(1)
    except Exception:
        return [{"db": 0, "f0": 0, "dur": w["end"] - w["start"]} for w in words]
    try:
        import pyworld as pw
        x16 = x[::3] if sr >= 48000 else x; sr16 = sr // 3 if sr >= 48000 else sr
        f0, t = pw.dio(np.ascontiguousarray(x16), sr16, frame_period=10)
    except Exception:
        f0, t = None, None
    out = []
    for w in words:
        a, b = int(w["start"] * sr), max(int(w["start"] * sr) + 1, int(w["end"] * sr))
        seg = x[a:b]
        db = 20 * np.log10(np.sqrt(np.mean(seg ** 2)) + 1e-9) if len(seg) else -90
        fz = 0.0
        if f0 is not None:
            m = (t >= w["start"]) & (t <= w["end"]) & (f0 > 0)
            fz = float(np.median(f0[m])) if m.any() else 0.0
        out.append({"db": float(db), "f0": fz, "dur": w["end"] - w["start"]})
    return out


def emphasis(words, pro):
    """z-score mix of loudness, pitch and length within the line"""
    if not words:
        return []
    def z(v):
        v = np.array(v, float); s = v.std() or 1
        return (v - np.median(v)) / s
    db = z([p["db"] for p in pro]); dur = z([p["dur"] / max(1, len(re.sub(r"\W", "", w["text"]))) for w, p in zip(words, pro)])
    f0s = [p["f0"] for p in pro]; f0 = z(f0s) if any(f0s) else np.zeros(len(words))
    return list(0.45 * db + 0.3 * f0 + 0.25 * dur)


def plan_cast(template, lines, me, others_x, my_x, pro_of, energy=1.0):
    clips, look, blinks = [], [], []
    humanoid = template == "humanoid"
    busy_until = -1.0
    for ln in lines:
        words = ln.get("words") or []
        if not words:
            continue
        text = ln.get("text", "")
        if ln["speaker"] == me:
            pro = pro_of(words); em = emphasis(words, pro)
            excl, ques = text.strip().endswith("!"), text.strip().endswith("?")
            order = sorted(range(len(words)), key=lambda i: -em[i])
            used = []
            # an exclamation: open palms on its strongest word
            if excl and humanoid and order:
                i = order[0]; t0 = max(ln["start"], words[i]["start"] - 0.2)
                clips.append({"clip": "talk_open_palms", "start": round(t0, 3), "end": round(min(ln["end"] + 0.3, t0 + 1.4), 3), "weight": 3, "auto": True}); used.append(t0); busy_until = t0 + 1.2
            towards = next(iter(others_x.values()), my_x + 1)
            for i in range(len(words)):  # one point per line, towards the listener
                wtxt = re.sub(r"\W", "", words[i]["text"].lower())
                if wtxt in POINT_WORDS and humanoid and all(abs(words[i]["start"] - u) > 0.9 for u in used) and words[i]["start"] > busy_until:
                    t0 = max(ln["start"], words[i]["start"] - 0.25)
                    clips.append({"clip": "point_R" if towards >= my_x else "point_L", "start": round(t0, 3), "end": round(t0 + 0.9, 3), "weight": 3, "auto": True}); used.append(words[i]["start"]); busy_until = t0 + 1.0
                    break
            for i in order:  # beats on emphasised words
                if em[i] < 0.25 or len(used) >= 1 + len(words) // 4:
                    break
                ws = words[i]["start"]
                if all(abs(ws - u) > 0.9 for u in used) and ws > busy_until - 0.2:
                    clips.append({"clip": "talk_beat" if humanoid else "talk", "start": round(max(ln["start"], ws - 0.12), 3), "additive": True,
                                  **({"end": round(ws + 0.7, 3)} if not humanoid else {}), "weight": round(0.8 * energy, 2), "auto": True})
                    used.append(ws)
            if ques:
                t0 = words[-1]["start"] - 0.1
                clips.append({"clip": "shrug" if humanoid else "tilt", "start": round(t0, 3), **({"end": round(t0 + 0.9, 3)} if not humanoid else {}), "weight": 3, "auto": True})
            look.append([round(ln["start"], 3), [0.0, 0.0]])
        else:
            # listening: look towards the speaker, nod after the line, blink on its end
            sx = others_x.get(ln["speaker"])
            if sx is not None:
                look.append([round(ln["start"] - 0.15, 3), [1.0 if sx > my_x else -1.0, 0.1]])
            clips.append({"clip": "nod" if humanoid else "tilt", "start": round(ln["end"] + 0.05, 3), "additive": humanoid, **({"end": round(ln["end"] + 0.7, 3)} if not humanoid else {}),
                          "weight": 0.8, "auto": True})
            blinks.append(round(ln["end"] + 0.35, 3))
    return clips, look, blinks


def plan_film(film_dir):
    d = Path(film_dir); shots = json.loads((d / "shots.json").read_text()); timing = json.loads((d / "timing.json").read_text())
    lines = timing.get("lines", []); wav = d / "build" / "voice.wav"
    cache = {}

    def pro_of(words):
        key = (words[0]["start"], words[-1]["end"])
        if key not in cache:
            cache[key] = prosody(wav, words)
        return cache[key]
    root = d.parent.parent; report = {}
    for sh in shots["shots"]:
        cast = sh.get("cast") or []
        xs = {}
        for c in cast:
            pl = c.get("place") or {}
            if c.get("speaker") and isinstance(pl, dict):
                xs[c["speaker"]] = pl.get("x", 540)
        s0, s1 = sh.get("start", 0), sh.get("end", 1e9)
        in_shot = [l for l in lines if l["end"] > (s0 if isinstance(s0, (int, float)) else 0) and l["start"] < (s1 if isinstance(s1, (int, float)) else 1e9)]
        for c in cast:
            me = c.get("speaker")
            if not me:
                continue
            pz = json.loads((root / c["puppet"]).read_text())
            tl = c.setdefault("timeline", {})
            tl["clips"] = [k for k in tl.get("clips", []) if not k.get("auto")]
            if not any(k.get("clip") == "idle" for k in tl["clips"]):
                tl["clips"].insert(0, {"clip": "idle", "start": 0, "fadeIn": 0, "auto": True})
            my_x = (c.get("place") or {}).get("x", 540) if isinstance(c.get("place"), dict) else 540
            clips, look, blinks = plan_cast(pz.get("template", "humanoid"), in_shot, me, {k: v for k, v in xs.items() if k != me}, my_x, pro_of,
                                            (pz.get("acting") or {}).get("energy", 1.0))
            tl["clips"] += clips
            if look and not tl.get("look_manual"):
                tl["look"] = sorted(look, key=lambda k: k[0])
            if blinks:
                tl["blinks"] = sorted(set([b for b in tl.get("blinks", []) if isinstance(b, (int, float))] + blinks))
            tl.setdefault("visemes_from", me)
            report[f"{sh['id']}:{me}"] = {"gestures": [k["clip"] + "@" + str(k["start"]) for k in clips], "looks": len(look), "blinks": len(blinks)}
    (d / "shots.json").write_text(json.dumps(shots, indent=1, ensure_ascii=False))
    return report


if __name__ == "__main__":
    print(json.dumps(plan_film(sys.argv[1])))
