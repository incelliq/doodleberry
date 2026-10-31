import os
import bpy, sys, time, math, importlib
OUT = os.environ.get('OUT', 'out/')
bpy.ops.wm.read_factory_settings(use_empty=False)
for o in list(bpy.data.objects): bpy.data.objects.remove(o)
mods = [m for m in __import__('sys').modules if m.endswith('mpfb')]
print('MPFBMODS', mods[:3])
base = mods[0]
HS = importlib.import_module(base + '.services.humanservice').HumanService
TS = importlib.import_module(base + '.services.targetservice').TargetService
h = HS.create_human()
print('HUMAN', h.name, len(h.data.vertices))
try:
    TS.set_macro_target_value(h, 'gender', 1.0) if hasattr(TS, 'set_macro_target_value') else None
except Exception as e: print('macro', e)
try:
    rig = HS.add_builtin_rig(h, 'game_engine'); print('RIG', rig.name if rig else None, len(rig.data.bones) if rig else 0)
except Exception as e: print('RIGERR', e)
print([n for n in dir(HS) if not n.startswith('_')][:60])
bpy.ops.export_scene.gltf(filepath=OUT + 'mpfb_human.glb', export_apply=True)
print('EXPORTED')
