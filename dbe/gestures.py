"""Gesture planner (plan 2.3): characters act from the script and the voice, with no hand-placed clips.

    python dbe/gestures.py FILM_DIR          (run with DBE_PY: reads build/voice.wav for prosody)

For each shot and each cast member with a speaker:
- while speaking: beat gestures on emphasised words (loudness, pitch and length above the line's median), at most one
  every 0.9 s; a pointing word ("you", "this", "that", "look", "here", "there") gets a point, raised with the clause (up to
  1.5 s before the word) and held to the end of the line (in a question, a quick point on the word); an exclamation gets open
  palms on its strongest word; a question ends with a shrug (humanoid) or a head tilt (doodle), brows raised;
- a denial gets a shrug from its first word (pretended ignorance: the other's word echoed back as a question) or a head
  shake on its "no" (WP-10); the scene's last line said as an admission ("Oh. That...") is the punchline: the speaker
  scratches their head after it and the listeners hold a stare instead of nodding;
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
NEGATION = re.compile(r"\b(no|nope|not|never|nothing|nobody|didn'?t|wasn'?t|isn'?t|aren'?t|don'?t|doesn'?t|won'?t|can'?t)\b")
GREETINGS = {"hi", "hello", "hey", "hiya", "howdy", "greetings", "morning", "evening", "welcome"}
ADMIT = re.compile(r"^\W*(oh|uh|um|ah|er|erm|well|oops|whoops|heh)\b", re.I)
# where the accusing line puts the thing on the accused ("sticking out behind your back", "in your pocket"): the
# admission then indicates it there, not the listener (WP-10, blind critics: the open hand toward the listener on
# "That telescope" read as pointing away from it)
ON_ME = re.compile(r"\b(behind|under|in|on|inside|up)\s+(your|his|her|their)\s+(back|pocket|pockets|bag|backpack|sleeve|shirt|jumper|hoodie|coat|jacket|hat)\b", re.I)


def denial_of(text, prev):
    """'negate' (a no, not, never...), 'feign' (the other's word echoed back as a question: "Telescope? What
    telescope?", a pretended ignorance) or None. prev: the line before, by someone else"""
    t = text.lower()
    if NEGATION.search(t):
        return "negate"
    if prev and t.strip().endswith("?"):
        theirs = {w for w in re.findall(r"[a-z']{4,}", prev.lower())}
        if any(w in theirs for w in re.findall(r"[a-z']{4,}", t)):
            return "feign"
    return None


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


REACT_DELAY = 0.25   # a listener takes in a word before the face answers it (human reaction time, ~200-300 ms)


def felt_at(ln):
    """when a listener can first feel the line: just after the word that carries its emotion is heard (the first
    word the emotion's pattern matches), else after the last word (its tone lands at the end); None if no emotion"""
    e = emotion_of(ln.get("text", ""))
    if not e:
        return None, None
    rx = dict(EMO_WORDS)[e]; words = ln.get("words") or []
    for i in range(len(words)):   # the earliest word at which the words so far already carry the emotion
        so_far = " ".join(w["text"] for w in words[:i + 1]).lower()
        if re.search(rx, so_far):
            return e, round(words[i]["end"] + REACT_DELAY, 3)
    return e, round(ln["end"] + REACT_DELAY, 3)


NEUTRAL = {"tempo": 1.0, "energy": 1.0, "beat_gap": 0.9, "beat_words": 4, "point": "point", "exclaim": "talk_open_palms", "question": "shrug",
           "listen_nod": 0.8, "look_away": 0, "never": [], "react": "surprised"}


def plan_cast(template, lines, me, others_x, my_x, pro_of, energy=1.0, prof=None, lib=None, presets=None):
    """prof: a personality profile (cast/profiles.json; None = neutral, the earlier gesture choices); lib: the clip names the
    character can play (tagged gestures and profile choices outside it fall back)"""
    P = {**NEUTRAL, **(prof or {})}; never = set(P.get("never") or [])
    clips, look, blinks, emo, poses = [], [], [], [], []
    humanoid = template == "humanoid"
    busy_until = -1.0; gap = P["beat_gap"]; energy = energy * P["energy"]
    can = lambda c: c and c != "none" and c not in never and (lib is None or c in lib)
    style = lambda k: {**k, **({"speed": round(P["tempo"], 2)} if P["tempo"] != 1 and not k.get("additive") else {}),
                       **({"gain": round(min(1.6, P["energy"]), 2)} if P["energy"] != 1 and not k.get("additive") else {})}
    for li, ln in enumerate(lines):
        words = ln.get("words") or []
        if not words:
            continue
        text = ln.get("text", "")
        prev = next((x.get("text", "") for x in reversed(lines[:li]) if x["speaker"] != ln["speaker"]), "")
        last = li == len(lines) - 1
        # the punchline (WP-10): the scene's last line, said as an admission ("Oh. That telescope."): the speaker is
        # caught out, so a sheepish reaction follows it, and whoever hears it holds a stare instead of nodding
        caught = last and bool(ADMIT.search(text))
        # the line that catches someone out (WP-10, blind critics: "a caught reaction before the admission, more
        # personality in the accuser"): the line just before an admission, said by someone else
        nxt = lines[li + 1] if li + 1 < len(lines) else None
        accuses = bool(nxt) and li + 1 == len(lines) - 1 and nxt["speaker"] != ln["speaker"] and bool(ADMIT.search(nxt.get("text", "")))
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
            # a denial (WP-10): a blind critic saw the denier stand neutral. Pretended ignorance shrugs from the first
            # word through the line; a plain no shakes the head on the word
            den = denial_of(text, prev) if humanoid else None
            if den == "feign" and can("shrug") and not used:
                t0 = max(ln["start"] - 0.1, busy_until)
                clips.append(style({"clip": "shrug", "start": round(t0, 3), "end": round(ln["end"] + 0.4, 3), "weight": 3, "auto": True, "why": "denial"}))
                used.append(t0); busy_until = ln["end"] + 0.4
            elif den == "negate" and can("head_shake"):
                k = next((i for i, w in enumerate(words) if NEGATION.search(w["text"].lower())), 0)
                t0 = max(ln["start"], words[k]["start"] - 0.1)
                clips.append({"clip": "head_shake", "start": round(t0, 3), "end": round(t0 + 1.0, 3), "weight": 2.5, "auto": True, "why": "denial"})
                used.append(words[k]["start"])
            if not humanoid:   # a puppet of another template (a doodle): what its own clips can say (WP-10, round 7:
                # a blind critic saw Nib "close to a frozen idle" through both lines with only talk planned)
                w0 = re.sub(r"\W", "", words[0]["text"].lower())
                if w0 in GREETINGS and (can("wave_R") or can("wave_L")):   # a greeting waves from the first word
                    wc = ("wave_R" if towards >= my_x else "wave_L") if can("wave_R") and can("wave_L") else ("wave_R" if can("wave_R") else "wave_L")
                    t0 = max(ln["start"] - 0.15, busy_until)
                    clips.append(style({"clip": wc, "start": round(t0, 3), "end": round(min(ln["end"], t0 + 1.4), 3), "weight": 3, "auto": True, "why": "greeting"}))
                    used.append(words[0]["start"]); busy_until = t0 + 1.4
                if NEGATION.search(text.lower()) and can("shake") and not used:   # a plain no
                    k = next((i for i, w in enumerate(words) if NEGATION.search(w["text"].lower())), 0)
                    t0 = max(ln["start"], words[k]["start"] - 0.1)
                    clips.append({"clip": "shake", "start": round(t0, 3), "end": round(t0 + 0.9, 3), "weight": 2.5, "auto": True, "why": "denial"}); used.append(words[k]["start"])
                if excl and order and can("hop"):   # an exclamation: a hop on the word it ends on ("on purpose!")
                    i = len(words) - 1 if words[-1]["start"] > busy_until else None
                    if i is not None:
                        t0 = max(ln["start"], words[i]["start"] - 0.12)
                        clips.append(style({"clip": "hop", "start": round(t0, 3), "weight": 3, "auto": True, "why": "exclamation"})); used.append(words[i]["start"]); busy_until = t0 + 0.7
                        if presets and "arms_up" in presets:   # and lands in a held ta-da (round 8: the hand-keyed Nib's
                            # wide-armed hold after "purpose!" was what the critic missed)
                            poses.append([round(t0 - 0.2, 3), "arms_up"]); poses.append([round(t0 + 1.1, 3), "neutral"])
                elif not ques and order and can("lean_in") and not used:   # a statement: lean in on its strongest word
                    i = order[0]; t0 = max(ln["start"], words[i]["start"] - 0.2)
                    clips.append(style({"clip": "lean_in", "start": round(t0, 3), "end": round(min(ln["end"] + 0.2, t0 + 1.4), 3), "weight": 2.5, "auto": True, "why": "statement"}))
                    used.append(words[i]["start"]); busy_until = t0 + 1.2
            # an exclamation: open palms (or the profile's choice) on its strongest word
            ex_clip = P["exclaim"] if humanoid else None
            if excl and humanoid and order and can(ex_clip) and not used:
                i = order[0]; t0 = max(ln["start"], words[i]["start"] - 0.2)
                clips.append(style({"clip": ex_clip, "start": round(t0, 3), "end": round(min(ln["end"] + 0.3, t0 + 1.4), 3), "weight": 3, "auto": True})); used.append(t0); busy_until = t0 + 1.2
            for i in range(len(words)):  # one point per line, towards the listener (a shy character only glances)
                wtxt = re.sub(r"\W", "", words[i]["text"].lower())
                if caught:   # owning up ("Oh. That telescope."): an open hand toward the listener after the interjection, held
                    # through the line; blind critics read the hand-keyed arm held out as giving in, a bare idle as flat
                    acc = next((x.get("text", "") for x in reversed(lines[:li]) if x["speaker"] != me), "")
                    on_me = bool(ON_ME.search(acc))   # the thing is on me: indicate it there, with a glance back at it
                    pc = ("present_L" if towards >= my_x else "present_R") if on_me else ("present_R" if towards >= my_x else "present_L")
                    k = 1 if len(words) > 1 else 0
                    if can(pc) and words[k]["start"] > busy_until:
                        t0 = max(ln["start"], words[k]["start"] - 0.15)
                        clips.append(style({"clip": pc, "start": round(t0, 3), "end": round(ln["end"] + 0.1, 3), "weight": 3, "auto": True, "why": "owning up" + (" (at it)" if on_me else "")}))
                        used.append(words[k]["start"])
                        if on_me:   # look round at it on the word, back to the listener by the line's end
                            look.append([round(t0, 3), [-1.0 if towards >= my_x else 1.0, 0.45]])
                            look.append([round(max(t0 + 0.5, ln["end"] - 0.15), 3), [1.0 if towards >= my_x else -1.0, 0.1]])
                    break
                if wtxt in POINT_WORDS and humanoid and P["point"] != "none" and all(abs(words[i]["start"] - u) > gap for u in used) and words[i]["start"] > busy_until:
                    # the point comes up with the clause, not on the word: as early as 1.5 s before it (never before the
                    # line or a gesture still playing), and is held to the end of the line (blind critics, WP-10: late
                    # points read as an afterthought)
                    # A question keeps the quick point on the word: held through "have you seen ...?" it read as
                    # pointing at someone for no reason (a blind critic, WP-10)
                    asks = ln.get("text", "").strip().endswith("?")
                    t0 = max(ln["start"], words[i]["start"] - (0.25 if asks else 1.5), busy_until); pc = "point_R" if towards >= my_x else "point_L"
                    t1 = t0 + 0.9 if asks else max(t0 + 0.9, min(ln["end"] + 0.2, words[i]["start"] + 1.6))
                    if P["point"] == "point" and can(pc):
                        clips.append(style({"clip": pc, "start": round(t0, 3), "end": round(t1, 3), "weight": 3, "auto": True})); used.append(words[i]["start"]); busy_until = t1 + 0.1
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
            if accuses and humanoid:   # the accuser: sure of it, then folds the arms and waits for the admission
                poses.append([round(ln["start"] - 0.2, 3), "confident"])
                t0 = max(ln["end"] + 0.1, busy_until)   # after a point held to the line's end
                if can("cross_arms") and t0 < nxt["start"]:
                    clips.append(style({"clip": "cross_arms", "start": round(t0, 3), "end": round(nxt["end"] + 1.2, 3), "weight": 3, "auto": True, "why": "accuser waits"}))
                    busy_until = nxt["end"] + 1.2
            q_clip = P["question"] if humanoid else "tilt"
            if caught and humanoid and can("scratch_head"):   # the punchline's sheepish beat, after the words
                clips.append(style({"clip": "scratch_head", "start": round(ln["end"] + 0.15, 3), "end": round(ln["end"] + 2.0, 3), "weight": 3, "auto": True, "why": "punchline"}))
                busy_until = ln["end"] + 2.0
            if caught and humanoid:   # the tail after it (blind critics: "livelier tails"): a sheepish grin, a glance
                # away and back, then a small shrug, as if to say "well, you got me"
                emo.append([round(ln["end"] + 0.6, 3), "happy"])
                sx_ = next(iter(others_x.values()), my_x + 1)
                look.append([round(ln["end"] + 0.5, 3), [-1.0 if sx_ > my_x else 1.0, 0.35]]); look.append([round(ln["end"] + 1.3, 3), [1.0 if sx_ > my_x else -1.0, 0.1]])
                if can("shrug"):
                    clips.append(style({"clip": "shrug", "start": round(ln["end"] + 2.1, 3), "end": round(ln["end"] + 3.3, 3), "weight": 2.5, "auto": True, "why": "tail"}))
                blinks.append(round(ln["end"] + 2.0, 3))
            if ques and can(q_clip) and den != "feign":
                t0 = words[-1]["start"] - 0.1
                clips.append(style({"clip": q_clip, "start": round(t0, 3), **({"end": round(t0 + 0.9, 3)} if not humanoid else {}), "weight": 3, "auto": True}))
            look.append([round(ln["start"], 3), [0.0, 0.0]])
            e = emotion_of(text)   # held from just before the line until the speaker's next line says otherwise
            emo.append([round(ln["start"] - 0.2, 3), e or "neutral"])
            if humanoid and EMO_POSE.get(e):
                poses.append([round(ln["start"] - 0.2, 3), EMO_POSE[e]])
            elif humanoid and poses and not accuses:
                poses.append([round(ln["start"] - 0.2, 3), "neutral"])
        else:
            # listening: look towards the speaker, nod after the line, blink on its end
            sx = others_x.get(ln["speaker"])
            if sx is not None:   # a shy character's eyes drift down and off the speaker
                la = P["look_away"]
                look.append([round(ln["start"] - 0.15, 3), [round((1.0 if sx > my_x else -1.0) * (1 - la), 2), round(0.1 + 0.5 * la, 2)]])
            if caught and sx is not None:   # the punchline lands: hold a long look at the one caught out, no nod
                look.append([round(ln["end"] + 0.1, 3), [1.0 if sx > my_x else -1.0, 0.0]])
                blinks.append(round(ln["end"] + 1.6, 3))
                if humanoid:   # then the tail (blind critics: "livelier tails"): a slow head shake, and a smile breaks
                    emo.append([round(ln["end"] + 1.8, 3), "happy"])
                    if can("head_shake"):
                        clips.append({"clip": "head_shake", "start": round(ln["end"] + 1.7, 3), "end": round(ln["end"] + 2.9, 3), "weight": 2.0, "speed": 0.7, "auto": True, "why": "tail"})
                continue
            if accuses and nxt["speaker"] == me and sx is not None and humanoid:
                # caught out (blind critics: "a caught reaction before the admission"): it lands as the line ends: a start,
                # the face falls open, the eyes dart away and come back before owning up; no nod
                t_hit = round(max(ln["start"], ln["end"] - 0.25), 3)
                emo.append([t_hit, "surprised"])
                if can("surprised") and t_hit > busy_until - 0.1:
                    clips.append({"clip": "surprised", "start": t_hit, "end": round(min(nxt["start"] + 0.1, t_hit + 1.2), 3), "weight": 3, "auto": True, "why": "caught"})
                    busy_until = min(nxt["start"] + 0.1, t_hit + 1.2)
                gap_ = max(0.3, nxt["start"] - ln["end"])
                look.append([round(ln["end"] + 0.1, 3), [-1.0 if sx > my_x else 1.0, 0.3]])
                look.append([round(ln["end"] + 0.1 + min(0.5, gap_ * 0.6), 3), [1.0 if sx > my_x else -1.0, 0.05]])
                blinks.append(round(ln["end"] + 0.05, 3))
                emo.append([round(nxt["start"] - 0.15, 3), "worried"])
                continue
            e, t_felt = felt_at(ln)
            rc = LISTEN.get(e) if humanoid else None
            if rc in ("present",) and sx is not None:
                rc = "present_R" if sx > my_x else "present_L"
            if e:   # a listener feels with the speaker once the feeling word is heard (not before: that reads as knowing the
                # line), the face first, then a reaction answers the line's end
                emo.append([t_felt, e if e != "angry" else "worried"])
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

    def presets_of(pz):
        f = root / "puppet" / "clips" / f"{pz.get('template', 'humanoid')}.json"
        return set((json.loads(f.read_text()).get("presets") or {}) if f.exists() else {}) | set(pz.get("poses") or {})
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
            # a puppet may act with humanoid gestures on another template (acting.gestures; Open Peeps' busts with arms)
            clips, look, blinks, emo, poses = plan_cast((pz.get("acting") or {}).get("gestures") or pz.get("template", "humanoid"), in_shot, me, {k: v for k, v in xs.items() if k != me}, my_x, pro_of,
                                                        (pz.get("acting") or {}).get("energy", 1.0), prof, library(pz), presets_of(pz))
            tl["clips"] += clips
            # the same auto gesture twice within half a second (a listener's reaction and a beat) reads as a stutter: keep the first
            seen, kept = [], []
            for k in sorted(tl["clips"], key=lambda k: (k.get("start", 0) if isinstance(k.get("start"), (int, float)) else 0)):
                st = k.get("start") if isinstance(k.get("start"), (int, float)) else None
                if k.get("auto") and st is not None and any(n == k["clip"] and abs(st - t) < 0.5 for n, t in seen):
                    continue
                if k.get("auto") and st is not None:
                    seen.append((k["clip"], st))
                kept.append(k)
            tl["clips"] = kept
            if not tl.get("poses_manual"):   # body presets are no longer planned: clear any an earlier plan left behind
                tl.pop("poses", None)
                gest = (pz.get("acting") or {}).get("gestures") or pz.get("template", "humanoid")
                if poses and gest != "humanoid":   # except a doodle's held ta-da after an exclamation
                    tl["poses"] = [[0, "neutral"]] + sorted(poses, key=lambda k: k[0])
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
