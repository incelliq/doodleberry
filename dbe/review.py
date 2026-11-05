"""Review room (plan 3.4): notes pinned to frames become data edits, and a critic measures the result before a
note is closed.

A note is plain English about what is on screen at its frame: "raise the arm earlier", "Ravi's nod should be
bigger", "make the wave a bit slower", "hold the shrug longer", "lose the point", "Momo should look at Ravi".
`interpret` reads it into an intent (verb, amount, body part, character); `locate` finds the clip layer that makes
that motion at that frame (the named character, the part's tracks, the clip active at or just before the frame);
`plan_edit` turns it into a timeline edit; `verify` compares the measured motion of the part before and after
(probe of the player, same window): an earlier move must start sooner by most of the asked amount, a bigger one must
travel further, and so on. QA must not get worse. Only then is the note closed as verified.
"""
import re

PARTS = {  # words in a note -> the part to watch, and the tracks that move it
    "arm": ("hand", ["upperarm", "forearm"]), "hand": ("hand", ["upperarm", "forearm"]), "point": ("hand", ["upperarm", "forearm"]),
    "wave": ("hand", ["upperarm", "forearm"]), "elbow": ("hand", ["forearm"]), "head": ("head", ["head"]), "nod": ("head", ["head"]),
    "leg": ("foot", ["thigh", "shin"]), "foot": ("foot", ["thigh", "shin"]), "kick": ("foot", ["thigh", "shin"]), "jump": ("hip", ["thigh", "shin"]),
    "body": ("head", ["torso"]), "shrug": ("hand", ["upperarm", "forearm"]), "lean": ("head", ["torso"]),
}
VERBS = [  # (pattern, verb)
    (r"\b(earlier|sooner|start(s)? earlier|too late|late)\b", "earlier"), (r"\b(later|start(s)? later|too early|early)\b", "later"),
    (r"\b(faster|quicker|snappier|too slow)\b", "faster"), (r"\b(slower|too fast|ease)\b", "slower"),
    (r"\b(bigger|higher|more|stronger|larger|too small|too subtle)\b", "bigger"), (r"\b(smaller|lower|less|subtler|softer|too big|too much)\b", "smaller"),
    (r"\b(hold|longer|linger|keep)\b", "longer"), (r"\b(shorter|cut it short|quicker out)\b", "shorter"),
    (r"\b(lose|remove|drop|delete|cut|no need for|get rid of)\b", "remove"),
]


def interpret(text, cast_names):
    t = text.lower()
    verb = next((v for p, v in VERBS if re.search(p, t)), None)
    m = re.search(r"by\s+([\d.]+)\s*(frames?|f\b|s\b|sec|seconds?)", t)
    amount = None
    if m:
        amount = float(m.group(1)) / (30.0 if m.group(2).startswith("f") else 1.0)
    elif re.search(r"\b(a (little|bit)|slightly|a touch)\b", t):
        amount = 0.2
    elif re.search(r"\b(much|a lot|way)\b", t):
        amount = 0.6
    part = next((w for w in PARTS if re.search(rf"\b{w}s?\b", t)), None)
    who = next((n for n in cast_names if re.search(rf"\b{re.escape(n.lower())}\b", t)), None)
    side = "R" if re.search(r"\bright\b", t) else "L" if re.search(r"\bleft\b", t) else None
    clip = None
    for w in ("wave", "point", "nod", "shrug", "jump", "clap", "celebrate", "facepalm", "think", "stomp", "scratch", "present"):
        if re.search(rf"\b{w}", t):
            clip = w
    return {"verb": verb, "amount": amount, "part": part, "who": who, "side": side, "clip_word": clip}


def locate(intent, shot, t, libs):
    """-> (cast index, clip layer index, watch part, why) or None. shot: resolved shot from timeline.get"""
    tracks_of = lambda k, lib: set(((lib.get(k["clip"]) or {}).get("tracks") or {}).keys())
    want = PARTS.get(intent["part"] or "", (None, []))
    cands = []
    for c in shot["cast"]:
        if intent["who"] and c["who"].lower() != intent["who"].lower():
            continue
        lib = libs[c["i"]]
        for k in c["clips"]:
            if k["clip"] == "idle" or (k["loop"] and k["end"] >= shot["end"] - 0.01 and k["clip"] in ("walk", "run")):
                continue
            tr = tracks_of(k, lib)
            if want[1] and not any(any(x.startswith(p) for p in want[1]) for x in tr):
                continue
            if intent["clip_word"] and intent["clip_word"] not in k["clip"]:
                continue
            if intent["side"] and not any(x.endswith("_" + intent["side"]) for x in tr) and want[0] in ("hand", "foot"):
                continue
            # active at the frame, or the move the note is about: starting a little after (earlier) or before it
            near = 0 if k["start"] <= t <= k["end"] else min(abs(k["start"] - t), abs(k["end"] - t))
            if near > 1.5:
                continue
            score = near + (0 if not k["auto"] else 0.05) + (0.2 if k["additive"] else 0)
            cands.append((score, c, k, tr))
    if not cands:
        return None
    _, c, k, tr = min(cands, key=lambda x: x[0])
    # watch what the clip moves most (the note's body word only picked the clip: "scratch the head" moves the hand)
    clip = libs[c["i"]].get(k["clip"]) or {}
    rng = {n: (max(v for _, v in keys) - min(v for _, v in keys)) for n, keys in (clip.get("tracks") or {}).items() if keys and isinstance(keys[0][1], (int, float))}
    if intent["side"]:
        rng = {n: r for n, r in rng.items() if not n.endswith(("_L", "_R")) or n.endswith("_" + intent["side"])} or rng
    big = max(rng, key=rng.get) if rng else "head"
    end = lambda n: ("hand_" + n[-1]) if n.startswith(("upperarm_", "forearm_", "hand_")) else ("foot_" + n[-1]) if n.startswith(("thigh_", "shin_", "foot_")) else "head"
    watch = end(big)
    return c["i"], k["i"], watch, f"{c['who']}'s {k['clip']} ({k['start']:.2f}-{k['end']:.2f} s)"


def returns_to_rest(clip):
    """a clip whose every track ends where it started at 0 (a gesture that comes back) holds nothing at its end"""
    tr = (clip or {}).get("tracks") or {}
    return bool(tr) and all(abs(keys[-1][1]) < 2 for keys in tr.values() if keys)


def plan_edit(intent, k, clip_len, clip=None):
    v, a = intent["verb"], intent["amount"]
    if v in ("longer", "shorter") and returns_to_rest(clip):   # stretch the gesture itself; its end is the rest pose
        f = (clip_len + (a or 0.6)) / clip_len if v == "longer" else 0.7
        return {"op": "set_clip", "props": {"speed": round((k.get("speed") or 1) / f, 3)}}, a or 0.6
    if v == "earlier":
        return {"op": "move_clip", "start": max(0.0, k["start"] - (a or 0.33))}, a or 0.33
    if v == "later":
        return {"op": "move_clip", "start": k["start"] + (a or 0.33)}, a or 0.33
    if v == "faster":
        return {"op": "set_clip", "props": {"speed": round((k.get("speed") or 1) * 1.4, 3)}}, 1.4
    if v == "slower":
        return {"op": "set_clip", "props": {"speed": round((k.get("speed") or 1) * 0.7, 3)}}, 0.7
    if v == "bigger":
        return {"op": "set_clip", "props": {"gain": round((k.get("gain") or 1) * 1.35, 3)}}, 1.35
    if v == "smaller":
        return {"op": "set_clip", "props": {"gain": round((k.get("gain") or 1) * 0.65, 3)}}, 0.65
    if v == "longer":
        return {"op": "resize_clip", "end": k["end"] + (a or 0.6)}, a or 0.6
    if v == "shorter":
        return {"op": "resize_clip", "end": max(k["start"] + 0.2, k["start"] + clip_len * 0.65)}, 0.65
    if v == "remove":
        return {"op": "delete_clip"}, None
    return None, None


def _disp(track, base):
    """per sample: distance of the part from where it was at the start of the window"""
    return [((x - base[0]) ** 2 + (y - base[1]) ** 2) ** 0.5 if x is not None else 0.0 for _, x, y in track]


def measure(track):
    if not track or track[0][1] is None:
        return None
    base = (track[0][1], track[0][2]); d = _disp(track, base); ts = [s[0] for s in track]; peak = max(d)
    if peak < 3:
        return {"peak_px": round(peak, 1), "rise_t": None, "rise_s": None, "held_s": 0.0}
    t50 = next(t for t, v in zip(ts, d) if v >= 0.5 * peak); t10 = next(t for t, v in zip(ts, d) if v >= 0.1 * peak); t90 = next(t for t, v in zip(ts, d) if v >= 0.9 * peak)
    held = sum(1 for v in d if v >= 0.5 * peak) * (ts[1] - ts[0] if len(ts) > 1 else 0)
    return {"peak_px": round(peak, 1), "rise_t": t50, "rise_s": round(t90 - t10, 3), "held_s": round(held, 3)}


def verify(intent, amount, before, after):
    """the critic: did the motion change the way the note asked?"""
    b, a = measure(before), measure(after); v = intent["verb"]
    if v == "remove":
        ok = a is None or a["peak_px"] < 0.25 * (b["peak_px"] if b else 1)
        return ok, f"movement {b and b['peak_px']} px -> {a and a['peak_px']} px", b, a
    if not b or not a or b["rise_t"] is None or a["rise_t"] is None:
        return False, "the part did not move enough to measure", b, a
    if v in ("earlier", "later"):
        shift = b["rise_t"] - a["rise_t"]; want = amount if v == "earlier" else -amount
        ok = shift * (1 if v == "earlier" else -1) >= 0.6 * amount
        return ok, f"the move now reaches half-way at {a['rise_t']:.2f} s (was {b['rise_t']:.2f} s): {abs(shift):.2f} s {'earlier' if shift > 0 else 'later'}, asked {amount:.2f} s", b, a
    if v in ("faster", "slower"):
        ok = (a["rise_s"] < b["rise_s"] * 0.9) if v == "faster" else (a["rise_s"] > b["rise_s"] * 1.1)
        return ok, f"rise takes {a['rise_s']:.2f} s (was {b['rise_s']:.2f} s)", b, a
    if v in ("bigger", "smaller"):
        ok = (a["peak_px"] > b["peak_px"] * 1.1) if v == "bigger" else (a["peak_px"] < b["peak_px"] * 0.9)
        return ok, f"the part travels {a['peak_px']} px (was {b['peak_px']} px)", b, a
    if v in ("longer", "shorter"):
        ok = (a["held_s"] > b["held_s"] + 0.15) if v == "longer" else (a["held_s"] < b["held_s"] - 0.1)
        return ok, f"held {a['held_s']:.2f} s (was {b['held_s']:.2f} s)", b, a
    return False, "no check for this kind of note", b, a


# ---------- gaze notes (WP-19): "Ravi should look at Momo when she answers" ----------
GAZE = re.compile(r"\b(look(s|ing)?|glance(s)?|face(s)?|turn(s)? to|watch(es)?|eye contact)\b", re.I)
WHEN = [  # how a note says when: the target's next line, a line by id, or "while X talks"
    (re.compile(r"\bwhen (s?he|they|\w+) (answers|replies|responds|speaks|talks|says|asks)\b", re.I), "next_line_of_target"),
    (re.compile(r"\b(while|as) (s?he|they|\w+) (talks|speaks|answers|is talking)\b", re.I), "next_line_of_target"),
    (re.compile(r"\b(during|on|in) (line )?(l\d+)\b", re.I), "line_id"),
]


def gaze_intent(text, cast_names):
    """-> {who, target, when, line} or None. The first name is who looks, the second whom at ("at Momo")"""
    t = text.lower()
    if not GAZE.search(t):
        return None
    m = re.search(r"\b(?:at|to|towards?)\s+(\w+)", t)
    target = next((n for n in cast_names if m and m.group(1) == n.lower()), None)
    who = next((n for n in cast_names if re.search(rf"\b{re.escape(n.lower())}\b", t) and n != target), None)
    if not who or not target:
        return None
    when, line = "at_note", None
    for pat, kind in WHEN:
        mm = pat.search(t)
        if mm:
            when = kind; line = mm.group(3) if kind == "line_id" else None
            break
    away = bool(re.search(r"\b(away from|not look|stop looking|look away)\b", t))
    return {"kind": "gaze", "who": who, "target": target, "when": when, "line": line, "away": away}


def gaze_window(intent, lines, t, speaker_of):
    """the line the note is about: by id, or the target's line at or next after the note's frame -> (line, why)"""
    if intent["when"] == "line_id":
        ln = next((l for l in lines if l["id"] == intent["line"]), None)
        return (ln, f"during {intent['line']}") if ln else (None, f"no line {intent['line']}")
    tgt = [l for l in lines if (speaker_of(l) or "").lower() == intent["target"].lower()]
    ln = next((l for l in tgt if l["start"] <= t <= l["end"]), None) or next((l for l in tgt if l["start"] >= t - 0.25), None)
    if ln:
        return ln, f"while {intent['target']} says {ln['id']} ({ln['start']:.2f}-{ln['end']:.2f} s)"
    return None, f"{intent['target']} has no line at or after {t:.2f} s"


def gaze_edit(look_keys, line_id, direction, value_after, lead=0.2, tail=0.3):
    """look keys with the line's span set to look `direction` ([x, y], screen terms): keys inside the span are
    replaced; keys are line-relative so they follow re-voicing. value_after: the look the curve had just after."""
    span0, span1 = (f"{line_id}.start-{lead}" if lead else f"{line_id}.start"), f"{line_id}.end+{tail}"
    return span0, span1, [[span0, direction], [f"{line_id}.end", direction], [span1, value_after]]


def gaze_share(track, direction, t0, t1):
    """share of frames in [t0, t1] whose look points the asked way (x within 45 degrees of it)"""
    rows = [r for r in track if t0 <= r[0] <= t1 and r[1] is not None]
    if not rows:
        return 0.0
    ok = sum(1 for _, x, y, *_ in rows if (x * direction[0] > 0.5 if direction[0] else abs(x) < 0.3))
    return round(ok / len(rows), 3)


# ---------- placement and camera notes (WP-19): "Ravi should stand further left", "push in", "go wider" ----------
def layout_intent(text, cast_names):
    """-> {"kind": "placement", who, dir (+1 right, -1 left), px, toward} or {"kind": "camera", step (+1 closer,
    -1 wider)} or None. Screen directions: left and right as the viewer sees them."""
    t = text.lower()
    at = {n: m.start() for n in cast_names for m in [re.search(rf"\b{re.escape(n.lower())}\b", t)] if m}
    who = min(at, key=at.get) if at else None   # the character named first is the one to move
    px = 120.0
    m = re.search(r"by\s+(\d+)\s*(px|pixels?)", t)
    if m:
        px = float(m.group(1))
    elif re.search(r"\b(a (little|bit)|slightly|a touch)\b", t):
        px = 60.0
    elif re.search(r"\b(much|a lot|way)\b", t):
        px = 240.0
    if who and re.search(r"\b(stand|move|step|put|place|sit|be|is|further|farther|more|too far)\b", t):
        other = next((n for n in cast_names if n != who and re.search(rf"\b{re.escape(n.lower())}\b", t)), None)
        if other and re.search(r"\b(closer to|nearer|next to|towards?)\b", t):
            return {"kind": "placement", "who": who, "toward": other, "dir": None, "px": px}
        if other and re.search(r"\b(further from|farther from|away from|apart)\b", t):
            return {"kind": "placement", "who": who, "toward": other, "dir": None, "px": -px}
        if re.search(r"\btoo far (to the )?left\b", t) or re.search(r"\b(further|farther|more|move|step|stand|put|place)\b.*\bright\b", t) and not re.search(r"\btoo far (to the )?right\b", t):
            return {"kind": "placement", "who": who, "toward": None, "dir": 1, "px": px}
        if re.search(r"\btoo far (to the )?right\b", t) or re.search(r"\b(further|farther|more|move|step|stand|put|place)\b.*\bleft\b", t):
            return {"kind": "placement", "who": who, "toward": None, "dir": -1, "px": px}
    if re.search(r"\b(push in|move in|go in|zoom in|tighter|too wide|closer on|get closer|closer shot)\b", t):
        return {"kind": "camera", "step": 1}
    if re.search(r"\b(pull back|pull out|go wider|wider|zoom out|too tight|too close|wide shot)\b", t):
        return {"kind": "camera", "step": -1}
    return None


# ---------- WP-19: notes about the timing of lines ----------
LINE_WORDS = re.compile(r"\b(line|pause|beat|gap|silence|breath|answer|reply|cue|dialogue|rushed|rush)\b")
MOTION_WORDS = re.compile(r"\b(arm|hand|head|leg|foot|body|wave|point|nod|shrug|gesture|jump|hop|walk|turn|look|glance|blink|camera|shot|cut)\w*\b")
ORDINAL = {"first": 0, "second": 1, "third": 2, "fourth": 3, "fifth": 4, "last": -1}


def timing_intent(text):
    """-> {"kind": "line_timing", "dir": +1 later | -1 earlier, "s": seconds, "which": None | index | line id} or None.
    'give the last line a beat before it', 'the answer comes in too late', 'pause longer before "mid"', 'less of a gap
    before the second line by 0.3 s', 'it feels rushed'"""
    t = text.lower()
    if not LINE_WORDS.search(t) or MOTION_WORDS.search(t):
        return None
    later = re.search(r"\b(later|too (soon|early|quick|fast)|rushed|rush|longer pause|pause longer|longer before|more time before|more (of a )?(pause|beat|gap|silence)|a beat (before|after)|give .* (a )?(beat|pause|breath)|wait (a|longer)|hold (a beat|on))\b", t)
    earlier = re.search(r"\b(pause|gap|silence|wait)\b.*\btoo long\b", t) or re.search(r"\b(earlier|sooner|too late|too slow|shorter pause|less (of a )?(pause|beat|gap|silence)|(pause|gap|silence|wait) is too long|tighten|pick up the cue|drags?)\b", t)
    if bool(later) == bool(earlier):
        return None
    s = 0.4
    m = re.search(r"by\s+(\d+(?:\.\d+)?)\s*(s|sec|seconds?|ms|frames?)\b", t)
    if m:
        v = float(m.group(1)); s = v / 1000 if m.group(2) == "ms" else v / 30 if m.group(2).startswith("frame") else v
    elif re.search(r"\b(a beat|a breath)\b", t):
        s = 0.5
    elif re.search(r"\b(a (little|bit|touch)|slightly)\b", t):
        s = 0.25
    elif re.search(r"\b(much|a lot|way|long pause)\b", t):
        s = 0.8
    which = None
    m = re.search(r"\b(first|second|third|fourth|fifth|last)\s+line\b", t)
    if m:
        which = ORDINAL[m.group(1)]
    m = re.search(r"[\"“']([\w-]+)[\"”']", text)
    if m:
        which = m.group(1)
    return {"kind": "line_timing", "dir": 1 if later else -1, "s": round(s, 3), "which": which}


def timing_line(intent, lines, t):
    """the line a timing note means: named (an id or first/second/last), else the one under the note's frame, else the
    next one after it -> (line, why)"""
    w = intent["which"]
    if isinstance(w, str):
        ln = next((l for l in lines if l["id"] == w), None)
        return (ln, f"line {w}") if ln else (None, f"no line {w}")
    if isinstance(w, int):
        return (lines[w], f"line {lines[w]['id']}") if -len(lines) <= w < len(lines) else (None, f"no line {w + 1}")
    ln = next((l for l in lines if l["start"] - 0.3 <= t <= l["end"]), None) or next((l for l in lines if l["start"] >= t), None)
    return (ln, f"line {ln['id']} at the note") if ln else (None, f"no line at or after {t:.2f} s")


def onset_after(wav, t0, t1, sr_hint=None):
    """when speech starts in a voice track between t0 and t1 (seconds): the first 10 ms frame above -40 dBFS"""
    import numpy as np
    import soundfile as sf
    info = sf.info(str(wav)); sr = info.samplerate
    a, _ = sf.read(str(wav), start=max(0, int(t0 * sr)), stop=int(t1 * sr), always_2d=True)
    a = a.mean(1); hop = int(0.01 * sr)
    for i in range(0, len(a) - hop, hop):
        if 20 * np.log10(np.sqrt((a[i:i + hop] ** 2).mean()) + 1e-12) > -40:
            return round(t0 + i / sr, 3)
    return None
