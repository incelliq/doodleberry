import bpy, os, glob
A = os.environ.get('ASSETS', 'assets')
OUT = A + '/converted'; os.makedirs(OUT, exist_ok=True)
# 1) Gobkit: clip names, lengths, sizes
for f in sorted(glob.glob(A + '/gobkit-v1/*.glb')):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=f)
    meshes = [o for o in bpy.data.objects if o.type == 'MESH']
    h = max(max((o.matrix_world @ v.co).z for v in o.data.vertices) for o in meshes)
    tris = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in meshes)
    arm = [o for o in bpy.data.objects if o.type == 'ARMATURE'][0]
    print('GOB', os.path.basename(f), f'h={h:.2f}m tris={tris} bones={len(arm.data.bones)}', [(a.name, int(a.frame_range[1] - a.frame_range[0])) for a in bpy.data.actions])
# 2) Kenney Survivors: model + 3 animation FBX -> one GLB per skin
K = A + '/kenney-survivors'
for skin in ['survivorFemaleA', 'survivorMaleB', 'zombieA', 'zombieC']:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=K + '/Model/characterMedium.fbx')
    arm = [o for o in bpy.data.objects if o.type == 'ARMATURE'][0]
    keep = set(bpy.data.objects)
    for anim in ['idle', 'run', 'jump']:
        n0 = set(bpy.data.actions)
        bpy.ops.import_scene.fbx(filepath=K + f'/Animations/{anim}.fbx')
        for a in set(bpy.data.actions) - n0: a.name = anim; a.use_fake_user = True
        for o in list(set(bpy.data.objects) - keep): bpy.data.objects.remove(o, do_unlink=True)
    img = bpy.data.images.load(K + f'/Skins/{skin}.png')
    for o in bpy.data.objects:
        if o.type == 'MESH':
            m = bpy.data.materials.new(skin); m.use_nodes = True
            t = m.node_tree.nodes.new('ShaderNodeTexImage'); t.image = img; t.interpolation = 'Closest'
            m.node_tree.links.new(t.outputs['Color'], m.node_tree.nodes['Principled BSDF'].inputs['Base Color'])
            m.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.8
            o.data.materials.clear(); o.data.materials.append(m)
    # push every action to an NLA track so the glTF exporter writes them all as named clips
    for a in [a for a in bpy.data.actions if '.' in a.name]: bpy.data.actions.remove(a)  # the model FBX brings its own copies
    arm.animation_data_create()
    for a in bpy.data.actions:
        tr = arm.animation_data.nla_tracks.new(); tr.name = a.name; tr.strips.new(a.name, 1, a)
    arm.animation_data.action = None
    bpy.ops.export_scene.gltf(filepath=OUT + f'/kenney_{skin}.glb', export_animation_mode='NLA_TRACKS')
    print('KEN', skin, [a.name for a in bpy.data.actions])
