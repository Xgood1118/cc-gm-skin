# -*- coding: utf-8 -*-
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skin.core import mat_identity, mat_mul, mat_translate, sample_keyframes  # noqa: E402


def test_identity_mul():
    i = mat_identity()
    a = mat_translate(3, 4, 5)
    assert mat_mul(i, a) == a


def test_translate_matrix():
    m = mat_translate(1, 2, 3)
    assert m[0][3] == 1 and m[1][3] == 2 and m[2][3] == 3


def test_sample_between_keys():
    keys = [{"t": 0.0, "rot": 0, "pos": [0, 0, 0]},
            {"t": 1.0, "rot": 90, "pos": [1, 0, 0]}]
    s = sample_keyframes(keys, 0.5)
    assert abs(s["rot"] - 45) < 1e-6
    assert abs(s["pos"][0] - 0.5) < 1e-6


def test_sample_out_of_range():
    keys = [{"t": 0.0, "rot": 0, "pos": [0, 0, 0]},
            {"t": 1.0, "rot": 90, "pos": [1, 0, 0]}]
    assert sample_keyframes(keys, -0.5)["rot"] == 0
    assert sample_keyframes(keys, 2.0)["rot"] == 90
