"""Series production (WP-28): a series bible, episodes planned from it, and continuity checked across the films.

**The bible** (series/<id>/bible.json): the series' format (a film.from_template format), its cast by role (puppet,
voice), its posting cadence, the **props** that persist (who owns one, the episode it first appears in, the episode it
is lost in, how it is drawn and where it is held), the **running gags** as data (a line for a role and/or an acting
direction, with a cadence: every n episodes, starting at one) and what the characters **learn** (a fact with its
keywords, the episode a role learns it in).

**Planning** (`plan_episodes`): each episode's brief (title, topic, exchanges) gets its number, its posting date from
the cadence, the gags due that episode, the props it must carry, and the knowledge each role has by then.

**Continuity** (`check`): read from the episodes' own films (so a hand edit is checked as well as a generated one):
the same puppet and voice for a role in every episode; every persisting prop on screen with its owner from the
episode it appears in until it is lost, and never before; gags on their cadence and never two episodes running when
the cadence is longer; nobody using a fact before the episode they learn it, and the learner not asking again about
something already learnt; and episodes within the series' length band.
"""
import datetime as dt
import json
import re
from pathlib import Path

DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def load(d):
    return json.loads((Path(d) / "bible.json").read_text())


def dates(cad, n):
    """posting dates for n episodes: the first on or after cad.start that falls on cad.day, then every cad.every_weeks"""
    d0 = dt.date.fromisoformat(cad["start"]); want = DAYS.index(cad.get("day", "thu"))
    while d0.weekday() != want:
        d0 += dt.timedelta(days=1)
    return [(d0 + dt.timedelta(weeks=k * cad.get("every_weeks", 1))).isoformat() for k in range(n)]


def gag_due(g, n):
    ev = g.get("every", 1); st = g.get("from", 1)
    return n >= st and (n - st) % ev == 0


def props_for(bible, n):
    return [p for p in bible.get("props", []) if p["introduced_in"] <= n and (not p.get("lost_in") or n < p["lost_in"])]


def knows(bible, role, n):
    return [k for k in bible.get("learns", []) if k["role"] == role and k["episode"] < n]


def plan_episodes(bible, briefs):
    """-> episodes [{n, name, date, title, brief, gags, props, knows}]"""
    ds = dates(bible["cadence"], len(briefs)); out = []
    for i, (b, d) in enumerate(zip(briefs, ds), 1):
        out.append({"n": i, "name": f"{bible['id']}-e{i:02d}", "date": d, "title": b["title"], "brief": b,
                    "gags": [g["id"] for g in bible.get("gags", []) if gag_due(g, i)], "props": [p["id"] for p in props_for(bible, i)],
                    "learns": [k["fact"] for k in bible.get("learns", []) if k["episode"] == i],
                    "knows": {r: [k["fact"] for k in knows(bible, r, i)] for r in bible["cast"]}})
    return out


def brief_for(bible, ep):
    """the film.from_template brief of one episode: its exchanges, with due gag lines placed before the button"""
    b = dict(ep["brief"]); ex = list(b["exchanges"])
    for g in bible.get("gags", []):
        if g["id"] in ep["gags"] and g.get("line"):
            role, text = g["line"]["role"], g["line"]["text"]
            if role == "expert":   # an expert line rides on the last answer
                last = dict(ex[-1]); last["a"] = f"{last['a']} {text}"; ex[-1] = last
            else:
                b["button"] = f"{text} {b.get('button', '')}".strip()
    b["exchanges"] = ex
    b["cast"] = {r: c["id"] for r, c in bible["cast"].items()}; b["voices"] = {c["id"]: c["voice"] for c in bible["cast"].values()}
    b["title"] = ep["title"]
    return b


def prop_entries(bible, ep, shots):
    """the persisting props, held by their owners in every shot their owner is in"""
    out = []
    for sh in shots:
        roles = {c.get("speaker"): k for k, c in enumerate(sh.get("cast", []))}
        props = []
        for p in props_for(bible, ep["n"]):
            owner = bible["cast"][p["owner"]]["id"]
            if owner in roles:
                props.append({"id": p["id"], "r": p.get("r", 30), "svg": p["svg"],
                              "attach": [[0, {"cast": roles[owner], "part": p.get("part", "hand_L"), **({"at": p["at"]} if p.get("at") else {})}]]})   # "at" is a point in the puppet's artboard; without it, the part's own point
        out.append(props)
    return out


def directions(bible, ep):
    return " ".join(g["direction"] for g in bible.get("gags", []) if g["id"] in ep["gags"] and g.get("direction"))


def check(bible, films):
    """continuity across the episodes' films: films = [(n, script, shots, length_s or None)] -> [problems]"""
    probs = []
    who = {}
    for n, sc, sh, ln in films:
        for role, c in bible["cast"].items():
            v = (sc.get("speakers") or {}).get(c["id"], {}).get("voice")
            pups = {x["puppet"] for s in sh["shots"] for x in s.get("cast", []) if x.get("speaker") == c["id"]}
            if v and v != c["voice"]:
                probs.append(f"e{n}: {c['id']} speaks with {v}, not {c['voice']}")
            for p in pups:
                if p != c["puppet"]:
                    probs.append(f"e{n}: {c['id']} is drawn from {p}, not {c['puppet']}")
        on = {p["id"] for s in sh["shots"] for p in s.get("props") or [] if p["id"] in {x["id"] for x in bible.get("props", [])}}
        for p in bible.get("props", []):
            live = p["introduced_in"] <= n and (not p.get("lost_in") or n < p["lost_in"])
            owner = bible["cast"][p["owner"]]["id"]
            owner_on = any(x.get("speaker") == owner for s in sh["shots"] for x in s.get("cast", []))
            if live and owner_on and p["id"] not in on:
                probs.append(f"e{n}: {p['id']} missing ({owner} has it from e{p['introduced_in']})")
            if not live and p["id"] in on:
                probs.append(f"e{n}: {p['id']} on screen " + (f"before e{p['introduced_in']}" if n < p["introduced_in"] else f"after it was lost in e{p['lost_in']}"))
        text = {c["id"]: " ".join(l["text"] for l in sc.get("lines", []) if l.get("speaker") == c["id"]).lower() for c in bible["cast"].values()}
        for k in bible.get("learns", []):
            rid = bible["cast"][k["role"]]["id"]; kw = [w.lower() for w in k["keywords"]]
            said = [l for l in sc.get("lines", []) if l.get("speaker") == rid and any(w in l["text"].lower() for w in kw)]
            if n < k["episode"] and said:
                probs.append(f"e{n}: {rid} speaks of {k['fact']} before learning it in e{k['episode']}")
            if n > k["episode"] and any(l["text"].strip().endswith("?") for l in said):
                probs.append(f"e{n}: {rid} asks about {k['fact']} again, learnt in e{k['episode']}")
        for g in bible.get("gags", []):
            mark = (g.get("line") or {}).get("text") or g.get("marker")
            present = bool(mark) and mark.lower()[:24] in " ".join(text.values())
            if gag_due(g, n) and not present and g.get("line"):
                probs.append(f"e{n}: gag {g['id']} is due and missing")
            if present and not gag_due(g, n):
                probs.append(f"e{n}: gag {g['id']} off its cadence (every {g.get('every', 1)} from e{g.get('from', 1)})")
        band = bible.get("length_s")
        if band and ln and not band[0] <= ln <= band[1]:
            probs.append(f"e{n}: {ln:.1f} s, outside {band[0]} to {band[1]} s")
    return probs


# ---------------- research and the fact gate, per episode ----------------
def facts_hash(brief):
    """the hash a gate review is tied to: the episode's facts and the exchanges (the lines that cite them)"""
    import hashlib
    key = {"facts": brief.get("facts", {}), "exchanges": brief.get("exchanges", [])}
    return hashlib.sha256(json.dumps(key, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def research_log(bible, ep, review):
    """research_log.md for one episode, from its brief's sources and the fresh fact-gate reviewer's report on it
    (review: {"verdict", "sources": [{url, loaded, quote_found, note}], "issues", "counter_evidence"} or None)"""
    b = ep["brief"]; facts = b.get("facts", {}); rv = review or {}
    by_url = {s.get("url"): s for s in rv.get("sources", [])}
    out = [f"# Research log: {bible['title']} #{ep['n']}: {ep['title']}", "",
           f"Series research ({bible['id']}); {('reviewed ' + rv['at']) if rv.get('at') else 'no gate review yet'}. Review level: standard.", "",
           "## Searches", f"- {b.get('topic', ep['title'])}: the series' sources ({bible.get('sources_note', 'see the bible')}).", "",
           "## Sources"]
    for fid, f in facts.items():
        s = f.get("source") or {}; r = by_url.get(s.get("url"), {})
        state = ("loaded" if r.get("loaded") else "not loaded") + (f", quote {'found' if r.get('quote_found') is True else r.get('quote_found')}" if "quote_found" in r else "") if r else "not yet reviewed"
        out.append(f"- **{fid}** ({s.get('url')}): \"{s.get('quote')}\". Supports: {f.get('claim')} Reviewer: {state}" + (f"; {r['note'].rstrip('.')}" if r.get("note") else "") + ".")
    nb = lambda i: str(i.get("problem", "")).startswith("(Non-blocking)")
    out += ["", "## Rejected"]
    out += [f"- {i.get('fact')}: {i.get('problem')} Fix: {i.get('fix')}" for i in rv.get("issues", []) if not nb(i)] or ["- nothing rejected by the gate review"]
    out += ["", "## Open questions"]
    out += ([f"- {s.get('url')}: {s.get('note') or 'did not load'}" for s in rv.get("sources", []) if not s.get("loaded")]
            + [f"- {i.get('fact')}: {i.get('problem')} Suggested: {i.get('fix')}" for i in rv.get("issues", []) if nb(i)]) or ["- none recorded"]
    out += ["", "## Counter-evidence"]
    out += [f"- {c}" for c in rv.get("counter_evidence", [])] or ["- not yet searched (the gate review records it)"]
    return "\n".join(out) + "\n"
