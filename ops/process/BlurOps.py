# -*- coding: utf-8 -*-
"""
滤波（处理类算子）—— **一个节点一个文件**。

2026.10.14（批次5 目标1）：原先处理类 6 个节点都挤在 `ops/process/ProcessOps.py`
一个大类文件里；现在每个节点独占一个文件：算法 + 引擎入口 `_run_*` + 日志文案 +
参数校验 + 声明表 `*_SPECS` 都在本文件里（与 `ops/detect/` 下三个检测节点同构）。
公共零件（`to_bgr` / `apply_to_roi` / `odd_kernel`）在 `core/ImageOps.py`。
"""
import cv2

from core.ImageOps import apply_to_roi, odd_kernel

from core.ParamRules import clamp_float, force_odd, read_float, read_int


def blur(img, roi, params):
    """滤波：均值 / 高斯 / 中值"""
    blur_type = params.get("blur_type", "高斯")
    ksize = odd_kernel(params.get("blur_ksize", 3), 1, 31)
    sigma = float(params.get("blur_sigma", 0.0))

    def _do(patch):
        if blur_type == "均值":
            return cv2.blur(patch, (ksize, ksize))
        if blur_type == "中值":
            # 中值滤波要求核奇数且 > 1
            return cv2.medianBlur(patch, max(3, ksize))
        return cv2.GaussianBlur(patch, (ksize, ksize), sigma)

    return apply_to_roi(img, roi, _do)


def _run_blur(detector, img, roi, params):
    return blur(img, roi, params), []


def validate_blur(params):
    """滤波：核大小取 [1,31] 内的奇数、高斯标准差夹进 [0,20]

    （批次4 目标4 的规则；实测 cv2 4.13 下核大小偶数 / 0 会直接抛异常）
    """
    fixed, notes = dict(params), []
    fixed["blur_ksize"] = force_odd(
        read_int(fixed, "blur_ksize", 3, "核大小", notes), 1, 31, "核大小", notes)
    fixed["blur_sigma"] = clamp_float(
        read_float(fixed, "blur_sigma", 0.0, "高斯标准差", notes), 0.0, 20.0, "高斯标准差", notes)
    return fixed, notes, []


# 声明表（kind = KIND_PROCESS）
BLUR_SPECS = [
    {
        "name": "滤波",
        "run": _run_blur,
        "format_result": lambda results: "执行成功（图像已处理，下游可见）",
        "validate": validate_blur,
        "param_specs": [
            ("blur_type", "滤波方式", "combo",
             {"options": ["均值", "高斯", "中值"], "default": "高斯"}),
            ("blur_ksize", "核大小", "int",
             {"min": 1, "max": 31, "default": 3, "odd": True}),
            ("blur_sigma", "高斯标准差", "float",
             {"min": 0.0, "max": 20.0, "step": 0.5, "decimals": 2, "default": 0.0}),
        ],
    },
]
