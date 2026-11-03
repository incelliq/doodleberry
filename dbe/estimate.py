"""Render time estimates (WP-20): frames times the renderer's rate, measured on this machine.

Every shot render appends a row to out/render_log.jsonl (frames, how many were captured and how many reused, seconds,
and what makes a shot slow: boil, raster parts, a static plate, camera moves), and every film render a row with its
total. The model, fitted on those rows:

    shot seconds = a + k * probe * captured + c * reused          (probe: the shot's own rate, measured: below)
    shot seconds = a + m(kind) * b * captured + c * reused        (no probe: a rate by kind of shot: boil, plate, raster)
    film seconds = sum of its shots + o0 + o1 * film length        (assembly, sound, captions, QA)

A probe (tools/probe_rate.mjs) renders a few frames of the shot itself the way the renderer will (four browsers,
the plate when there is one) and times them: sets and effects differ by a factor of three or more per frame, which
no rate by kind of shot captures. Probes are cached by the shot's render hash (out/probe_cache.json), and each
render's log row carries its probe, so k is fitted on probe-and-render pairs.

The frames a shot will capture come from its last render (same frames), or, for a new shot, from its step rate
(12 drawings a second on twos) or all its frames. With exclude=<film>, that film's own rows are left out, so an
estimate can be checked against a render it has not seen.
"""
import json
import math
from pathlib import Path

import numpy as np

from . import ROOT

LOG = ROOT / "out" / "render_log.jsonl"
PROBES = ROOT / "out" / "probe_cache.json"
DEFAULT = {"a": 8.0, "b": 0.25, "c": 0.03, "o0": 25.0, "o1": 1.5}   # before anything is measured here


def rows(exclude=None):
    out = []
    if LOG.exists():
        for line in LOG.read_text().splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if exclude and r.get("film") == exclude:
                continue
            out.append(r)
    return out


def kind(r):
    return ("boil" if r.get("boil") else "") + ("+plate" if r.get("plate") else "") + ("+raster" if r.get("raster") else "") or "plain"


def fit(exclude=None):
    """the model's constants from the log (DEFAULT where there is too little)"""
    R = [r for r in rows(exclude) if r.get("renderer", "svg") == "svg" and r.get("kind") != "film" and r.get("frames") and "reused" in r]
    m = dict(DEFAULT); m["kinds"] = {}; m["shots_measured"] = len(R); m["k"] = 1.0; m["a_probe"] = DEFAULT["a"]; m["c_probe"] = DEFAULT["c"]
    P = [r for r in R if r.get("ms_probe")]; m["probe_pairs"] = len(P)
    if len(P) >= 3:   # seconds = a + k * probe * captured + c * reused
        X = np.array([[1.0, r["ms_probe"] / 1000 * (r["frames"] - r["reused"]), r["reused"]] for r in P]); y = np.array([r["seconds"] for r in P])
        sol, *_ = np.linalg.lstsq(X, y, rcond=None)
        if sol[1] > 0:
            m["a_probe"], m["k"], m["c_probe"] = max(0.0, float(sol[0])), float(sol[1]), max(0.0, float(sol[2]))
    if len(R) >= 3:
        X = np.array([[1.0, r["frames"] - r["reused"], r["reused"]] for r in R]); y = np.array([r["seconds"] for r in R])
        sol, *_ = np.linalg.lstsq(X, y, rcond=None)
        a, b, c = (float(v) for v in sol)
        if b > 0:
            m.update(a=max(0.0, a), b=b, c=max(0.0, c))
    for r in R:
        cap = r["frames"] - r["reused"]
        if cap > 0:
            m["kinds"].setdefault(kind(r), []).append((r["seconds"] - m["a"] - m["c"] * r["reused"]) / (m["b"] * cap))
    m["kinds"] = {k: round(float(np.median(v)), 3) for k, v in m["kinds"].items()}
    # after the shots (assembly, captions, sound, QA, lint): a film's seconds less the shots it rendered in that run.
    # Lint, foley and the layout probes draw frames in the browser, so that part grows with the film's frames times
    # how costly they are to draw (the shots' probes): after = o0 + o1 * frames + o2 * sum(frames * probe)
    pts = after_points(exclude)
    m["after_by_film"] = {f: p["after"] for f, p in pts.items()}
    P = [p for p in pts.values() if p.get("probe_work") is not None]
    if len(P) >= 3:
        X = np.array([[1.0, p["frames"], p["probe_work"]] for p in P]); y = np.array([p["after"] for p in P])
        sol, *_ = np.linalg.lstsq(X, y, rcond=None)
        m["o0"], m["o1f"], m["o2"] = (float(v) for v in sol)
    if len(pts) >= 2:
        X = np.array([[1.0, p["length"]] for p in pts.values()]); y = np.array([p["after"] for p in pts.values()]); sol, *_ = np.linalg.lstsq(X, y, rcond=None)
        m["o0_len"], m["o1"] = max(0.0, float(sol[0])), max(0.0, float(sol[1]))
    m["films_measured"] = len(pts); m["films_with_probes"] = len(P)
    return m


def after_points(exclude=None):
    """per film, its last render that redid shots: seconds after the shots, frames, and frames times probe rate"""
    R = rows(); out = {}
    for f in [r for r in R if r.get("kind") == "film" and r.get("film") != exclude]:
        t1 = f["at"]; t0 = t1 - f["seconds"] - 1
        sh = [r for r in R if r.get("film") == f["film"] and r.get("kind") != "film" and t0 <= r.get("at", 0) <= t1 + 1]
        if not sh:
            continue
        work = sum(r["frames"] * r["ms_probe"] / 1000 for r in sh) if all(r.get("ms_probe") for r in sh) else None
        out[f["film"]] = {"after": f["seconds"] - sum(r["seconds"] for r in sh), "length": f.get("length_s") or 0,
                          "frames": sum(r["frames"] for r in sh), "probe_work": work}
    return out


def shot_seconds(m, feat, history=None, probe_ms=None):
    """-> (seconds, captured frames, how the captured frames were guessed, the kind of shot)"""
    frames = feat["frames"]
    if history and history.get("frames") == frames and "reused" in history:
        cap, basis = frames - history["reused"], "its last render"
        plate = history.get("plate", False)
    else:
        if feat.get("step"):
            cap, basis = min(frames, math.ceil(frames * feat["step"] / feat.get("fps", 30)) + 1), f"its step ({feat['step']} drawings a second)"
        else:
            cap, basis = frames, "every frame"
        plate = not feat.get("camera") and not feat.get("comp")
    k = kind({**feat, "plate": plate})
    if probe_ms:
        return round(m["a_probe"] + m["k"] * probe_ms / 1000 * cap + m["c_probe"] * (frames - cap), 1), cap, basis + "; rate probed", k
    mult = m["kinds"].get(k) or m["kinds"].get(kind({**feat, "plate": False})) or 1.0
    secs = m["a"] + mult * m["b"] * cap + m["c"] * (frames - cap)
    return round(secs, 1), cap, basis, k


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


def last_render(film, shot, exclude=None):
    rs = [r for r in rows(exclude) if r.get("film") == film and r.get("shot") == shot and "reused" in r]
    return rs[-1] if rs else None
