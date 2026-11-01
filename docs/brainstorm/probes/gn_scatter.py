# Build a Geometry Nodes graph from code (grid -> distribute points (seeded) -> instance cones), evaluate headless,
# export the evaluated mesh, and print a content hash. Run twice: the hashes must match (determinism).
import bpy, hashlib, sys, json, time
t0 = time.time()
bpy.ops.wm.read_factory_settings(use_empty=True)
spec = json.loads(sys.argv[sys.argv.index("--") + 1])
me = bpy.data.meshes.new("base"); ob = bpy.data.objects.new("terrain", me); bpy.context.scene.collection.objects.link(ob)
ng = bpy.data.node_groups.new("scatter", "GeometryNodeTree")
ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
N = ng.nodes; L = ng.links
grid = N.new("GeometryNodeMeshGrid"); grid.inputs["Size X"].default_value = spec["size"]; grid.inputs["Size Y"].default_value = spec["size"]
grid.inputs["Vertices X"].default_value = 40; grid.inputs["Vertices Y"].default_value = 40
noise = N.new("ShaderNodeTexNoise"); setpos = N.new("GeometryNodeSetPosition"); comb = N.new("ShaderNodeCombineXYZ")
mult = N.new("ShaderNodeMath"); mult.operation = "MULTIPLY"; mult.inputs[1].default_value = spec["height"]
L.new(noise.outputs["Fac"], mult.inputs[0]); L.new(mult.outputs[0], comb.inputs["Z"]); L.new(comb.outputs[0], setpos.inputs["Offset"])
L.new(grid.outputs["Mesh"], setpos.inputs["Geometry"])
dist = N.new("GeometryNodeDistributePointsOnFaces"); dist.inputs["Density"].default_value = spec["density"]; dist.inputs["Seed"].default_value = spec["seed"]
L.new(setpos.outputs["Geometry"], dist.inputs["Mesh"])
cone = N.new("GeometryNodeMeshCone"); cone.inputs["Radius Bottom"].default_value = 0.3; cone.inputs["Depth"].default_value = 1.2
inst = N.new("GeometryNodeInstanceOnPoints"); L.new(dist.outputs["Points"], inst.inputs["Points"]); L.new(cone.outputs["Mesh"], inst.inputs["Instance"])
real = N.new("GeometryNodeRealizeInstances"); L.new(inst.outputs["Instances"], real.inputs["Geometry"])
join = N.new("GeometryNodeJoinGeometry"); L.new(setpos.outputs["Geometry"], join.inputs[0]); L.new(real.outputs["Geometry"], join.inputs[0])
out = N.new("NodeGroupOutput"); L.new(join.outputs[0], out.inputs[0])
mod = ob.modifiers.new("scatter", "NODES"); mod.node_group = ng
dg = bpy.context.evaluated_depsgraph_get(); ev = ob.evaluated_get(dg); m = ev.to_mesh()
co = [round(c, 5) for v in m.vertices for c in v.co]
h = hashlib.sha256(json.dumps(co).encode()).hexdigest()[:16]
print("GN_RESULT", json.dumps({"verts": len(m.vertices), "faces": len(m.polygons), "hash": h, "s": round(time.time() - t0, 2)}))
