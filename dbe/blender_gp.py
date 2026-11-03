"""Render Grease Pencil frames (from dbe.exporters.to_gp_frames) inside headless Blender.

    blender -b --factory-startup --gpu-backend vulkan --python dbe/blender_gp.py -- FRAMES.json OUT_PREFIX [BG.png] [scale]

Each frame becomes a Grease Pencil keyframe; strokes keep their z order, fills and ink colours. An orthographic
camera frames the scene in screen pixels (0.01 m per px). Optional background image as a camera-facing plane.
"""
import json
import sys

import bpy

args = sys.argv[sys.argv.index("--") + 1:]
data = json.load(open(args[0]))
out_prefix = args[1]
bg = args[2] if len(args) > 2 and args[2] != "-" else None
scale = float(args[3]) if len(args) > 3 else 1.0
W, H = data["size"]
K = 0.01

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.resolution_x, sc.render.resolution_y = int(W * scale), int(H * scale)
sc.render.resolution_percentage = 100
sc.render.fps = data["fps"]
sc.frame_start, sc.frame_end = 1, data["frames"]
sc.render.engine = "BLENDER_EEVEE"
import os
sc.eevee.taa_render_samples = int(os.environ.get("DBE_GP_SAMPLES", "4"))  # flat 2D art: a few AA samples are enough (default 64)
sc.render.film_transparent = bg is None  # no plate: RGBA frames for compositing over the animated set
sc.render.image_settings.color_mode = "RGBA" if bg is None else "RGB"
w = bpy.data.worlds.new("w"); w.use_nodes = True; w.node_tree.nodes["Background"].inputs["Color"].default_value = (1, 1, 1, 1); sc.world = w
sc.view_settings.view_transform = "Standard"

cam_data = bpy.data.cameras.new("cam"); cam_data.type = "ORTHO"; cam_data.ortho_scale = max(W, H) * K
cam_data.sensor_fit = "AUTO"
cam = bpy.data.objects.new("cam", cam_data); sc.collection.objects.link(cam); sc.camera = cam
cam.location = (0, -10, 0); cam.rotation_euler = (1.5707963, 0, 0)

if bg:
    img = bpy.data.images.load(bg)
    mat = bpy.data.materials.new("bg"); mat.use_nodes = True
    nt = mat.node_tree; tex = nt.nodes.new("ShaderNodeTexImage"); tex.image = img
    emit = nt.nodes.new("ShaderNodeEmission"); out = nt.nodes["Material Output"]
    nt.links.new(tex.outputs["Color"], emit.inputs["Color"]); nt.links.new(emit.outputs["Emission"], out.inputs["Surface"])
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 1, 0), rotation=(1.5707963, 0, 0))
    plane = bpy.context.object; plane.scale = (W * K, H * K, 1); plane.data.materials.append(mat)

gpd = bpy.data.grease_pencils_v3.new("film") if hasattr(bpy.data, "grease_pencils_v3") else bpy.data.grease_pencils.new("film")
ob = bpy.data.objects.new("film", gpd); sc.collection.objects.link(ob)
if hasattr(ob, "use_grease_pencil_lights"):
    ob.use_grease_pencil_lights = False  # flat colours: palette values exactly, no scene lighting
mats = {}


def mat_for(fill, line, op=1.0):
    key = (fill, line, op)
    if key in mats:
        return mats[key]
    m = bpy.data.materials.new(f"m{len(mats)}"); bpy.data.materials.create_gpencil_data(m)
    if m.node_tree:
        m.node_tree.nodes.clear()  # new materials get a Principled BSDF; GP colours come from the settings below
    gm = m.grease_pencil
    lin = lambda c: c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4  # palette hex is sRGB; GP colours are linear
    hx = lambda h: tuple(lin(int(h[i:i + 2], 16) / 255) for i in (1, 3, 5)) + (1.0,)
    gm.show_fill = bool(fill); gm.show_stroke = bool(line)
    if fill:
        gm.fill_color = hx(fill)[:3] + (op,)
    if line:
        gm.color = hx(line)
    gpd.materials.append(m)
    mats[key] = len(gpd.materials) - 1
    return mats[key]


layer = gpd.layers.new("ink")


def split(strokes):
    """a stroke with both fill and outline becomes a fill-only stroke then a line-only one, so each material is plain"""
    out = []
    for s in strokes:
        if s["fill"] and s["line"]:
            out.append({**s, "line": None}); out.append({**s, "fill": None})
        else:
            out.append(s)
    return out


for fi, strokes in enumerate(data["data"]):
    strokes = split(strokes)
    fr = layer.frames.new(fi + 1)
    dr = fr.drawing
    if not strokes:
        continue
    dr.add_strokes([len(s["pts"]) for s in strokes])
    for k, s in enumerate(strokes):
        st = dr.strokes[k]
        st.material_index = mat_for(s["fill"], s["line"], round(s.get("op", 1), 3))
        st.cyclic = bool(s["closed"])
        if s["fill"]:
            st.fill_opacity = 1.0
            st.fill_id = k + 1  # Blender 5.x: strokes with fill_id 0 are never filled
        r = max(0.0005, s["w"] * K * 0.5) if s["line"] else 0.0001
        depth = -k * 1e-5  # later strokes slightly nearer the camera
        for j, (x, y) in enumerate(s["pts"]):
            p = st.points[j]
            p.position = ((x - W / 2) * K, depth, (H / 2 - y) * K)
            p.radius = r
    if hasattr(dr, 'tag_positions_changed'):
        dr.tag_positions_changed()

only = os.environ.get("DBE_GP_FRAMES")   # e.g. "10,25,40": render just these frames (renderer parity stills, WP-14)
if only:
    for f in [int(x) for x in only.split(",") if x.strip()]:
        sc.frame_set(f); sc.render.filepath = f"{out_prefix}{f:04d}"
        bpy.ops.render.render(write_still=True)
else:
    sc.render.filepath = out_prefix
    bpy.ops.render.render(animation=True)
print("GP_DONE", data["frames"])
