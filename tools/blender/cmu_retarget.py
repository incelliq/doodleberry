"""Retarget CMU mocap (ASF/AMC) onto the Quaternius UAL mannequin (UE-style skeleton) and export GLB.

    blender -b --factory-startup --python cmu_retarget.py -- TARGET.glb OUT.glb SUBJ.asf CLIP.amc[=Name] [CLIP2.amc[=Name] ...]

Method: CMU's ASF/AMC rest pose has every bone's world rotation equal to identity, so a bone's world rotation at a
frame (R = R_parent · C · M · C⁻¹) is directly its rotation away from rest. For each mapped target bone we align its
rest direction to the source bone's rest direction (Q), then pose it to R · Q · Rest_target in world space, parents
first. The root height is scaled from the source to the target pelvis. 120 fps is resampled to 30 fps.
CMU data: mocap.cs.cmu.edu ("free for all uses"; may be included in commercial products; do not resell the data).
"""
import sys, math
import bpy
from mathutils import Matrix, Euler, Vector, Quaternion

args = sys.argv[sys.argv.index('--') + 1:]
TARGET, OUT, ASF = args[0], args[1], args[2]
CLIPS = [(a.split('=')[0], a.split('=')[1] if '=' in a else a.split('/')[-1].split('.')[0]) for a in args[3:]]
SCALE = (1.0 / 0.45) * 2.54 / 100.0  # CMU units -> metres (from the CMU FAQ)
STEP = 4  # 120 fps -> 30 fps

MAP = {  # CMU bone -> UE mannequin bone
    'lowerback': 'spine_01', 'upperback': 'spine_02', 'thorax': 'spine_03', 'lowerneck': 'neck_01', 'upperneck': 'Head',
    'lclavicle': 'clavicle_l', 'lhumerus': 'upperarm_l', 'lradius': 'lowerarm_l', 'lwrist': 'hand_l',
    'rclavicle': 'clavicle_r', 'rhumerus': 'upperarm_r', 'rradius': 'lowerarm_r', 'rwrist': 'hand_r',
    'lfemur': 'thigh_l', 'ltibia': 'calf_l', 'lfoot': 'foot_l', 'ltoes': 'ball_l',
    'rfemur': 'thigh_r', 'rtibia': 'calf_r', 'rfoot': 'foot_r', 'rtoes': 'ball_r',
}
K = Matrix.Rotation(math.radians(90), 3, 'X')  # CMU is Y-up; Blender is Z-up


def parse_asf(path):
    bones, hier, mode, cur = {}, {}, None, None
    for raw in open(path):
        ln = raw.strip()
        if not ln or ln.startswith('#'):
            continue
        if ln.startswith(':'):
            mode = ln.split()[0]
            continue
        tok = ln.split()
        if mode == ':bonedata':
            if tok[0] == 'begin':
                cur = {'dof': [], 'axis': (0, 0, 0)}
            elif tok[0] == 'end':
                bones[cur['name']] = cur
            elif tok[0] == 'name':
                cur['name'] = tok[1]
            elif tok[0] == 'direction':
                cur['dir'] = Vector([float(x) for x in tok[1:4]])
            elif tok[0] == 'length':
                cur['len'] = float(tok[1])
            elif tok[0] == 'axis':
                cur['axis'] = tuple(float(x) for x in tok[1:4])
            elif tok[0] == 'dof':
                cur['dof'] = [d.lower() for d in tok[1:]]
        elif mode == ':hierarchy' and tok[0] not in ('begin', 'end'):
            for ch in tok[1:]:
                hier[ch] = tok[0]
    for b in bones.values():
        b['C'] = Euler([math.radians(a) for a in b['axis']], 'XYZ').to_matrix()
        b['Ci'] = b['C'].inverted()
    return bones, hier


def parse_amc(path):
    frames, cur = [], None
    for raw in open(path):
        ln = raw.strip()
        if not ln or ln[0] in '#:':
            continue
        tok = ln.split()
        if len(tok) == 1 and tok[0].isdigit():
            cur = {}
            frames.append(cur)
        elif cur is not None:
            cur[tok[0]] = [float(x) for x in tok[1:]]
    return frames


def order(hier, bones):
    out, seen = [], set(['root'])
    while len(out) < len(bones):
        for b in bones:
            if b not in seen and hier.get(b) in seen:
                out.append(b)
                seen.add(b)
    return out


def world_rots(fr, bones, hier, seq):
    r = fr['root']
    R = {'root': Euler([math.radians(a) for a in r[3:6]], 'XYZ').to_matrix()}
    for b in seq:
        B = bones[b]
        ang = {'rx': 0.0, 'ry': 0.0, 'rz': 0.0}
        for d, v in zip(B['dof'], fr.get(b, [])):
            ang[d] = math.radians(v)
        M = Euler((ang['rx'], ang['ry'], ang['rz']), 'XYZ').to_matrix()
        R[b] = R[hier[b]] @ B['C'] @ M @ B['Ci']
    return R, Vector(r[0:3])


bones, hier = parse_asf(ASF)
seq = order(hier, bones)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=TARGET)
arm = [o for o in bpy.data.objects if o.type == 'ARMATURE'][0]
ORIGINAL = [a.name for a in bpy.data.actions]  # the target's own clips are kept and exported alongside
AW = arm.matrix_world.to_3x3()
rest = {b.name: (AW @ b.matrix_local.to_3x3()).normalized() for b in arm.data.bones}
rest_dir = {b.name: (AW @ (b.tail_local - b.head_local)).normalized() for b in arm.data.bones}
# Q aligns each target bone's rest direction with its source bone's rest direction (both in Blender world space)
Q = {}
for s, t in MAP.items():
    src = (K @ bones[s]['dir']).normalized()
    Q[t] = rest_dir[t].rotation_difference(src).to_matrix()
pelvis_h = (arm.matrix_world @ arm.data.bones['pelvis'].head_local).z
tseq = [b.name for b in arm.data.bones if b.name in MAP.values() or b.name == 'pelvis']  # parents come before children
inv_map = {v: k for k, v in MAP.items()}

arm.animation_data_create()
for path, name in CLIPS:
    frames = parse_amc(path)[::STEP]
    src_h = frames[0]['root'][1]
    hs = pelvis_h / (src_h * SCALE) if src_h else 1.0
    act = bpy.data.actions.new(name)
    act.use_fake_user = True
    arm.animation_data.action = act
    if hasattr(arm.animation_data, 'action_slot') and act.slots:
        arm.animation_data.action_slot = act.slots[0]
    x0 = None
    for fi, fr in enumerate(frames):
        R, pos = world_rots(fr, bones, hier, seq)
        p = K @ (pos * SCALE * hs)
        if x0 is None:
            x0 = Vector((p.x, p.y, 0))
        for t in tseq:
            pb = arm.pose.bones[t]
            if t == 'pelvis':
                Rw = (K @ R['root'] @ K.inverted()) @ rest['pelvis']
                head_w = p - x0
            else:
                Rw = (K @ R[inv_map[t]] @ K.inverted()) @ Q[t] @ rest[t]
                head_w = arm.matrix_world @ pb.head  # keep the posed joint position from the parent chain
            Mw = Rw.to_4x4()
            Mw.translation = head_w
            loc, rot, _ = (arm.matrix_world.inverted() @ Mw).decompose()
            pb.matrix = Matrix.LocRotScale(loc, rot, None)
            bpy.context.view_layer.update()
        for t in tseq:
            pb = arm.pose.bones[t]
            pb.keyframe_insert('rotation_quaternion', frame=fi + 1)
            if t == 'pelvis':
                pb.keyframe_insert('location', frame=fi + 1)
    arm.animation_data.action = None
    nk = 0
    try:
        for lay in act.layers:
            for st in lay.strips:
                for cb in st.channelbags:
                    nk += sum(len(fc.keyframe_points) for fc in cb.fcurves)
    except AttributeError:
        nk = sum(len(fc.keyframe_points) for fc in act.fcurves)
    print('CLIP', name, len(frames), 'frames @30fps', nk, 'keys')
for tr in list(arm.animation_data.nla_tracks):
    arm.animation_data.nla_tracks.remove(tr)
print('ALL CLIPS', len(bpy.data.actions), ORIGINAL[:3], '...')
bpy.ops.export_scene.gltf(filepath=OUT, export_animation_mode='ACTIONS')
print('EXPORTED', OUT)
