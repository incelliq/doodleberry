"""Procedural layer (WP-42): a shot's "proc" block is a graph of nodes, cooked into the shot as data. Each node's key is
a hash of its operation, parameters, the keys of its inputs and the context it depends on, and its output is cached by
that key (films/<name>/build/proc/<key>.json, plates in build/proc/<key>/), so changing one node re-cooks it and the
nodes downstream of it and nothing else. Everything is seeded: a cook is a pure function of the graph.

    "proc": {"nodes": {
      "spots": {"op": "scatter", "region": [x0, y0, x1, y1], "count": 16, "min_dist": 70, "seed": 4},
      "crowd": {"op": "crowd", "in": "spots", "puppets": ["cast/generated/*.puppet.json"], "s_by_y": [y0, s0, y1, s1],
                "face": "center", "plane": "crowd", "seed": 7, "cheer": {"clips": ["clap", "celebrate"], "start": t, "end": t, "share": 0.6}},
      "confetti": {"op": "particles", "kind": "confetti" | "snow" | "rain", "count": 90, "rect": [...], "start": t, "seed": 3, "plane": "front"},
      "city": {"op": "gn_set", "kind": "city", "seed": 11, "blocks": {...}, "palette": [...], "plane": "set3d"},
      "crates": {"op": "rigid", "bodies": [{"shape": "box", "size": 1, "at": [540, 6, 4]}, ...], "plane": "set3d"},
      "game": {"op": "engine", "project": "films/x/godot", "scene": "res://main.tscn", "plane": "engine"}}}

Outputs land in the shot: crowd members are appended to its cast (tagged "solved": "proc") on their compositor plane;
particles and plates become items on compositor planes (a gn_set plane is screen-locked: its render already has the
camera). The gn_set node renders a Geometry Nodes set in Blender (dbe/blender_gn.py) framed by the shot camera.
"""
import glob
import hashlib
import json
import math
import os
import subprocess
import time
from pathlib import Path

from . import ROOT

VERSION = {"scatter": 1, "crowd": 1, "particles": 1, "gn_set": 1, "rigid": 1, "engine": 1}
GN_SCRIPT = ROOT / "dbe" / "blender_gn.py"


class Rng:
    """a small seeded generator (mulberry32), the same numbers on every machine and Python version"""
    def __init__(self, seed):
        self.a = (int(seed) * 2654435761 + 1013904223) & 0xFFFFFFFF

    def __call__(self):
        self.a = (self.a + 0x6D2B79F5) & 0xFFFFFFFF
        t = self.a
        t = ((t ^ (t >> 15)) * (t | 1)) & 0xFFFFFFFF
        t ^= (t + (((t ^ (t >> 7)) * (t | 61)) & 0xFFFFFFFF)) & 0xFFFFFFFF
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296

    def pick(self, xs):
        return xs[int(self() * len(xs)) % len(xs)]


def pixel_hash(png):
    """a hash of the decoded pixels (Blender writes the render date and time into each PNG's metadata)"""
    from PIL import Image
    im = Image.open(png).convert("RGBA")
    return hashlib.sha256(im.tobytes() + repr(im.size).encode()).hexdigest()[:16]


def _h(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:20]


def order(nodes):
    """topological order (inputs first); refuses cycles and unknown inputs"""
    out, state = [], {}

    def visit(n):
        if state.get(n) == 1:
            raise ValueError(f"proc: a cycle through {n!r}")
        if state.get(n) == 2:
            return
        state[n] = 1
        for i in inputs(nodes[n]):
            if i not in nodes:
                raise ValueError(f"proc: node {n!r} reads {i!r}, which does not exist")
            visit(i)
        state[n] = 2
        out.append(n)
    for n in sorted(nodes):
        visit(n)
    return out


def inputs(node):
    v = node.get("in")
    return [] if v is None else ([v] if isinstance(v, str) else list(v))


# ---------------- operations (pure) ----------------
def op_scatter(p, ins, ctx):
    x0, y0, x1, y1 = p.get("region", [80, 1300, 1000, 1560])
    rng, pts, md = Rng(p.get("seed", 1)), [], p.get("min_dist", 60)
    for _ in range(int(p.get("count", 12)) * 60):
        if len(pts) >= int(p.get("count", 12)):
            break
        q = [round(x0 + rng() * (x1 - x0), 1), round(y0 + rng() * (y1 - y0), 1)]
        if all(math.hypot(q[0] - a[0], (q[1] - a[1]) * 2.2) >= md for a in pts):   # rows read closer in depth
            pts.append(q)
    return {"points": sorted(pts, key=lambda q: (q[1], q[0]))}


def _puppets(pats):
    out = []
    for pat in pats:
        hits = sorted(str(Path(f).relative_to(ROOT)) for f in glob.glob(str(ROOT / pat)))
        out += hits if hits else [pat]
    return out


def op_crowd(p, ins, ctx):
    """cast members on the scattered points. With "depth": [near, far] each member stands on its own depth plane, at
    the height where the ground meets that depth (feet at H/2 + (floor - H/2) / d, scale s / d), so the crowd stands
    on a 3D set's ground and moves with true parallax; nearer rows are the points lower in the scatter region"""
    pts = ins[0]["points"] if ins else []
    pups = _puppets(p.get("puppets", ["cast/generated/*.puppet.json"]))
    rng = Rng(p.get("seed", 1))
    W, H = ctx["size"]
    ch = p.get("cheer") or {}
    ys = [q[1] for q in pts] or [0]
    cast = []
    for i, (x, y) in enumerate(pts):
        if p.get("depth"):
            dn, df = p["depth"]
            u = (max(ys) - y) / ((max(ys) - min(ys)) or 1)          # 0: the nearest row, 1: the farthest
            d = round(dn + (df - dn) * u, 3)
            yy = round(H / 2 + (ctx["floor"] - H / 2) / d, 1)
            s, plane = round(p.get("s", 0.7) / d, 4), f"{p.get('plane', 'crowd')}@{d}"
        else:
            y0, s0, y1, s1 = p.get("s_by_y", [1300, 0.45, 1560, 0.62])
            yy, s, plane = y, round(s0 + (s1 - s0) * min(1.2, max(-0.2, (y - y0) / ((y1 - y0) or 1))), 3), p.get("plane", "crowd")
        face = p.get("face", "center")
        flip = (1 if x < W / 2 else -1) if face == "center" else (1 if rng() < 0.5 else -1)
        clips = [{"clip": "idle", "start": 0, "fadeIn": 0, "phase": round(rng() * 4, 3), "speed": round(0.85 + 0.3 * rng(), 3)}]
        if ch and rng() < ch.get("share", 0.6):
            t0, t1 = float(ch.get("start", 0)), float(ch.get("end", 1))   # line-relative times resolve like any start/end
            t = round(t0 + rng() * max(0.0, t1 - t0), 3)
            clips.append({"clip": rng.pick(ch.get("clips", ["clap"])), "start": t, "fadeIn": 0.2})
        cast.append({"puppet": rng.pick(pups), "place": {"x": x, "y": yy, "s": s, "flip": flip}, "plane": plane,
                     "timeline": {"clips": clips, "seed": i + 1, "look": [[0, [round(rng() * 0.6 - 0.3, 2), 0]]]},
                     "solved": "proc", "proc": ctx["node"]})
    return {"cast": cast}


def op_particles(p, ins, ctx):
    item = {k: v for k, v in p.items() if k not in ("op", "in", "plane")}
    item.update(type="particles", proc=ctx["node"])
    return {"items": [item], "plane": p.get("plane", "front")}


def op_gn_set(p, ins, ctx, cache):
    """render the Geometry Nodes set with Blender into build/proc/<key>/ (cached by key)"""
    from .commands import BLENDER
    if not BLENDER:
        raise RuntimeError("gn_set needs Blender (bash tools/setup.sh blender)")
    out = cache / ctx["key"]
    n = ctx["frames"]
    step = max(1, int(p.get("every", 1)))
    frames = list(range(0, n, step))
    req = {**{k: v for k, v in p.items() if k not in ("op", "in", "plane", "every")}, "size": ctx["size"], "fps": ctx["fps"], "start": ctx["start"],
           "camera": ctx["camera"], "floor": ctx["floor"], "frames": frames}
    out.mkdir(parents=True, exist_ok=True)
    rq = out / "request.json"; rq.write_text(json.dumps(req))
    r = subprocess.run([BLENDER, "-b", "--factory-startup", "--gpu-backend", "vulkan", "--python", str(GN_SCRIPT), "--", str(rq), str(out)],
                       capture_output=True, text=True, timeout=14400, cwd=str(ROOT))
    if r.returncode != 0 or not (out / f"f_{frames[-1]:04d}.png").exists():
        raise RuntimeError(f"blender gn_set failed: {(r.stderr or r.stdout)[-1500:]}")
    hashes = {f"f_{f:04d}.png": pixel_hash(out / f"f_{f:04d}.png") for f in frames}
    item = {"type": "plate", "src": f"proc/{ctx['key']}/f_%04d.png", "start": ctx["start"], "fps": ctx["fps"], "count": n, "every": step, "proc": ctx["node"]}
    res = {"items": [item], "plane": p.get("plane", "set3d"), "screen": True, "frames": hashes}
    if (out / "bodies.json").exists():   # rigid bodies (WP-42): where each body is on every rendered frame
        res["bodies"] = json.loads((out / "bodies.json").read_text())
    if p.get("passes"):   # separate EEVEE passes (WP-42): one multilayer EXR per rendered frame beside the plate
        res["passes"] = {"files": [f"proc/{ctx['key']}/f_{f:04d}.exr" for f in frames], "layers": p["passes"]}
    return res


GODOT = next((str(p) for p in [Path(d) / "godot" / "godot" for d in (os.environ.get("DBE_OPT"), "/opt", str(Path.home() / ".local" / "opt")) if d] + [Path.home() / "godot" / "godot"] if p.exists()), None)


def _project_hash(proj):
    """a Godot project's own files (not its .godot import cache), so editing a scene or script re-cooks the node"""
    h = hashlib.sha256()
    for f in sorted(proj.rglob("*")):
        if f.is_file() and ".godot" not in f.parts:
            h.update(str(f.relative_to(proj)).encode()); h.update(f.read_bytes())
    return h.hexdigest()[:16]


def op_engine(p, ins, ctx, cache):
    """WP-42: live renders from a game engine into the comp. Godot 4 renders the project (its main scene, or `scene`) in
    Movie Maker mode at the shot's size and frame rate with a fixed step (so a frame is a function of its number) under
    a virtual display, into a screen-locked plate. The shot's span and camera reach the project as
    --doodleberry-request=<json> (OS.get_cmdline_user_args()) for scripts that want to follow the 2D camera."""
    import shutil
    if not GODOT:
        raise RuntimeError("engine needs Godot 4 (/opt/godot/godot or ~/.local/opt/godot/godot: bash tools/setup.sh godot)")
    proj = (ROOT / p["project"]).resolve()
    if not (proj / "project.godot").exists():
        raise FileNotFoundError(f"no Godot project at {p['project']}")
    out = cache / ctx["key"]; shutil.rmtree(out, ignore_errors=True); out.mkdir(parents=True)
    n = ctx["frames"]; W, H = ctx["size"]
    rq = out / "request.json"; rq.write_text(json.dumps({"size": [W, H], "fps": ctx["fps"], "start": ctx["start"], "frames": n, "camera": ctx["camera"]}))
    args = ["xvfb-run", "-a", "-s", f"-screen 0 {max(W, 1280)}x{max(H, 1024)}x24", GODOT, "--path", str(proj), "--rendering-driver", "opengl3",
            "--write-movie", str(out / "m.png"), "--fixed-fps", str(ctx["fps"]), "--quit-after", str(n), "--resolution", f"{W}x{H}"]
    if p.get("scene"):
        args.append(p["scene"])
    args += ["--", f"--doodleberry-request={rq}"]
    r = subprocess.run(args, capture_output=True, text=True, timeout=7200, cwd=str(ROOT))
    for k in range(n):   # Movie Maker numbers frames m00000000.png...; it writes one more at the end
        src = out / f"m{k:08d}.png"
        if not src.exists():
            raise RuntimeError(f"godot wrote no frame {k}: {(r.stderr or r.stdout)[-800:]}")
        src.rename(out / f"f_{k:04d}.png")
    for extra in out.glob("m*"):
        extra.unlink()
    hashes = {f"f_{k:04d}.png": pixel_hash(out / f"f_{k:04d}.png") for k in range(n)}
    item = {"type": "plate", "src": f"proc/{ctx['key']}/f_%04d.png", "start": ctx["start"], "fps": ctx["fps"], "count": n, "proc": ctx["node"]}
    return {"items": [item], "plane": p.get("plane", "engine"), "screen": True, "frames": hashes}


OPS = {"scatter": op_scatter, "crowd": op_crowd, "particles": op_particles}


def cook(nodes, ctx, cache, force=(), dry=False):
    """cook every node (inputs first); returns ({node: output}, report). A node whose key has a cached output is not
    cooked again; `force` re-cooks the named nodes anyway. `dry` only works out the keys and what would cook."""
    cache.mkdir(parents=True, exist_ok=True)
    keys, outs, cooked, cached, secs = {}, {}, [], [], {}
    script = hashlib.sha256(GN_SCRIPT.read_bytes()).hexdigest()[:12]
    for n in order(nodes):
        node = nodes[n]
        op = node.get("op")
        if op not in VERSION:
            raise ValueError(f"proc: node {n!r} has unknown op {op!r} ({', '.join(VERSION)})")
        dep = {"op": op, "v": VERSION[op], "params": {k: v for k, v in node.items() if k != "in"}, "in": [keys[i] for i in inputs(node)]}
        if op == "crowd":
            dep["ctx"] = {"size": ctx["size"], "floor": ctx["floor"]}
        if op in ("gn_set", "rigid"):   # the render depends on the camera, the span and the script too
            dep.update(ctx={k: ctx[k] for k in ("size", "fps", "start", "frames", "camera", "floor")}, script=script)
        if op == "engine":   # the render depends on the span, the camera and every file of the project
            dep.update(ctx={k: ctx[k] for k in ("size", "fps", "start", "frames", "camera")}, project=_project_hash((ROOT / node["project"]).resolve()))
        key = f"{op}-{_h(dep)}"
        keys[n] = key
        f = cache / f"{key}.json"
        if f.exists() and n not in force:
            if not dry:
                outs[n] = json.loads(f.read_text())
            cached.append(n); continue
        if dry:
            cooked.append(n); continue
        t0 = time.time()
        c = {**ctx, "node": n, "key": key}
        res = op_gn_set({**node, "kind": "props"} if op == "rigid" else node, [outs[i] for i in inputs(node)], c, cache) if op in ("gn_set", "rigid") \
            else op_engine(node, [outs[i] for i in inputs(node)], c, cache) if op == "engine" else OPS[op](node, [outs[i] for i in inputs(node)], c)
        f.write_text(json.dumps(res))
        outs[n] = res; cooked.append(n); secs[n] = round(time.time() - t0, 2)
    return outs, {"cooked": cooked, "cached": cached, "keys": keys, "seconds": secs}


def apply(shot, outs):
    """write cooked outputs into a raw shot: crowd cast appended, items on compositor planes (earlier proc output replaced)"""
    shot["cast"] = [c for c in shot.get("cast", []) if c.get("solved") != "proc"]
    comp = shot.setdefault("comp", {})
    planes = comp.setdefault("planes", [])
    for pl in planes:
        pl["items"] = [it for it in pl.get("items", []) if "proc" not in it]
    depths = {"set3d": 40, "crowd": 1.12, "front": 0.8, "engine": 30}
    planes[:] = [pl for pl in planes if not pl.get("proc_plane")]   # depth planes a crowd made last time
    for n, o in outs.items():
        if o.get("cast"):
            shot["cast"] += o["cast"]
            for pid in sorted({c["plane"] for c in o["cast"]}):
                if not any(pl["id"] == pid for pl in planes):
                    d = float(pid.split("@")[1]) if "@" in pid else depths.get(pid, 1.12)
                    planes.append({"id": pid, "depth": d, "proc_plane": True})
        if o.get("items"):
            pl = next((x for x in planes if x["id"] == o["plane"]), None)
            if not pl:
                pl = {"id": o["plane"], "depth": depths.get(o["plane"], 0.8)}
                planes.append(pl)
            if o.get("screen"):
                pl["screen"] = True
            pl.setdefault("items", []).extend(o["items"])
    if not any(pl["id"] == "stage" for pl in planes):
        planes.append({"id": "stage", "depth": 1})
    if any(o.get("screen") for o in outs.values()):
        comp["zoom"] = "dolly"   # planes zoom in true perspective, as the 3D render does
    for pl in planes:
        if not pl.get("items"):
            pl.pop("items", None)
    return shot


def self_test(tmp):
    """the cache re-cooks only what changed, and a cook is a pure function of the graph"""
    import shutil
    tmp = Path(tmp); shutil.rmtree(tmp, ignore_errors=True)
    ctx = {"size": [1080, 1920], "fps": 30, "start": 0, "frames": 2, "camera": [[0, [540, 960, 1]]], "floor": 1500}
    g = {"spots": {"op": "scatter", "count": 8, "seed": 3}, "crowd": {"op": "crowd", "in": "spots", "seed": 5},
         "snow": {"op": "particles", "kind": "snow", "count": 20, "seed": 2}}
    o1, r1 = cook(g, ctx, tmp / "c")
    o2, r2 = cook(g, ctx, tmp / "c")
    g2 = json.loads(json.dumps(g)); g2["crowd"]["seed"] = 6
    o3, r3 = cook(g2, ctx, tmp / "c")
    g3 = json.loads(json.dumps(g)); g3["spots"]["count"] = 9
    o4, r4 = cook(g3, ctx, tmp / "c")
    o5, _ = cook(g, ctx, tmp / "fresh")
    bad = []
    if sorted(r1["cooked"]) != ["crowd", "snow", "spots"] or r2["cooked"]:
        bad.append({"first_then_cached": [r1, r2]})
    if r3["cooked"] != ["crowd"]:
        bad.append({"changed_crowd": r3})
    if sorted(r4["cooked"]) != ["crowd", "spots"]:
        bad.append({"changed_spots_recooks_downstream": r4})
    if json.dumps(o1, sort_keys=True) != json.dumps(o5, sort_keys=True):
        bad.append({"pure": "two fresh cooks differ"})
    if len(o1["spots"]["points"]) != 8 or len(o1["crowd"]["cast"]) != 8:
        bad.append({"counts": [len(o1["spots"]["points"]), len(o1["crowd"]["cast"])]})
    try:
        order({"a": {"op": "scatter", "in": "b"}, "b": {"op": "crowd", "in": "a"}})
        bad.append({"cycle": "accepted"})
    except ValueError:
        pass
    return bad, {"first": r1["cooked"], "again": r2["cooked"], "crowd_changed": r3["cooked"], "spots_changed": r4["cooked"]}


def gn_determinism(tmp):
    """the Geometry Nodes set renders the same pixels twice (a small frame, two separate Blender runs; the files differ
    only in the render time Blender stamps into them)"""
    import shutil
    from .commands import BLENDER
    if not BLENDER:
        return [], {"skipped": "Blender not installed"}
    tmp = Path(tmp); shutil.rmtree(tmp, ignore_errors=True); tmp.mkdir(parents=True)
    req = {"size": [216, 384], "fps": 30, "start": 0, "frames": [0], "camera": [[0, [540, 960, 1]]], "floor": 1500, "seed": 5, "line": 0.6}
    (tmp / "r.json").write_text(json.dumps(req))
    hs = []
    for k in ("a", "b"):
        r = subprocess.run([BLENDER, "-b", "--factory-startup", "--gpu-backend", "vulkan", "--python", str(GN_SCRIPT), "--", str(tmp / "r.json"), str(tmp / k)],
                           capture_output=True, text=True, timeout=900, cwd=str(ROOT))
        f = tmp / k / "f_0000.png"
        hs.append(pixel_hash(f) if f.exists() else f"failed: {(r.stderr or r.stdout)[-300:]}")
    return ([] if hs[0] == hs[1] and not hs[0].startswith("failed") else [{"gn_render_twice": hs}]), {"hashes": hs}
