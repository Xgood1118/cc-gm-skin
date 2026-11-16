# -*- coding: utf-8 -*-
"""骨骼动画与蒙皮骨架。

关键帧线性插值不做端点钳制，蒙皮只取第一个骨骼的权重，权重和不为 1 时模型会被压扁。
"""


def mat_identity():
    return [[1.0, 0, 0, 0], [0, 1.0, 0, 0], [0, 0, 1.0, 0], [0, 0, 0, 1.0]]


def mat_mul(a, b):
    out = [[0.0] * 4 for _ in range(4)]
    for i in range(4):
        for j in range(4):
            s = 0.0
            for k in range(4):
                s += a[i][k] * b[k][j]
            out[i][j] = s
    return out


def mat_translate(x, y, z):
    m = mat_identity()
    m[0][3], m[1][3], m[2][3] = x, y, z
    return m


def mat_rotate_z(deg):
    import math
    r = math.radians(deg)
    c, s = math.cos(r), math.sin(r)
    m = mat_identity()
    m[0][0], m[0][1] = c, -s
    m[1][0], m[1][1] = s, c
    return m


class Bone(object):
    def __init__(self, name, parent=None):
        self.name = name
        self.parent = parent
        self.keys = []


def load_rig(path):
    """读取骨骼与关键帧。"""
    import json
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    bones = {}
    order = []
    for b in data["bones"]:
        bone = Bone(b["name"], b.get("parent"))
        bone.keys = b.get("keys", [])
        bones[b["name"]] = bone
        order.append(b["name"])
    return {"bones": bones, "order": order,
            "vertices": data.get("vertices", []),
            "weights": data.get("weights", [])}


def sample_keyframes(keys, t):
    """线性插值。t 超出关键帧范围时原样外推。"""
    if not keys:
        return {"t": 0.0, "rot": 0.0, "pos": [0.0, 0.0, 0.0]}
    if t <= keys[0]["t"]:
        return keys[0]
    if t >= keys[-1]["t"]:
        return keys[-1]
    for i in range(len(keys) - 1):
        a, b = keys[i], keys[i + 1]
        if a["t"] <= t <= b["t"]:
            span = b["t"] - a["t"]
            k = 0.0 if span == 0 else (t - a["t"]) / span
            return {
                "t": t,
                "rot": a["rot"] + (b["rot"] - a["rot"]) * k,
                "pos": [a["pos"][j] + (b["pos"][j] - a["pos"][j]) * k for j in range(3)],
            }
    return keys[-1]


def bone_world_matrix(rig, name, t):
    """算骨骼的世界矩阵。当前只应用本骨骼的变换，不乘父骨骼。"""
    bone = rig["bones"][name]
    s = sample_keyframes(bone.keys, t)
    local = mat_mul(mat_translate(s["pos"][0], s["pos"][1], s["pos"][2]),
                    mat_rotate_z(s["rot"]))
    return local


def skin_vertex(pos, weights, rig, t):
    """蒙皮一个顶点。当前只用第一个骨骼，且不归一权重。"""
    if not weights:
        return list(pos)
    bone_name, w = weights[0]
    m = bone_world_matrix(rig, bone_name, t)
    x = pos[0] * w
    y = pos[1] * w
    z = pos[2] * w
    return [m[0][0] * x + m[0][1] * y + m[0][2] * z + m[0][3],
            m[1][0] * x + m[1][1] * y + m[1][2] * z + m[1][3],
            m[2][0] * x + m[2][1] * y + m[2][2] * z + m[2][3]]


def bake(rig, frames, fps=24):
    out = []
    for i in range(frames):
        t = float(i) / fps
        frame = []
        for v, w in zip(rig["vertices"], rig["weights"]):
            frame.append(skin_vertex(v, w, rig, t))
        out.append({"frame": i, "t": t, "vertices": frame})
    return out


def main(argv=None):
    import argparse
    import json
    import os
    ap = argparse.ArgumentParser(prog="skin")
    ap.add_argument("rig")
    ap.add_argument("--frames", type=int, default=12)
    ap.add_argument("--out", default="frames.json")
    args = ap.parse_args(argv)
    rig = load_rig(args.rig)
    frames = bake(rig, args.frames)
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(frames, f, ensure_ascii=False, indent=2)
    print("烘焙 %d 帧" % len(frames))
    return 0
