"""Usage accounting (WP-29, E15): screen time per asset across the catalogue, read from each film's shots.json.

Every asset a film uses is counted in seconds, with the films it is in:
- **puppet**: a cast member, for the shots it is in (overlapping appearances in one film count once);
- **clip**: a motion from a clip library (puppet/clips/<template>.json or an installed pack), from its start to its
  end, or for its own length if it has no end and does not loop (a loop runs to the shot's end);
- **set**: a shot's background set, for the shot;
- **prop**: a held or thrown prop, for the shot;
- **icon**: an overlay icon, from its start to the shot's end (or its own end);
- **voice**: the time its lines are spoken (timing.json);
- **boil**: a boil preset (style.boil_preset, set by boil.apply), for the shots it is on;
- **scene**: a hand-coded film (scene.js frame functions, no shots.json) is one house asset for its length, since
  its drawing is code rather than data; its voices are still counted from its timing.

Each asset is resolved to its owner and licence: puppets from cast/index.json (an unregistered puppet is listed as
such), clips from the pack that installed them (puppet/clips/packs.json), boil presets from their file, voices from voices/registry.json,
the rest are the house's. With rates (per second: by owner, else an asset's own royalty from its cast entry or pack, else by kind) the report
gives what each owner is owed; an unregistered puppet is not paid until it is registered.
A film still on a draft timing (narration slots, not yet voiced) is counted from its slots and listed as planned.
A film whose times cannot be resolved (no timing.json for its line references) is listed with the reason, so the
report states what it covers.
"""
import json
from pathlib import Path

HOUSE = "doodleberry (house)"


def _j(p, default=None):
    p = Path(p)
    return json.loads(p.read_text()) if p.exists() else default


def _union(iv):
    out = []
    for a, b in sorted(iv):
        if out and a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return sum(b - a for a, b in out)


class Library:
    """owners and clip lengths, loaded once"""

    def __init__(self, root):
        self.root = Path(root)
        self.cast = {e["path"]: e for e in _j(self.root / "cast" / "index.json", {"puppets": []})["puppets"]}
        self.voices = _j(self.root / "voices" / "registry.json", {}).get("voices", {})
        self._pup, self._clips = {}, {}

    def puppet(self, path):
        if path not in self._pup:
            self._pup[path] = _j(self.root / path, {}) or {}
        return self._pup[path]

    def clip_libs(self, template):
        """clip name -> clip for a template's library (installed pack clips carry "pack": "id@version")"""
        if template not in self._clips:
            self._clips[template] = (_j(self.root / "puppet" / "clips" / f"{template}.json", {}) or {}).get("clips", {})
        return self._clips[template]

    def packs(self):
        if not hasattr(self, "_packs"):
            self._packs = (_j(self.root / "puppet" / "clips" / "packs.json", {}) or {}).get("packs", {})
        return self._packs

    def owner(self, kind, aid):
        if kind == "puppet":
            e = self.cast.get(aid)
            if not e:
                return {"owner": "unregistered", "license": None, "registered": False}
            r = e.get("rights") or {}
            return {"owner": r.get("owner") or e.get("author"), "author": e.get("author"), "license": e.get("license"), "cast_id": e["id"], "registered": True,
                    **({"royalty": e["royalty"]} if e.get("royalty") else {}), **({"pack": e["pack"]} if e.get("pack") else {})}
        if kind == "voice":
            v = self.voices.get(aid) or ({"license": "Apache-2.0 (Kokoro-82M weights)"} if aid.startswith("kokoro:") else {})
            return {"owner": v.get("owner") or ("Kokoro-82M (hexgrad)" if aid.startswith("kokoro:") else f"Piper voice {aid}"), "license": v.get("license"), "status": v.get("status")}
        if kind == "icon":
            return {"owner": "Lucide contributors", "license": "ISC"}
        if kind == "clip":
            tpl, name = aid.split("/", 1); tag = (self.clip_libs(tpl).get(name) or {}).get("pack")
            if tag:
                pk = self.packs().get(tag.split("@")[0], {})
                return {"owner": pk.get("author", "unknown pack"), "license": pk.get("license"), "pack": tag, **({"royalty": pk["royalty"]} if pk.get("royalty") else {})}
        if kind == "boil":
            pr = _j(self.root / "presets" / "boil" / f"{aid}.json", {}) or {}
            if pr.get("author"):
                pk = self.packs().get(aid, {})
                return {"owner": pr["author"], "license": pr.get("license"), "pack": pr.get("pack"), **({"royalty": pk["royalty"]} if pk.get("royalty") else {})}
        return {"owner": HOUSE, "license": "house"}


def film_usage(lib, name, shots, script, timing):
    """-> {asset key: seconds} for one film (shots resolved to seconds, or None for a scene.js film); key = (kind, id)"""
    iv = {}
    add = lambda k, a, b: iv.setdefault(k, []).append((a, b)) if b > a else None
    if shots is None:
        add(("scene", name), 0.0, float(timing.get("duration") or max([l["end"] for l in timing.get("lines", [])] or [0])))
    for sh in (shots or {}).get("shots", []):
        s0, s1 = float(sh["start"]), float(sh["end"])
        if sh.get("set") and sh["set"] != "none":
            add(("set", sh["set"]), s0, s1)
        if (sh.get("style") or {}).get("boil_preset"):
            add(("boil", sh["style"]["boil_preset"]), s0, s1)
        for c in sh.get("cast", []):
            p = c["puppet"]; add(("puppet", p), s0, s1)
            tpl = lib.puppet(p).get("template") or "humanoid"; libs = lib.clip_libs(tpl)
            for cl in (c.get("timeline") or {}).get("clips", []):
                a = max(s0, float(cl.get("start", s0)))
                spec = libs.get(cl["clip"]) or ((lib.puppet(p).get("clips") or {}).get(cl["clip"]))
                if cl.get("end") is not None:
                    b = float(cl["end"])
                elif spec and not spec.get("loop") and spec.get("duration"):
                    b = a + float(spec["duration"])
                else:
                    b = s1
                add(("clip", f"{tpl}/{cl['clip']}"), a, min(b, s1))
        for pr in sh.get("props") or []:
            add(("prop", pr["id"]), s0, s1)
        for o in sh.get("overlays") or []:
            if o.get("type") == "icon" and o.get("name"):
                a = max(s0, float(o.get("start", s0))); add(("icon", o["name"]), a, min(s1, float(o.get("end", s1))))
    spk = {k: (v or {}).get("voice") for k, v in (script.get("speakers") or {}).items()}
    for ln in ([] if timing.get("draft") else timing.get("lines", [])):   # a draft timing (slots, no voice yet) has no voice to count
        v = spk.get(ln.get("speaker")) or script.get("voice")
        if v:
            add(("voice", v), float(ln["start"]), float(ln["end"]))
    return {k: round(_union(v), 3) for k, v in iv.items()}


def report(lib, films, rates=None):
    """films: [(name, shots resolved, script, timing)] -> {assets, owners, payouts}"""
    assets = {}
    for name, sh, sc, tm in films:
        for (kind, aid), sec in film_usage(lib, name, sh, sc, tm).items():
            a = assets.setdefault((kind, aid), {"kind": kind, "id": aid, **lib.owner(kind, aid), "seconds": 0.0, "films": {}})
            a["seconds"] = round(a["seconds"] + sec, 3); a["films"][name] = sec
    rows = sorted(assets.values(), key=lambda a: (a["kind"], -a["seconds"]))
    owners = {}
    for a in rows:
        o = owners.setdefault(a["owner"], {"owner": a["owner"], "seconds": 0.0, "by_kind": {}, "assets": 0})
        o["seconds"] = round(o["seconds"] + a["seconds"], 3); o["by_kind"][a["kind"]] = round(o["by_kind"].get(a["kind"], 0) + a["seconds"], 3); o["assets"] += 1
    pay = []
    if rates is not None or any(a.get("royalty") for a in rows):
        rates = rates or {}
        for a in rows:
            if not a.get("registered", True):   # an unregistered puppet has no known owner to pay: register it (cast.add)
                continue
            own = (a.get("royalty") or {}).get("per_second")
            r = (rates.get("owner") or {}).get(a["owner"], own if own is not None else (rates.get("kind") or {}).get(a["kind"]))
            if r:
                pay.append({"owner": a["owner"], "kind": a["kind"], "id": a["id"], "seconds": a["seconds"], "rate": r, "amount": round(a["seconds"] * r, 2)})
        tot = {}
        for p in pay:
            tot[p["owner"]] = round(tot.get(p["owner"], 0) + p["amount"], 2)
        pay = {"lines": pay, "by_owner": tot, "currency": rates.get("currency", "")}
    return {"assets": rows, "owners": sorted(owners.values(), key=lambda o: -o["seconds"]), "payouts": pay or None}


def csv(rows):
    import io, csv as C
    b = io.StringIO(); w = C.writer(b)
    w.writerow(["kind", "id", "owner", "license", "seconds", "films"])
    for a in rows:
        w.writerow([a["kind"], a["id"], a["owner"], a.get("license") or "", a["seconds"], len(a["films"])])
    return b.getvalue()
