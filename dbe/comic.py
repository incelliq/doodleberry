"""Comics and storybooks from a film's data (WP-30), typeset with Typst.

Every voiced line becomes a panel: the film's frame at that moment (drawn by the player without its speech bubbles or
captions), cropped around the characters, with the line set by Typst as a speech balloon whose tail points at the
speaker's head (the player reports where each head is), or as a caption box for a narrator. A shot with no lines gets
one silent panel. A **comic** puts six panels on an A4 page (two columns); a **storybook** puts one picture on each
square page with its words set below it in prose ("..." said Momo). Text comes from timing.json (the words as spoken,
with data bindings filled in), names from script.json, the title from shots.json.
"""
import json
from pathlib import Path

PANEL_ASPECT = 4 / 3


def tstr(s):
    """a Typst string literal"""
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ") + '"'


def panels(shots, timing, script):
    """-> [{t, line, speaker, text, narrator}] in film order"""
    names = {k: (v or {}).get("name") or k.capitalize() for k, v in (script.get("speakers") or {}).items()}
    narr = {k for k, v in (script.get("speakers") or {}).items() if (v or {}).get("narrator")} | {"narrator", None, ""}
    lines = timing.get("lines", []); out = []
    for sh in shots["shots"]:
        inside = [l for l in lines if sh["start"] <= (l["start"] + l["end"]) / 2 < sh["end"]]
        if not inside:
            out.append({"t": round((sh["start"] + sh["end"]) / 2, 3), "shot": sh["id"], "text": "", "speaker": None, "narrator": True})
        for l in inside:
            sp = l.get("speaker")
            out.append({"t": round(l["start"] + 0.6 * (l["end"] - l["start"]), 3), "shot": sh["id"], "line": l["id"], "speaker": sp,
                        "name": names.get(sp, (sp or "").capitalize()), "text": l["text"], "narrator": sp in narr or sp not in {c.get("speaker") for c in sh.get("cast", [])}})
    return out


def crop_box(W, H, heads, aspect=PANEL_ASPECT):
    """a full-width crop at the panel's aspect, with room above the highest head for a balloon"""
    ch = min(H, round(W / aspect))
    ys = [y for _, y in heads.values()]
    top = (min(ys) - 0.3 * ch) if ys else (H * 0.57 - ch / 2)
    top = max(0, min(H - ch, top))
    return [0, round(top), W, round(top) + ch]


def _balloon(p, head, box, pw_mm, ph_mm):
    """Typst for one balloon or caption inside a panel of pw x ph mm; head in frame px; box = the crop"""
    if not p["text"]:
        return ""
    k = pw_mm / (box[2] - box[0]); fs = 8.5 if len(p["text"]) < 90 else 7.5
    if p["narrator"] or not head:
        return f'#place(top + left, dx: 2mm, dy: 2mm, box(width: {pw_mm * 0.62:.1f}mm, fill: rgb("#fff3c4"), stroke: 0.6pt, inset: 1.6mm, text(size: {fs}pt, {tstr(p["text"])})))\n'
    hx, hy = (head[0] - box[0]) * k, (head[1] - box[1]) * k
    bw = pw_mm * 0.6; bx = max(1.5, min(pw_mm - bw - 1.5, hx - bw / 2)); by = 1.8
    # the tail starts inside the balloon (drawn over it, so it joins the outline) and stops short of the head
    tx0, ty0 = max(bx + 4, min(bx + bw - 4, hx)), by + 3
    tx1, ty1 = tx0 + (hx - tx0) * 0.8, ty0 + max(6.0, (hy - ty0) * 0.75)
    tail = f'#place(top + left, polygon(fill: white, stroke: 0.6pt, ({tx0 - 2.4:.1f}mm, {ty0:.1f}mm), ({tx0 + 2.4:.1f}mm, {ty0:.1f}mm), ({tx1:.1f}mm, {ty1:.1f}mm)))\n'
    body = f'#place(top + left, dx: {bx:.1f}mm, dy: {by:.1f}mm, box(width: {bw:.1f}mm, fill: white, stroke: 0.6pt, radius: 3mm, inset: (x: 2.2mm, y: 1.6mm), align(center, text(size: {fs}pt, {tstr(p["text"])}))))\n'
    return tail + body


def typst_source(kind, title, frames, items, font, W, H):
    """frames: [{png, heads}] per item (png paths relative to the .typ file)"""
    if kind == "comic":
        page, cols, gut, mar = ("210mm", "297mm"), 2, 4.0, 12.0
        pw = (210 - 2 * mar - (cols - 1) * gut) / cols; ph = pw / PANEL_ASPECT
        src = [f'#set page(width: {page[0]}, height: {page[1]}, margin: {mar}mm)', f'#set text(font: {tstr(font)}, size: 9pt, lang: "en")',
               f'#align(center, text(size: 20pt, weight: "bold", {tstr(title)}))', '#v(2mm)', f'#grid(columns: ({pw:.2f}mm, {pw:.2f}mm), gutter: {gut}mm,']
        cells = []
        for it, fr in zip(items, frames):
            box = fr["crop"]; head = fr["heads"].get(it.get("speaker")) if it.get("speaker") else None
            cells.append(f'  block(width: {pw:.2f}mm, height: {ph:.2f}mm, clip: true, stroke: 1pt)[#image({tstr(fr["png"])}, width: {pw:.2f}mm, height: {ph:.2f}mm)\n{_balloon(it, head, box, pw, ph)}],')
        return "\n".join(src + cells + [")"]) + "\n"
    # storybook: a square page, the picture above, the words below
    side, mar = 210, 14
    pw = side - 2 * mar; ph = pw / PANEL_ASPECT
    src = [f'#set page(width: {side}mm, height: {side}mm, margin: {mar}mm)', f'#set text(font: {tstr(font)}, size: 18pt, lang: "en")',
           f'#align(center + horizon, text(size: 30pt, {tstr(title)}))']
    for it, fr in zip(items, frames):
        words = it["text"] if it.get("narrator") or not it.get("text") else f'“{it["text"]}” said {it["name"]}.'
        src += ['#pagebreak()', f'#block(width: {pw}mm, height: {ph:.2f}mm, clip: true, radius: 3mm)[#image({tstr(fr["png"])}, width: {pw}mm, height: {ph:.2f}mm)]',
                '#v(5mm)', f'#par(justify: false, {tstr(words)})']
    return "\n".join(src) + "\n"
