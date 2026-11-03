"""dotLottie 2.0 (WP-23): Lottie animations in one ZIP with palette themes.

Layout (dotlottie.io/spec/2.0): manifest.json ({"version": "2", "generator", "animations": [{"id", "initialTheme"?,
"themes"?}], "themes": [{"id", "name"?}]}), a/<id>.json the animations, t/<id>.json the themes. A theme is
{"rules": [{"id": <slot id>, "type": "Color", "value": [r, g, b, a] (0-1)}]}; a rule replaces the value of every
property whose "sid" is its id, from the animation's root "slots" ({"<sid>": {"p": <property>}}). The exporter
(to_lottie(slots=True)) gives every palette colour its slot, named after the palette entry ("skin", "cloth1"...),
so a theme recolours a character by name.

Themes come from a dict {slot: "#hex"} or a preset worked out from the animation's own palette:
original (its own colours, to switch back), night (one cool, darker cast over every colour alike, as moonlight;
ink kept dark), pastel (every colour lighter, towards white) and mono (each colour's luminance, as a photocopy).
"""
import colorsys
import json
import re
import zipfile
from pathlib import Path

ID = re.compile(r"^[a-zA-Z0-9._ -]+$")
PRESETS = ("original", "night", "pastel", "mono")


def hex_rgba(h):
    h = h.lstrip("#")
    return [round(int(h[i:i + 2], 16) / 255, 4) for i in (0, 2, 4)] + [1]


def slots_of(anim):
    return {k: v["p"]["k"] for k, v in (anim.get("slots") or {}).items()}


def preset(name, slots):
    """a theme's colours from the slots' own: {slot: [r, g, b, a]}"""
    out = {}
    for sid, c in slots.items():
        r, g, b = c[:3]; a = c[3] if len(c) > 3 else 1
        if name == "original":
            v = [r, g, b]
        elif name == "night":   # one cool cast over every colour alike (moonlight), so nothing reads as recoloured
            l = colorsys.rgb_to_hls(r, g, b)[1]
            v = [r, g, b] if l < 0.2 else [x * 0.72 * 0.7 + m * 0.3 for x, m in zip((r, g, b), (0.36, 0.42, 0.62))]   # ink stays ink
        elif name == "pastel":   # every colour 40% of the way to white
            v = [x + (1 - x) * 0.4 for x in (r, g, b)] if colorsys.rgb_to_hls(r, g, b)[1] >= 0.2 else [r, g, b]
        elif name == "mono":
            y = 0.2126 * r + 0.7152 * g + 0.0722 * b; v = [y, y, y]
        else:
            raise ValueError(f"unknown theme preset {name}: {', '.join(PRESETS)}")
        out[sid] = [round(x, 4) for x in v] + [a]
    return out


def theme_rules(colours, anim_ids=None):
    return {"rules": [{"id": sid, "type": "Color", "value": v, **({"animations": anim_ids} if anim_ids else {})} for sid, v in sorted(colours.items())]}


def pack(animations, themes, out, generator="doodleberry", initial_theme=None):
    """animations: [(id, lottie dict)]; themes: {theme id: {slot: [r, g, b, a]}} -> out (.lottie)"""
    for i, _ in animations:
        if not ID.match(i):
            raise ValueError(f"animation id {i!r} must match {ID.pattern}")
    for t in themes:
        if not ID.match(t):
            raise ValueError(f"theme id {t!r} must match {ID.pattern}")
    man = {"version": "2", "generator": generator,
           "animations": [{"id": i, **({"initialTheme": initial_theme} if initial_theme else {})} for i, _ in animations],
           **({"themes": [{"id": t, "name": t.replace("_", " ").title()} for t in themes]} if themes else {})}
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        z.writestr("manifest.json", json.dumps(man, indent=1))
        for i, a in animations:
            z.writestr(f"a/{i}.json", json.dumps(a, separators=(",", ":")))
        for t, cols in themes.items():
            z.writestr(f"t/{t}.json", json.dumps(theme_rules(cols), indent=1))
    return out


def check(path):
    """read a .lottie back and check it against the 2.0 layout: -> (checks, info)"""
    z = zipfile.ZipFile(path); names = set(z.namelist())
    man = json.loads(z.read("manifest.json")) if "manifest.json" in names else {}
    anims = {a["id"]: json.loads(z.read(f"a/{a['id']}.json")) for a in man.get("animations", []) if f"a/{a['id']}.json" in names}
    themes = {t["id"]: json.loads(z.read(f"t/{t['id']}.json")) for t in man.get("themes", []) if f"t/{t['id']}.json" in names}
    slots = set().union(*[set((a.get("slots") or {})) for a in anims.values()]) if anims else set()
    root_ok = set(man) <= {"version", "generator", "animations", "themes", "stateMachines", "initial"}
    checks = {"zip, deflated": all(i.compress_type == zipfile.ZIP_DEFLATED for i in z.infolist()), "manifest version 2": man.get("version") == "2" and root_ok,
              "every animation in a/": bool(man.get("animations")) and len(anims) == len(man["animations"]),
              "every theme in t/": len(themes) == len(man.get("themes", [])),
              "ids allowed": all(ID.match(i) for i in list(anims) + list(themes)),
              "theme rules are colours of known slots": all(r.get("type") == "Color" and r["id"] in slots and len(r["value"]) in (3, 4) and all(0 <= x <= 1 for x in r["value"])
                                                          for t in themes.values() for r in t["rules"]),
              "slotted properties have slots": all(_sids(a) <= set(a.get("slots") or {}) for a in anims.values())}
    return checks, {"bytes": Path(path).stat().st_size, "animations": list(anims), "themes": list(themes), "slots": sorted(slots), "manifest": man}


def _sids(o, acc=None):
    acc = set() if acc is None else acc
    if isinstance(o, dict):
        if isinstance(o.get("sid"), str):
            acc.add(o["sid"])
        for k, v in o.items():
            if k != "slots":
                _sids(v, acc)
    elif isinstance(o, list):
        for v in o:
            _sids(v, acc)
    return acc


def themed(anim, colours):
    """the animation with a theme's colours written into its slotted properties (what a player should draw)"""
    a = json.loads(json.dumps(anim))

    def walk(o):
        if isinstance(o, dict):
            if isinstance(o.get("sid"), str) and o["sid"] in colours:
                o["k"] = colours[o["sid"]]
            for k, v in o.items():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(a)
    for sid, c in colours.items():
        if sid in (a.get("slots") or {}):
            a["slots"][sid]["p"]["k"] = c
    return a
