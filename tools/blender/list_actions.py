import bpy, sys, time
import os
A = os.environ.get('ASSETS', 'assets')
bpy.ops.wm.read_factory_settings(use_empty=True)
for f in [A + '/kaykit-adv/addons/kaykit_character_pack_adventures/Characters/gltf/Knight.glb', A + '/RobotExpressive.glb']:
    n0 = len(bpy.data.actions)
    bpy.ops.import_scene.gltf(filepath=f)
    acts = [a.name for a in bpy.data.actions][n0:]
    print('FILE', f.split('/')[-1], 'actions', len(acts), acts[:80])
print('ENGINES', [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items])
