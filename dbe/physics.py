"""Multi-body physics for shots (WP-09): a shot's "physics" block is simulated with Rapier's deterministic build
(tools/physics/solve.mjs) and baked into prop tracks that every frame samples, so renders stay pure functions of the
frame number and a rerun gives the same bytes (the bake's sha256 is kept in the block as "solved_hash").
Gravity defaults to that of the props it takes over (a juggle's), else 2600 px/s^2.

    "physics": {"start": "drop.start", "end": 9.5, "gravity": 2600, "retime": "beats" | {"subdiv": 2} | false,
                "floor": 1500, "walls": true,
                "bodies": [{"id": "ball1", "prop": true},                       // a prop already in the shot: starts
                                                                                // from its motion at `start`
                           {"id": "crate", "shape": "box", "size": [120, 120], "at": [700, 1380], "color": "#c8874a"}],
                "static": [{"box": [cx, cy, w, h], "angle": 0, "draw": true, "color": "#8a6d4b"}],
                "impulses": [{"t": 8.1, "body": "crate", "v": [-400, -900]}]}

Bodies that are not props become props ("solved": "physics"). Contacts are retimed onto the beat grid of score.json
(the strongest first; the warp between them stays within 0.75-1.33x speed) unless "retime" is false.
"""
import json
import subprocess
import tempfile
from pathlib import Path

from . import ROOT

SOLVER = ROOT / "tools" / "physics" / "solve.mjs"
PKG = ROOT / "tools" / "physics" / "node_modules" / "@dimforge" / "rapier2d-deterministic-compat"


def available():
    return PKG.exists()


def request(block, shot, size, fps, beat_s, offset_s):
    """the solver request for one resolved shot (pure)"""
    W, H = size
    start = float(block.get("start", shot.get("start", 0)))
    end = float(block.get("end", shot.get("end", start + 3)))
    static = []
    if block.get("floor") is not None:
        static.append({"box": [W / 2, float(block["floor"]) + 40, 3 * W, 80], "restitution": block.get("floor_restitution", 0.45), "friction": 0.7})
    if block.get("walls"):
        static += [{"box": [-40, H / 2, 80, 3 * H]}, {"box": [W + 40, H / 2, 80, 3 * H]}]
    static += [dict(s) for s in block.get("static", [])]
    props = {p.get("id"): p for p in shot.get("props", [])}
    bodies = []
    for b in block.get("bodies", []):
        d = {k: v for k, v in b.items() if k in ("id", "shape", "r", "size", "at", "angle", "v", "spin", "density", "restitution", "friction")}
        if b.get("prop"):
            pr = props.get(b["id"])
            if not pr:
                raise ValueError(f"physics body {b['id']!r}: no prop with that id in the shot")
            d["prop"] = {k: v for k, v in pr.items() if k != "track"}   # its own motion, not an earlier bake
            d.setdefault("r", pr.get("r", 34))
            if pr.get("shape") == "box":
                d.setdefault("shape", "box")
                d.setdefault("size", pr.get("size"))
        bodies.append(d)
    rt = block.get("retime", "beats")
    retime = None
    if rt:
        sub = (rt.get("subdiv") if isinstance(rt, dict) else None) or 2
        retime = {"grid": beat_s / sub, "offset": offset_s, "min_dv": (rt.get("min_dv") if isinstance(rt, dict) else None) or 250}
    g = block.get("gravity") or next((b["prop"]["gravity"] for b in bodies if b.get("prop") and b["prop"].get("gravity")), 2600)   # carry on under the props' own gravity
    return {"fps": fps, "start": start, "end": end, "gravity": g, "scale": 100, "sample_fps": block.get("sample_fps", 60),
            "bodies": bodies, "static": static, "impulses": block.get("impulses", []), "retime": retime,
            "casts": [{"puppet": c["puppet"], "place": c.get("place"), "timeline": c.get("timeline", {})} for c in shot.get("cast", [])]}


def run(req):
    if not available():
        raise RuntimeError("Rapier is not installed: bash tools/setup.sh physics")
    with tempfile.TemporaryDirectory(prefix="phys_") as td:
        a, b = Path(td) / "req.json", Path(td) / "out.json"
        a.write_text(json.dumps(req))
        r = subprocess.run(["node", str(SOLVER), str(a), str(b)], capture_output=True, text=True, timeout=600, cwd=str(ROOT))
        if r.returncode != 0:
            raise RuntimeError(f"physics solver failed: {(r.stderr or r.stdout)[-1500:]}")
        return json.loads(b.read_text())


def apply(raw_shot, block, out, req):
    """bake the solver output into the raw shots.json shot (replaces earlier physics output)"""
    props = [p for p in raw_shot.get("props", []) if p.get("solved") != "physics"]
    by = {p.get("id"): p for p in props}
    for b in block.get("bodies", []):
        tr = out["bodies"][b["id"]]
        if b.get("prop"):
            by[b["id"]]["track"] = tr
            continue
        pr = {"id": b["id"], "solved": "physics", "r": b.get("r", 30), "color": b.get("color", "#e8603c"), "squash": b.get("squash", True), "impact": b.get("impact", True), "track": tr}
        for k in ("shape", "size", "svg", "stretch", "smear"):
            if k in b:
                pr[k] = b[k]
        props.append(pr)
    for i, s in enumerate(block.get("static", [])):   # drawn static colliders: a still prop
        if s.get("draw") and s.get("box"):
            cx, cy, w, h = s["box"]
            props.insert(0, {"id": s.get("id", f"static{i + 1}"), "solved": "physics", "shape": "box", "size": [w, h], "color": s.get("color", "#8a6d4b"), "impact": False,
                             "track": {"t0": req["start"], "fps": 1, "frames": [[cx, cy, s.get("angle", 0)]]}})
    raw_shot["props"] = props
    raw_shot["physics"] = {**block, "solved_hash": out["hash"]}
    return raw_shot


def self_test():
    """two identical bakes of a small scene must be byte-equal, and retimed key contacts must sit on the grid"""
    if not available():
        return {"ok": True, "skipped": "Rapier not installed (bash tools/setup.sh physics)"}
    block = {"start": 0, "end": 2.5, "floor": 1500, "walls": True, "retime": {"subdiv": 2},
             "bodies": [{"id": "a", "r": 30, "at": [420, 700], "v": [160, 0]}, {"id": "b", "r": 30, "at": [480, 420]},
                        {"id": "c", "shape": "box", "size": [90, 90], "at": [640, 1300], "angle": 12}]}
    req = request(block, {"start": 0, "end": 2.5, "cast": []}, [1080, 1920], 30, 0.6, 0.0)
    o1, o2 = run(req), run(req)
    grid = 0.3
    on = all(abs(k["film"] / grid - round(k["film"] / grid)) < 1e-6 for k in o1["keys"])
    rest = o1["bodies"]["c"]["frames"][-1]
    ok = o1["hash"] == o2["hash"] and json.dumps(o1["bodies"]) == json.dumps(o2["bodies"]) and on and len(o1["keys"]) >= 2 and abs(rest[1] - 1455) < 3
    return {"ok": bool(ok), "hash": o1["hash"][:16], "keys": len(o1["keys"]), "rapier": o1["rapier"], "box_rest_y": rest[1]}
