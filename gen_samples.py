# -*- coding: utf-8 -*-
"""生成两骨骼绑定：躯干绕 Z 旋转 0 到 90 度，手臂跟随躯干再自转。"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

RIG = {
    "bones": [
        {"name": "root", "parent": None,
         "keys": [{"t": 0.0, "rot": 0, "pos": [0, 0, 0]},
                  {"t": 0.5, "rot": 45, "pos": [0.5, 0, 0]},
                  {"t": 1.0, "rot": 90, "pos": [1, 0, 0]}]},
        {"name": "arm", "parent": "root",
         "keys": [{"t": 0.0, "rot": 0, "pos": [1, 0, 0]},
                  {"t": 0.5, "rot": -30, "pos": [1, 0, 0]},
                  {"t": 1.0, "rot": 60, "pos": [1, 0, 0]}]},
    ],
    "vertices": [[0, 0, 0], [1, 0, 0], [0, 1, 0], [2, 0, 0]],
    "weights": [
        [["root", 1.0]],
        [["root", 0.7], ["arm", 0.3]],
        [["root", 1.0]],
        [["arm", 1.0]],
    ],
}

if __name__ == "__main__":
    os.makedirs(os.path.join(HERE, "data"), exist_ok=True)
    path = os.path.join(HERE, "data", "rig.json")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(RIG, f, ensure_ascii=False, indent=2)
    print("已生成", path)
