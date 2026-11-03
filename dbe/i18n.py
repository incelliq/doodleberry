"""Localisation (WP-25): every word a viewer reads or hears, by key, and what a language needs.

**Strings.** `extract` lists every piece of text in a film with a stable key: the script's lines (`line:<id>`), every
text field of every overlay and underlay (`shot:<id>:overlay:<n>:<field>`, list items as `...:<field>:<i>`), the set's
own words (the classroom board: `shot:<id>:set:board:<i>`), extra bubbles, a shot's audio-description words, chart
labels drawn from data.json (`data:<path>`), the film's title and brief, and the titles and thumbnail lines chosen
for posting (`titles:<n>`, `thumb:<n>:top`). `apply` writes translations back. A translation must keep every
`{{...}}` data binding of its source (the numbers come from data.json in every language); month and weekday names in
chart labels are translated from the locale's own data (CLDR, through Babel) when no translation is given.

**Languages.** `language(tag)` gives what the rest of the pipeline needs from CLDR and engine/fonts/scripts.json: the
language's name in English and in itself, its direction, its writing system (fonts, caption font, OCR language) and
the Whisper language code. `voices_for(tag)` lists the voices that speak it, clean ones first.

**Cultural rules** (dbe/cultures.json): gestures some audiences read as rude become ones they do not (a hand swap or
an open palm for a pointed finger), applied when a film is localised unless the film's own i18n file turns a rule
off; and words in props, sets and on-screen text that a locale's reviewers should look at before posting (flags only:
whether to change them is a person's decision).
"""
import copy
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEXT_FIELDS = ("text", "title", "body", "label", "by", "prefix", "suffix", "unit", "accent_text", "caption", "top", "bottom", "name_text", "subtitle")
BIND = re.compile(r"\{\{[^}]+\}\}")
_SCRIPTS = json.loads((ROOT / "engine" / "fonts" / "scripts.json").read_text())["scripts"]
WHISPER = {"zh": "zh", "si": "si", "ar": "ar", "he": "he", "fa": "fa", "ur": "ur"}   # most tags are Whisper's own


def _script_of(text):
    best, n = None, 0
    for sc in _SCRIPTS:
        k = len(re.findall("[" + sc["ranges"] + "]", text or ""))
        if k > n:
            best, n = sc, k
    return best


def language(tag):
    """-> {tag, name, native, dir, script, caption_font, ocr, whisper, nospace}"""
    from babel import Locale
    loc = Locale.parse(tag.replace("-", "_"))
    sample = (loc.languages.get(loc.language) or "") + " ".join(loc.months["format"]["wide"].values())
    sc = _script_of(sample)
    return {"tag": tag, "name": Locale("en").languages.get(loc.language, tag), "native": loc.get_display_name(loc) or tag, "dir": loc.text_direction,
            "script": sc["script"] if sc else "latin", "caption_font": sc["caption"] if sc else "Fredoka", "ocr": (sc["ocr"] if sc else "eng"),
            "nospace": bool(sc and sc.get("nospace")), "whisper": WHISPER.get(loc.language, loc.language)}


def voices_for(tag, registry):
    """voices that speak a language, clean first: Kokoro ids by their language letter, Piper ids by their prefix"""
    kok = {"en": "ab", "es": "e", "fr": "f", "hi": "h", "it": "i", "ja": "j", "pt": "p", "zh": "z"}
    lang = tag.split("-")[0].split("_")[0]; out = []
    for vid, r in registry.items():
        if vid.startswith("kokoro:"):
            ok = vid.split(":", 1)[1][:1] in kok.get(lang, "#")
        else:
            ok = vid.split("_")[0] == lang
        if ok:
            out.append({"voice": vid, "status": r.get("status"), "license": r.get("license"), "gender": r.get("gender")})
    rank = {"clean": 0, "unclear": 1, "restricted": 2}
    return sorted(out, key=lambda v: (rank.get(v["status"], 3), v["voice"]))


# ---------------- strings ----------------
def _overlay_items(sh):
    for kind in ("overlays", "underlays"):
        for n, o in enumerate(sh.get(kind) or []):
            yield kind[:-1], n, o


def extract(shots, script, titles=None, data=None):
    """-> [{key, text, where}] every string a viewer reads or hears"""
    out = []
    add = lambda k, t, where: out.append({"key": k, "text": t, "where": where}) if isinstance(t, str) and t.strip() else None
    for ln in script.get("lines", []):
        add(f"line:{ln['id']}", ln.get("text"), "spoken line (and its bubble or caption)")
        if ln.get("alt"):
            add(f"line:{ln['id']}:alt", ln["alt"], "spoken line, short alternate")
        if ln.get("bubble"):
            add(f"line:{ln['id']}:bubble", ln["bubble"], "the line's bubble as written on screen (optional: without it the bubble shows the translated line)")
    for k in ("title",):
        add(f"film:{k}", shots.get(k), "film title")
    for k, v in (shots.get("brief") or {}).items():
        if isinstance(v, str):
            add(f"brief:{k}", v, "brief")
    for sh in shots.get("shots", []):
        sid = sh["id"]
        for kind, n, o in _overlay_items(sh):
            for f in TEXT_FIELDS:
                v = o.get(f)
                if isinstance(v, list):
                    for i, x in enumerate(v):
                        add(f"shot:{sid}:{kind}:{n}:{f}:{i}", x, f"{o.get('type')} {f}")
                else:
                    add(f"shot:{sid}:{kind}:{n}:{f}", v, f"{o.get('type')} {f}")
        for i, x in enumerate((sh.get("set_opts") or {}).get("board") or []):
            add(f"shot:{sid}:set:board:{i}", x, f"{sh.get('set')} set, board")
        for f in ("sign", "label", "title"):
            add(f"shot:{sid}:set:{f}", (sh.get("set_opts") or {}).get(f), f"{sh.get('set')} set, {f}")
        if isinstance(sh.get("describe"), str):
            add(f"shot:{sid}:describe", sh["describe"], "audio description")
        eb = sh.get("extra_bubbles")
        for i, b in enumerate(eb if isinstance(eb, list) else []):
            add(f"shot:{sid}:bubble:{i}", (b or {}).get("text"), "extra bubble")
    for path, lab in _data_labels(shots, data or {}):
        add(f"data:{path}", lab, "chart label from data.json")
    for i, t in enumerate((titles or {}).get("titles", [])):
        add(f"titles:{i}", t.get("text"), "posting title")
    for i, t in enumerate((titles or {}).get("thumbnails", [])):
        for f in ("top", "bottom"):
            add(f"thumb:{i}:{f}", t.get(f), "thumbnail line")
    return out


def _data_labels(shots, data):
    """chart labels a film draws from data.json: (path, label)"""
    seen = set()
    for sh in shots.get("shots", []):
        for _, _, o in _overlay_items(sh):
            src = o.get("data_from")
            if not src or src in seen:
                continue
            seen.add(src); rows = data
            for part in src.split("."):
                rows = rows.get(part) if isinstance(rows, dict) else None
            for i, r in enumerate(rows if isinstance(rows, list) else []):
                if isinstance(r, list) and r and isinstance(r[0], str):
                    yield f"{src}.{i}.0", r[0]


def _months(tag):
    """English month and weekday names -> the locale's (CLDR)"""
    from babel import Locale
    en, lo = Locale("en"), Locale.parse(tag.replace("-", "_"))
    m = {}
    for width in ("wide", "abbreviated"):
        for i, name in en.months["format"][width].items():
            m[name] = lo.months["stand-alone"]["wide"][i]
        for i, name in en.days["format"][width].items():
            m[name] = lo.days["stand-alone"]["wide"][i]
    return m


def check_bindings(source, translated):
    """the {{...}} bindings a translation lost or gained"""
    a, b = sorted(BIND.findall(source or "")), sorted(BIND.findall(translated or ""))
    return [x for x in a if x not in b] + [x for x in b if x not in a]


def apply(shots, script, titles, data, tr, tag, keep_rest=False):
    """write translations (key -> text) into copies; -> (shots, script, titles, data, missing, binding_errors, auto).
    keep_rest: a correction, not a translation: titles and thumbnails not in tr are kept as they are"""
    shots, script, titles, data = (copy.deepcopy(x) for x in (shots, script, titles or {}, data or {}))
    src = {s["key"]: s["text"] for s in extract(shots, script, titles, data)}
    months = _months(tag); auto = {}
    for k, v in src.items():   # chart labels that are month or weekday names come from the locale
        if k.startswith("data:") and k not in tr and v in months:
            auto[k] = months[v]
    tr = {**auto, **tr}
    bad = {k: check_bindings(src[k], v) for k, v in tr.items() if k in src and check_bindings(src[k], v)}
    missing = [k for k in src if k not in tr and not k.startswith(("brief:", "titles:", "thumb:", "film:")) and not k.endswith((":alt", ":bubble"))]
    lines = {ln["id"]: ln for ln in script.get("lines", [])}
    shot_by = {sh["id"]: sh for sh in shots.get("shots", [])}
    for k, v in tr.items():
        if k not in src:   # a key this film does not have (a stale or mistyped translation): left out
            continue
        p = k.split(":")
        if p[0] == "line" and p[1] in lines:
            lines[p[1]][p[2] if len(p) > 2 else "text"] = v
        elif p[0] == "film":
            shots[p[1]] = v
        elif p[0] == "brief":
            shots.setdefault("brief", {})[p[1]] = v
        elif p[0] == "shot" and p[1] in shot_by:
            sh = shot_by[p[1]]
            if p[2] in ("overlay", "underlay"):
                o = sh[p[2] + "s"][int(p[3])]
                if len(p) > 5:
                    o[p[4]][int(p[5])] = v
                else:
                    o[p[4]] = v
            elif p[2] == "set" and p[3] == "board":
                sh["set_opts"]["board"][int(p[4])] = v
            elif p[2] == "set":
                sh["set_opts"][p[3]] = v
            elif p[2] == "describe":
                sh["describe"] = v
            elif p[2] == "bubble":
                sh["extra_bubbles"][int(p[3])]["text"] = v
        elif p[0] == "data":
            path = p[1].split("."); node = data
            for part in path[:-1]:
                node = node[int(part)] if isinstance(node, list) else node[part]
            node[int(path[-1])] = v
        elif p[0] == "titles":
            titles["titles"][int(p[1])]["text"] = v
        elif p[0] == "thumb":
            titles["thumbnails"][int(p[1])][p[2]] = v
    if titles and not keep_rest:   # posting titles and thumbnails left untranslated are dropped, not posted in the source language
        for key, kind in (("titles", "titles"), ("thumb", "thumbnails")):
            keep = [x for i, x in enumerate(titles.get(kind, [])) if any(k.startswith(f"{key}:{i}") for k in tr if k in src)]
            if len(keep) != len(titles.get(kind, [])):
                titles[kind] = keep; titles.setdefault("chosen", {})["title" if kind == "titles" else "thumbnail"] = 0
    for lid, ln in lines.items():   # a line translated without its own bubble or alternate: they would still be the source's
        for f in ("bubble", "alt"):
            if ln.get(f) and f"line:{lid}" in tr and f"line:{lid}:{f}" not in tr:
                ln.pop(f)
    return shots, script, titles, data, missing, bad, auto


# ---------------- cultural rules ----------------
def rules_for(tag):
    c = json.loads((Path(__file__).with_name("cultures.json")).read_text())
    lang = tag.split("-")[0]; region = tag.split("-")[1].upper() if "-" in tag else None
    return [r for r in c["rules"] if lang in r.get("languages", []) or (region and region in r.get("regions", []))]


def apply_rules(shots, tag, off=()):
    """gesture swaps of the locale's rules (unless turned off); -> (shots, changes)"""
    shots = copy.deepcopy(shots); changes = []
    for r in rules_for(tag):
        if r["id"] in off or not r.get("clips"):
            continue
        for sh in shots.get("shots", []):
            for c in sh.get("cast", []):
                for cl in (c.get("timeline") or {}).get("clips", []):
                    to = r["clips"].get(cl.get("clip"))
                    if to:
                        changes.append({"rule": r["id"], "shot": sh["id"], "from": cl["clip"], "to": to}); cl["clip"] = to
    return shots, changes


def review_flags(shots, script, tag):
    """words a locale's reviewers should look at (props, sets, on-screen text, lines): flags, never changes"""
    flags = []
    texts = [(f"line:{l['id']}", l.get("text", "")) for l in script.get("lines", [])]
    for sh in shots.get("shots", []):
        texts.append((f"shot:{sh['id']}:set", sh.get("set", "")))
        for p in sh.get("props") or []:
            texts.append((f"shot:{sh['id']}:prop", json.dumps(p.get("id", "")) + " " + str(p.get("name", ""))))
        for _, n, o in _overlay_items(sh):
            texts.append((f"shot:{sh['id']}:overlay:{n}", " ".join(str(o.get(f, "")) for f in TEXT_FIELDS)))
    for r in rules_for(tag):
        if not r.get("words"):
            continue
        rx = re.compile(r"\b(" + "|".join(r["words"]) + r")\b", re.I)
        for k, t in texts:
            m = rx.search(t or "")
            if m:
                flags.append({"rule": r["id"], "where": k, "word": m.group(0), "why": r["why"]})
    return flags
