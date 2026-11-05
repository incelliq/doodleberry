"""A procedural 3D set built with Geometry Nodes and rendered in headless Blender (WP-42), framed by the shot's 2D
camera so it sits behind the 2D puppets exactly.

    blender -b --factory-startup --gpu-backend vulkan --python dbe/blender_gn.py -- REQ.json OUT_DIR

REQ: {size: [W, H], fps, start, frames: [frame numbers to render] | count, camera: [[t, [cx, cy, zoom]]], floor: y px,
      kind: "city", seed, blocks: {count, min_dist, depth: [near, far], width, height: [lo, hi]}, palette: [...],
      sky: "#..", ground: "#..", ink: "#..", line: 1.4, samples: 1, ink_lines: true, zpass: false (EXR with depth)}

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
if R.get("zpass"):   # WP-43: depth ground truth, a multilayer EXR with the picture and the camera distance per pixel
    sc.view_layers[0].use_pass_z = True
    ims = sc.render.image_settings
    if hasattr(ims, "media_type"):   # Blender 5: pick the multilayer media type, then its only format
        ims.media_type = "MULTI_LAYER_IMAGE"
    ims.file_format = "OPEN_EXR_MULTILAYER"
    sc.render.image_settings.color_depth = "32"
    sc.render.use_freestyle = False
for f in frames:
    t = R.get("start", 0) + f / fps
    cx, cy, z = sample_keys(keys, t)
    cam.location = ((cx - W / 2) * K, -D0 / z, -(cy - H / 2) * K)
    sc.frame_set(1)
    sc.render.filepath = os.path.join(OUT, f"f_{f:04d}.{'exr' if R.get('zpass') else 'png'}")
    bpy.ops.render.render(write_still=True)
print("rendered", len(frames), "frames to", OUT)
