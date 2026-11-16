# -*- coding: utf-8 -*-
"""骨骼动画与蒙皮。

约定（README 同步说明）：

- 矩阵为 4x4 行主序，列向量约定：v' = M * v。
- 子骨骼世界矩阵 = 父骨骼世界矩阵 * 本骨骼局部矩阵（局部变换先作用，父级后作用）。
- 局部矩阵 = 平移 * 绕 Z 旋转。
- 绑定姿势取每根骨骼的第一帧关键帧；蒙皮矩阵 = 当前世界矩阵 * 绑定世界矩阵的逆，
  因此静止（处于绑定姿势）时顶点坐标与输入完全一致。
- 顶点最终位置 = 各骨骼（归一化权重 * 蒙皮矩阵 * 顶点）之和；权重为 0 的骨骼跳过。
- 旋转插值走最短路径（角度差折回 [-180, 180)），关键帧范围外钳制到端点。
"""
import json
import math


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
    r = math.radians(deg)
    c, s = math.cos(r), math.sin(r)
    m = mat_identity()
    m[0][0], m[0][1] = c, -s
    m[1][0], m[1][1] = s, c
    return m


def mat_invert_rigid(m):
    """刚性变换（旋转 + 平移，无缩放）的逆矩阵：R^-1 = R^T，t' = -R^T t。"""
    out = mat_identity()
    for i in range(3):
        for j in range(3):
            out[i][j] = m[j][i]
    for i in range(3):
        out[i][3] = -(out[i][0] * m[0][3] + out[i][1] * m[1][3] + out[i][2] * m[2][3])
    return out


def _apply_mat(m, p):
    return [m[i][0] * p[0] + m[i][1] * p[1] + m[i][2] * p[2] + m[i][3] for i in range(3)]


class Bone(object):
    def __init__(self, name, parent=None):
        self.name = name
        self.parent = parent
        self.keys = []


def load_rig(path):
    """读取骨骼与关键帧。"""
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


def _shortest_angle_delta(a, b):
    """b - a 折回到 [-180, 180)，保证旋转插值走最短路径。"""
    return (b - a + 180.0) % 360.0 - 180.0


def sample_keyframes(keys, t):
    """线性插值。旋转走最短路径；t 超出关键帧范围时钳制到端点，不外推。"""
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
                "rot": a["rot"] + _shortest_angle_delta(a["rot"], b["rot"]) * k,
                "pos": [a["pos"][j] + (b["pos"][j] - a["pos"][j]) * k for j in range(3)],
            }
    return keys[-1]


def _local_matrix(bone, t):
    s = sample_keyframes(bone.keys, t)
    return mat_mul(mat_translate(s["pos"][0], s["pos"][1], s["pos"][2]),
                   mat_rotate_z(s["rot"]))


def bone_world_matrix(rig, name, t):
    """骨骼世界矩阵 = 父骨骼世界矩阵 * 本骨骼局部矩阵（递归到根）。"""
    bone = rig["bones"][name]
    local = _local_matrix(bone, t)
    if bone.parent:
        return mat_mul(bone_world_matrix(rig, bone.parent, t), local)
    return local


def _bind_world_matrix(rig, name):
    """绑定姿势（每根骨骼的第一帧关键帧）下的世界矩阵，带缓存。"""
    cache = rig.setdefault("_bind_world", {})
    if name not in cache:
        bone = rig["bones"][name]
        if bone.keys:
            k = bone.keys[0]
            local = mat_mul(mat_translate(k["pos"][0], k["pos"][1], k["pos"][2]),
                            mat_rotate_z(k["rot"]))
        else:
            local = mat_identity()
        if bone.parent:
            local = mat_mul(_bind_world_matrix(rig, bone.parent), local)
        cache[name] = local
    return cache[name]


def _skin_matrix(rig, name, t):
    """蒙皮矩阵 = 当前世界矩阵 * 绑定世界矩阵的逆，扣除绑定姿势偏移。"""
    return mat_mul(bone_world_matrix(rig, name, t),
                   mat_invert_rigid(_bind_world_matrix(rig, name)))


def skin_vertex(pos, weights, rig, t):
    """蒙皮一个顶点：权重归一到 1，权重为 0 的骨骼不参与计算。"""
    total = sum(w for _, w in weights if w != 0)
    if total == 0:
        return list(pos)
    out = [0.0, 0.0, 0.0]
    for bone_name, w in weights:
        if w == 0:
            continue
        p = _apply_mat(_skin_matrix(rig, bone_name, t), pos)
        k = w / total
        out[0] += k * p[0]
        out[1] += k * p[1]
        out[2] += k * p[2]
    return out


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
