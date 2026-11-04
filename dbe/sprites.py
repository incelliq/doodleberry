"""Sprite sheets (WP-30): a character's clips as packed sprite sheets for game engines and web canvases.

Each clip is drawn by the player (the character alone, transparent) at the sheet's frame rate, every frame trimmed
to its ink with a margin, and the frames packed into one PNG with shelves (tallest first). Beside it, the atlas in the
TexturePacker JSON "hash" layout that Phaser, PixiJS, Cocos, Defold and Unity's TexturePacker importer read:
frames by name ("<clip>/<nnnn>") with their rectangle in the sheet, whether they were trimmed, their place in the
untrimmed frame (spriteSourceSize, sourceSize) and the pivot (the character's ground point), plus an "animations"
map clip -> frame names in order. And a Godot 4 SpriteFrames resource (.tres) with one animation per clip (each
frame an AtlasTexture region of the sheet with a margin restoring the untrimmed frame), so an AnimatedSprite2D plays it.
"""
import json
from pathlib import Path

import numpy as np
from PIL import Image


def trim(im, margin=2):
    a = np.asarray(im)[..., 3]
    ys, xs = np.nonzero(a > 0)
    if not len(xs):
        return im.crop((0, 0, 1, 1)), (0, 0)
    x0, y0 = max(0, xs.min() - margin), max(0, ys.min() - margin)
    x1, y1 = min(im.width, xs.max() + 1 + margin), min(im.height, ys.max() + 1 + margin)
    return im.crop((x0, y0, x1, y1)), (int(x0), int(y0))


def pack(sizes, max_w=4096):
    """shelf packing, tallest first: sizes [(w, h)] -> (positions [(x, y)], sheet (w, h))"""
    order = sorted(range(len(sizes)), key=lambda i: (-sizes[i][1], -sizes[i][0]))
    pos = [None] * len(sizes); x = y = shelf = 0; W = 0
    for i in order:
        w, h = sizes[i]
        if x + w > max_w:
            y += shelf; x = 0; shelf = 0
        pos[i] = (x, y); x += w; shelf = max(shelf, h); W = max(W, x)
    return pos, (W, y + shelf)


def build(frames, out_dir, name, src_size, pivot, fps):
    """frames: [(clip, index, PIL RGBA full frame)] -> sheet.png, atlas.json, <name>.tres in out_dir"""
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    cut = [(c, i, *trim(im)) for c, i, im in frames]
    pos, (SW, SH) = pack([(t.width, t.height) for _, _, t, _ in cut])
    sheet = Image.new("RGBA", (SW, SH), (0, 0, 0, 0)); atlas = {"frames": {}, "animations": {}, "meta": {}}
    for (c, i, t, (ox, oy)), (x, y) in zip(cut, pos):
        sheet.paste(t, (x, y)); key = f"{c}/{i:04d}"
        atlas["frames"][key] = {"frame": {"x": x, "y": y, "w": t.width, "h": t.height}, "rotated": False, "trimmed": True,
                                "spriteSourceSize": {"x": ox, "y": oy, "w": t.width, "h": t.height}, "sourceSize": {"w": src_size[0], "h": src_size[1]},
                                "pivot": {"x": round(pivot[0] / src_size[0], 4), "y": round(pivot[1] / src_size[1], 4)}}
        atlas["animations"].setdefault(c, []).append(key)
    sheet.save(out_dir / f"{name}.png", optimize=True)
    atlas["meta"] = {"app": "Doodleberry sprite sheets (WP-30)", "image": f"{name}.png", "format": "RGBA8888", "size": {"w": SW, "h": SH},
                     "scale": "1", "frameRate": fps}
    (out_dir / f"{name}.json").write_text(json.dumps(atlas, indent=1))
    # Godot 4: a SpriteFrames resource, an AtlasTexture per frame whose margin restores the untrimmed frame (as
    # TexturePacker's Godot export does), so an AnimatedSprite2D (centered off) at the frame's origin draws it in place
    subs, anims, k = [], [], 0
    for clip, keys in atlas["animations"].items():
        fr = []
        for key in keys:
            f = atlas["frames"][key]; k += 1
            ss, sz = f["spriteSourceSize"], f["sourceSize"]   # the margin gives the trimmed frame back its place in the full frame
            subs.append(f'[sub_resource type="AtlasTexture" id="a{k}"]\natlas = ExtResource("sheet")\nregion = Rect2({f["frame"]["x"]}, {f["frame"]["y"]}, {f["frame"]["w"]}, {f["frame"]["h"]})\n'
                        f'margin = Rect2({ss["x"]}, {ss["y"]}, {sz["w"] - ss["w"]}, {sz["h"] - ss["h"]})')
            fr.append(f'{{\n"duration": 1.0,\n"texture": SubResource("a{k}")\n}}')
        anims.append(f'{{\n"frames": [{", ".join(fr)}],\n"loop": true,\n"name": &"{clip}",\n"speed": {float(fps)}\n}}')
    tres = [f'[gd_resource type="SpriteFrames" load_steps={k + 2} format=3]', f'[ext_resource type="Texture2D" path="res://{name}.png" id="sheet"]', *subs,
            "[resource]", f"animations = [{', '.join(anims)}]"]
    (out_dir / f"{name}.tres").write_text("\n\n".join(tres) + "\n")
    return atlas
