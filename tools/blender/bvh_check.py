"""Read a BVH with Blender's own importer and print every bone's head position at some frames (WP-12 check).
    blender -b --factory-startup --python bvh_check.py -- FILE.bvh OUT.json FRAME [FRAME ...]
Positions are Blender world coordinates (z up); the BVH's y-up (x, y) appears as Blender's (x, z)."""
import sys, json
import bpy
args = sys.argv[sys.argv.index('--') + 1:]
src, out, frames = args[0], args[1], [int(f) for f in args[2:]]
bpy.ops.import_anim.bvh(filepath=src, global_scale=1.0, frame_start=1, use_fps_scale=False, update_scene_fps=True, update_scene_duration=True, rotate_mode='NATIVE')
arm = next(o for o in bpy.context.scene.objects if o.type == 'ARMATURE')
res = {}
for f in frames:
    bpy.context.scene.frame_set(f + 1)   # BVH frame 0 is Blender frame 1
    res[f] = {b.name: list(arm.matrix_world @ b.head) for b in arm.pose.bones}
json.dump(res, open(out, 'w'))
