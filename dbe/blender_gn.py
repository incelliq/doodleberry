"""A procedural 3D set built with Geometry Nodes and rendered in headless Blender (WP-42), framed by the shot's 2D
camera so it sits behind the 2D puppets exactly.

    blender -b --factory-startup --gpu-backend vulkan --python dbe/blender_gn.py -- REQ.json OUT_DIR

REQ: {size: [W, H], fps, start, frames: [frame numbers to render] | count, camera: [[t, [cx, cy, zoom]]], floor: y px,
      kind: "city", seed, blocks: {count, min_dist, depth: [near, far], width, height: [lo, hi]}, palette: [...],
      sky: "#..", ground: "#..", ink: "#..", line: 1.4, samples: 1, ink_lines: true, zpass: false (EXR with depth)}
     kind: "props" (WP-42): bodies: [{shape: box | ball, size (m), at: [x px, depth m, height m above the ground], rot,
      colour, mass, friction, bounce, velocity: [vx, vy, vz] m/s} | {shape: cloth, size: [w, h] m, at: [x px, depth, top
      edge height], res}], wind (strength over the scene), substeps, iterations: rigid bodies under Bullet and cloth strips (Blender cloth, pinned
      along the top), baked, then rendered; bodies.json records where each is on every rendered frame
     lineart: true (WP-42): Grease Pencil 3 Line Art draws the ink (not Freestyle), baked to editable strokes saved in
      lineart.blend, and projected to frame pixels per frame in lineart.json; line_px
     passes: ["z", "mist", "normal", "position", "vector", "emit", "cryptomatte_object", ...] (WP-42): EEVEE's separate
      passes beside the picture, one multilayer EXR per frame

The camera maps the 2D stage exactly: 1 px = 1 cm on the stage plane (y = 0), the camera stands D0 = 12 m in front,
pans with the 2D camera centre and dollies in by its zoom, so a point on the stage plane lands where the 2D renderer
draws it, and anything behind it shows true perspective. The ground meets the stage plane at the 2D floor line.
Pure function of the request: same request, same pixels.
"""
import json
import math
import os
import sys

import bpy

args = sys.argv[sys.argv.index("--") + 1:]
R = json.load(open(args[0]))
OUT = args[1]
W, H = R["size"]
K, D0 = 0.01, 12.0
fps = R.get("fps", 30)


def hex_rgb(h, a=1.0):
    h = h.lstrip("#")
    srgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb]
    return (*lin, a)


def _keys():   # dbe/keys.py, loaded by path (Blender's Python has no dbe package on its path)
    import importlib.util
    sp = importlib.util.spec_from_file_location("dbe_keys", os.path.join(os.path.dirname(os.path.abspath(__file__)), "keys.py"))
    m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m); return m


sample_keys = _keys().sample_keys


bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.resolution_x, sc.render.resolution_y = W, H
sc.render.resolution_percentage = int(R.get("percent", 100))
sc.render.fps = fps
sc.render.engine = "BLENDER_EEVEE"
sc.eevee.taa_render_samples = int(R.get("samples", 1))   # the ink lines cover the edges: one sample looks the same as eight, 4x faster
sc.view_settings.view_transform = "Standard"   # flat colours as picked, no filmic roll-off
sc.render.film_transparent = False
sc.render.image_settings.file_format = "PNG"
sc.render.image_settings.color_mode = "RGB"

# world: a flat sky
world = bpy.data.worlds.new("sky"); sc.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
bg.inputs[0].default_value = hex_rgb(R.get("sky", "#bfe3f2"))
bg.inputs[1].default_value = 1.0

floor_z = -(R.get("floor", 1500) - H / 2) * K


def toon_material(name, palette, attr=None):
    """cel shading: diffuse -> two tones; colour from a palette by a per-instance random value"""
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    if attr:
        at = nt.nodes.new("ShaderNodeAttribute"); at.attribute_type = "INSTANCER"; at.attribute_name = attr
        ramp = nt.nodes.new("ShaderNodeValToRGB"); ramp.color_ramp.interpolation = "CONSTANT"
        els = ramp.color_ramp.elements
        while len(els) < len(palette):
            els.new(0.5)
        for i, c in enumerate(palette):
            els[i].position = i / len(palette); els[i].color = hex_rgb(c)
        nt.links.new(at.outputs["Fac"], ramp.inputs["Fac"])
        base = ramp.outputs["Color"]
    else:
        rgb = nt.nodes.new("ShaderNodeRGB"); rgb.outputs[0].default_value = hex_rgb(palette[0]); base = rgb.outputs[0]
    dif = nt.nodes.new("ShaderNodeBsdfDiffuse")
    nt.links.new(base, dif.inputs["Color"])
    s2r = nt.nodes.new("ShaderNodeShaderToRGB"); nt.links.new(dif.outputs[0], s2r.inputs[0])
    tone = nt.nodes.new("ShaderNodeValToRGB"); tone.color_ramp.interpolation = "CONSTANT"
    tone.color_ramp.elements[0].position = 0.0; tone.color_ramp.elements[0].color = (0.62, 0.62, 0.62, 1)
    tone.color_ramp.elements[1].position = 0.28; tone.color_ramp.elements[1].color = (1, 1, 1, 1)
    nt.links.new(s2r.outputs["Color"], tone.inputs["Fac"])
    mix = nt.nodes.new("ShaderNodeMix"); mix.data_type = "RGBA"; mix.blend_type = "MULTIPLY"; mix.inputs["Factor"].default_value = 1.0
    nt.links.new(base, mix.inputs[6]); nt.links.new(tone.outputs["Color"], mix.inputs[7])
    em = nt.nodes.new("ShaderNodeEmission"); nt.links.new(mix.outputs[2], em.inputs["Color"])
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    return m


# ground
bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 190, floor_z))
ground = bpy.context.active_object; ground.scale = (900, 420, 1)   # from well in front of the camera to the far lot
ground.data.materials.append(toon_material("ground", [R.get("ground", "#cfd8a8")]))



def build_props():
    """WP-42: rigid bodies under Bullet (Blender's rigid body world): boxes and balls dropped onto the ground (and each
    other), simulated with a fixed step and baked before rendering, so a frame is a pure function of the request"""
    rw = sc.rigidbody_world
    if rw is None:
        bpy.ops.rigidbody.world_add(); rw = sc.rigidbody_world
    rw.substeps_per_frame = int(R.get("substeps", 10)); rw.solver_iterations = int(R.get("iterations", 20))
    last = max(R.get("frames") or list(range(R.get("count", 1)))) + 2
    rw.point_cache.frame_start = 1; rw.point_cache.frame_end = last
    sc.frame_start = 1; sc.frame_end = last
    bpy.context.view_layer.objects.active = ground; ground.select_set(True)
    bpy.ops.rigidbody.object_add(); ground.rigid_body.type = "PASSIVE"; ground.rigid_body.collision_shape = "BOX"
    ground.rigid_body.friction = R.get("friction", 0.6); ground.select_set(False)
    if R.get("wind"):   # a wind over the whole scene (Blender wind strength: a few hundred moves a banner)
        # it blows left to right and a little away from the camera: wind pushes on a cloth's face, and a banner faces the camera
        bpy.ops.object.effector_add(type="WIND", location=(-6, 6, floor_z + 3), rotation=(0, math.radians(90), math.radians(30)))   # blows along (0.87, 0.5, 0)
        wf = bpy.context.active_object; wf.field.strength = float(R["wind"]); wf.field.flow = 0
        wf.field.noise = 0; wf.field.seed = int(R.get("seed", 1))
    for i, b in enumerate(R.get("bodies", [])):
        sz = b.get("size", 1.0); x, depth, hgt = b.get("at", [W / 2, 6, 3])
        loc = ((x - W / 2) * K, depth, floor_z + hgt)
        if b.get("shape") == "cloth":   # a strip pinned along its top edge (a banner, a flag): Blender cloth, baked
            w_, h_ = (sz, sz) if not isinstance(sz, list) else sz
            bpy.ops.mesh.primitive_grid_add(x_subdivisions=int(b.get("res", 12)), y_subdivisions=int(b.get("res", 12) * h_ / w_) + 2, size=1, location=(0, 0, 0))
            o = bpy.context.active_object; o.name = b.get("name", f"cloth{i}")
            o.rotation_euler = (math.radians(90), 0, 0); o.scale = (w_, h_, 1)
            bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
            o.location = (loc[0], loc[1], loc[2] - h_ / 2)   # `at` is the top edge
            top = max(v.co.z for v in o.data.vertices)
            vg = o.vertex_groups.new(name="pin"); vg.add([v.index for v in o.data.vertices if v.co.z > top - 1e-4], 1.0, "REPLACE")
            o.data.materials.append(toon_material(f"m{i}", [b.get("colour", "#e86a5a")]))
            cl = o.modifiers.new("cloth", "CLOTH"); cs = cl.settings
            cs.vertex_group_mass = "pin"; cs.quality = int(R.get("substeps", 10)); cs.mass = b.get("mass", 0.3)
            cl.point_cache.frame_start = 1; cl.point_cache.frame_end = last
            o.select_set(False)
            continue
        sz = float(sz)
        if b.get("shape", "box") == "ball":
            bpy.ops.mesh.primitive_uv_sphere_add(radius=sz / 2, segments=24, ring_count=12, location=loc)
        else:
            bpy.ops.mesh.primitive_cube_add(size=sz, location=loc)
        o = bpy.context.active_object; o.name = b.get("name", f"body{i}")
        o.rotation_euler = tuple(math.radians(v) for v in b.get("rot", [0, 0, 0]))
        o.data.materials.append(toon_material(f"m{i}", [b.get("colour", "#e8a87c")]))
        bpy.ops.rigidbody.object_add(); rb = o.rigid_body
        rb.type = "ACTIVE"; rb.collision_shape = "SPHERE" if b.get("shape") == "ball" else "BOX"
        rb.mass = float(b.get("mass", 1.0)); rb.friction = b.get("friction", 0.6); rb.restitution = b.get("bounce", 0.2)
        if b.get("velocity"):   # an initial push (m/s): keyed as an animated start that hands over to the simulation
            rb.kinematic = True; o.keyframe_insert("location", frame=1)
            vx, vy, vz = b["velocity"]; o.location = (loc[0] + vx / fps, loc[1] + vy / fps, loc[2] + vz / fps); o.keyframe_insert("location", frame=2)
            rb.keyframe_insert("kinematic", frame=1); rb.kinematic = False; rb.keyframe_insert("kinematic", frame=2)
        o.select_set(False)
    bpy.ops.ptcache.bake_all(bake=True)


if R.get("kind", "city") == "city":
    # the Geometry Nodes set: points scattered on a lot behind the stage, an instance per point with a random size and shade
    B = R.get("blocks", {})
    near, far = B.get("depth", [14, 120])
    width = B.get("width", 140)
    lo, hi = B.get("height", [4, 26])
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, 0))
    host = bpy.context.active_object; host.name = "set"
    mod = host.modifiers.new("set", "NODES")
    ng = bpy.data.node_groups.new("city", "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    mod.node_group = ng
    N = ng.nodes; L = ng.links.new
    out = N.new("NodeGroupOutput")
    grid = N.new("GeometryNodeMeshGrid")
    grid.inputs["Size X"].default_value = width; grid.inputs["Size Y"].default_value = far - near
    grid.inputs["Vertices X"].default_value = 2; grid.inputs["Vertices Y"].default_value = 2
    move = N.new("GeometryNodeTransform")
    move.inputs["Translation"].default_value = (0, (near + far) / 2, floor_z)
    L(grid.outputs["Mesh"], move.inputs["Geometry"])
    dist = N.new("GeometryNodeDistributePointsOnFaces"); dist.distribute_method = "POISSON"
    dist.inputs["Distance Min"].default_value = B.get("min_dist", 9.0)
    dist.inputs["Density Max"].default_value = B.get("density", 0.05)
    dist.inputs["Seed"].default_value = int(R.get("seed", 1))
    L(move.outputs["Geometry"], dist.inputs["Mesh"])
    cube = N.new("GeometryNodeMeshCube"); cube.inputs["Size"].default_value = (1, 1, 1)
    lift = N.new("GeometryNodeTransform"); lift.inputs["Translation"].default_value = (0, 0, 0.5)   # stand on the ground
    L(cube.outputs["Mesh"], lift.inputs["Geometry"])
    inst = N.new("GeometryNodeInstanceOnPoints")
    L(dist.outputs["Points"], inst.inputs["Points"]); L(lift.outputs["Geometry"], inst.inputs["Instance"])
    rnd = N.new("FunctionNodeRandomValue"); rnd.data_type = "FLOAT_VECTOR"
    rnd.inputs["Min"].default_value = (B.get("foot", [5, 8])[0], B.get("foot", [5, 8])[0], lo)
    rnd.inputs["Max"].default_value = (B.get("foot", [5, 8])[1], B.get("foot", [5, 8])[1], hi)
    rnd.inputs["Seed"].default_value = int(R.get("seed", 1)) + 1
    L(rnd.outputs["Value"], inst.inputs["Scale"])
    shade = N.new("FunctionNodeRandomValue"); shade.data_type = "FLOAT"
    shade.inputs["Seed"].default_value = int(R.get("seed", 1)) + 2
    store = N.new("GeometryNodeStoreNamedAttribute"); store.data_type = "FLOAT"; store.domain = "INSTANCE"
    store.inputs["Name"].default_value = "shade"
    L(inst.outputs["Instances"], store.inputs["Geometry"]); L(shade.outputs["Value"], store.inputs["Value"])
    setmat = N.new("GeometryNodeSetMaterial")
    setmat.inputs["Material"].default_value = toon_material("blocks", R.get("palette", ["#e8a87c", "#d27c5a", "#f2d6a2", "#9fc1d6", "#c9b8e8"]), attr="shade")
    L(store.outputs["Geometry"], setmat.inputs["Geometry"])
    L(setmat.outputs["Geometry"], out.inputs["Geometry"])
else:
    build_props()

# light (the toon ramp reads it) and ink lines
sun = bpy.data.lights.new("sun", "SUN"); sun.energy = 3.0
so = bpy.data.objects.new("sun", sun); sc.collection.objects.link(so); so.rotation_euler = (math.radians(50), math.radians(-25), math.radians(30))
sc.render.use_freestyle = bool(R.get("ink_lines", True))
sc.render.line_thickness_mode = "ABSOLUTE"; sc.render.line_thickness = R.get("line", 1.4)
ls = sc.view_layers[0].freestyle_settings.linesets[0] if sc.view_layers[0].freestyle_settings.linesets else sc.view_layers[0].freestyle_settings.linesets.new("ink")
if ls.linestyle is None:
    ls.linestyle = bpy.data.linestyles.new("ink")
ls.linestyle.color = hex_rgb(R.get("ink", "#24160e"))[:3]

# the camera: the 2D camera mapped onto the stage plane
cam_d = bpy.data.cameras.new("cam"); cam_d.lens_unit = "MILLIMETERS"; cam_d.sensor_fit = "HORIZONTAL"; cam_d.sensor_width = 36
cam_d.lens = 18 * D0 / (W * K / 2); cam_d.clip_end = 1000
cam = bpy.data.objects.new("cam", cam_d); sc.collection.objects.link(cam); sc.camera = cam
cam.rotation_euler = (math.radians(90), 0, 0)
keys = R.get("camera") or [[0, [W / 2, H / 2, 1]]]
frames = R.get("frames") or list(range(R.get("count", 1)))
os.makedirs(OUT, exist_ok=True)
PASSES = ("z", "mist", "normal", "position", "vector", "emit", "environment", "shadow", "ambient_occlusion", "diffuse_color",
          "diffuse_direct", "object_index", "cryptomatte_object", "cryptomatte_material")
if R.get("passes"):   # WP-42: separate EEVEE passes beside the picture (one multilayer EXR per frame, as zpass below)
    bad = [x for x in R["passes"] if x not in PASSES]
    if bad:
        raise SystemExit(f"unknown passes {bad} (known: {', '.join(PASSES)})")
    for x in R["passes"]:
        setattr(sc.view_layers[0], f"use_pass_{x}", True)
    if "mist" in R["passes"]:   # mist from the stage plane to the far lot
        world.mist_settings.start = R.get("mist_start", 2.0); world.mist_settings.depth = R.get("mist_depth", 150.0)
if R.get("zpass") or R.get("passes"):   # WP-43: depth ground truth, a multilayer EXR with the picture and the camera distance per pixel
    sc.view_layers[0].use_pass_z = True
    ims = sc.render.image_settings
    if hasattr(ims, "media_type"):   # Blender 5: pick the multilayer media type, then its only format
        ims.media_type = "MULTI_LAYER_IMAGE"
    ims.file_format = "OPEN_EXR_MULTILAYER"
    sc.render.image_settings.color_depth = "32"
    if not R.get("passes"):   # depth ground truth wants the bare geometry; separate passes keep the ink of the picture
        sc.render.use_freestyle = False
LA = None
if R.get("lineart"):   # WP-42: Grease Pencil 3 Line Art draws the ink instead of Freestyle; baked to editable strokes
    sc.render.use_freestyle = False
    for f in frames:   # the camera keyed at the rendered frames, so the bake sees it where the renders do
        cx, cy, z = sample_keys(keys, R.get("start", 0) + f / fps)
        cam.location = ((cx - W / 2) * K, -D0 / z, -(cy - H / 2) * K); cam.keyframe_insert("location", frame=f + 1)
    if R.get("kind") != "props":
        sc.frame_start = min(frames) + 1; sc.frame_end = max(frames) + 1
    bpy.ops.object.grease_pencil_add(type="LINEART_SCENE"); LA = bpy.context.active_object; LA.name = "lineart"
    mod = next(m for m in LA.modifiers if m.type == "LINEART")
    mod.radius = float(R.get("line_px", 3)) / 2 * K   # (a radius in metres; 1 px = 1 cm on the stage plane)
    if hasattr(mod, "target_material") and LA.data.materials:
        LA.data.materials[0].grease_pencil.color = hex_rgb(R.get("ink", "#24160e"))
    bpy.ops.object.lineart_bake_strokes()
track = {}
lines = {}
for f in frames:
    t = R.get("start", 0) + f / fps
    cx, cy, z = sample_keys(keys, t)
    cam.location = ((cx - W / 2) * K, -D0 / z, -(cy - H / 2) * K)
    sc.frame_set(f + 1 if R.get("kind") == "props" else 1)
    if R.get("kind") == "props":   # where each body is (m, the stage's axes: x right, y away, z up), for checks and the record
        track[f] = {o.name: [round(v, 5) for v in (*o.matrix_world.translation, *o.matrix_world.to_euler())] for o in sc.objects if o.rigid_body and o.rigid_body.type == "ACTIVE"}
        for o in sc.objects:   # cloth: the evaluated mesh's top (pinned) and lowest points, and its free bottom edge's mean x
            if any(m.type == "CLOTH" for m in o.modifiers):
                ev = o.evaluated_get(bpy.context.evaluated_depsgraph_get()); vs = [ev.matrix_world @ v.co for v in ev.data.vertices]
                zs = [v.z for v in vs]; lo = min(zs); bot = [v for v in vs if v.z < lo + 0.05]
                track[f][o.name] = {"top": round(max(zs), 5), "low": round(lo, 5), "bottom_x": round(sum(v.x for v in bot) / len(bot), 5),
                                    "pinned_x": round(sum(v.x for v in vs if v.z > max(zs) - 1e-3) / max(1, sum(1 for v in vs if v.z > max(zs) - 1e-3)), 5)}
    if LA is not None:   # the baked strokes of this frame, projected to frame pixels: the ink as editable vectors
        from bpy_extras.object_utils import world_to_camera_view
        lines[f] = []
        for l in LA.data.layers:
            fr_ = next((x for x in l.frames if x.frame_number == f + 1), None)
            if fr_ is None:
                continue
            for st in fr_.drawing.strokes:
                pts = [world_to_camera_view(sc, cam, LA.matrix_world @ p.position) for p in st.points]
                lines[f].append([[round(q.x * W, 2), round((1 - q.y) * H, 2)] for q in pts if q.z > 0])
    multi = R.get("zpass") or R.get("passes")
    sc.render.filepath = os.path.join(OUT, f"f_{f:04d}.{'exr' if multi else 'png'}")
    bpy.ops.render.render(write_still=True)
    if R.get("passes"):   # the picture as the plate too (the passes stay in the EXR)
        ims = sc.render.image_settings
        if hasattr(ims, "media_type"):
            ims.media_type = "IMAGE"
        ims.file_format = "PNG"; ims.color_depth = "8"
        bpy.data.images["Render Result"].save_render(filepath=os.path.join(OUT, f"f_{f:04d}.png"), scene=sc)
        if hasattr(ims, "media_type"):
            ims.media_type = "MULTI_LAYER_IMAGE"
        ims.file_format = "OPEN_EXR_MULTILAYER"; ims.color_depth = "32"
if track:
    json.dump({"floor_z": floor_z, "frames": track}, open(os.path.join(OUT, "bodies.json"), "w"))
if LA is not None:
    json.dump({"size": [W, H], "frames": lines}, open(os.path.join(OUT, "lineart.json"), "w"))
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "lineart.blend"), check_existing=False)   # the strokes, editable
print("rendered", len(frames), "frames to", OUT)
