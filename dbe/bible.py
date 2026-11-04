"""Character bibles (WP-16): one file per cast member, cast/bible/<id>.json, and a continuity check across every film
the character appears in.

A bible holds what a writer, director or agent needs to keep a character the same from film to film:
  {"id", "personality", "voice": {"voice", "fx"}, "profile" (acting profile, cast/profiles.json), "gestures" (tendencies,
   in words), "never": [clip names it never plays], "look": {"outfit", "always": [...]}, "catchphrases": [...],
   "relationships": {other id: words}, "continuity": [notes], "exceptions": {film: why it may differ}}
The voice may name a voice per language ({"voice", "fx", "by_lang": {"ar": "..."}}): a film in another language
(script.json "lang") is checked against that language's voice, and one with none chosen is reported.
Anything missing is filled from the cast registry (cast/index.json: personality, voice, profile, family).

`check(id)` finds the films whose shots use the character's puppet and reports, per film: a voice other than the
bible's (script.json speakers), an acting profile that overrides the bible's, a clip from its `never` list placed
by hand or by the planner, and a puppet file that changed since it was registered (its hash).
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BIBLE = ROOT / "cast" / "bible"
FIELDS = ["personality", "voice", "profile", "gestures", "never", "look", "catchphrases", "relationships", "continuity", "exceptions"]


def _j(p, d=None):
    p = Path(p)
    return json.loads(p.read_text()) if p.exists() else d


def entry(cid):
    e = next((x for x in _j(ROOT / "cast" / "index.json", {"puppets": []})["puppets"] if x["id"] == cid), None)
    if not e:
        raise KeyError(f"no cast member {cid}")
    return e


def read(cid):
    """the bible, with what the registry knows filled in (marked in `from_registry`)"""
    e = entry(cid); b = _j(BIBLE / f"{cid}.json", {}) or {}
    filled = []
    for k, rk in (("personality", "personality"), ("voice", "voice"), ("profile", "profile")):
        if not b.get(k) and e.get(rk):
            b[k] = e[rk]; filled.append(k)
    if e.get("family") and not (b.get("look") or {}).get("family"):
        b.setdefault("look", {})["family"] = e["family"]; filled.append("look.family")
    return {"id": cid, "name": e.get("name", cid), "puppet": e["path"], **{k: b[k] for k in FIELDS if k in b}, "from_registry": filled,
            "missing": [k for k in ("personality", "voice", "profile", "gestures", "continuity") if not b.get(k)]}


def write(cid, changes):
    entry(cid)
    bad = [k for k in changes if k not in FIELDS]
    if bad:
        raise ValueError(f"unknown bible fields {bad} (fields: {', '.join(FIELDS)})")
    b = _j(BIBLE / f"{cid}.json", {}) or {}
    for k, v in changes.items():
        if v is None:
            b.pop(k, None)
        elif isinstance(v, dict) and isinstance(b.get(k), dict):
            b[k] = {**b[k], **v}
        else:
            b[k] = v
    BIBLE.mkdir(parents=True, exist_ok=True)
    (BIBLE / f"{cid}.json").write_text(json.dumps({"id": cid, **{k: b[k] for k in FIELDS if k in b}}, indent=1, ensure_ascii=False) + "\n")
    return read(cid)


def appearances(path):
    """[(film, [cast entries using this puppet path, with their shot id])]"""
    out = []
    for sj in sorted((ROOT / "films").glob("*/shots.json")):
        film = sj.parent.name
        if film.startswith("zz-") or "--" in film:   # scratch films and derived cuts
            continue
        try:
            s = json.loads(sj.read_text())
        except ValueError:
            continue
        uses = [{"shot": sh.get("id"), **c} for sh in s.get("shots", []) for c in sh.get("cast", []) if c.get("puppet") == path]
        if uses:
            out.append((film, uses))
    return out


def check(cid):
    b = read(cid); e = entry(cid)
    issues, films = [], []
    pth = ROOT / b["puppet"]
    if e.get("sha256") and pth.exists() and hashlib.sha256(pth.read_bytes()).hexdigest()[:16] != e["sha256"]:
        issues.append({"film": None, "kind": "puppet_changed", "what": f"{b['puppet']} changed since it was registered (hash {e['sha256']})"})
    V = b.get("voice") or {}; never = set(b.get("never") or []); exc = b.get("exceptions") or {}; allowed = []
    for film, uses in appearances(b["puppet"]):
        films.append(film)
        if film in exc:
            allowed.append({"film": film, "why": exc[film]}); continue
        sc = _j(ROOT / "films" / film / "script.json", {}) or {}
        lang = (sc.get("lang") or "en").split("-")[0]
        want_voice = V.get("voice") if lang == "en" else (V.get("by_lang") or {}).get(lang)
        for spk in sorted({u.get("speaker") for u in uses if u.get("speaker")}):
            sv = ((sc.get("speakers") or {}).get(spk) or {})
            if V and lang != "en" and not want_voice and sv.get("voice"):
                issues.append({"film": film, "kind": "voice", "what": f"speaks {lang} as {sv['voice']}; the bible chooses no {lang} voice"})
            elif want_voice and sv.get("voice") and sv["voice"] != want_voice:
                issues.append({"film": film, "kind": "voice", "what": f"speaks as {sv['voice']} (bible: {want_voice})"})
            if b.get("profile") and sv.get("profile") and sv["profile"] != b["profile"]:
                issues.append({"film": film, "kind": "profile", "what": f"acts as {sv['profile']} (bible: {b['profile']})"})
        for u in uses:
            for c in (u.get("timeline") or {}).get("clips", []):
                if c.get("clip") in never:
                    issues.append({"film": film, "kind": "never", "what": f"shot {u['shot']} plays {c['clip']}, which the bible rules out"})
    return {"id": cid, "films": films, "issues": issues, "allowed": allowed, "missing": b["missing"]}
