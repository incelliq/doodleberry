"""Blender cut-out rig extractor (runs inside Blender; see dbe/cutout_import.py for the other half).

    blender -b --factory-startup RIG.blend --python dbe/blender_cutout.py -- OUT_DIR [VARIANTS_JSON]

Cut-out rigs in Blender (textured planes parented to bones or skinned to an armature, sprite sheets switched with
UV Warp, shape keys for lids) are flattened to data: every rendered mesh's triangles in the front view (x right,
z up) with UVs and material, its depth (y, smaller = nearer the camera), the bone that carries it, and the
armature's bones in the rest layout. Packed images are saved as PNG. Blender 2.8+ drops the old texture slots of
2.7x files, so the material-to-image match is made later from the UVs and alpha.

Variants re-evaluate the rig in other states and keep only the meshes that changed:
  [{"name": "mouth/AI", "action": "Lib_Phonemes", "frame": 1}, {"name": "eyes/closed", "action": "Lib_Eyes", "frame": 2},
   {"name": "x", "bones": {"lips-offset": {"location": [0.33, 0, 0]}}, "shape_keys": {"head.002": {"up-eye-down.L": 1}}}]
Python drivers stay off (the file is opened without auto-run); simple transform drivers still evaluate.
"""
import json
import sys
from pathlib import Path

import bpy

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = Path(argv[0]); OUT.mkdir(parents=True, exist_ok=True)
VARIANTS = json.loads(Path(argv[1]).read_text()) if len(argv) > 1 else []

arm = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
scene = bpy.context.scene


def reset_pose():
    if not arm:
        return
    if arm.animation_data:
        arm.animation_data.action = None
    for pb in arm.pose.bones:
        pb.location = (0, 0, 0); pb.scale = (1, 1, 1)
        pb.rotation_quaternion = (1, 0, 0, 0); pb.rotation_euler = (0, 0, 0)
    for ob in bpy.data.objects:
        if ob.type == "MESH" and ob.data.shape_keys:
            for kb in ob.data.shape_keys.key_blocks[1:]:
                if not (ob.data.shape_keys.animation_data and any(d.data_path == f'key_blocks["{kb.name}"].value' for d in ob.data.shape_keys.animation_data.drivers)):
                    kb.value = 0.0


def carrier_bone(ob):
    if ob.parent == arm and ob.parent_type == "BONE":
        return ob.parent_bone, "parent"
    mod = next((m for m in ob.modifiers if m.type == "ARMATURE" and m.object == arm), None)
    if mod and ob.vertex_groups:
        w = {}
        for v in ob.data.vertices:
            for g in v.groups:
                nm = ob.vertex_groups[g.group].name
                if arm and nm in arm.data.bones:
                    w[nm] = w.get(nm, 0) + g.weight
        if w:
            return max(w, key=w.get), "skin"
    if ob.parent == arm:
        return None, "object"
    return None, None


def mesh_record(ob, dg):
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    me.calc_loop_triangles()
    uv = me.uv_layers.active
    M = ev.matrix_world
    co = [M @ v.co for v in me.vertices]
    skinned = any(m.type == "ARMATURE" and m.object == arm for m in ob.modifiers) and ob.vertex_groups
    vw = {}
    if skinned and len(me.vertices) == len(ob.data.vertices):  # weights from the original mesh (same vertex order)
        for v in ob.data.vertices:
            ws = sorted(((ob.vertex_groups[g.group].name, g.weight) for g in v.groups if arm and ob.vertex_groups[g.group].name in arm.data.bones), key=lambda t: -t[1])[:3]
            vw[v.index] = [[n, round(w, 3)] for n, w in ws]
    tris = []
    for t in me.loop_triangles:
        tri = []
        for li, vi in zip(t.loops, t.vertices):
            p = co[vi]; u = uv.data[li].uv if uv else (0, 0)
            tri.append([round(p.x, 5), round(p.z, 5), round(u[0], 5), round(u[1], 5)])
        mat = ob.material_slots[t.material_index].material.name if ob.material_slots and ob.material_slots[t.material_index].material else None
        rec = {"p": tri, "mat": mat}
        if vw:
            rec["w"] = [vw.get(vi, []) for vi in t.vertices]
        tris.append(rec)
    depth = sum(p.y for p in co) / max(1, len(co))
    ev.to_mesh_clear()
    return {"tris": tris, "depth": round(depth, 5)}


def visible(ob):
    if ob.type != "MESH" or ob.hide_render:
        return False
    if not ob.material_slots or not any(s.material for s in ob.material_slots):
        return False
    bone, how = carrier_bone(ob)
    return how is not None


def snapshot():
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    return {ob.name: mesh_record(ob, dg) for ob in bpy.data.objects if visible(ob)}


reset_pose(); bpy.context.view_layer.update()
base = snapshot()

objects = []
for ob in bpy.data.objects:
    if ob.name in base:
        bone, how = carrier_bone(ob)
        objects.append({"name": ob.name, "bone": bone, "how": how, **base[ob.name]})

bones = {}
if arm:
    Mw = arm.matrix_world
    for b in arm.data.bones:
        h = Mw @ b.head_local; t = Mw @ b.tail_local
        bones[b.name] = {"head": [round(h.x, 5), round(h.z, 5)], "tail": [round(t.x, 5), round(t.z, 5)],
                         "parent": b.parent.name if b.parent else None, "deform": b.use_deform}

images = {}
for im in bpy.data.images:
    if im.packed_file and im.size[0] > 0:
        fn = OUT / (Path(im.name).stem.replace(".", "_") + ".png")
        im2 = im.copy(); im2.filepath_raw = str(fn); im2.file_format = "PNG"
        try:
            im2.save()
        except Exception:
            im2.save_render(str(fn))
        images[im.name] = {"file": fn.name, "size": list(im.size)}

variants = {}
for v in VARIANTS:
    reset_pose()
    if v.get("action") and arm:
        act = bpy.data.actions.get(v["action"])
        if act:
            arm.animation_data_create(); arm.animation_data.action = act
            if hasattr(arm.animation_data, "action_slot") and act.slots:
                arm.animation_data.action_slot = act.slots[0]
    for bn, tr in (v.get("bones") or {}).items():
        pb = arm.pose.bones.get(bn)
        if pb:
            for k, val in tr.items():
                setattr(pb, k, val)
    for obn, keys in (v.get("shape_keys") or {}).items():
        ob = bpy.data.objects.get(obn)
        if ob and ob.data.shape_keys:
            for kn, val in keys.items():
                if kn in ob.data.shape_keys.key_blocks:
                    ob.data.shape_keys.key_blocks[kn].value = val
    scene.frame_set(int(v.get("frame", scene.frame_current)))
    bpy.context.view_layer.update()
    snap = snapshot()
    changed = {n: r for n, r in snap.items() if n in base and (r["tris"] != base[n]["tris"] or abs(r["depth"] - base[n]["depth"]) > 1e-4)}
    variants[v["name"]] = changed
reset_pose()

cam = scene.camera
info = {"blend": bpy.data.filepath, "version": list(bpy.data.version), "objects": objects, "bones": bones, "images": images,
        "materials": sorted({t["mat"] for o in objects for t in o["tris"] if t["mat"]}),
        "texture_images": [(t.name, getattr(getattr(t, "image", None), "name", None)) for t in bpy.data.textures],
        "variants": variants, "notes": [t.as_string() for t in bpy.data.texts][:3],
        "camera": {"type": cam.data.type, "ortho_scale": cam.data.ortho_scale, "loc": list(cam.location)} if cam else None}
(OUT / "rig.json").write_text(json.dumps(info))
print("CUTOUT", json.dumps({"objects": len(objects), "bones": len(bones), "images": list(images), "variants": {k: len(v) for k, v in variants.items()}}))
