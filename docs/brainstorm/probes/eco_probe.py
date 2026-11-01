import importlib, json, time, traceback
res = {}
def probe(name, fn):
    t = time.time()
    try:
        out = fn(); res[name] = {"ok": True, "s": round(time.time() - t, 2), "out": out}
    except Exception as e:
        res[name] = {"ok": False, "err": f"{type(e).__name__}: {str(e)[:160]}"}
def box2d():
    import Box2D
    w = Box2D.b2World(gravity=(0, -10)); g = w.CreateStaticBody(position=(0, 0)); g.CreatePolygonFixture(box=(50, 1))
    b = w.CreateDynamicBody(position=(0, 10)); b.CreatePolygonFixture(box=(1, 1), density=1, friction=0.3, restitution=0.5)
    ys = []
    for i in range(180):
        w.Step(1 / 60, 8, 3); ys.append(round(b.position[1], 4))
    w2 = Box2D.b2World(gravity=(0, -10)); g2 = w2.CreateStaticBody(position=(0, 0)); g2.CreatePolygonFixture(box=(50, 1))
    b2 = w2.CreateDynamicBody(position=(0, 10)); b2.CreatePolygonFixture(box=(1, 1), density=1, friction=0.3, restitution=0.5)
    ys2 = []
    for i in range(180):
        w2.Step(1 / 60, 8, 3); ys2.append(round(b2.position[1], 4))
    return {"rest_y": ys[-1], "min_y": min(ys), "deterministic_rerun": ys == ys2}
def pybullet():
    import pybullet as p
    c = p.connect(p.DIRECT); p.setGravity(0, 0, -10); p.createMultiBody(0, p.createCollisionShape(p.GEOM_PLANE))
    ids = [p.createMultiBody(1, p.createCollisionShape(p.GEOM_BOX, halfExtents=[.5, .5, .5]), basePosition=[0, 0, 0.5 + i * 1.01]) for i in range(5)]
    for _ in range(600): p.stepSimulation()
    top = p.getBasePositionAndOrientation(ids[-1])[0]; p.disconnect()
    return {"stack_top_z_after_10s": round(top[2], 3), "expected": 4.54}
def taichi():
    import taichi as ti
    ti.init(arch=ti.cpu, log_level=ti.ERROR)
    n = 1 << 18; x = ti.field(ti.f32, n)
    @ti.kernel
    def step():
        for i in x: x[i] = ti.sin(i * 0.001) * 2.0
    step(); t = time.time(); [step() for _ in range(50)]; ti.sync()
    return {"version": ti.__version__, "ms_per_kernel_256k": round((time.time() - t) / 50 * 1000, 3)}
def manifold():
    import manifold3d as m
    a = m.Manifold.cube([2, 2, 2], True); b = m.Manifold.sphere(1.3, 48)
    r = a - b
    return {"volume": round(r.volume(), 4), "genus": r.genus()}
def usd():
    from pxr import Usd, UsdGeom, Gf
    st = Usd.Stage.CreateInMemory(); x = UsdGeom.Xform.Define(st, "/World"); s = UsdGeom.Sphere.Define(st, "/World/ball")
    s.GetRadiusAttr().Set(2.0); UsdGeom.XformCommonAPI(s).SetTranslate(Gf.Vec3d(0, 1, 0))
    txt = st.GetRootLayer().ExportToString()
    return {"usda_bytes": len(txt), "has_sphere": "def Sphere" in txt}
def music21():
    import music21 as m
    s = m.stream.Stream([m.note.Note(p, quarterLength=1) for p in ["C4", "E4", "G4", "C5"]])
    return {"key": str(s.analyze("key")), "version": m.__version__}
for name, fn in [("Box2D", box2d), ("pybullet", pybullet), ("taichi", taichi), ("manifold3d", manifold), ("usd-core", usd), ("music21", music21)]:
    probe(name, fn)
print(json.dumps(res, indent=1))
