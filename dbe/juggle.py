"""Juggling solver (WP-09): a siteswap pattern becomes props with ballistic flights and two hands that scoop, every
throw and catch on the beat grid of the film's score.

A shot asks for it with a "juggle" block (kept in shots.json, so re-solving after a tempo or voice change rewrites
the same output):

    "juggle": {"cast": 0, "pattern": "3", "start": "hi.end+0.2", "end": 9.0, "every": 1, "dwell": 1, "subdiv": 2,
               "height": null, "balls": [{"id": "j1", "color": "#e8603c"}, ...], "r": null}

- pattern: a vanilla siteswap ("3" cascade, "441", "531", "51", "4" fountain...). Odd throws cross to the other
  hand, even throws stay; "2" is a hold, "0" an empty beat. Ground-state patterns only (balls start in the hands).
- every: music beats per throw; dwell: how long a hand holds a ball before throwing it, in throws. Both are snapped
  so every throw and every catch falls on the grid (beat / subdiv) of score.json (bpm, offset_s).
- height: how far the highest throw rises above the throw point, in frame px (sets the props' gravity).

Output, all tagged "solved": "juggle" so a re-solve replaces it: one prop per ball (attach keys: held in a palm,
then "flight": "ballistic" with "arrive" on the grid), and the cast's IK keys for both arms (one per frame, a scoop
while carrying and a lift while empty). Everything is a pure function of the request: rerunning gives the same bytes.
"""
import json
import math

PALETTE = ["#e8603c", "#3c8ee8", "#f6c945", "#5fb85a", "#b05fd0", "#f08bb0", "#38b2ac"]
DIG = "0123456789abcdefghijklmnopqrstuvwxyz"


def parse(pattern):
    """a vanilla siteswap -> its throw values; raises ValueError if it is not juggleable"""
    p = str(pattern).strip().lower()
    if not p or any(c not in DIG for c in p):
        raise ValueError(f"siteswap {pattern!r}: use digits 0-9 and letters a-z (a = 10)")
    v = [DIG.index(c) for c in p]
    n = len(v)
    if sum(v) % n:
        raise ValueError(f"siteswap {pattern!r}: the average throw ({sum(v)}/{n}) must be a whole number of balls")
    land = sorted((i + s) % n for i, s in enumerate(v))
    if land != list(range(n)):
        raise ValueError(f"siteswap {pattern!r}: two balls would land on the same beat")
    return v


def balls_of(v):
    return sum(v) // len(v)


def schedule(v, throws):
    """which ball each throw carries, starting with every ball in the hands (ground state).
    Returns ([{"n", "hand", "s", "ball", "to_hand"} ...], balls); hands alternate R (even n), L (odd n)."""
    b = balls_of(v)
    arriving, out, fresh = {}, [], 0
    for n in range(throws):
        s = v[n % len(v)]
        if s == 0:
            if n in arriving:
                raise ValueError("a ball lands on an empty beat")
            continue
        if n in arriving:
            ball = arriving.pop(n)
        else:
            ball = fresh
            fresh += 1
            if fresh > b:
                raise ValueError(f"siteswap {''.join(DIG[x] for x in v)!r} is not a ground-state pattern: start it with a transition")
        hand = "R" if n % 2 == 0 else "L"
        to = hand if s % 2 == 0 else ("L" if hand == "R" else "R")
        out.append({"n": n, "hand": hand, "s": s, "ball": ball, "to_hand": to})
        arriving[n + s] = ball
    return out, b


def _snap(x, unit):
    return round(round(x / unit) * unit, 6)


def geometry(puppet):
    """hand stations in the puppet's artboard space (IK targets for the wrists) and the palm point on each hand"""
    P = puppet["parts"]
    hip = P.get("hip", {}).get("pivot") or [puppet["artboard"][0] / 2, puppet.get("ground", puppet["artboard"][1])]
    out = {}
    for h in ("R", "L"):
        sh, el, wr = P[f"upperarm_{h}"]["pivot"], P[f"forearm_{h}"]["pivot"], P[f"hand_{h}"]["pivot"]
        reach = math.dist(sh, el) + math.dist(el, wr)
        side = 1 if sh[0] >= hip[0] else -1
        out[h] = {"side": side, "reach": reach, "shoulder": sh,
                  "catch": [sh[0] + side * 0.45 * reach, sh[1] + 0.72 * reach],   # elbows by the sides, forearms out
                  "throw": [sh[0] + side * 0.12 * reach, sh[1] + 0.76 * reach],
                  "rest": list(wr), "bend": -side,                                   # elbows bend down, not out
                  "palm": [wr[0], wr[1] + 0.11 * reach]}
    return out


def _hand_path(events, geo, t, dwell_s, cycle_s):
    """where a wrist is at time t, from its sorted contact events [(t, "catch"|"throw")]"""
    c, th, reach = geo["catch"], geo["throw"], geo["reach"]
    dip, lift = 0.13 * reach, 0.10 * reach
    ev = list(events)
    if ev and ev[0][1] == "throw":           # it starts holding: a carry leads into the first throw
        ev.insert(0, (ev[0][0] - dwell_s, "catch"))
    if ev and ev[-1][1] == "throw":          # after the last throw the hand returns to the catch station
        ev.append((ev[-1][0] + max(0.2, cycle_s - dwell_s), "catch"))
    if not ev or t <= ev[0][0]:
        return list(c)
    for (t0, k0), (t1, k1) in zip(ev, ev[1:]):
        if t0 <= t <= t1:
            u = (t - t0) / (t1 - t0 or 1)
            e = u * u * (3 - 2 * u)
            if k0 == "catch" and k1 == "throw":       # carry: dip and drive up into the throw
                return [c[0] + (th[0] - c[0]) * e, c[1] + (th[1] - c[1]) * u + dip * math.sin(math.pi * u)]
            if k0 == "throw" and k1 == "catch":       # empty: rise out to meet the next ball
                return [th[0] + (c[0] - th[0]) * e, th[1] + (c[1] - th[1]) * u - lift * math.sin(math.pi * u)]
            a, b = (c if k0 == "catch" else th), (c if k1 == "catch" else th)
            return [a[0] + (b[0] - a[0]) * e, a[1] + (b[1] - a[1]) * e]
    return list(c)   # a hand that has caught its last ball keeps it at the catch station


def solve(req, puppet, place, beat_s, offset_s, fps, shot_start, shot_end):
    """the juggle block -> {"props", "ik", "contacts", "grid", "gravity"} (no file access: pure)"""
    v = parse(req.get("pattern", "3"))
    subdiv = max(1, int(req.get("subdiv", 2)))
    grid = beat_s / subdiv
    every = max(grid, _snap(float(req.get("every", 1)) * beat_s, grid))           # seconds per throw, on the grid
    dwell = max(grid, _snap(float(req.get("dwell", 1)) * every, grid))            # seconds a ball is held
    mins = min([s for s in v if s not in (0, 2)] or [3])
    if dwell >= mins * every - grid / 2:                                           # e.g. "1" throws need a short dwell
        dwell = max(grid, _snap(mins * every - max(grid, every / 2), grid))
    start = req.get("start", shot_start)
    t0 = offset_s + math.ceil((float(start) - offset_s) / grid - 1e-9) * grid      # first throw: the next grid point
    t0 = max(t0, offset_s + math.ceil((shot_start - offset_s) / grid - 1e-9) * grid)
    end = float(req.get("end", shot_end))
    n_throws = max(0, int(math.floor((end - t0) / every + 1e-9)) + 1)
    sched, b = schedule(v, n_throws)
    smax = max(v)
    # a throw is only made if its catch happens before the end: balls finish in the hands
    cut = next((i for i, x in enumerate(sched) if t0 + (x["n"] + x["s"]) * every - dwell > end + 1e-6), len(sched))
    sched = sched[:cut]   # stop at the first throw whose catch would fall after the end (later throws need its ball)
    geo = geometry(puppet)
    s_cast = place.get("s", 1)
    ci = int(req.get("cast", 0))
    height = float(req.get("height") or 1.7 * geo["R"]["reach"] * s_cast)          # apex of the highest throw, frame px
    t_hi = (smax - dwell / every) * every
    gravity = round(8 * height / (t_hi * t_hi), 3)
    r = float(req.get("r") or round(0.1 * geo["R"]["reach"] * s_cast, 1))
    balls = list(req.get("balls") or [])
    while len(balls) < b:
        balls.append({})
    balls = [{"id": bb.get("id") or f"ball{i + 1}", "color": bb.get("color") or PALETTE[i % len(PALETTE)], **{k: x for k, x in bb.items() if k not in ("id", "color")}}
             for i, bb in enumerate(balls[:b])]

    def palm(h, slot=0):
        p = geo[h]["palm"]
        return [round(p[0] - geo[h]["side"] * slot * 1.7 * r / s_cast, 2), round(p[1], 2)]

    # first holds: balls that start in a hand, ordered by their first throw
    first, held = {}, {"R": 0, "L": 0}
    for x in sched:
        if x["ball"] not in first:
            first[x["ball"]] = (x["hand"], held[x["hand"]])
            held[x["hand"]] += 1
    keys = {i: [] for i in range(b)}
    for i in range(b):
        if i in first:
            h, slot = first[i]
            keys[i].append([round(shot_start, 4), {"cast": ci, "part": f"hand_{h}", "at": palm(h, slot)}])
    events = {"R": [], "L": []}
    contacts = []
    for x in sched:
        tt = round(t0 + x["n"] * every, 6)
        if x["s"] == 2 and x["to_hand"] == x["hand"] and dwell >= every:   # a hold: no throw at all
            continue
        ta = round(tt + x["s"] * every - dwell, 6)
        keys[x["ball"]].append([tt, {"cast": ci, "part": f"hand_{x['to_hand']}", "at": palm(x["to_hand"]), "flight": "ballistic", "arrive": ta}])
        events[x["hand"]].append((tt, "throw"))
        events[x["to_hand"]].append((ta, "catch"))
        contacts.append({"t": tt, "kind": "throw", "hand": x["hand"], "ball": balls[x["ball"]]["id"]})
        contacts.append({"t": ta, "kind": "catch", "hand": x["to_hand"], "ball": balls[x["ball"]]["id"]})
    # balls resting in a hand at the end share the palm: spread them out in the order they arrived
    for h in ("R", "L"):
        rest = sorted((keys[i][-1][1].get("arrive", keys[i][-1][0]), i) for i in range(b) if keys[i] and keys[i][-1][1]["part"] == f"hand_{h}")
        for slot, (_, i) in enumerate(rest):
            keys[i][-1][1]["at"] = palm(h, slot)
    props = []
    for i, bb in enumerate(balls):
        pr = {"id": bb["id"], "r": r, "color": bb["color"], "gravity": gravity, "stretch": True, "squash": True, "smear": True,
              "impact": False, "solved": "juggle", "attach": keys[i]}
        pr.update({k: x for k, x in bb.items() if k not in ("id", "color")})
        props.append(pr)
    ik = {}
    f0, f1 = int(math.ceil(shot_start * fps - 1e-6)), int(math.floor(min(shot_end, end) * fps + 1e-6))
    let_go = 0.5   # after the end the arms ease back to their rest and the clips take over again
    for h in ("R", "L"):
        ev = sorted(events[h])
        keys = [[round(f / fps, 4), [round(c, 1) for c in _hand_path(ev, geo[h], f / fps, dwell, 2 * every)]] for f in range(f0, f1 + 1)]
        if end < shot_end and keys:
            last = keys[-1][1]
            for f in range(f1 + 1, int(math.floor(min(shot_end, end + let_go) * fps + 1e-6)) + 1):
                u = min(1.0, (f / fps - end) / let_go)
                e = u * u * (3 - 2 * u)
                keys.append([round(f / fps, 4), [round(last[i] + (geo[h]["rest"][i] - last[i]) * e, 1) for i in (0, 1)]])
            keys.append([round(keys[-1][0] + 1 / fps, 4), None])
        ik[f"arm_{h}"] = keys
    contacts.sort(key=lambda c: (c["t"], c["kind"]))
    on_grid = all(abs((c["t"] - offset_s) / grid - round((c["t"] - offset_s) / grid)) < 1e-6 for c in contacts)
    return {"props": props, "ik": ik, "ik_bend": {f"arm_{h}": geo[h]["bend"] for h in ("R", "L")}, "contacts": contacts, "grid": round(grid, 6), "throw_every": every, "dwell": dwell,
            "gravity": gravity, "balls": b, "pattern": "".join(DIG[x] for x in v), "on_grid": on_grid,
            "first_throw": round(t0, 6), "throws": sum(1 for c in contacts if c["kind"] == "throw")}


def apply(shot, result):
    """write a solve into a raw shots.json shot: replaces earlier juggle output, keeps everything else"""
    shot["props"] = [p for p in shot.get("props", []) if p.get("solved") != "juggle"] + result["props"]
    ci = None
    for p in result["props"]:
        for _, tg in p["attach"]:
            ci = tg.get("cast", ci)
    if ci is not None:
        c = shot["cast"][ci]
        tl = c.setdefault("timeline", {})
        tl["ik"] = {**{k: x for k, x in tl.get("ik", {}).items() if k not in result["ik"]}, **result["ik"]}
        tl["ik_bend"] = {**tl.get("ik_bend", {}), **result.get("ik_bend", {})}
        tl["ik_solved"] = "juggle"
    return shot


def self_test():
    ok = True
    notes = []
    for good in ("3", "441", "531", "51", "423", "4", "b"):
        try:
            parse(good)
        except ValueError as e:
            ok = False
            notes.append(f"{good}: {e}")
    for bad in ("432", "21", "3-", ""):
        try:
            parse(bad)
            ok = False
            notes.append(f"{bad} accepted")
        except ValueError:
            pass
    s, b = schedule(parse("3"), 9)
    ok &= b == 3 and [x["ball"] for x in s] == [0, 1, 2, 0, 1, 2, 0, 1, 2] and all(x["to_hand"] != x["hand"] for x in s)
    s, b = schedule(parse("441"), 6)
    ok &= b == 3 and [x["s"] for x in s] == [4, 4, 1, 4, 4, 1]
    try:
        schedule(parse("51"), 4)   # 51 is a ground-state 3-ball pattern
    except ValueError:
        ok = False
        notes.append("51 refused")
    pup = {"artboard": [600, 1000], "ground": 980, "parts": {
        "hip": {"pivot": [300, 560]}, "upperarm_R": {"pivot": [372, 350]}, "forearm_R": {"pivot": [378, 470]}, "hand_R": {"pivot": [380, 580]},
        "upperarm_L": {"pivot": [228, 350]}, "forearm_L": {"pivot": [222, 470]}, "hand_L": {"pivot": [220, 580]}}}
    a = solve({"pattern": "3", "start": 0.1, "end": 4}, pup, {"x": 540, "y": 1500, "s": 0.8}, 0.6, 0.0, 30, 0.0, 4.5)
    b2 = solve({"pattern": "3", "start": 0.1, "end": 4}, pup, {"x": 540, "y": 1500, "s": 0.8}, 0.6, 0.0, 30, 0.0, 4.5)
    ok &= a["on_grid"] and json.dumps(a, sort_keys=True) == json.dumps(b2, sort_keys=True) and a["first_throw"] == 0.3
    ok &= a["throws"] >= 5 and len(a["props"]) == 3
    return {"ok": bool(ok), "notes": notes, "throws": a["throws"], "gravity": a["gravity"]}
