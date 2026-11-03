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


EMO_WORDS = [   # what a line's words say about how its speaker feels (first match wins); a question alone is not an emotion
    ("sad", r"\b(oh no|sorry|sad|lost|broke|broken|hurts?|miss(ed)?|ugh|alas|my tail|cried|cry)\b"),
    ("angry", r"\b(hate|stop it|how dare|furious|unfair|grr+)\b"),
    ("surprised", r"\b(no way|really\?|what\?|wow|whoa|huh|seriously)\b"),
    ("happy", r"\b(did it|yes!|yay|hooray|great|nice|best|love|amazing|awesome|thank|brilliant|perfect)\b")]
EMO_POSE = {"happy": "confident", "sad": "worried"}
LISTEN = {"sad": "present", "happy": "clap", "surprised": "surprised"}   # a listener's reaction to how a line feels


def emotion_of(text):
    t = text.lower()
    return next((e for e, rx in EMO_WORDS if re.search(rx, t)), None)


NEUTRAL = {"tempo": 1.0, "energy": 1.0, "beat_gap": 0.9, "beat_words": 4, "point": "point", "exclaim": "talk_open_palms", "question": "shrug",
           "listen_nod": 0.8, "look_away": 0, "never": [], "react": "surprised"}


def plan_cast(template, lines, me, others_x, my_x, pro_of, energy=1.0, prof=None, lib=None):
    """prof: a personality profile (cast/profiles.json; None = neutral, the earlier gesture choices); lib: the clip names the
    character can play (tagged gestures and profile choices outside it fall back)"""
    P = {**NEUTRAL, **(prof or {})}; never = set(P.get("never") or [])
    clips, look, blinks, emo, poses = [], [], [], [], []
    humanoid = template == "humanoid"
    busy_until = -1.0; gap = P["beat_gap"]; energy = energy * P["energy"]
    can = lambda c: c and c != "none" and c not in never and (lib is None or c in lib)
    style = lambda k: {**k, **({"speed": round(P["tempo"], 2)} if P["tempo"] != 1 and not k.get("additive") else {}),
                       **({"gain": round(min(1.6, P["energy"]), 2)} if P["energy"] != 1 and not k.get("additive") else {})}
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
            towards = next(iter(others_x.values()), my_x + 1)
            # tagged gestures (WP-10): an agent's tags on words, validated against the clip library before they get here
            for tg in ln.get("gestures") or []:
                k = tg.get("word", 0)
                if not 0 <= k < len(words):
                    continue
                c = tg["clip"]; c = ("point_R" if towards >= my_x else "point_L") if c == "point" else ("present_R" if towards >= my_x else "present_L") if c == "present" else c
                if not can(c):
                    continue
                t0 = max(ln["start"], words[k]["start"] - 0.2)
                clips.append(style({"clip": c, "start": round(t0, 3), "end": round(t0 + 1.0, 3), "weight": 3, "auto": True, "tagged": True})); used.append(words[k]["start"]); busy_until = max(busy_until, t0 + 1.0)
            # an exclamation: open palms (or the profile's choice) on its strongest word
            ex_clip = P["exclaim"] if humanoid else None
            if excl and humanoid and order and can(ex_clip) and not used:
                i = order[0]; t0 = max(ln["start"], words[i]["start"] - 0.2)
                clips.append(style({"clip": ex_clip, "start": round(t0, 3), "end": round(min(ln["end"] + 0.3, t0 + 1.4), 3), "weight": 3, "auto": True})); used.append(t0); busy_until = t0 + 1.2
            for i in range(len(words)):  # one point per line, towards the listener (a shy character only glances)
                wtxt = re.sub(r"\W", "", words[i]["text"].lower())
                if wtxt in POINT_WORDS and humanoid and P["point"] != "none" and all(abs(words[i]["start"] - u) > gap for u in used) and words[i]["start"] > busy_until:
                    t0 = max(ln["start"], words[i]["start"] - 0.25); pc = "point_R" if towards >= my_x else "point_L"
                    if P["point"] == "point" and can(pc):
                        clips.append(style({"clip": pc, "start": round(t0, 3), "end": round(t0 + 0.9, 3), "weight": 3, "auto": True})); used.append(words[i]["start"]); busy_until = t0 + 1.0
                    elif P["point"] == "glance" and others_x:
                        look.append([round(t0, 3), [1.0 if towards > my_x else -1.0, 0.2]]); look.append([round(t0 + 0.6, 3), [0.0, 0.3]])
                    break
            for i in order:  # beats on emphasised words
                if em[i] < 0.25 or len(used) >= 1 + len(words) // P["beat_words"]:
                    break
                ws = words[i]["start"]
                if all(abs(ws - u) > gap for u in used) and ws > busy_until - 0.2:
                    clips.append({"clip": "talk_beat" if humanoid else "talk", "start": round(max(ln["start"], ws - 0.12), 3), "additive": True,
                                  **({"end": round(ws + 0.7, 3)} if not humanoid else {}), "weight": round(0.8 * energy, 2), "auto": True})
                    used.append(ws)
            q_clip = P["question"] if humanoid else "tilt"
            if ques and can(q_clip):
                t0 = words[-1]["start"] - 0.1
                clips.append(style({"clip": q_clip, "start": round(t0, 3), **({"end": round(t0 + 0.9, 3)} if not humanoid else {}), "weight": 3, "auto": True}))
            look.append([round(ln["start"], 3), [0.0, 0.0]])
            e = emotion_of(text)   # held from just before the line until the speaker's next line says otherwise
            emo.append([round(ln["start"] - 0.2, 3), e or "neutral"])
            if humanoid and EMO_POSE.get(e):
                poses.append([round(ln["start"] - 0.2, 3), EMO_POSE[e]])
            elif humanoid and poses:
                poses.append([round(ln["start"] - 0.2, 3), "neutral"])
        else:
            # listening: look towards the speaker, nod after the line, blink on its end
            sx = others_x.get(ln["speaker"])
            if sx is not None:   # a shy character's eyes drift down and off the speaker
                la = P["look_away"]
                look.append([round(ln["start"] - 0.15, 3), [round((1.0 if sx > my_x else -1.0) * (1 - la), 2), round(0.1 + 0.5 * la, 2)]])
            e = emotion_of(ln.get("text", ""))
            rc = LISTEN.get(e) if humanoid else None
            if rc in ("present",) and sx is not None:
                rc = "present_R" if sx > my_x else "present_L"
            if e:   # a listener feels with the speaker: the face follows, and a reaction answers the line
                emo.append([round(ln["start"] + 0.3, 3), e if e != "angry" else "worried"])
            if rc and can(rc) and ln["end"] > busy_until:
                clips.append(style({"clip": rc, "start": round(ln["end"] + 0.1, 3), "end": round(ln["end"] + 1.3, 3), "weight": 2.5, "auto": True})); busy_until = ln["end"] + 1.3
            elif P["listen_nod"] > 0:
                clips.append({"clip": "nod" if humanoid else "tilt", "start": round(ln["end"] + 0.05, 3), "additive": humanoid, **({"end": round(ln["end"] + 0.7, 3)} if not humanoid else {}),
                              "weight": round(P["listen_nod"], 2), "auto": True})
            blinks.append(round(ln["end"] + 0.35, 3))
    return clips, look, blinks, emo, poses


def plan_film(film_dir, spans=None):
    d = Path(film_dir); shots = json.loads((d / "shots.json").read_text()); timing = json.loads((d / "timing.json").read_text())
    lines = timing.get("lines", []); wav = d / "build" / "voice.wav"
    cache = {}

    def pro_of(words):
        key = (words[0]["start"], words[-1]["end"])
        if key not in cache:
            cache[key] = prosody(wav, words)
        return cache[key]
    root = d.parent.parent; report = {}
    script = json.loads((d / "script.json").read_text()) if (d / "script.json").exists() else {}
    by_id = {l.get("id"): l for l in script.get("lines", [])}
    lines = [{**l, **{k: by_id[l["id"]][k] for k in ("gestures", "beat") if k in by_id.get(l["id"], {})}} for l in lines]   # an agent's tags ride on the script's lines
    profiles = json.loads((root / "cast" / "profiles.json").read_text()) if (root / "cast" / "profiles.json").exists() else {"profiles": {}}
    cast_ix = {e["path"]: e for e in json.loads((root / "cast" / "index.json").read_text()).get("puppets", [])} if (root / "cast" / "index.json").exists() else {}

    def profile_of(me, pz, path):
        name = ((script.get("speakers") or {}).get(me) or {}).get("profile") or (pz.get("acting") or {}).get("profile") or (cast_ix.get(path) or {}).get("profile")
        return name, (profiles["profiles"].get(name) if name else None)

    def library(pz):
        f = root / "puppet" / "clips" / f"{pz.get('template', 'humanoid')}.json"
        return set(json.loads(f.read_text())["clips"]) | set(pz.get("clips") or {}) if f.exists() else None
    for sh in shots["shots"]:
        cast = sh.get("cast") or []
        xs = {}
        for c in cast:
            pl = c.get("place") or {}
            if c.get("speaker") and isinstance(pl, dict):
                xs[c["speaker"]] = pl.get("x", 540)
        s0, s1 = (spans or {}).get(sh["id"], (sh.get("start", 0), sh.get("end", 1e9)))
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
            pname, prof = profile_of(me, pz, c["puppet"])
            clips, look, blinks, emo, poses = plan_cast(pz.get("template", "humanoid"), in_shot, me, {k: v for k, v in xs.items() if k != me}, my_x, pro_of,
                                                        (pz.get("acting") or {}).get("energy", 1.0), prof, library(pz))
            tl["clips"] += clips
            if emo and not tl.get("emotion_manual"):   # how it feels, held between lines (WP-10)
                emo = sorted(emo, key=lambda k: k[0]); tl["emotion"] = [k for i, k in enumerate(emo) if i == 0 or k[1] != emo[i - 1][1]]
            # (body presets per emotion were tried and dropped: a blind critic read a held preset as a stiff pose and a
            #  hand resting on the tail as giving the gag away; faces carry the emotion, gestures the body)
            if look and not tl.get("look_manual"):
                tl["look"] = sorted(look, key=lambda k: k[0])
            if blinks:
                tl["blinks"] = sorted(set([b for b in tl.get("blinks", []) if isinstance(b, (int, float))] + blinks))
            tl.setdefault("visemes_from", me)
            report[f"{sh['id']}:{me}"] = {"gestures": [k["clip"] + "@" + str(k["start"]) for k in clips], "looks": len(look), "blinks": len(blinks), **({"profile": pname} if pname else {})}
        # camera beats in gags (WP-10): a stare (a line marked "beat": "stare", or with script "gag_beats", a pause of
        # 0.8 s or more after an exclamation, question or trailing off) holds on whoever reacts and pushes in
        if isinstance(sh.get("camera_auto"), (dict, bool)) and sh.get("camera_auto"):
            ca = sh["camera_auto"] if isinstance(sh["camera_auto"], dict) else {}
            beats = [b for b in ca.get("beats", []) if not b.get("auto")]
            for a, b in zip(in_shot, in_shot[1:]):
                gag = a.get("beat") == "stare" or (script.get("gag_beats") and b["start"] - a["end"] >= 0.8 and a["text"].rstrip().endswith(("!", "?", "...", "…")))
                who = b["speaker"] if b["speaker"] != a["speaker"] and b["speaker"] in xs else next((k for k in xs if k != a["speaker"]), None)
                if gag and who and b["start"] - a["end"] >= 0.4:
                    t0, t1 = round(a["end"] + 0.1, 3), round(b["start"] - 0.05, 3)
                    beats.append({"t0": t0, "t1": t1, "who": who, "zoom": 1.3, "auto": True})
                    rc = next((c for c in cast if c.get("speaker") == who), None)
                    if rc:
                        pz2 = json.loads((root / rc["puppet"]).read_text()); _, pr2 = profile_of(who, pz2, rc["puppet"]); P2 = {**NEUTRAL, **(pr2 or {})}; lib2 = library(pz2)
                        if P2["react"] in (lib2 or {P2["react"]}) and P2["react"] not in (P2.get("never") or []):
                            rc["timeline"]["clips"].append({"clip": P2["react"], "start": t0, "end": round(t1 + 0.3, 3), "weight": 2, "auto": True, "beat": "stare"})
                    report.setdefault("beats", []).append({"shot": sh["id"], "after": a["id"], "who": who, "t0": t0, "t1": t1})
            if beats or ca.get("beats"):
                ca["beats"] = beats; sh["camera_auto"] = ca
    (d / "shots.json").write_text(json.dumps(shots, indent=1, ensure_ascii=False))
    return report


if __name__ == "__main__":
    print(json.dumps(plan_film(sys.argv[1], json.loads(sys.argv[2]) if len(sys.argv) > 2 else None)))
