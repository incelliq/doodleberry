"""A film's data flow as a graph (WP-20): what each product is made from, whether it is fresh, and why not.

    facts ──────────────────────────────────────────────┐
    script ─▶ voice ─┬─▶ shot:<id> … ─▶ picture ─┐       │
                     │        └──(cues)──┐       ├─▶ final ─▶ qa
    score, sound ────┴────────────────▶ mix ─────┘

Every time a node is made (voice.build, a shot render, film.render) its inputs are recorded with it, each input as
a content hash, and for a shot also its resolved shot entry. Comparing the inputs recorded with the inputs as they
are now gives a node's state: fresh, stale (with the inputs that changed: "the shot's entry: cast[0].timeline.look",
"puppet cast/generated/ravi.puppet.json", "line l2", "renderer code dbe/player/player.js"), waiting on a stale node
upstream, or never made. Re-cooking a node makes it and what lies downstream of it, nothing else.

Records: films/<name>/build/graph.json (voice, picture, mix, final, qa) and build/shots/<id>.inputs.json.
"""
import hashlib
import json
from pathlib import Path

from . import ROOT

FILMS = ROOT / "films"


def sha(b):
    if isinstance(b, str):
        b = b.encode()
    return hashlib.sha256(b).hexdigest()[:16]


def file_sha(p):
    p = Path(p)
    return sha(p.read_bytes()) if p.exists() else None


def _json(p, d=None):
    try:
        return json.loads(Path(p).read_text())
    except Exception:
        return d


# ---------------- inputs of each node, as they are now ----------------
def shot_inputs(name, sh, s, timing, engine_files):
    """what a shot's picture is made from: its resolved entry, puppets, the lines and mouth cues it shows, clip
    libraries and the renderer code (the same things its render hash covers, kept apart so a change can be named)"""
    out = {"shot": sh, "film": {"size": s.get("size"), "fps": s.get("fps"), "captions": s.get("captions")}}
    mg = 0.5 if sh.get("camera_auto") else 0.0; a0, a1 = sh.get("start", 0) - mg, sh.get("end", 1e9) + mg
    for c in sh.get("cast", []):
        out[f"puppet {c['puppet']}"] = file_sha(ROOT / c["puppet"])
        sp = (c.get("timeline") or {}).get("visemes_from") or c.get("speaker")
        if sp:
            out[f"mouth cues of {sp}"] = sha(json.dumps([v for v in (timing.get("visemes") or {}).get(sp, []) if a0 <= v[0] <= a1]))
    for l in timing.get("lines", []):
        if l["start"] < a1 - 1e-6 and l["end"] > a0 + 1e-6:
            out[f"line {l['id']}"] = sha(json.dumps(l, sort_keys=True))
    for f in sorted((ROOT / "puppet" / "clips").glob("*.json")):
        out[f"clips {f.relative_to(ROOT)}"] = file_sha(f)
    for f in engine_files:
        out[f"renderer code {f}"] = file_sha(ROOT / f)
    return out


def voice_inputs(d):
    sc = _json(d / "script.json", {}) or {}
    return {"script lines": sha(json.dumps([{k: l.get(k) for k in ("id", "text", "speaker", "voice", "alt", "slot", "pace")} for l in sc.get("lines", [])], sort_keys=True)),
            "voices": sha(json.dumps({k: sc.get(k) for k in ("voice", "voices", "cast", "lead_in_s", "gap_s")}, sort_keys=True))}


def mix_inputs(d):
    return {"voice": file_sha(d / "build" / "voice.wav"), "score": file_sha(d / "score.json"), "sound edits": file_sha(d / "sound.json"),
            "cues": file_sha(d / "build" / "cues.json"), "lines": sha(json.dumps((_json(d / "timing.json", {}) or {}).get("lines", []), sort_keys=True))}


def picture_inputs(d, s):
    out = {f"shot {x['id']}": (Path(d / "build" / "shots" / f"{x['id']}.hash").read_text().strip() if (d / "build" / "shots" / f"{x['id']}.hash").exists() else None)
           for x in s["shots"]}
    out["transitions"] = sha(json.dumps([x.get("transition") for x in s["shots"]])); out["finishing"] = sha(json.dumps(s.get("post"), sort_keys=True))
    return out


def final_inputs(d, s):
    return {"picture": file_sha(d / "build" / "picture.mp4"), "mix": file_sha(d / "build" / "mix.wav"),
            "captions": sha(json.dumps([(_json(d / "timing.json", {}) or {}).get("lines", []), s.get("captions", True), s.get("caption_style")], sort_keys=True))}


def qa_inputs(d):
    return {"final": file_sha(d / "build" / "final.mp4"), "facts": file_sha(d / "facts.json")}


# ---------------- records ----------------
def record(d, node, inputs, seconds=None):
    """note that `node` was just made from `inputs`"""
    import time
    if node.startswith("shot:"):
        f = d / "build" / "shots" / f"{node[5:]}.inputs.json"
    else:
        f = d / "build" / "graph.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    rec = {"inputs": inputs, "made": round(time.time(), 1), **({"seconds": round(seconds, 2)} if seconds is not None else {})}
    if node.startswith("shot:"):
        f.write_text(json.dumps(rec, sort_keys=True))
    else:
        g = _json(f, {}) or {}; g[node] = rec; f.write_text(json.dumps(g, indent=1, sort_keys=True))


def recorded(d, node):
    if node.startswith("shot:"):
        return _json(d / "build" / "shots" / f"{node[5:]}.inputs.json")
    return (_json(d / "build" / "graph.json", {}) or {}).get(node)


def json_paths(a, b, path="", out=None, limit=8):
    """where two JSON values differ, as paths (cast[0].timeline.look)"""
    out = [] if out is None else out
    if len(out) >= limit:
        return out
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if a.get(k) != b.get(k):
                json_paths(a.get(k), b.get(k), f"{path}.{k}" if path else str(k), out, limit)
    elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b) and not all(isinstance(x, (int, float)) for x in a + b):
        for i, (x, y) in enumerate(zip(a, b)):
            if x != y:
                json_paths(x, y, f"{path}[{i}]", out, limit)
    else:
        out.append(path or "(all)")
    return out


def changed(old, new):
    """the inputs that changed between a record and now, each with what changed in it"""
    why = []
    for k in sorted(set(old) | set(new)):
        if old.get(k) == new.get(k):
            continue
        if k not in old:
            why.append({"input": k, "change": "new"})
        elif k not in new:
            why.append({"input": k, "change": "gone"})
        elif k == "shot":
            why.append({"input": "the shot's entry in shots.json", "change": "edited", "paths": json_paths(old[k], new[k])})
        elif isinstance(old[k], dict):
            why.append({"input": k, "change": "edited", "paths": json_paths(old[k], new[k])})
        else:
            why.append({"input": k, "change": "edited"})
    return why


# ---------------- the graph ----------------
def build(name, shots_resolved, timing, engine_files):
    d = FILMS / name; s = shots_resolved
    nodes, edges = {}, []

    def node(nid, kind, label, inputs=None, source=False, file=None):
        n = {"id": nid, "kind": kind, "label": label}
        if source:
            n.update(state="source", file=file, hash=file_sha(d / file) if file else None)
        else:
            rec = recorded(d, nid)
            product = {"voice": "build/voice.wav", "picture": "build/picture.mp4", "mix": "build/mix.wav", "final": "build/final.mp4",
                       "qa": "build/qa.json"}.get(nid) or (f"build/shots/{nid[5:]}.mp4" if nid.startswith("shot:") else None)
            if rec is None and product and (d / product).exists():
                n.update(state="unknown", why=[{"input": "(made before its inputs were recorded)", "change": "unknown"}])
            elif rec is None:
                n.update(state="missing", why=[{"input": "(never made here)", "change": "missing"}])
            else:
                why = changed(rec.get("inputs", {}), inputs)
                n.update(state="stale" if why else "fresh", why=why, made=rec.get("made"), seconds=rec.get("seconds"))
        nodes[nid] = n
        return n

    node("facts", "source", "facts", source=True, file="facts.json")
    node("script", "source", "script", source=True, file="script.json")
    node("score", "source", "score", source=True, file="score.json")
    node("sound", "source", "sound edits", source=True, file="sound.json")
    node("voice", "voice", "voice and timing", voice_inputs(d)); edges.append(("script", "voice"))
    for x in s["shots"]:
        nid = f"shot:{x['id']}"
        n = node(nid, "shot", f"shot {x['id']} ({x.get('renderer', 'svg')})", shot_inputs(name, x, s, timing, engine_files))
        n.update(start=x["start"], end=x["end"], renderer=x.get("renderer", "svg"))
        edges += [("voice", nid), (nid, "picture"), (nid, "mix")]
    node("picture", "picture", "picture (shots joined)", picture_inputs(d, s))
    node("mix", "mix", "sound mix", mix_inputs(d)); edges += [("voice", "mix"), ("score", "mix"), ("sound", "mix")]
    node("final", "final", "final film", final_inputs(d, s)); edges += [("picture", "final"), ("mix", "final")]
    node("qa", "qa", "QA", qa_inputs(d)); edges += [("final", "qa"), ("facts", "qa")]
    # stale upstream makes a node wait (it will change when that one is made again)
    parents = {}
    for a, b in edges:
        parents.setdefault(b, []).append(a)
    order = ["voice"] + [f"shot:{x['id']}" for x in s["shots"]] + ["picture", "mix", "final", "qa"]
    for nid in order:
        n = nodes[nid]; up = [p for p in parents.get(nid, []) if nodes[p]["state"] in ("stale", "missing", "waiting")]
        if up and n["state"] == "fresh":
            n["state"] = "waiting"
        if up:
            n["waits_on"] = up
    return {"film": name, "nodes": list(nodes.values()), "edges": [{"from": a, "to": b} for a, b in edges],
            "stale": [n["id"] for n in nodes.values() if n["state"] in ("stale", "missing", "waiting")]}


def downstream(graph, nid):
    kids = {}
    for e in graph["edges"]:
        kids.setdefault(e["from"], []).append(e["to"])
    seen, todo = [], [nid]
    while todo:
        x = todo.pop(0)
        for y in kids.get(x, []):
            if y not in seen:
                seen.append(y); todo.append(y)
    return seen
