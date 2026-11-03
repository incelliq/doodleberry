"""Render time estimates (WP-20): frames times the renderer's rate, measured on this machine.

Every shot render appends a row to out/render_log.jsonl (frames, captured and reused, seconds, bake seconds, its
probe), and every film render a row with its total. A film's render is its shots' bakes and renders plus the work
after the shots (joining, captions, sound, mux, QA). The estimate uses what has been measured here, best first:

- a shot already rendered here with the same frames: its last render and bake times;
- otherwise its **probe**: tools/probe_rate.mjs renders a few frames of the shot the way the renderer will (four
  browsers, the plate when there is one) and times capturing, reusing and encoding a frame and starting up, and a
  1- and a 31-frame bake time the acting. render = start-up + k * (capture * captured + reuse * reused + encode *
  frames), with k fitted on probe-and-render pairs (about 0.9 here); sets and effects differ by a factor of three or
  more per frame, which is why the shot itself is timed;
- the work after the shots: this film's own last render (its seconds less its shots' bakes and renders), else a
  rough o0 + o1 * film length from the other films (it depends on how detailed the frames are to encode, captions,
  sound and QA, which vary by a factor of three between films of the same length).

`as_of` limits the log to rows written before a time, so an estimate can be checked against a render it did not
see; `exclude` leaves a film's rows out (an estimate for a film never rendered here).
"""
import json
import math

import numpy as np

from . import ROOT

LOG = ROOT / "out" / "render_log.jsonl"
PROBES = ROOT / "out" / "probe_cache.json"
DEFAULT = {"k": 0.9, "o0": 25.0, "o1": 2.5, "a": 8.0, "b": 0.3}


def rows(exclude=None, before=None):
    out = []
    if LOG.exists():
        for line in LOG.read_text().splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if (exclude and r.get("film") == exclude) or (before and r.get("at", 0) >= before):
                continue
            out.append(r)
    return out


def probe_get(key):
    try:
        return json.loads(PROBES.read_text()).get(key)
    except Exception:
        return None


def probe_put(key, val):
    try:
        d = json.loads(PROBES.read_text())
    except Exception:
        d = {}
    d[key] = val; PROBES.parent.mkdir(parents=True, exist_ok=True); PROBES.write_text(json.dumps(d))


def probe_latest(film, shot):
    """the newest probe of a shot whatever its hash (for rows written before probes were logged with them)"""
    try:
        d = json.loads(PROBES.read_text())
    except Exception:
        return None
    hits = [v for k, v in d.items() if k.startswith(f"{film}:{shot}:")]
    return hits[-1] if hits else None


def work(p, frames, captured):
    """seconds of capturing, reusing and encoding, as the probe measured them (all workers together)"""
    return (p["ms_per_frame"] * captured + p.get("ms_reuse", 0) * (frames - captured) + p.get("ms_encode", 0) * frames) / 1000


def bake_of(r):
    if r.get("bake_s") is not None:
        return r["bake_s"]
    p = probe_latest(r.get("film"), r.get("shot")) or {}
    return p.get("bake_s_fixed", 0) + p.get("bake_ms_frame", 0) * r.get("frames", 0) / 1000


def film_runs(exclude=None, before=None):
    """per film render: its row, the shot rows of that run, and the seconds after the shots (bakes taken out)"""
    R = rows(exclude, before); out = []
    for f in [r for r in R if r.get("kind") == "film"]:
        t1 = f["at"]; t0 = t1 - f["seconds"] - 1
        sh = [r for r in R if r.get("film") == f["film"] and r.get("kind") != "film" and "reused" in r and t0 <= r.get("at", 0) <= t1 + 1]
        out.append({"film": f["film"], "row": f, "shots": sh, "after": f["seconds"] - sum(r["seconds"] + bake_of(r) for r in sh), "length": f.get("length_s") or 0})
    return out


def fit(exclude=None, before=None):
    m = dict(DEFAULT); R = [r for r in rows(exclude, before) if r.get("kind") != "film" and "reused" in r and r.get("frames")]
    ratios = []
    for r in R:
        p = r.get("probe") or probe_latest(r["film"], r["shot"])
        if p and p.get("ms_encode") is not None:
            w = work(p, r["frames"], r["frames"] - r["reused"])
            if w > 0:
                ratios.append((r["seconds"] - p.get("ms_startup", 0) / 1000) / w)
    if len(ratios) >= 3:
        m["k"] = float(np.median(ratios))
    m["probe_pairs"] = len(ratios)
    runs = [x for x in film_runs(exclude, before) if x["shots"]]
    m["after_by_film"] = {}
    for x in runs:
        m["after_by_film"][x["film"]] = round(x["after"], 1)   # later runs overwrite earlier ones
    pts = list({x["film"]: (x["length"], x["after"]) for x in runs}.values())
    if len(pts) >= 2 and len({p[0] for p in pts}) >= 2:
        sol, *_ = np.linalg.lstsq(np.array([[1.0, p[0]] for p in pts]), np.array([p[1] for p in pts]), rcond=None)
        m["o0"], m["o1"] = max(0.0, float(sol[0])), max(0.0, float(sol[1]))
    m["films_measured"] = len(pts)
    return m


def last_render(film, shot, exclude=None, before=None):
    rs = [r for r in rows(exclude, before) if r.get("film") == film and r.get("shot") == shot and "reused" in r]
    return rs[-1] if rs else None


def captured_guess(feat, hist):
    frames = feat["frames"]
    if hist and hist.get("frames") == frames:
        return frames - hist["reused"], "as its last render"
    if feat.get("step"):
        return min(frames, math.ceil(frames * feat["step"] / feat.get("fps", 30)) + 1), f"its step ({feat['step']} drawings a second)"
    return frames, "every frame"


def shot_seconds(m, feat, hist=None, probe=None):
    """-> {seconds, render_s, bake_s, captured, basis}"""
    frames = feat["frames"]; cap, cap_basis = captured_guess(feat, hist)
    if hist and hist.get("frames") == frames:
        render, basis = hist["seconds"], "its last render here"
        bake = hist.get("bake_s") if hist.get("bake_s") is not None else (probe or {}).get("bake_s_fixed", 0) + (probe or {}).get("bake_ms_frame", 0) * frames / 1000
    elif probe and probe.get("ms_encode") is not None:
        render = probe.get("ms_startup", 0) / 1000 + m["k"] * work(probe, frames, cap); basis = f"probed ({cap_basis})"
        bake = probe.get("bake_s_fixed", 0) + probe.get("bake_ms_frame", 0) * frames / 1000
    else:
        render = m["a"] + m["b"] * cap; basis = f"no probe: a rough rate ({cap_basis})"; bake = 1.0
    return {"seconds": round(render + bake, 1), "render_s": round(render, 1), "bake_s": round(bake, 1), "captured": cap, "basis": basis}
