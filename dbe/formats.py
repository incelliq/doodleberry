"""Format templates (plan 2.15): a brief plus a template gives a storyboard (script.json with slots, shots.json,
facts.json, data.json, brief.md, edit.json for series) that already obeys the cold-open and reading-time rules.

Templates are beat lists. A beat has a role (the speaker role it is written for), text with {fields} from the brief
(a brief may also override any beat's text in brief["lines"][beat_id]), a scene (beats with the same scene share a
shot), optional on-screen kit elements, and optional "predict": a prediction prompt before a reveal (the question
stays up through the line and a silent count of `predict` seconds, long enough to read). Line-relative timing
everywhere, so voicing later keeps the cut (narration slots, plan 2.16).

Formats: myth_vs_data, explainer (hook, question, two steps, source), dialogue (learner and expert), wonder_story,
we_reran_it, anniversary, series (several parts,
each in its own format, cut into episodes by edit.json).
"""
import json
import re

ROLES = {"expert": "ravi", "learner": "momo", "narrator": "priya"}
SETS = {"open": "classroom", "myth": "paper", "predict": "paper", "reveal": "paper", "why": "classroom", "close": "classroom",
        "explain": "paper", "detail": "paper",
        "wonder": "night", "story": "forest", "then": "paper", "now": "paper", "street": "street"}


def _beat(id_, role, text, scene, **k):
    return {"id": id_, "role": role, "text": text, "scene": scene, **k}


TEMPLATES = {
    "myth_vs_data": {
        "about": "a common belief, a prediction prompt, the data, why, the source",
        "needs": ["myth", "question", "finding", "why", "source"],
        "beats": [
            _beat("hook", "expert", "You have probably heard this one.", "open"),
            _beat("myth", "learner", "{myth}", "myth", sign="{myth}"),
            _beat("predict", "expert", "{question}", "predict", predict=2.0, sign="What do you think?"),
            _beat("reveal", "expert", "{finding}", "reveal", chart=True, title="{reveal_title}", fact="finding"),
            _beat("why", "expert", "{why}", "why", fact="why"),
            _beat("button", "learner", "{button}", "close", cite="{source}"),
        ],
        "defaults": {"button": "Huh. Myth busted.", "reveal_title": "THE DATA"},
    },
    "dialogue": {
        "about": "a learner asks, an expert answers (E28); questions are the learner's, so viewers ask with them",
        "needs": ["topic", "exchanges"],
        "beats": "exchanges",
        "defaults": {"hook": "Can I ask you something about {topic}?", "button": "That makes sense now."},
    },
    "wonder_story": {
        "about": "imagine, build, reveal, reflect: a small story around one surprising fact",
        "needs": ["imagine", "build", "reveal", "reflect"],
        "beats": [
            _beat("imagine", "narrator", "Imagine {imagine}.", "wonder"),
            _beat("build", "narrator", "{build}", "story"),
            _beat("predict", "learner", "{question}", "story", predict=2.0, sign="Guess!"),
            _beat("reveal", "narrator", "{reveal}", "wonder", title="{reveal_title}", fact="reveal"),
            _beat("reflect", "narrator", "{reflect}", "wonder"),
        ],
        "defaults": {"question": "How far do you think?", "reveal_title": "WOW"},
    },
    "we_reran_it": {
        "about": "an earlier claim, re-checked with newer data: then, now, what changed",
        "needs": ["old_claim", "new_finding", "changed", "source"],
        "beats": [
            _beat("hook", "expert", "{when}, we said {old_claim}.", "then", sign="{old_claim}"),
            _beat("rerun", "expert", "So we ran the numbers again.", "now"),
            _beat("predict", "learner", "Did it hold up?", "now", predict=2.0, sign="Did it hold up?"),
            _beat("reveal", "expert", "{new_finding}", "now", chart=True, fact="new_finding"),
            _beat("changed", "expert", "{changed}", "why", fact="changed", cite="{source}"),
        ],
        "defaults": {"when": "A few years ago"},
    },
    "explainer": {
        "about": "a hook, the learner's question, the idea in two steps, the source (the calendar's analysis and news slots)",
        "needs": ["hook", "point", "detail", "source"],
        "beats": [
            _beat("hook", "expert", "{hook}", "open"),
            _beat("ask", "learner", "{question}", "open"),
            _beat("point", "expert", "{point}", "explain", title="{point_title}", chart=True, fact="point"),
            _beat("detail", "expert", "{detail}", "detail", fact="detail"),
            _beat("button", "learner", "{button}", "close", cite="{source}"),
        ],
        "defaults": {"question": "Wait, how does that work?", "point_title": "HERE'S HOW", "button": "So that's how it works."},
    },
    "anniversary": {
        "about": "on this day: the event, what it changed, where things stand now",
        "needs": ["years", "event", "changed", "now"],
        "beats": [
            _beat("hook", "narrator", "{years} years ago today, {event}.", "then", title="{years} YEARS", fact="event"),
            _beat("changed", "narrator", "{changed}", "then", fact="changed"),
            _beat("now", "narrator", "{now}", "now", fact="now", cite="{source}"),
            _beat("button", "learner", "{button}", "close"),
        ],
        "defaults": {"button": "Happy anniversary!", "source": ""},
    },
}


def _fill(s, brief):
    def rep(m):
        k = m.group(1)
        if k not in brief:
            raise KeyError(f"the brief needs {k!r}")
        return str(brief[k])
    return re.sub(r"\{(\w+)\}", rep, s)


def beats_of(fmt, brief):
    t = TEMPLATES[fmt]; b = {**t.get("defaults", {}), **brief}
    b = {k: (_fill(v, {**t.get("defaults", {}), **brief}) if isinstance(v, str) and "{" in v and "{{" not in v else v) for k, v in b.items()}
    missing = [k for k in t["needs"] if k not in b]
    if missing:
        raise KeyError(f"brief for {fmt} needs: {', '.join(missing)}")
    if t["beats"] == "exchanges":
        out = [_beat("hook", "learner", b["hook"], "open")]
        for i, ex in enumerate(b["exchanges"], 1):
            q, a = (ex["q"], ex["a"]) if isinstance(ex, dict) else ex
            out.append(_beat(f"q{i}", "learner", q, f"ex{i}"))
            out.append(_beat(f"a{i}", "expert", a, f"ex{i}", fact=(ex.get("fact") if isinstance(ex, dict) else None)))
        out.append(_beat("button", "learner", b["button"], f"ex{len(b['exchanges'])}"))
        return out, b
    beats = []
    for be in t["beats"]:
        be = dict(be)
        text = (b.get("lines") or {}).get(be["id"], be["text"])
        be["text"] = _fill(text, b)
        for k in ("sign", "title", "cite"):
            if be.get(k):
                be[k] = _fill(be[k], b)
        beats.append(be)
    return beats, b


def build(fmt, brief, prefix=""):
    """-> (script lines, shots, facts) for one part; ids prefixed for series"""
    beats, b = beats_of(fmt, brief)
    cast_ids = {**ROLES, **(brief.get("cast") or {})}
    lines, facts, shots = [], [], []
    last_tail = 1.2
    for be in beats:
        lid = f"{prefix}{be['id']}"
        ln = {"id": lid, "speaker": cast_ids[be["role"]], "fact": None, "text": be["text"]}
        if be.get("fact") and brief.get("facts", {}).get(be["fact"]):
            f = brief["facts"][be["fact"]]; fid = f"{prefix}{be['fact']}"
            facts.append({"id": fid, "claim": f.get("claim", be["text"]), "source": f.get("source"), **({"source_sentence": f["source"]["quote"]} if isinstance(f.get("source"), dict) and f["source"].get("quote") else {}), "status": f.get("status", "needs_check")})
            ln["fact"] = fid
        if be.get("predict"):
            ln["pause"] = be["predict"]   # the silent count after the question
        lines.append(ln)
    # scenes -> shots (beats of a scene in order)
    order = []
    for be in beats:
        if be["scene"] not in order:
            order.append(be["scene"])
    for si, sc in enumerate(order):
        bs = [x for x in beats if x["scene"] == sc]; first, last = f"{prefix}{bs[0]['id']}", f"{prefix}{bs[-1]['id']}"
        roles = []
        for x in bs:
            if x["role"] not in roles:
                roles.append(x["role"])
        if len(roles) == 1 and sc in ("open", "close", "why") and "learner" not in roles:
            roles.append("learner")   # a listener in conversational scenes
        xs = {1: [540], 2: [300, 780], 3: [200, 540, 880]}[min(3, len(roles))]
        chart = any(x.get("chart") for x in bs) and brief.get("data")
        cast = [] if chart else [{"puppet": f"cast/generated/{cast_ids[r]}.puppet.json", "speaker": cast_ids[r],
                                  "place": {"x": x, "y": 1540, "s": 1.05 if len(roles) > 1 else 1.15},
                                  "timeline": {"clips": [{"clip": "idle", "start": 0, "fadeIn": 0}], "springs": True, "visemes_from": cast_ids[r]}}
                                 for r, x in zip(roles[:3], xs)]
        overlays = []
        for x in bs:
            lid = f"{prefix}{x['id']}"
            if x.get("sign"):
                words = len(re.findall(r"[\w']+", x["sign"])); hold = round(max(words / 3 + 1.2, 2.0), 2)
                end = f"{lid}.end+{x['predict']}" if x.get("predict") else f"{lid}.start+{hold}"
                overlays.append({"type": "paper", "text": [x["sign"]], "y": 300, "size": 70, "start": f"{lid}.start", "end": end})
            if x.get("title"):
                overlays.append({"type": "title", "text": x["title"], "y": 1380 if chart else 420, "size": 110, "start": f"{lid}.start+0.3"})
            if x.get("chart") and brief.get("data"):
                overlays.append({"type": "bars", "data_from": brief.get("chart_key", "chart"), "title": brief.get("chart_title", ""), "y": 420, "h": 760,
                                 "start": f"{lid}.start", "duration": 1.2})
            if x.get("cite") and x["cite"].strip():   # held for words / 3 + 1 s at least, against the line's draft length
                tail = cite_tail(x["cite"], x["text"])
                overlays.append({"type": "citation", "text": x["cite"], "y": 1240, "start": f"{lid}.start", "end": f"{lid}.end+{tail}"})
                last_tail = max(last_tail, tail + 0.2)
        start = 0 if (si == 0 and not prefix) else f"{first}.start-0.3"
        set_ = brief.get("sets", {}).get(sc, SETS.get(sc, "classroom"))
        board = {"set_opts": {"board": [w.strip() for w in re.findall(r".{1,16}(?:\s|$)", str(brief.get("title", "")) + " ")][:3]}} if set_ == "classroom" and brief.get("title") else {}
        shots.append({"id": f"{prefix}s{si + 1}", "renderer": "svg", "set": set_, **board,
                      "start": start, "end": None, "start_line": first, "end_line": last, "bubbles": False,
                      **({"camera_auto": {"handheld": 0.3}} if len(cast) > 1 else {}),
                      **({"style": {"float": True}} if not cast else {}), "cast": cast, **({"overlays": overlays} if overlays else {})})
    for a, b_ in zip(shots, shots[1:]):
        a["end"] = b_["start"]
    shots[-1]["end"] = f"{lines[-1]['id']}.end+{round(last_tail, 2)}"
    return lines, shots, facts


def _words(t):
    return len(re.findall(r"[\w']+", str(t)))


def cite_tail(cite, line, wpm=135):
    """seconds a citation stays up after its line ends: 1 s, or more when the line (at its draft pace) is shorter than
    the citation's reading time"""
    need = _words(cite) / 3 + 1; line_s = _words(line) * 60.0 / wpm + 0.25
    return round(max(1.0, need - line_s + 0.2), 2)


def storyboard(fmt, brief):
    """the whole film for a format, or a series of parts"""
    if fmt == "series":
        lines, shots, facts, parts = [], [], [], []
        for i, part in enumerate(brief["parts"], 1):
            l, s, f = build(part["format"], {**{k: v for k, v in brief.items() if k not in ("parts",)}, **part}, prefix=f"p{i}")
            if shots:   # the first shot of a part starts where the previous part ends
                shots[-1]["end"] = s[0]["start"]
            lines += l; shots += s; facts += f; parts.append(len(s))
        shots[0]["start"] = 0
        return lines, shots, facts, {"cuts": {"full": {"ranges": "all"}, "ep": {"split": len(parts)}}}
    l, s, f = build(fmt, brief)
    return l, s, f, None
