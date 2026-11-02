"""Acting from prose (plan 2.4), comedy timing and gags (plan 2.11), rig abilities and rig-aware writing (plan 2.12).

A direction is plain English, one action per sentence, e.g.
    "Momo is nervous and glances at Ravi."
    "When Ravi says 'telescope', Momo does a double take."
    "After her line Priya shrugs, then nods slowly."
    "Ravi walks to Momo and points at the sky."
Directions live on script lines ("direction": "...", anchored to that line) or on shots ("direction": "..."), or are
passed to `acting.direct`. Each sentence is parsed into: who (a speaker in the shot; he/she/they = the last one named),
when (a word of a line, the start/end/span of a line, the start/end of the shot, or right after the previous action:
"then"), what (a verb from the lexicon, an emotion, a gaze or a gag), at whom/where (another character, the camera, up,
down, left, right), and how (slowly, quickly, a little, hugely). The result is timeline edits in shots.json, tagged
"directed" so re-directing replaces them; times anchored to lines are written line-relative so re-voicing keeps sync.

Gags (2.11) are beat patterns built from the same parts, with the timing comedy needs (holds before the snap, blinks
on the beat, the third time different): double take, long stare, slow burn, deadpan, button, rule of three.

Abilities (2.12): every action declares what it needs from a rig (parts for a clip, swap shapes, pupils, brows, a
turn control). `abilities(puppet, lib)` lists what a character does for free and what would cost a drawing;
`rig_check` reads a film's directions and lists exactly the drawings missing for each character.
"""
import json
import re

# ---------- lexicon ----------
EMOTIONS = {"happy": "happy", "glad": "happy", "delighted": "happy", "pleased": "happy", "cheerful": "happy", "excited": "happy", "proud": "happy",
            "sad": "sad", "upset": "sad", "gloomy": "sad", "disappointed": "sad", "glum": "sad",
            "angry": "angry", "furious": "angry", "cross": "angry", "annoyed": "angry", "grumpy": "angry",
            "surprised": "surprised", "shocked": "surprised", "amazed": "surprised", "astonished": "surprised",
            "nervous": "worried", "worried": "worried", "anxious": "worried", "scared": "worried", "unsure": "worried",
            "calm": "neutral", "neutral": "neutral", "serious": "neutral"}
# verb pattern -> (clip, seconds, needs) ; side-aware clips use {side}
VERBS = [
    (r"\bnods?\b", ("nod", 0.8, {"additive": True})),
    (r"\bshrugs?\b", ("shrug", 1.3, {})),
    (r"\bclaps?\b", ("clap", 1.5, {})),
    (r"\b(jumps?|hops?|leaps?)\b", ("jump", 1.1, {})),
    (r"\b(celebrates?|cheers?)\b|jumps for joy", ("celebrate", 1.6, {})),
    (r"\bfacepalms?\b|puts? (his|her|their) (face|head) in (his|her|their) hands?", ("facepalm", 1.4, {})),
    (r"\bcross(es)? (his|her|their) arms\b|\bfolds? (his|her|their) arms\b", ("cross_arms", 2.0, {"hold": True})),
    (r"\b(thinks?|ponders?|wonders?)\b", ("think", 1.6, {"hold": True})),
    (r"\bscratch(es)? (his|her|their) head\b", ("scratch_head", 1.4, {})),
    (r"\bstomps?\b", ("stomp", 0.9, {})),
    (r"\b(slumps?|sighs?|droops?)\b", ("sad", 1.2, {"hold": True})),
    (r"\b(waves?)\b", ("wave_{side}", 1.4, {})),
    (r"\bpoints?\b", ("point_{side}", 1.0, {})),
    (r"\b(presents?|shows?|gestures? to)\b", ("present_{side}", 1.0, {})),
    (r"\bruns?\b", ("run", 1.2, {})),
    (r"\b(shakes? (his|her|their) head)\b", ("head_shake", 0.9, {"additive": True})),
]
GAGS = {
    "double take": r"\bdoubles? takes?\b|\bdoes a double take\b",
    "long stare": r"\b(long stare|stares?)\b",
    "slow burn": r"\bslow burn\b|\bslowly gets angry\b",
    "deadpan": r"\bdeadpan\b|\blooks at (the )?camera\b",
    "button": r"\bbutton\b",
}
MANNER = [(r"\bslowly\b", {"speed": 0.7}), (r"\b(quickly|suddenly|fast)\b", {"speed": 1.4}),
          (r"\b(a little|slightly|small|barely)\b", {"gain": 0.6}), (r"\b(hugely|wildly|big|enormously)\b", {"gain": 1.3})]
SPOTS = {"camera": [0.0, 0.0], "us": [0.0, 0.0], "viewer": [0.0, 0.0], "audience": [0.0, 0.0], "sky": [0.0, -1.0], "moon": [0.2, -1.0], "stars": [0.0, -1.0],
         "up": [0.0, -1.0], "ceiling": [0.0, -1.0], "floor": [0.0, 1.0], "ground": [0.0, 1.0], "down": [0.0, 1.0], "feet": [0.0, 1.0],
         "left": [-1.0, 0.0], "right": [1.0, 0.0], "board": [0.0, -0.6], "window": [0.8, -0.5], "door": [1.0, 0.0]}

# what each action needs from a rig (2.12)
NEEDS_EMOTION = {"happy": [("mouth", "smile"), ("brows", "raised")], "sad": [("mouth", "frown"), ("brows", "worried")],
                 "angry": [("mouth", "frown"), ("brows", "angry")], "surprised": [("mouth", "O"), ("brows", "raised")],
                 "worried": [("mouth", "small"), ("brows", "worried")], "neutral": []}


def _look_vec(target, me_x, others):
    if target in others:
        return [1.0 if others[target] > me_x else -1.0, 0.05]
    if target in SPOTS:
        return SPOTS[target]
    return None


class Ctx:
    def __init__(self, shot, lines, line_id=None):
        self.shot = shot; self.lines = lines; self.line_id = line_id
        self.cast = {(c.get("speaker") or "").lower(): i for i, c in enumerate(shot.get("cast") or []) if c.get("speaker")}
        self.xs = {}
        for c in shot.get("cast") or []:
            pl = c.get("place")
            if c.get("speaker"):
                self.xs[c["speaker"].lower()] = (pl[0][1] if isinstance(pl, list) else pl or {}).get("x", 540)
        self.subject = None; self.cursor = None; self.cursors = {}   # "then" / "next" follow the same character


def _time(ctx, s):
    """-> (time in seconds, anchor string for shots.json, explanation)"""
    m = re.search(r"\bwhen (\w+) says ['\"“‘]?([\w']+)", s, re.I)
    if m:
        spk, word = m.group(1).lower(), m.group(2).lower()
        for ln in ctx.lines:
            if ln.get("speaker", "").lower() == spk and ctx.shot["start"] - 0.01 <= ln["start"] < ctx.shot["end"]:
                for w in ln.get("words") or []:
                    if re.sub(r"\W", "", w["text"].lower()) == re.sub(r"\W", "", word):
                        off = round(w["start"] - ln["start"], 3)
                        return w["start"], f"{ln['id']}.start+{off}", f"on '{w['text']}'"
    m = re.search(r"\b(after|during|while|before) (?:(\w+)'s|(his|her|their)|the) line\b|\bwhile (\w+) (?:speaks|talks)\b", s, re.I)
    if m:
        kind = (m.group(1) or "during").lower(); who = (m.group(2) or m.group(4) or "").lower()
        cand = [l for l in ctx.lines if ctx.shot["start"] - 0.01 <= l["start"] < ctx.shot["end"] and (not who or l.get("speaker", "").lower() == who)]
        if ctx.line_id:
            cand = [l for l in cand if l["id"] == ctx.line_id] or cand
        if cand:
            ln = cand[0]
            if kind == "after":
                return ln["end"] + 0.15, f"{ln['id']}.end+0.15", "after the line"
            if kind == "before":
                return max(ctx.shot["start"], ln["start"] - 0.6), f"{ln['id']}.start-0.6", "before the line"
            return ln["start"] + 0.1, f"{ln['id']}.start+0.1", "during the line"
    if re.search(r"\bat the (very )?start\b|\bat first\b|\bto begin\b", s, re.I):
        return ctx.shot["start"] + 0.2, None, "at the start"
    if re.search(r"\bat the end\b|\bfinally\b", s, re.I):
        return ctx.shot["end"] - 1.2, None, "at the end"
    mine = ctx.cursors.get(ctx.subject)
    if re.match(r"\s*then\b", s, re.I) and (mine if mine is not None else ctx.cursor) is not None:
        return (mine if mine is not None else ctx.cursor), None, "then"
    if ctx.line_id:
        ln = next((l for l in ctx.lines if l["id"] == ctx.line_id), None)
        if ln:
            if mine is not None and mine > ln["start"]:
                return mine, None, "next"
            return ln["start"], f"{ln['id']}.start", "with the line"
    return (mine if mine is not None else ctx.shot["start"] + 0.3), None, "next"


def parse(ctx, sentence):
    """one sentence -> list of actions {who, t, anchor, kind, ...}"""
    s = sentence.strip()
    if not s:
        return []
    names = [n for n in ctx.cast if re.search(rf"\b{re.escape(n)}\b", s, re.I)]
    who = None
    for n in sorted(names, key=lambda n: re.search(rf"\b{re.escape(n)}\b", s, re.I).start()):
        # the subject is the first name not inside a "when X says" clause
        if not re.search(rf"\bwhen {re.escape(n)} says\b|\bafter {re.escape(n)}'s\b|\bwhile {re.escape(n)}\b", s, re.I):
            who = n; break
    if who is None and re.search(r"\b(he|she|they|him|her)\b", s, re.I):
        who = ctx.subject
    if who is None:
        who = ctx.subject or (names[0] if names else (next(iter(ctx.cast)) if len(ctx.cast) == 1 else None))
    if who is None:
        return [{"error": f"no character named in: {s}"}]
    ctx.subject = who
    t, anchor, why = _time(ctx, s)
    manner = {}
    for pat, m in MANNER:
        if re.search(pat, s, re.I):
            manner.update(m)
    target = None
    m = re.search(r"\b(?:at|to|towards?|toward)\s+(?:the\s+)?(\w+)", s, re.I)
    if m:
        target = m.group(1).lower()
    if target == who:
        target = None
    if target is None:
        others = [n for n in names if n != who]
        target = others[0] if others else None
    if target in (None, "end", "start", "line") or (target not in ctx.cast and target not in SPOTS):
        rest = [n for n in ctx.cast if n != who]
        target = rest[0] if len(rest) == 1 else None   # two-handers: gaze goes to the other character
    out = []
    base = {"who": who, "t": round(t, 3), "anchor": anchor, "when": why, **({"manner": manner} if manner else {})}
    for gag, pat in GAGS.items():
        if re.search(pat, s, re.I):
            out.append({**base, "kind": "gag", "gag": gag, "target": target})
            return out
    for word, emo in EMOTIONS.items():
        if re.search(rf"\b(is|looks|gets|becomes|feels|seems|grows|turns)?\s*(very |so |a bit |quite )?{word}\b", s, re.I) and re.search(rf"\b{word}\b", s, re.I):
            out.append({**base, "kind": "emotion", "emotion": emo})
            break
    if re.search(r"\bglances?\b", s, re.I):
        out.append({**base, "kind": "look", "target": target or "camera", "hold": 0.7})
    elif re.search(r"\b(looks?|turns?|faces?|watches?)\b\s+(at|to|towards?|toward|up|down|left|right)\b", s, re.I):
        tg = target or next((w for w in ("up", "down", "left", "right") if re.search(rf"\b{w}\b", s, re.I)), "camera")
        out.append({**base, "kind": "look", "target": tg, "hold": 2.5})
    if re.search(r"\b(walks?|steps?|moves?|goes|comes?)\b\s+(over\s+)?(to|towards?|toward)\b", s, re.I) and target in ctx.cast:
        out.append({**base, "kind": "walk", "target": target})
    for pat, (clip, dur, opts) in VERBS:
        if re.search(pat, s, re.I):
            out.append({**base, "kind": "clip", "clip": clip, "dur": dur, "target": target, **opts})
    if len(re.findall(r"\b(nods?|claps?|jumps?|waves?|shrugs?)\b", s, re.I)) >= 3 or re.search(r"\b(three times|rule of three)\b", s, re.I):
        out.append({**base, "kind": "gag", "gag": "rule of three", "target": target, "clip": next((a["clip"] for a in out if a["kind"] == "clip"), "nod")})
        out = [a for a in out if a["kind"] != "clip"]
    if not out:
        out.append({**base, "kind": "unknown", "text": s})
    return out


# ---------- compile actions into timeline edits ----------
def _side(ctx, who, target):
    v = _look_vec(target, ctx.xs.get(who, 540), {k: v for k, v in ctx.xs.items() if k != who}) if target else None
    return "R" if (v is None or v[0] >= 0) else "L"


def compile_actions(ctx, actions, tag):
    """-> {cast_index: timeline edits} and the cursor after the last action"""
    edits = {}
    def tl(who):
        return edits.setdefault(ctx.cast[who], {"clips": [], "look": [], "blinks": [], "emotion": [], "place": []})
    def at(a, dt=0.0):
        if a.get("anchor") and dt == 0:
            return a["anchor"]
        if a.get("anchor"):
            m = re.match(r"^(.*?)([+-][0-9.]+)?$", a["anchor"]); base, off = m.group(1), float(m.group(2) or 0) + dt
            return f"{base}{'+' if off >= 0 else '-'}{abs(round(off, 3))}"
        return round(a["t"] + dt, 3)
    end = None
    for a in actions:
        if a["kind"] in ("error", "unknown") or a.get("error"):
            continue
        who = a["who"]; T = tl(who); man = a.get("manner") or {}; sp = man.get("speed", 1.0); gain = man.get("gain", 1.0)
        me_x = ctx.xs.get(who, 540); others = {k: v for k, v in ctx.xs.items() if k != who}
        vec = _look_vec(a.get("target"), me_x, others) if a.get("target") else None
        if a["kind"] == "emotion":
            T["emotion"].append([at(a), a["emotion"]]); end = a["t"]
        elif a["kind"] == "look":
            v = vec or [0.0, 0.0]; T["look"] += [[at(a), v], [at(a, a["hold"] / sp), [0.0, 0.0]]]; end = a["t"] + a["hold"] / sp
        elif a["kind"] == "walk":
            tx = others[a["target"]] + (-200 if others[a["target"]] > me_x else 200); dur = max(0.8, abs(tx - me_x) / 260) / sp
            T["place"].append({"from": me_x, "to": round(tx, 1), "t0": at(a), "t1": at(a, dur), "t": a["t"], "dur": dur})
            T["clips"].append({"clip": "walk", "start": at(a), "end": at(a, dur), "speed": sp, "weight": 3}); end = a["t"] + dur
        elif a["kind"] == "clip":
            clip = a["clip"].replace("{side}", _side(ctx, who, a.get("target")))
            dur = a["dur"] / sp; k = {"clip": clip, "start": at(a), "speed": round(sp, 2)}
            if a.get("additive"):
                k.update({"additive": True, "weight": round(0.9 * gain, 2)})
            else:
                k.update({"weight": round(3 * gain, 2)})
            if a.get("hold"):
                k["end"] = at(a, max(dur, 2.0)); dur = max(dur, 2.0)
            T["clips"].append(k)
            if vec:
                T["look"] += [[at(a), vec], [at(a, dur), [0.0, 0.0]]]
            end = a["t"] + dur
        elif a["kind"] == "gag":
            end = a["t"] + gag(a, T, at, vec, sp, ctx)
    for T in edits.values():
        for k in list(T):
            if not T[k]:
                del T[k]
    return edits, end


def gag(a, T, at, vec, sp, ctx):
    """beat patterns (2.11): returns the gag's length in seconds"""
    g = a["gag"]; v = vec or [0.0, 0.0]; away = [-v[0] or 0.6, 0.15]
    if g == "double take":
        # look, look away as if nothing happened, a beat, then snap back with a surprised jolt and a blink
        T["look"] += [[at(a), v], [at(a, 0.45), away], [at(a, 1.05), v], [at(a, 2.3), [0.0, 0.0]]]
        T["clips"].append({"clip": "surprised", "start": at(a, 1.0), "weight": 3, "fadeIn": 0.05})
        T["blinks"].append(round(a["t"] + 1.0, 3)); T["emotion"].append([at(a, 1.0), "surprised"])
        return 2.3
    if g == "long stare":
        # a held look with blinks on a slow count; the hold is the joke, so it lasts
        T["look"] += [[at(a), v], [at(a, 2.6), [0.0, 0.0]]]
        T["blinks"] += [round(a["t"] + 0.9, 3), round(a["t"] + 1.9, 3)]; T["emotion"].append([at(a), "neutral"])
        T["clips"].append({"clip": "idle", "start": at(a), "end": at(a, 2.6), "weight": 3, "gain": 0.3, "base": True})
        return 2.6
    if g == "slow burn":
        T["look"] += [[at(a), [0.0, 0.0]]]; T["emotion"] += [[at(a), "neutral"], [at(a, 1.4), "angry"]]
        T["blinks"].append(round(a["t"] + 0.8, 3)); T["clips"].append({"clip": "cross_arms", "start": at(a, 1.4), "end": at(a, 3.0), "weight": 3})
        return 3.0
    if g == "deadpan":
        T["look"] += [[at(a), [0.0, 0.0]], [at(a, 1.6), [0.0, 0.0]]]; T["emotion"].append([at(a), "neutral"])
        T["blinks"].append(round(a["t"] + 0.7, 3))
        return 1.6
    if g == "button":
        T["clips"].append({"clip": "nod", "start": at(a), "additive": True, "weight": 0.9}); T["emotion"].append([at(a), "happy"])
        return 0.8
    if g == "rule of three":
        # twice as set-up, the third bigger and later (the beat before the payoff)
        c = (a.get("clip") or "nod"); add = c in ("nod", "head_shake")
        for i, dt in enumerate((0.0, 0.9, 2.1)):
            k = {"clip": c, "start": at(a, dt), "weight": (0.9 if add else 3) * (1.4 if i == 2 else 1)}
            if add:
                k["additive"] = True
            T["clips"].append(k)
        T["emotion"].append([at(a, 2.1), "surprised"])
        return 3.0
    return 0.0


# ---------- rig abilities (2.12) ----------
def clip_needs(clip):
    return sorted(set((clip.get("tracks") or {}).keys()))


def abilities(p, lib):
    parts = set(p.get("parts", {})); sw = p.get("swaps") or {}
    shapes = {k: set((v.get("shapes") or {}).keys()) for k, v in sw.items()}
    free, costly = [], []
    for name, clip in sorted((lib.get("clips") or {}).items()):
        miss = [x for x in clip_needs(clip) if x not in parts]
        (costly if miss else free).append({"move": f"clip {name}", **({"draw": [f"part {m}" for m in miss]} if miss else {})})
    for emo, needs in NEEDS_EMOTION.items():
        miss = [f"{k}: {s}" for k, s in needs if s not in shapes.get(k, set())]
        (costly if miss else free).append({"move": f"emotion {emo}", **({"draw": miss} if miss else {})})
    for what, ok, draw in (("glance / look at", "pupils" in sw, ["pupils (eye whites with movable irises)"]),
                           ("blink", "half" in shapes.get("eyes", set()) and "closed" in shapes.get("eyes", set()), ["eyes: half, closed"]),
                           ("lip-sync", len(shapes.get("mouth", set())) >= 4, ["mouth: closed, small, mid, wide (O, FV, smile, frown help)"]),
                           ("turn (three-quarter)", "turn" in (p.get("controls") or {}), ["three-quarter view or a turn control"]),
                           ("tail / chain", bool(p.get("chains")), ["a chain of parts (tail)"])):
        (free if ok else costly).append({"move": what, **({} if ok else {"draw": draw})})
    return {"name": p.get("name"), "template": p.get("template"), "free": free, "costly": costly}


def needs_of(action, p, lib):
    """drawings an action would need from this rig (empty = free)"""
    ab = abilities(p, lib); costly = {c["move"]: c.get("draw", []) for c in ab["costly"]}
    k = action.get("kind"); out = []
    if k == "clip":
        name = action["clip"].replace("{side}", "R")
        if name not in (lib.get("clips") or {}):
            out.append(f"a {name.replace('_', ' ')} clip for the {p.get('template')} template")
        out += costly.get(f"clip {name}", [])
    elif k == "emotion":
        out += costly.get(f"emotion {action['emotion']}", [])
    elif k == "look":
        out += costly.get("glance / look at", [])
    elif k == "walk":
        out += costly.get("clip walk", [])
    elif k == "gag":
        if action["gag"] in ("double take", "long stare", "deadpan", "slow burn"):   # gags played with the eyes
            out += costly.get("glance / look at", []) + costly.get("blink", [])
        if action["gag"] in ("button",):
            out += costly.get("emotion happy", [])
        if action["gag"] == "rule of three":
            out += costly.get(f"clip {action.get('clip') or 'nod'}", []) + ([] if (action.get("clip") or "nod") in (lib.get("clips") or {}) else [f"a {action.get('clip')} clip for the {p.get('template')} template"])
        if action["gag"] == "double take":
            out += costly.get("emotion surprised", [])
        if action["gag"] == "slow burn":
            out += costly.get("emotion angry", [])
    return sorted(set(out))
