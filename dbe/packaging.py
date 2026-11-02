"""Title, thumbnail and cover lab (plan 3.9, WP-07).

A film's packaging is the first thing anyone sees, so it is held to the film's own evidence:

- **truth check** (`truth`): no claim in a title, thumbnail or cover that the film does not support. The support is
  the film's facts (facts.json claims) and its narration (script lines, which are themselves traced to facts). Checked:
  - numbers: every number in the text appears in the support (digits or words, "3x" as three, million and billion;
    counts and years exactly, large numbers to 0.5%);
  - absolutes and superlatives (always, never, every, proven, cure, first, deadliest, only, most, ...): the same word
    appears in the support next to the subject;
  - causal claims (causes, cures, prevents, kills, leads to, beats, ...) stated, not asked: some fact or line shares
    two of the claim's subject words and is not negated; a claim the support negates ("no good evidence it causes arthritis") is
    *contradicted*; a myth film's myth stated as fact is the classic case;
  - topic: the text shares content words with the film.
  Questions make no claim, so "Does cracking your knuckles cause arthritis?" passes where "Cracking your knuckles
  causes arthritis" fails. This is a mechanical floor; an agent's reading against the facts goes on top of it.
- **newcomer check** (`newcomer`): at most 60 characters (55 for the thumbnail pair), no unexplained acronyms, few long
  words, no insider wording (episode numbers, "our", "we", "again" without context).
- **double-barrel thumbnail**: two short parts (top and bottom, at most 4 words and 18 characters each), checked as one
  statement.
- **covers** (`pick_frame`, `make_cover`): a deliberate frame per cut and platform, scored on the final encode (least
  bare ground, a character on screen, away from cuts and the first and last second), with the thumbnail text in the
  brand kit's font and colours inside the platform-safe area; a platform whose aspect the film was not rendered in
  gets the frame on the brand's paper, never a stretch.

Titles live in films/<name>/titles.json: {"titles": [{"text", "by", "checks"}], "thumbnails": [{"top", "bottom",
"checks"}], "chosen": {"title": i, "thumbnail": j}}.
"""
import json
import re
from pathlib import Path

from . import ROOT

NUM_WORDS = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
             "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
             "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
             "hundred": 100, "thousand": 1000, "dozen": 12, "half": 0.5, "twice": 2, "double": 2, "triple": 3}
SCALE = {"thousand": 1e3, "k": 1e3, "million": 1e6, "m": 1e6, "billion": 1e9, "bn": 1e9, "b": 1e9, "trillion": 1e12}
ABSOLUTES = ["always", "never", "every", "everyone", "everything", "nobody", "nothing", "all", "proven", "proof", "cure", "cures", "cured",
             "guaranteed", "first", "only", "most", "best", "worst", "deadliest", "biggest", "largest", "smallest", "fastest", "oldest",
             "safest", "100%", "completely", "totally", "forever", "impossible", "secret", "shocking"]
CAUSAL = r"\b(cause[sd]?|causing|cure[sd]?|prevent(?:s|ed)?|kill(?:s|ed)?|lead(?:s)? to|led to|make[s]? you|gives? you|reverse[sd]?|stop(?:s|ped)?|" \
         r"boost(?:s|ed)?|destroy(?:s|ed)?|damage[sd]?|harm(?:s|ed)?|heal(?:s|ed)?|protect(?:s|ed)?|ruin(?:s|ed)?|beat(?:s)?|win(?:s)?|won)\b"
NEGATION = r"\b(no|not|never|none|nor|isn't|aren't|doesn't|don't|didn't|wasn't|won't|cannot|can't|without|myth|false|untrue|unproven|" \
           r"no (?:good |clear |strong )?evidence|found no|did not|does not|is not)\b"
STOP = set("a an the of to in on for and or but is are was were be been it its this that these those with by from at as so do does did "
           "what why how who when where which you your we our they their he she his her i me my not no can could will would should "
           "than then there here about into over under up down out more less just very really".split())
ACRONYM_OK = {"US", "UK", "EU", "UN", "TV", "DNA", "AI", "NASA", "OK", "CO2", "TB", "HIV", "COVID", "USA"}


def _words(t):
    return re.findall(r"(?:[^\W_]|[%'])+", str(t).lower())


def _content(t):
    out = set()
    for w in _words(t):
        w = w.strip("'")
        if w and w not in STOP and not w.isdigit() and len(w) > 2:
            out.add(re.sub(r"(ies)$", "y", re.sub(r"(?<=[a-z]{3})(es|s)$", "", w)))
    return out


def numbers(t):
    """the numbers a text states, as values (12, 1.5e6, 3 for '3x' or 'three times')"""
    s = str(t).lower().replace(",", "")
    vals = []
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*(%|x\b|k\b|m\b|bn\b|b\b|thousand|million|billion|trillion)?", s):
        v = float(m.group(1)); u = (m.group(2) or "").strip()
        vals.append(v * SCALE.get(u, 1) if u not in ("%", "x") else v)
    toks = re.findall(r"[a-z]+", s)
    for i, w in enumerate(toks):
        if w in NUM_WORDS and w not in ("half", "one") or (w == "one" and i + 1 < len(toks) and toks[i + 1] in ("in", "million", "billion", "thousand", "hundred")):
            v = NUM_WORDS[w]
            if i + 1 < len(toks) and toks[i + 1] in SCALE:
                v *= SCALE[toks[i + 1]]
            vals.append(float(v))
    return vals


def _years(vals):
    return [v for v in vals if 1000 <= v <= 2100 and float(v).is_integer()]


def support_of(film_dir):
    """the film's evidence: fact claims and narration lines"""
    d = Path(film_dir)
    facts = json.loads((d / "facts.json").read_text()).get("facts", []) if (d / "facts.json").exists() else []
    script = json.loads((d / "script.json").read_text()) if (d / "script.json").exists() else {}
    return [f.get("claim", "") for f in facts if f.get("claim")] + [l.get("text", "") for l in script.get("lines", [])]


def truth(text, support, fmt=None):
    """-> {"ok", "problems": [...], "kind": "question" | "statement"}; problems say unsupported or contradicted"""
    t = str(text).strip(); probs = []
    question = t.endswith("?")
    sup_l = [s.lower() for s in support]; sup_all = " ".join(sup_l)
    # numbers
    have = numbers(sup_all)
    for v in numbers(t):
        exact = float(v).is_integer() and abs(v) < 10000   # counts and years match exactly; big round numbers to 0.5%
        if not any((v == h) if exact else abs(v - h) <= abs(h) * 0.005 for h in have):
            probs.append(f"unsupported number: {v:g} is not in the film's facts or narration")
    cw = _content(t)
    if sup_l and cw and not (cw & _content(sup_all)):
        probs.append("off topic: no content word in common with the film")
    # absolutes and superlatives: the word must be in a support sentence that shares a subject word
    for a in ABSOLUTES:
        if re.search(rf"(?<![\w%]){re.escape(a)}(?![\w%])", t.lower()):
            if not any(re.search(rf"(?<![\w%]){re.escape(a)}(?![\w%])", s) and (cw - {a}) & _content(s) for s in sup_l):
                probs.append(f"unsupported absolute: '{a}' is not said of this subject in the facts")
    # causal claims, stated rather than asked
    m = re.search(CAUSAL, t.lower())
    if m and not question:
        subj = cw - _content(m.group(0))
        near = [s for s in sup_l if len(subj & _content(s)) >= min(2, len(subj))]
        affirm = [s for s in near if not re.search(NEGATION, s)]   # the same subject, said without a negation
        negated = [s for s in near if re.search(NEGATION, s)]
        title_neg = bool(re.search(NEGATION, t.lower()))
        if not title_neg and negated and not affirm:
            probs.append(f"contradicted: the film says otherwise ({negated[0][:90]})")
        elif not title_neg and not affirm:
            probs.append(f"unsupported claim: no fact or line says this ('{m.group(0)}')")
        elif title_neg and affirm and not negated:
            probs.append(f"contradicted: the film affirms what the title denies ({affirm[0][:90]})")
    if fmt == "myth_vs_data" and not question and not re.search(NEGATION, t.lower()) and m:
        if not any("contradicted" in p for p in probs):
            probs.append("a myth film's title states the claim as fact: ask it or deny it")
    return {"ok": not probs, "problems": probs, "kind": "question" if question else "statement"}


def _quoted(text, lines):
    n = lambda x: " ".join(_words(x))
    t = n(text)
    return bool(t) and any(t in n(l) for l in lines or [])


def newcomer(text, limit=60, lines=None):
    """lines: the film's narration; a title quoting a line word for word may keep its "we" (a character speaking)"""
    t = str(text).strip(); probs = []
    if len(t) > limit:
        probs.append(f"{len(t)} characters (at most {limit})")
    acr = [w for w in re.findall(r"\b[A-Z][A-Z0-9]{1,}\b", t) if w not in ACRONYM_OK]
    if acr and t.upper() != t:
        probs.append(f"unexplained acronym: {', '.join(acr)}")
    longw = [w for w in re.findall(r"[A-Za-z]+", t) if len(re.findall(r"[aeiouy]+", w.lower())) >= 5]
    if len(longw) > 1:
        probs.append(f"long words: {', '.join(longw)}")
    if re.search(r"\b(part|episode|ep\.?)\s*\d+\b|\bour\b|\bus\b(?!a)|\bwe\b|\bagain\b", t, re.I) and not _quoted(t, lines):
        probs.append("insider wording (episode numbers, we, our, again): a newcomer has not seen the others")
    if re.search(r"[\U0001F300-\U0001FAFF☀-➿]", t):
        probs.append("emoji (brand rule: no emoji in titles)")
    return {"ok": not probs, "problems": probs}


def thumb_check(top, bottom, support, fmt=None):
    probs = []
    for k, part in (("top", top), ("bottom", bottom)):
        if len(str(part).split()) > 4 or len(str(part)) > 18:
            probs.append(f"{k} part '{part}' is longer than 4 words or 18 characters")
    tr = truth(f"{top} {bottom}", support, fmt)
    nc = newcomer(f"{top} {bottom}", limit=55, lines=support)
    return {"ok": not probs and tr["ok"] and nc["ok"], "problems": probs + tr["problems"] + nc["problems"]}


def check_title(text, support, fmt=None):
    tr = truth(text, support, fmt); nc = newcomer(text, lines=support)
    return {"ok": tr["ok"] and nc["ok"], "truth": tr, "newcomer": nc}


def load(film_dir):
    p = Path(film_dir) / "titles.json"
    return json.loads(p.read_text()) if p.exists() else {"titles": [], "thumbnails": [], "chosen": {}}


# ---------------------------------------------------------------- covers
def pick_frame(video, cuts, duration, cast_times=None, step=0.5):
    """the best cover moment: least bare ground, a character on screen, at least 0.5 s from a cut and 1 s from the
    ends -> (t, score, samples)"""
    from .layout_qa import bare_share, frames_every
    rows = []
    for t, f in frames_every(video, step, 360):
        if t < 1.0 or t > duration - 1.0 or any(abs(t - c) < 0.5 for c in cuts):
            continue
        share, _ = bare_share(f, None, win=11)
        on = 1.0 if (cast_times is None or any(a <= t <= b for a, b in cast_times)) else 0.0
        rows.append({"t": round(t, 2), "bare": round(share, 3), "cast": on, "score": round((1 - share) + 0.25 * on, 3)})
    if not rows:
        return None, None, []
    best = max(rows, key=lambda r: r["score"])
    return best["t"], best["score"], rows


def _font(name, size):
    from PIL import ImageFont
    for p in (ROOT / "engine" / "fonts" / f"{name}.ttf", ROOT / "engine" / "fonts" / "Fredoka.ttf"):
        if p.exists():
            return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


def make_cover(frame_png, out_png, aspect, top, bottom, brand):
    """the chosen frame with the double-barrel text in the brand kit, inside the safe area; another aspect puts the
    frame on the brand's paper (scaled to fit, never stretched)"""
    from PIL import Image, ImageDraw
    pal = (brand or {}).get("palette", {}); paper = pal.get("paper", "#f6f5ef"); ink = pal.get("ink", "#24160e")
    hi = pal.get(((brand or {}).get("captions") or {}).get("highlight", "highlight"), pal.get("highlight", "#ffd23f"))
    W, H = {"9:16": (1080, 1920), "16:9": (1920, 1080), "1:1": (1080, 1080)}[aspect]
    fr = Image.open(frame_png).convert("RGB")
    if abs(fr.width / fr.height - W / H) < 0.01:
        im = fr.resize((W, H))
    else:
        im = Image.new("RGB", (W, H), paper); k = min(W / fr.width, H / fr.height) * (0.92 if W > H else 1.0)
        f2 = fr.resize((int(fr.width * k), int(fr.height * k)))
        x = (W - f2.width) // 2 if H >= W else int(W * 0.62 - f2.width / 2)
        x = max(0, min(W - f2.width, x)); im.paste(f2, (x, (H - f2.height) // 2))
    dr = ImageDraw.Draw(im)
    hf = ((brand or {}).get("fonts") or {}).get("headline", "Fredoka")
    if H > W:
        box = (64, 220, 960, 1500)   # the 9:16 safe area, above the caption block
    elif W > H:
        box = (int(W * 0.05), int(H * 0.08), int(W * 0.5), int(H * 0.92))   # the left half beside the frame
    else:
        box = (int(W * 0.06), int(H * 0.06), int(W * 0.94), int(H * 0.94))
    bw = box[2] - box[0]
    rows = []
    for txt, col in ((str(top).upper(), "#ffffff"), (str(bottom).upper(), hi)):
        if txt.strip():
            fs = 150 if H > W else 120
            while fs > 34 and _font(hf, fs).getlength(txt) + 24 > bw:
                fs -= 4
            rows.append((txt, col, fs))
    block = sum(fs for _, _, fs in rows) + 18 * max(0, len(rows) - 1)
    y0 = calm_band(im, box, block)   # where the frame is quietest, so the text never sits on the film's own words
    y = y0
    for txt, col, fs in rows:
        dr.text((box[0] + 10, y), txt, font=_font(hf, fs), fill=col, stroke_width=max(6, fs // 12), stroke_fill=ink)
        y += fs + 18
    im.save(out_png)
    return {"size": [W, H], "text_box": [box[0], y0, box[2], y0 + block]}


def calm_band(im, box, h, step=20):
    """the top of the h-pixel band inside box with the least edge detail"""
    import numpy as np
    g = np.asarray(im.convert("L"), dtype=np.float32)
    e = np.abs(np.diff(g, axis=0))[:, :-1] + np.abs(np.diff(g, axis=1))[:-1, :]
    x0, y0, x1, y1 = box
    best, by = None, y0
    for y in range(y0, max(y0, y1 - h) + 1, step):
        v = float(e[y:y + h, x0:x1].mean())
        if best is None or v < best - 1e-6:
            best, by = v, y
    return by


def self_test(tmp):
    """seeded misleading titles fail and fair ones pass; every film in the repository carries two true titles and a
    true thumbnail; covers come out per aspect with their text inside the safe area, on the calm part of the frame"""
    import subprocess
    from PIL import Image, ImageDraw
    fails, got = [], {}
    sup = ["Studies comparing habitual knuckle-crackers with non-crackers found no clear link between knuckle cracking and arthritis.",
           "The pop comes from a gas bubble in the joint fluid.", "Sterile flies eradicated the screwworm from the US in 1966."]
    cases = {"Does cracking your knuckles cause arthritis?": True, "What makes your knuckles pop?": True,
             "Cracking your knuckles does not cause arthritis": True, "How flies beat the screwworm in 1966": True,
             "Cracking your knuckles causes arthritis": False, "Knuckle cracking: 9 in 10 doctors agree": False,
             "The only cure for arthritis": False, "How flies beat the screwworm in 1970": False, "Why your stomach hurts": False,
             "Part 2: our knuckles again": False}
    got["truth"] = {t: check_title(t, sup, None if "screwworm" in t else "myth_vs_data")["ok"] for t in cases}
    wrong = [t for t, want in cases.items() if got["truth"][t] != want]
    if wrong:
        fails.append(f"truth check: {wrong}")
    if thumb_check("CRACKING", "CAUSES ARTHRITIS", sup, "myth_vs_data")["ok"] or not thumb_check("KNUCKLE POP", "WHAT IS IT?", sup)["ok"]:
        fails.append("thumbnail check")
    short = []
    for d in sorted((ROOT / "films").iterdir()):
        if not (d / "script.json").exists() or "--" in d.name:
            continue
        t = load(d); s = support_of(d); fmt = json.loads((d / "script.json").read_text()).get("format")
        n = sum(check_title(y["text"], s, fmt)["ok"] for y in t["titles"]); m = sum(thumb_check(y["top"], y["bottom"], s, fmt)["ok"] for y in t["thumbnails"])
        if n < 2 or m < 1:
            short.append(f"{d.name}: {n} titles, {m} thumbnails")
    got["films_short_of_titles"] = short
    if short:
        fails.append(f"back catalogue: {short}")
    tmp = Path(tmp); tmp.mkdir(parents=True, exist_ok=True)
    fr = Image.new("RGB", (1080, 1920), "#dbe7f0"); dr = ImageDraw.Draw(fr)
    for k in range(0, 1080, 24):   # a busy top band (like a sign) and a calm middle
        dr.line([(k, 220), (k + 40, 620)], fill="#24160e", width=6)
    fr.save(tmp / "frame.png")
    brand = json.loads((ROOT / "brand" / "brand.json").read_text())
    covers = {}
    for asp in ("9:16", "16:9", "1:1"):
        info = make_cover(tmp / "frame.png", tmp / f"cover_{asp.replace(':', 'x')}.png", asp, "KNUCKLE POP", "WHAT IS IT?", brand)
        im = Image.open(tmp / f"cover_{asp.replace(':', 'x')}.png"); covers[asp] = {"size": list(im.size), "text_box": info["text_box"]}
        if list(im.size) != info["size"]:
            fails.append(f"cover {asp}: size {im.size}")
    tb = covers["9:16"]["text_box"]
    if not (64 <= tb[0] and tb[2] <= 960 and 200 <= tb[1] and tb[3] <= 1560) or tb[1] < 620:
        fails.append(f"9:16 cover text outside the safe area or on the busy band: {tb}")
    got["covers"] = covers
    v = tmp / "clip.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=360x640:rate=30:duration=4", "-pix_fmt", "yuv420p", str(v)], check=True)
    t_, score, rows = pick_frame(v, [2.0], 4.0)
    got["frame_pick"] = {"t": t_, "candidates": len(rows)}
    if t_ is None or abs(t_ - 2.0) < 0.5 or t_ < 1.0 or t_ > 3.0:
        fails.append(f"frame pick ignored the cut or the ends: {t_}")
    return fails, got
