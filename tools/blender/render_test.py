import bpy, sys, time, math
import os
A = os.environ.get('ASSETS', 'assets')
OUT = os.environ.get('OUT', 'out/')
engine = sys.argv[sys.argv.index('--') + 1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=A + '/kaykit-adv/addons/kaykit_character_pack_adventures/Characters/gltf/Knight.glb')
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
act = bpy.data.actions.get('Death_A')
arm.animation_data_create(); arm.animation_data.action = act
if hasattr(arm.animation_data, 'action_slot') and act.slots: arm.animation_data.action_slot = act.slots[0]
sc = bpy.context.scene
sc.frame_set(int(act.frame_range[0] + (act.frame_range[1] - act.frame_range[0]) * 0.45))
bpy.ops.mesh.primitive_plane_add(size=30)
g = bpy.context.object; m = bpy.data.materials.new('floor'); m.use_nodes = True
m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.35, 0.28, 0.22, 1); g.data.materials.append(m)
bpy.ops.object.light_add(type='AREA', location=(3, -3, 5)); key = bpy.context.object; key.data.energy = 1500; key.data.size = 3; key.rotation_euler = (math.radians(45), 0, math.radians(45))
bpy.ops.object.light_add(type='AREA', location=(-3, 3, 3)); rim = bpy.context.object; rim.data.energy = 900; rim.data.color = (0.5, 0.7, 1); rim.rotation_euler = (math.radians(-60), 0, math.radians(-135))
w = bpy.data.worlds.new('w'); w.use_nodes = True; w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.05, 0.06, 0.09, 1); sc.world = w
bpy.ops.object.camera_add(location=(2.2, -4.2, 1.6)); cam = bpy.context.object; sc.camera = cam
cam.data.lens = 40
d = bpy.data.objects.new('t', None); sc.collection.objects.link(d); d.location = (0, 0, 0.9)
c = cam.constraints.new('TRACK_TO'); c.target = d; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'
r = sc.render; r.resolution_x, r.resolution_y, r.resolution_percentage = 1080, 1920, 100
r.engine = engine
if engine == 'CYCLES':
    sc.cycles.device = 'CPU'; sc.cycles.samples = 32; sc.cycles.use_denoising = True
else:
    try: sc.eevee.taa_render_samples = 16
    except Exception as e: print('eevee opt', e)
r.filepath = OUT + f'knight_{engine}.png'
t = time.time(); bpy.ops.render.render(write_still=True); print('RENDER', engine, round(time.time() - t, 1), 's')
