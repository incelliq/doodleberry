"""Godot 4 export (WP-30): a film as a Godot project, so its characters can be used in a game or an interactive piece.

Each shot becomes a scene (shots/<id>.tscn): the set as a still plate, then every puppet part and swap drawing as a
Sprite2D whose texture is that part's drawing as an SVG in the puppet's artboard (Godot imports SVG), animated by an
AnimationPlayer from the bake (tools/bake.mjs, which every renderer reads): a `transform` track per drawing (the
part's world matrix per frame, camera folded in), a `visible` track where a swap shape, view or layer order changes,
and `z_index` from the part's order. main.tscn plays the shots in order with the film's sound (Ogg Vorbis).

`read_scene` is an independent reader of the .tscn text (not Godot): it evaluates the tracks at any frame, so the
export is checked by composing the drawings as Godot would place them and comparing with the player's own frame.
"""
import json
import re
from pathlib import Path

from . import geom as G
from .exporters import _load, _view_masks, z_track
from .layers_export import _strokes_svg


def _num(v):
    return f"{v:.5g}" if abs(v) >= 1e-9 else "0"


def _tf(m):
    return "Transform2D(" + ", ".join(_num(v) for v in m) + ")"


def part_svg(strokes, pal, artboard):
    W, H = artboard
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">{_strokes_svg(strokes, pal)}</svg>'


def drawings(baked):
    """every drawing of every cast member: [(node, svg, z per frame, visible per frame, matrix per frame)]"""
    out = []
    for ci, c in enumerate(baked["cast"]):
        p0 = _load(c["puppet"]); frs = c["frames"]; n = len(frs); tag = re.sub(r"\W", "_", c.get("name") or f"cast{ci}")
        for view, on in _view_masks(p0, frs):
            p = G.in_view(p0, view); pal = p.get("palette", {}); vt = f"_{view}" if view else ""
            Ms = [G.part_matrices(p, fr["angles"], fr.get("shifts"), fr.get("scales")) for fr in frs]
            Rs = [G.root_matrix(p, fr) for fr in frs]
            for pid, part in p["parts"].items():
                if not part.get("strokes"):
                    continue
                repl = [sid for sid, sw in (p.get("swaps") or {}).items() if sw.get("replaces") == pid]
                vis = [0 if any(G.chosen_swaps(p, fr).get(s) for s in repl) else 1 for fr in frs] if repl else [1] * n
                vis = [v * o for v, o in zip(vis, on)]
                if any(vis):
                    out.append((f"{ci}_{tag}{vt}_{pid}", part_svg(part["strokes"], pal, p["artboard"]), z_track(frs, pid, part.get("z", 0)), vis,
                                [G.mul(Rs[i], Ms[i][pid]) for i in range(n)]))
            for sid, sw in (p.get("swaps") or {}).items():
                for shape, strokes in sw["shapes"].items():
                    if not strokes:
                        continue
                    vis = [1 if G.chosen_swaps(p, fr).get(sid) == shape and o else 0 for fr, o in zip(frs, on)]
                    if not any(vis):
                        continue
                    mats = []
                    for i, fr in enumerate(frs):
                        m = G.mul(Rs[i], Ms[i].get(sw["anchor"], G.I))
                        if (fr.get("shifts") or {}).get("@" + sid):
                            m = G.mul(m, [1, 0, 0, 1, *fr["shifts"]["@" + sid]])
                        if sid == "pupils" and fr.get("look"):
                            m = G.mul(m, [1, 0, 0, 1, fr["look"][0] * sw.get("movable", 8), fr["look"][1] * sw.get("movable", 8) * 0.7])
                        mats.append(m)
                    out.append((f"{ci}_{tag}{vt}_{sid}_{re.sub(r'\W', '_', shape)}", part_svg(strokes, pal, p["artboard"]), z_track(frs, "@" + sid, sw.get("z", 40)), vis, mats))
    return out


def shot_scene(baked, size, plate, outdir, shot_id):
    """write shots/<id>.tscn and its part SVGs; -> the scene path. plate: the set as a still (.png) or, better, as a
    video (.ogv, Ogg Theora, which Godot plays itself), so the set's own life and the characters' ground shadows move"""
    fps, n = baked["fps"], baked["frames"]; L = n / fps
    D = drawings(baked)
    zs = sorted({z for _, _, zt, _, _ in D for z in zt}); zi = {z: i for i, z in enumerate(zs)}   # z values -> ranks (z_index is an int)
    (outdir / "parts").mkdir(parents=True, exist_ok=True)
    ext, subs, nodes, tracks = [], [], [], []
    video = plate.endswith(".ogv")
    ext.append(f'[ext_resource type="{"VideoStreamTheora" if video else "Texture2D"}" path="res://plates/{plate}" id="plate"]')
    times = "PackedFloat32Array(" + ", ".join(_num(f / fps) for f in range(n)) + ")"
    ones = "PackedFloat32Array(" + ", ".join("1" for _ in range(n)) + ")"
    for k, (node, svg, zt, vis, mats) in enumerate(D):
        f = f"{shot_id}_{node}.svg"; (outdir / "parts" / f).write_text(svg)
        ext.append(f'[ext_resource type="Texture2D" path="res://parts/{f}" id="t{k}"]')
        nodes.append(f'[node name="{node}" type="Sprite2D" parent="."]\ntexture = ExtResource("t{k}")\ncentered = false\nz_index = {zi[zt[0]] + 1}\n'
                     f'transform = {_tf(mats[0])}\nvisible = {"true" if vis[0] else "false"}')
        tracks.append((f"{node}:transform", 0, 1, [_tf(m) for m in mats]))
        if len(set(vis)) > 1:
            tracks.append((f"{node}:visible", 1, 0, ["true" if v else "false" for v in vis]))
        if len(set(zt)) > 1:
            tracks.append((f"{node}:z_index", 1, 0, [str(zi[z] + 1) for z in zt]))
    anim = [f'[sub_resource type="Animation" id="shot_anim"]', f'resource_name = "shot"', f"length = {_num(L)}", "step = " + _num(1 / fps)]
    for i, (path, update, interp, vals) in enumerate(tracks):
        anim += [f'tracks/{i}/type = "value"', f"tracks/{i}/imported = false", f"tracks/{i}/enabled = true", f'tracks/{i}/path = NodePath("{path}")',
                 f"tracks/{i}/interp = {interp}", f"tracks/{i}/loop_wrap = true",
                 f'tracks/{i}/keys = {{\n"times": {times},\n"transitions": {ones},\n"update": {update},\n"values": [{", ".join(vals)}]\n}}']
    subs = ["\n".join(anim), '[sub_resource type="AnimationLibrary" id="lib"]\n_data = {\n&"shot": SubResource("shot_anim")\n}']
    head = f"[gd_scene load_steps={len(ext) + len(subs) + 1} format=3]"
    W, H = size
    plate_node = (f'[node name="Plate" type="VideoStreamPlayer" parent="."]\noffset_right = {W}.0\noffset_bottom = {H}.0\nstream = ExtResource("plate")\nautoplay = true\nexpand = true'
                  if video else '[node name="Plate" type="Sprite2D" parent="."]\ntexture = ExtResource("plate")\ncentered = false\nz_index = 0')
    body = [f'[node name="Shot_{shot_id}" type="Node2D"]', plate_node,
            *nodes, '[node name="AnimationPlayer" type="AnimationPlayer" parent="."]\nlibraries = {\n&"": SubResource("lib")\n}\nautoplay = &"shot"']
    path = outdir / "shots" / f"{shot_id}.tscn"; path.parent.mkdir(exist_ok=True)
    path.write_text("\n\n".join([head, *ext, *subs, *body]) + "\n")
    return path, len(D), len(tracks)


MAIN_GD = '''extends Node2D
# Plays the film's shots in order with its sound (exported by Doodleberry, WP-30).
const SHOTS = {shots}
var i := 0

func _ready() -> void:
	if $Sound.stream:
		$Sound.play()
	_next()

func _next() -> void:
	if i >= SHOTS.size():
		return
	for c in $Stage.get_children():
		c.queue_free()
	var s = load(SHOTS[i]).instantiate()
	$Stage.add_child(s)
	var ap: AnimationPlayer = s.get_node("AnimationPlayer")
	ap.animation_finished.connect(func(_n): _next(), CONNECT_ONE_SHOT)
	ap.play("shot")
	i += 1
'''


def project(outdir, title, size, shot_ids, sound):
    W, H = size
    (outdir / "project.godot").write_text(
        "; Engine configuration file (exported by Doodleberry, WP-30)\nconfig_version=5\n\n[application]\n\n"
        f'config/name="{title}"\nrun/main_scene="res://main.tscn"\nconfig/features=PackedStringArray("4.5")\n\n[display]\n\n'
        f'window/size/viewport_width={W}\nwindow/size/viewport_height={H}\nwindow/stretch/mode="canvas_items"\n')
    (outdir / "main.gd").write_text(MAIN_GD.replace("{shots}", json.dumps([f"res://shots/{s}.tscn" for s in shot_ids])))
    ext = ['[ext_resource type="Script" path="res://main.gd" id="main"]'] + (['[ext_resource type="AudioStream" path="res://sound.ogg" id="snd"]'] if sound else [])
    (outdir / "main.tscn").write_text("\n\n".join([f"[gd_scene load_steps={len(ext) + 1} format=3]", *ext,
        '[node name="Film" type="Node2D"]\nscript = ExtResource("main")', '[node name="Stage" type="Node2D" parent="."]',
        '[node name="Sound" type="AudioStreamPlayer" parent="."]' + ('\nstream = ExtResource("snd")' if sound else "")]) + "\n")


def read_scene(path):
    """an independent reader of an exported .tscn: {nodes: {name: {texture, z, transform, visible}}, tracks: {path: (update, [values])}, fps}"""
    t = Path(path).read_text()
    ext = {i: p for p, i in re.findall(r'\[ext_resource type="Texture2D" path="res://([^"]+)" id="([^"]+)"\]', t)}
    tf = lambda s: [float(x) for x in re.match(r"Transform2D\(([^)]*)\)", s).group(1).split(",")]
    nodes = {}
    for m in re.finditer(r'\[node name="([^"]+)" type="Sprite2D" parent="\."\]\ntexture = ExtResource\("([^"]+)"\)\ncentered = false\nz_index = (-?\d+)(?:\ntransform = (Transform2D\([^)]*\)))?(?:\nvisible = (\w+))?', t):
        nodes[m.group(1)] = {"texture": ext[m.group(2)], "z": int(m.group(3)), "transform": tf(m.group(4)) if m.group(4) else [1, 0, 0, 1, 0, 0], "visible": m.group(5) != "false"}
    tracks = {}
    for m in re.finditer(r'tracks/(\d+)/path = NodePath\("([^"]+)"\).*?tracks/\1/keys = \{\n"times": [^\n]*\n"transitions": [^\n]*\n"update": (\d),\n"values": \[(.*?)\]\n\}', t, re.S):
        raw = m.group(4)
        vals = [tf(x) for x in re.findall(r"Transform2D\([^)]*\)", raw)] if "Transform2D" in raw else [v.strip() for v in raw.split(",")]
        tracks[m.group(2)] = (int(m.group(3)), vals)
    step = float(re.search(r"^step = ([\d.e-]+)", t, re.M).group(1))
    return {"nodes": nodes, "tracks": tracks, "fps": round(1 / step)}


def state_at(scene, f):
    """each node's texture, transform, visibility and z at frame f, from the tracks (as Godot's AnimationPlayer would)"""
    out = {}
    for name, nd in scene["nodes"].items():
        s = dict(nd)
        for prop in ("transform", "visible", "z_index"):
            tr = scene["tracks"].get(f"{name}:{prop}")
            if tr:
                v = tr[1][min(f, len(tr[1]) - 1)]
                s["transform" if prop == "transform" else "visible" if prop == "visible" else "z"] = v if prop == "transform" else (v == "true" if prop == "visible" else int(v))
        out[name] = s
    return out
