"""The director's desk (WP-21): plain-English notes on a film, routed to the commands that make each change.

`route(text, film)` reads each sentence and returns the edits it asks for, as command calls with a reason; nothing is
guessed: a sentence it cannot place is returned as not understood. Kinds of change:

- **line**: "Change Ravi's first line to 'Yes, bring your card.'" -> script.json (film.write), then the voice is
  rebuilt, the shots re-timed and the acting re-planned;
- **timing**: "Hold shot 2 a second longer" / "Shorten shot 1 by half a second" -> a pause after the shot's last
  line (script.json "pause"), then the same rebuild; the film's last shot changes its tail past the last line;
- **camera**: "Push in on shot 1" / "Go wider on the last shot" -> the shot's auto camera framing (shots.json);
- **set**: "Put shot 2 in the park" -> the shot's set (a known set);
- **music**: "Make the music calmer" / "livelier" -> the score's tempo (score.json);
- **acting**: any sentence naming a character and what they do ("Priya shrugs after her line") -> acting.direct;
- **preview**: "Show me" -> the storyboard and animatic.

Each routed command runs as the person or agent at the desk, so their role decides what goes through (dbe/team.py).
"""
import copy
import json
import re
from pathlib import Path

ORD = {"first": 0, "second": 1, "third": 2, "fourth": 3, "fifth": 4, "1st": 0, "2nd": 1, "3rd": 2, "4th": 3, "5th": 4, "last": -1}
NUMW = {"a": 1.0, "one": 1.0, "half a": 0.5, "a half": 0.5, "two": 2.0, "three": 3.0, "a quarter of a": 0.25}
SETS = ["plain", "park", "clinic", "paper", "cutaway", "kitchen", "classroom", "office", "street", "farm", "bedroom", "forest", "lab", "night", "reservoir", "stage"]
ACT = r"\b(nod|nods|shrug|shrugs|wave|waves|point|points|look|looks|glance|glances|smile|smiles|frown|frowns|jump|jumps|clap|claps|laugh|laughs|sigh|sighs|turn|turns|lean|leans|scratch|scratches|facepalm|celebrat\w*|nervous|excited|sad|angry|happy|surprised|double take|stomp|stomps|cross|crosses|thumbs up|bow|bows)\b"


def sentences(text):
    out = []
    for s in re.split(r"\n+|;\s*", re.sub(r"([.!?][\"”’']?)\s+(?=[A-Z])", r"\1\n", text.strip())):
        s = s.strip()
        if s:
            out.append(s)
    return out


def _secs(s):
    s = s.lower().strip()
    if s in NUMW:
        return NUMW[s]
    try:
        return float(s)
    except ValueError:
        return None


def _shot(ref, shots):
    ref = ref.lower().strip()
    ids = [sh["id"] for sh in shots]
    if ref in ORD:
        return ids[ORD[ref]] if abs(ORD[ref]) <= len(ids) else None
    if ref in ids:
        return ref
    m = re.fullmatch(r"s?(\d+)", ref)
    if m and 1 <= int(m.group(1)) <= len(ids):
        return ids[int(m.group(1)) - 1]
    return None


def route(text, film):
    """film: {name, script, shots, score} -> {edits: [{kind, what, calls: [(command, args)]}], not_understood: [...]}"""
    sc, sh, score, name = film["script"], film["shots"], film.get("score") or {}, film["name"]
    speakers = {k: k for k in (sc.get("speakers") or {})} | {(v or {}).get("name", k).lower(): k for k, v in (sc.get("speakers") or {}).items()}
    speakers |= {l.get("speaker"): l.get("speaker") for l in sc.get("lines", []) if l.get("speaker")}
    edits, unk = [], []
    rebuild = [("voice.build", {"name": name}), ("film.retime", {"name": name}), ("acting.plan", {"name": name})]
    S = copy.deepcopy(sc); SH = copy.deepcopy(sh); SC = copy.deepcopy(score)
    for s in sentences(text):
        # "make shot 2 a second longer" is said the timing rule's way: "hold shot 2 by a second"
        s = re.sub(r"make\s+(?:the\s+)?((?:shot\s+)?\w+(?:\s+shot)?)\s+(half a|a half|a|one|two|three|[\d.]+)\s+seconds?\s+(longer|shorter)",
                   lambda m: f"{'hold' if m.group(3).lower() == 'longer' else 'shorten'} {m.group(1)} by {m.group(2)} seconds", s, flags=re.I)
        low = s.lower()
        # line text
        m = re.search(r"(?:change|make|have|rewrite)\s+(\w+)(?:'s|’s|s')?\s+(first|second|third|fourth|fifth|last|\d(?:st|nd|rd|th))\s+line\s*(?:to|say|into|as|:)\s*[\"“'‘]?(.+?)[\"”'’]?\s*$", s, re.I)
        if m and m.group(1).lower() in speakers:
            who = speakers[m.group(1).lower()]; mine = [l for l in S["lines"] if l.get("speaker") == who]; k = ORD.get(m.group(2).lower())
            if mine and k is not None and abs(k) <= len(mine):
                ln = mine[k]; old = ln["text"]; ln["text"] = m.group(3).strip()
                edits.append({"kind": "line", "what": f"{who}'s line {ln['id']}: “{old}” -> “{ln['text']}”", "sentence": s})
                continue
        # timing: hold / shorten a shot
        m = re.search(r"(hold|extend|lengthen|shorten|trim|cut)\s+(?:the\s+)?(?:shot\s+)?(\w+)(?:\s+shot)?\s+(?:by\s+|for\s+)?(half a|a half|a quarter of a|a|one|two|three|[\d.]+)\s+(?:more\s+)?seconds?(?:\s+(longer|shorter))?", low)
        if m:
            sid = _shot(m.group(2), SH["shots"]); d = _secs(m.group(3))
            if sid and d:
                d = -d if (m.group(1) in ("shorten", "trim", "cut") or m.group(4) == "shorter") else d
                shot = next(x for x in SH["shots"] if x["id"] == sid); last = shot.get("end_line")
                if shot is SH["shots"][-1]:   # the film's last shot runs a tail past its last line (film.retime)
                    t0 = shot.get("tail", 1.5); shot["tail"] = round(max(0.3, t0 + d), 2)
                    edits.append({"kind": "timing", "what": f"shot {sid} (the last) runs {shot['tail']} s past its last line (was {t0})", "sentence": s})
                    continue
                ln = next((l for l in S["lines"] if l["id"] == last), None)
                if ln is None:
                    unk.append({"sentence": s, "why": f"shot {sid} does not end on a line, so its length is not set by a pause"}); continue
                new = round(max(0.0, ln.get("pause", 0.0) + d), 2)
                if ln.get("pause", 0.0) + d < -0.01:
                    unk.append({"sentence": s, "why": f"shot {sid} has only {ln.get('pause', 0.0)} s of pause to cut"}); continue
                ln["pause"] = new
                edits.append({"kind": "timing", "what": f"pause after {last} (end of shot {sid}) now {new} s", "sentence": s})
                continue
        # camera
        m = re.search(r"(push in|move in|closer|tighter|go in|zoom in|pull back|pull out|wider|go wide|zoom out|wide shot)(?:\s+(?:on|for|in))?\s+(?:the\s+)?(?:shot\s+)?(\w+)(?:\s+shot)?", low) or \
            re.search(r"(?:shot\s+)?(\w+)(?:\s+shot)?\s+(?:should be|is too)\s+(closer|tighter|wider|tight|wide)", low)
        if m:
            a, b = m.group(1), m.group(2)
            verb, ref = (a, b) if re.match(r"(push|move|closer|tighter|go|zoom|pull|wider|wide)", a) else (b, a)
            sid = _shot(ref, SH["shots"])
            if sid:
                shot = next(x for x in SH["shots"] if x["id"] == sid)
                if shot.get("camera"):
                    unk.append({"sentence": s, "why": f"shot {sid} has hand-set camera keys; change them on the timeline"}); continue
                ca = shot["camera_auto"] if isinstance(shot.get("camera_auto"), dict) else {}
                step = 0.25 if re.match(r"(push|move in|closer|tight|go in|zoom in)", verb) else -0.25
                for k_, dflt in (("zoom_single", 1.9), ("zoom", 1.45)):
                    ca[k_] = round(min(2.6, max(1.0, ca.get(k_, dflt) + step)), 2)
                shot["camera_auto"] = ca
                edits.append({"kind": "camera", "what": f"shot {sid}: auto camera {'closer' if step > 0 else 'wider'} (singles {ca['zoom_single']}, groups {ca['zoom']})", "sentence": s})
                continue
        # set
        m = re.search(r"(?:put|set|move|place|stage)\s+(?:the\s+)?(?:shot\s+)?(\w+)(?:\s+shot)?\s+(?:in|at|on|to)\s+(?:the\s+|a\s+)?(\w+)", low) or \
            re.search(r"(?:change|switch)\s+(?:the\s+)?(?:set|background)\s+(?:of|for|in)\s+(?:shot\s+)?(\w+)(?:\s+shot)?\s+to\s+(?:the\s+|a\s+)?(\w+)", low)
        if m and m.group(2) in SETS:
            sid = _shot(m.group(1), SH["shots"])
            if sid:
                shot = next(x for x in SH["shots"] if x["id"] == sid); old = shot.get("set"); shot["set"] = m.group(2)
                if old != m.group(2):
                    shot.pop("set_opts", None) if m.group(2) != "classroom" else None
                edits.append({"kind": "set", "what": f"shot {sid}: {old} -> {m.group(2)}", "sentence": s})
                continue
        # music
        m = re.search(r"music\b.*\b(calmer|slower|softer|gentler|more relaxed|livelier|faster|more upbeat|upbeat|more energetic|bouncier)", low) or \
            re.search(r"\b(calmer|slower|softer|gentler|livelier|faster|more upbeat|upbeat|more energetic|bouncier)\b.*\bmusic", low)
        if m and SC:
            slow = m.group(1) in ("calmer", "slower", "softer", "gentler", "more relaxed")
            old = SC.get("bpm", 100); SC["bpm"] = int(min(140, max(70, old + (-14 if slow else 14))))
            edits.append({"kind": "music", "what": f"tempo {old} -> {SC['bpm']} bpm", "sentence": s})
            continue
        # preview
        if re.search(r"\b(show me|let me see|preview|play it|storyboard|animatic)\b", low):
            edits.append({"kind": "preview", "what": "storyboard and animatic", "sentence": s, "calls": [("film.storyboard", {"name": name}), ("film.animatic", {"name": name})]})
            continue
        # acting: a character and what they do
        names = [w for w in speakers if w and re.search(rf"\b{re.escape(w)}\b", low)]
        if names and re.search(ACT, low):
            edits.append({"kind": "acting", "what": s, "sentence": s, "calls": [("acting.direct", {"name": name, "text": s})]})
            continue
        unk.append({"sentence": s, "why": "no change of a kind the desk knows (line, timing, camera, set, music, acting, preview)"})
    # one write per file that changed, then what must follow it
    calls = []
    if S != sc:
        calls.append(("film.write", {"name": name, "file": "script.json", "content": json.dumps(S, indent=1, ensure_ascii=False)}))
    if SH != sh:
        calls.append(("film.write", {"name": name, "file": "shots.json", "content": json.dumps(SH, indent=1, ensure_ascii=False)}))
    if SC != score:
        calls.append(("film.write", {"name": name, "file": "score.json", "content": json.dumps(SC, indent=1, ensure_ascii=False)}))
    if any(e["kind"] == "line" for e in edits) or S != sc:
        calls += rebuild
    elif SH != sh and any(e["kind"] == "timing" for e in edits):
        calls.append(("film.retime", {"name": name}))
    calls += [c for e in edits for c in e.get("calls", []) if c[0] == "acting.direct"]
    calls += [c for e in edits for c in e.get("calls", []) if c[0] != "acting.direct"]
    return {"edits": edits, "calls": calls, "not_understood": unk}
