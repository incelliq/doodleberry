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
