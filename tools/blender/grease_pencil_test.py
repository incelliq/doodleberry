import bpy, math, time
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
# Grease Pencil v3 object built from code: a body stroke loop (filled) and a smile, animated over 24 frames
gpd = bpy.data.grease_pencils_v3.new('Blob') if hasattr(bpy.data, 'grease_pencils_v3') else bpy.data.grease_pencils.new('Blob')
ob = bpy.data.objects.new('Blob', gpd); sc.collection.objects.link(ob)
mat_fill = bpy.data.materials.new('green'); bpy.data.materials.create_gpencil_data(mat_fill)
mat_fill.grease_pencil.show_fill = True; mat_fill.grease_pencil.fill_color = (0.36, 0.72, 0.45, 1); mat_fill.grease_pencil.color = (0.14, 0.09, 0.06, 1)
mat_ink = bpy.data.materials.new('ink'); bpy.data.materials.create_gpencil_data(mat_ink); mat_ink.grease_pencil.color = (0.14, 0.09, 0.06, 1)
gpd.materials.append(mat_fill); gpd.materials.append(mat_ink)
layer = gpd.layers.new('Body')
for f in range(1, 25):
    fr = layer.frames.new(f)
    dr = fr.drawing
    y = 0.6 * math.sin(f / 24 * math.pi)
    n = 40
    dr.add_strokes([n, 12])
    body, smile = dr.strokes[0], dr.strokes[1]
    for i, p in enumerate(body.points):
        a = i / n * 2 * math.pi
        p.position = (math.cos(a) * 1.0, 0, math.sin(a) * 1.1 * (1 - 0.1 * y) + y)
        p.radius = 0.03
    body.cyclic = True; body.material_index = 0
    for i, p in enumerate(smile.points):
        u = i / 11
        p.position = (-0.4 + 0.8 * u, -0.01, 0.2 + y - 0.25 * math.sin(u * math.pi))
        p.radius = 0.025
    smile.material_index = 1
cam_data = bpy.data.cameras.new('cam'); cam = bpy.data.objects.new('cam', cam_data); sc.collection.objects.link(cam); sc.camera = cam
cam.location = (0, -6, 0.3); cam.rotation_euler = (math.radians(90), 0, 0)
sc.render.resolution_x, sc.render.resolution_y = 540, 960
w = bpy.data.worlds.new('w'); w.use_nodes = True; w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.85, 0.92, 0.97, 1); sc.world = w
sc.frame_start, sc.frame_end = 1, 24
sc.render.engine = 'BLENDER_EEVEE'
sc.render.filepath = 'out/gp_'
t = time.time(); bpy.ops.render.render(animation=True); print('GPRENDER', round((time.time() - t) / 24, 2), 's/frame')
