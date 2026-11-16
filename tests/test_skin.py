# -*- coding: utf-8 -*-
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skin.core import (  # noqa: E402
    Bone, bake, bone_world_matrix, load_rig, sample_keyframes, skin_vertex,
)

HERE = os.path.dirname(os.path.abspath(__file__))
RIG_PATH = os.path.join(HERE, "..", "data", "rig.json")


def make_rig(defs):
    """defs: {name: (parent, keys)}"""
    bones = {}
    for name, (parent, keys) in defs.items():
        b = Bone(name, parent)
        b.keys = keys
        bones[name] = b
    return {"bones": bones, "order": list(defs), "vertices": [], "weights": []}


def test_child_follows_parent_translation():
    """父骨骼平移后，子骨骼的世界位置同步移动。"""
    rig = make_rig({
        "root": (None, [{"t": 0.0, "rot": 0, "pos": [0, 0, 0]},
                        {"t": 1.0, "rot": 0, "pos": [5, 0, 0]}]),
        "arm": ("root", [{"t": 0.0, "rot": 0, "pos": [1, 0, 0]}]),
    })
    m0 = bone_world_matrix(rig, "arm", 0.0)
    m1 = bone_world_matrix(rig, "arm", 1.0)
    assert abs(m0[0][3] - 1.0) < 1e-9
    assert abs(m1[0][3] - 6.0) < 1e-9  # 父平移 5 + 子局部 1


def test_child_follows_parent_rotation():
    """父骨骼旋转 90 度，子骨骼的局部偏移跟着转到 Y 轴。"""
    rig = make_rig({
        "root": (None, [{"t": 0.0, "rot": 0, "pos": [0, 0, 0]},
                        {"t": 1.0, "rot": 90, "pos": [0, 0, 0]}]),
        "arm": ("root", [{"t": 0.0, "rot": 0, "pos": [1, 0, 0]}]),
    })
    m = bone_world_matrix(rig, "arm", 1.0)
    assert abs(m[0][3] - 0.0) < 1e-9
    assert abs(m[1][3] - 1.0) < 1e-9


def test_weights_normalized_to_one():
    """权重和不为 1 时按归一处理：0.25/0.25 与 0.5/0.5 结果相同，顶点不被压扁。"""
    rig = make_rig({
        "a": (None, [{"t": 0.0, "rot": 0, "pos": [0, 0, 0]},
                     {"t": 1.0, "rot": 0, "pos": [2, 0, 0]}]),
        "b": (None, [{"t": 0.0, "rot": 0, "pos": [0, 0, 0]}]),
    })
    p_half = skin_vertex([0, 0, 0], [["a", 0.5], ["b", 0.5]], rig, 1.0)
    p_quarter = skin_vertex([0, 0, 0], [["a", 0.25], ["b", 0.25]], rig, 1.0)
    # 骨骼 a 把顶点搬到 (2,0,0)，b 保持原位，归一后应落在中点 (1,0,0)
    assert abs(p_half[0] - 1.0) < 1e-9
    assert abs(p_half[1]) < 1e-9
    for i in range(3):
        assert abs(p_half[i] - p_quarter[i]) < 1e-9
    # 骨骼分离时顶点长度不缩短：中点到原点距离保持为 1
    assert abs(math.sqrt(sum(c * c for c in p_half)) - 1.0) < 1e-9


def test_zero_weight_bone_ignored():
    """权重为 0 的骨骼不影响结果。"""
    rig = make_rig({
        "a": (None, [{"t": 0.0, "rot": 0, "pos": [0, 0, 0]},
                     {"t": 1.0, "rot": 0, "pos": [2, 0, 0]}]),
        "b": (None, [{"t": 0.0, "rot": 0, "pos": [0, 0, 0]},
                     {"t": 1.0, "rot": 0, "pos": [0, 9, 0]}]),
    })
    with_zero = skin_vertex([1, 1, 0], [["a", 1.0], ["b", 0.0]], rig, 1.0)
    without = skin_vertex([1, 1, 0], [["a", 1.0]], rig, 1.0)
    assert with_zero == without
    assert abs(with_zero[0] - 3.0) < 1e-9 and abs(with_zero[1] - 1.0) < 1e-9


def test_rotation_takes_shortest_path():
    """0 -> 270 度应走 -90 方向的最短路径，中点是 -45 而不是 135。"""
    keys = [{"t": 0.0, "rot": 0, "pos": [0, 0, 0]},
            {"t": 1.0, "rot": 270, "pos": [0, 0, 0]}]
    s = sample_keyframes(keys, 0.5)
    assert abs(s["rot"] - (-45.0)) < 1e-9
    # 170 -> -170 跨 180 度，中点应是 180（或 -180），不能反向穿过 0
    keys2 = [{"t": 0.0, "rot": 170, "pos": [0, 0, 0]},
             {"t": 1.0, "rot": -170, "pos": [0, 0, 0]}]
    s2 = sample_keyframes(keys2, 0.5)
    assert abs(abs(s2["rot"]) - 180.0) < 1e-9


def test_sample_clamps_out_of_range():
    """关键帧范围外钳制到端点，不外推。"""
    keys = [{"t": 0.0, "rot": 0, "pos": [0, 0, 0]},
            {"t": 1.0, "rot": 90, "pos": [1, 2, 0]}]
    lo = sample_keyframes(keys, -3.0)
    hi = sample_keyframes(keys, 7.5)
    assert lo["rot"] == 0 and lo["pos"] == [0, 0, 0]
    assert hi["rot"] == 90 and hi["pos"] == [1, 2, 0]


def test_rest_pose_matches_input():
    """静止帧（绑定姿势）下顶点坐标与输入完全一致。"""
    rig = load_rig(RIG_PATH)
    frames = bake(rig, 1)
    assert len(frames) == 1
    for got, want in zip(frames[0]["vertices"], rig["vertices"]):
        for i in range(3):
            assert abs(got[i] - want[i]) < 1e-9


def test_bake_frame_count_and_all_vertices():
    rig = load_rig(RIG_PATH)
    frames = bake(rig, 12)
    assert len(frames) == 12
    for f in frames:
        assert len(f["vertices"]) == len(rig["vertices"])


def test_bake_is_deterministic():
    """同一输入连续跑两次，输出逐字节相同。"""
    a = json.dumps(bake(load_rig(RIG_PATH), 12), ensure_ascii=False, indent=2)
    b = json.dumps(bake(load_rig(RIG_PATH), 12), ensure_ascii=False, indent=2)
    assert a == b
