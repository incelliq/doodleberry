"""Self-healing (plan 2.9) and layout auto-repair (plan 2.18).

`film.heal` renders, reads every failure (the QA bar, the measured layout checks, the visual lint), turns each into
a concrete edit of shots.json (or the script, when the voice itself must slow down), re-renders what changed and
repeats until the film passes or no known repair applies. Every edit is logged with the failure that caused it,
and the shots.json from before the first round is kept in build/shots.before_heal.json.

Known repairs (diagnose() maps failure -> repairs; apply() edits the raw shots.json):
- frozen stretch (no_still_over_0.5s): a shot animated on low steps goes back to 12 per second; a shot with no
  camera gets the slow float camera; cast without an idle clip gets one;
- text outside the safe area: the element is moved inside by exactly the overshoot (plus a margin), and shrunk when
  it is wider than the safe area;
- type too small: the element's size is raised to the platform minimum;
- reading time: a timed text block stays up for words / 3 + 1 s (within its shot);
- caption flow too fast (words per second): with revoice=True the script is re-voiced slower (length_scale);
- frame fill (too much bare ground): the cast in that shot is scaled up (feet stay on the floor), up to 1.6x;
- lint "head cut by the frame": an auto camera frames singles less tight; a static shot scales the character down
  and moves it in;
- lint "bubble over face": an auto camera leaves more headroom; otherwise the shot's lines go back to captions.
"""
import copy
import json
import re

SAFE = {"9:16": (64, 200, 960, 1560), "16:9": (96, 54, 1824, 1026)}
MIN_PX = {"9:16": 26, "16:9": 24}


def _texts(o):
    t = o.get("text")
    if t is None:
        t = o.get("label") or o.get("lines")
    if isinstance(t, list):
        t = " ".join(str(x) for x in t)
    return str(t or "")


def _elements(sh):
    for kind in ("overlays", "underlays"):
        for i, o in enumerate(sh.get(kind) or []):
            yield kind, i, o


def _shot_at(shots, t):
    return next((s for s in shots if s["start"] <= t < s["end"]), shots[-1])


def diagnose(rep, lint, shots_res, size, script=None):
    """failures -> [{check, shot, what, edit: (kind, ...)}]"""
    W, H = size; asp = "9:16" if H > W else "16:9"; x0, y0, x1, y1 = SAFE[asp]
    shots = shots_res["shots"]; out = []
    checks = dict(rep.get("checks") or {}); lay = rep.get("layout") or {}
    checks.update({k: v for k, v in (lay.get("checks") or {}).items() if k not in checks})
    # frozen stretches
    for a, b in [(f["start"], f["start"] + f["len"]) for f in rep.get("frozen_stretches_over_0.5s") or []]:
        sh = _shot_at(shots, (a + b) / 2); st = sh.get("style") or {}
        if st.get("step") and st["step"] < 8:
            out.append({"check": "no_still_over_0.5s", "shot": sh["id"], "what": f"animated on {st['step']}s per second: back to 12", "edit": ("style", "step", 12)})
        elif not sh.get("camera") and not sh.get("camera_auto") and not st.get("float"):
            out.append({"check": "no_still_over_0.5s", "shot": sh["id"], "what": "slow float camera so no frame stands still", "edit": ("style", "float", True)})
        else:
            for ci, c in enumerate(sh.get("cast") or []):
                if not any(k.get("clip") == "idle" for k in (c.get("timeline") or {}).get("clips", [])):
                    out.append({"check": "no_still_over_0.5s", "shot": sh["id"], "what": f"idle life for cast {ci}", "edit": ("idle", ci)})
    # text outside the safe area / too small (boxes are words or lines of an element)
    text = lay.get("text") or {}
    moves = {}
    for b in text.get("outside_safe") or []:
        sh = _shot_at(shots, b["t"])
        for kind, i, o in _elements(sh):
            if b["text"] and b["text"] in _texts(o):
                dx = (x0 + 8 - b["x0"]) if b["x0"] < x0 else ((x1 - 8 - b["x1"]) if b["x1"] > x1 else 0)
                dy = (y0 + 8 - b["y0"]) if b["y0"] < y0 else ((y1 - 8 - b["y1"]) if b["y1"] > y1 else 0)
                k = (sh["id"], kind, i); m = moves.setdefault(k, [0, 0, 0])
                m[0] = dx if abs(dx) > abs(m[0]) else m[0]; m[1] = dy if abs(dy) > abs(m[1]) else m[1]
                m[2] = max(m[2], b["x1"] - b["x0"])
                break
    for (sid, kind, i), (dx, dy, wdt) in moves.items():
        out.append({"check": "text_in_safe_area", "shot": sid, "what": f"{kind}[{i}] moved {round(dx)}, {round(dy)} px into the safe area", "edit": ("move", kind, i, dx, dy)})
    for b in text.get("too_small") or []:
        sh = _shot_at(shots, b["t"])
        for kind, i, o in _elements(sh):
            if b["text"] and b["text"] in _texts(o) and o.get("size"):
                out.append({"check": "type_size", "shot": sh["id"], "what": f"{kind}[{i}] type {b['px']} px -> {MIN_PX[asp]} px", "edit": ("scale", kind, i, MIN_PX[asp] / max(1, b["px"]) * 1.05)})
                break
    # reading time
    rd = lay.get("reading") or {}
    for r in rd.get("too_short") or []:
        sh = next(s for s in shots if s["id"] == r["shot"])
        for kind, i, o in _elements(sh):
            if r["text"] and _texts(o).startswith(r["text"][:20]) and o.get("start") is not None:
                out.append({"check": "reading_time", "shot": sh["id"], "what": f"{kind}[{i}] held {r['needs_s']} s for its words", "edit": ("hold", kind, i, r["needs_s"])})
                break
    if rd.get("caption_words_per_s", 0) > 3.2 and script is not None:
        out.append({"check": "reading_time", "shot": "*", "what": f"captions flow at {rd['caption_words_per_s']} words/s: re-voice slower",
                    "edit": ("revoice", round(min(1.3, rd["caption_words_per_s"] / 3.0), 3))})
    # frame fill
    ff = lay.get("frame_fill") or {}
    for sid, bare in (ff.get("per_shot_mean") or {}).items():
        if bare > 0.40:
            sh = next(s for s in shots if s["id"] == sid)
            if sh.get("cast"):
                out.append({"check": "frame_fill", "shot": sid, "what": f"bare ground {bare:.0%}: cast scaled up", "edit": ("grow", min(1.25, 1 + (bare - 0.38)))})
    # visual lint errors
    for it in (lint or {}).get("issues", []):
        if it.get("level") != "error":
            continue
        sh = next((s for s in shots if s["id"] == it["shot"]), None)
        if not sh:
            continue
        if it["check"] == "off-screen":
            if sh.get("camera_auto"):
                out.append({"check": "lint:head cut", "shot": sh["id"], "what": "auto camera frames singles less tight", "edit": ("camera_auto", "zoom_single", -0.2)})
            else:
                ci = next((ci for ci, c in enumerate(sh.get("cast") or []) if (c.get("speaker") or "") == it["who"]), None)
                if ci is not None:
                    out.append({"check": "lint:head cut", "shot": sh["id"], "what": f"{it['who']} scaled down and moved in", "edit": ("shrink", ci)})
        elif it["check"] == "bubble over face":
            if sh.get("camera_auto"):
                out.append({"check": "lint:bubble over face", "shot": sh["id"], "what": "auto camera leaves more room for bubbles", "edit": ("camera_auto", "zoom_bubble", -0.15)})
            else:
                out.append({"check": "lint:bubble over face", "shot": sh["id"], "what": "lines go back to captions in this shot", "edit": ("bubbles_off",)})
    # one repair per (shot, edit) even if several frames asked for it
    seen, uniq = set(), []
    for r in out:
        k = (r["shot"], json.dumps(r["edit"][:3]))
        if k not in seen:
            seen.add(k); uniq.append(r)
    return uniq


def apply(raw, repairs, resolved, size):
    """edit a copy of the raw shots.json; returns (new, script_length_scale or None)"""
    W, H = size; s = copy.deepcopy(raw); by_id = {sh["id"]: sh for sh in s["shots"]}; res = {sh["id"]: sh for sh in resolved["shots"]}
    revoice = None
    for r in repairs:
        e = r["edit"]; sh = by_id.get(r["shot"])
        if e[0] == "revoice":
            revoice = e[1]; continue
        if sh is None:
            continue
        if e[0] == "style":
            sh.setdefault("style", {})[e[1]] = e[2]
        elif e[0] == "idle":
            tl = sh["cast"][e[1]].setdefault("timeline", {}); tl.setdefault("clips", []).insert(0, {"clip": "idle", "start": 0, "fadeIn": 0})
        elif e[0] == "move":
            o = sh[e[1]][e[2]]
            o["x"] = round((o["x"] if isinstance(o.get("x"), (int, float)) else W / 2) + e[3], 1)
            if isinstance(o.get("y"), (int, float)):
                o["y"] = round(o["y"] + e[4], 1)
            elif e[4]:
                r["what"] += " (no y to move: left as is)"
        elif e[0] == "scale":
            o = sh[e[1]][e[2]]; o["size"] = round(o["size"] * e[3], 1)
        elif e[0] == "hold":
            o = sh[e[1]][e[2]]; ro = res[sh["id"]][e[1]][e[2]]
            o["end"] = round(min(res[sh["id"]]["end"], ro["start"] + e[3]), 3); o.pop("until", None)
        elif e[0] == "grow":
            for c in sh.get("cast") or []:
                if isinstance(c.get("place"), dict):
                    c["place"]["s"] = round(min(1.6, c["place"].get("s", 1) * e[1]), 3)
        elif e[0] == "camera_auto":
            ca = sh["camera_auto"] if isinstance(sh["camera_auto"], dict) else {}
            dflt = {"zoom_single": 1.9, "zoom_bubble": 1.5}[e[1]]
            ca[e[1]] = round(max(1.1, ca.get(e[1], dflt) + e[2]), 2); sh["camera_auto"] = ca
        elif e[0] == "shrink":
            c = sh["cast"][e[1]]
            if isinstance(c.get("place"), dict):
                p = c["place"]; p["s"] = round(p.get("s", 1) * 0.88, 3); p["x"] = round(W / 2 + (p.get("x", W / 2) - W / 2) * 0.85, 1)
        elif e[0] == "bubbles_off":
            sh["bubbles"] = False
    return s, revoice


def failures(rep, lint):
    """names of everything failing: QA checks, layout checks (advisory included), lint errors"""
    f = [k for k, v in (rep.get("checks") or {}).items() if v is False]
    lay = (rep.get("layout") or {}).get("checks") or {}
    f += [k for k, v in lay.items() if v is False and k not in f]
    f += sorted({"lint:" + i["check"] for i in (lint or {}).get("issues", []) if i.get("level") == "error"})
    return f
