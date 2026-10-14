# -*- coding: utf-8 -*-
"""
形态学（处理类算子）—— **一个节点一个文件**。

2026.10.14（批次5 目标1）：原先处理类 6 个节点都挤在 `ops/process/ProcessOps.py`
一个大类文件里；现在每个节点独占一个文件：算法 + 引擎入口 `_run_*` + 日志文案 +
参数校验 + 声明表 `*_SPECS` 都在本文件里（与 `ops/detect/` 下三个检测节点同构）。
公共零件（`to_bgr` / `apply_to_roi` / `odd_kernel`）在 `core/ImageOps.py`。
"""
import cv2

from core.ImageOps import apply_to_roi, odd_kernel, to_bgr

from core.ParamRules import clamp_int, force_odd, read_int


def morphology(img, roi, params):
    """形态学：腐蚀 / 膨胀 / 开运算 / 闭运算 / 梯度 / 顶帽 / 黑帽

    OpenCV 里这七个是同一个 API（cv2.morphologyEx）的不同模式，参数完全一样
    （核形状 + 核大小 + 迭代次数），只有 op 不同，所以共用一个节点、一张参数表。
    """
    op_name = params.get("morph_op", "腐蚀")
    shape_name = params.get("morph_shape", "矩形")
    ksize = odd_kernel(params.get("morph_ksize", 3), 1, 31)
    iterations = max(1, min(10, int(params.get("morph_iterations", 1))))
    shape = {"矩形": cv2.MORPH_RECT,
             "椭圆": cv2.MORPH_ELLIPSE,
             "十字": cv2.MORPH_CROSS}.get(shape_name, cv2.MORPH_RECT)
    op = {"腐蚀": cv2.MORPH_ERODE,
          "膨胀": cv2.MORPH_DILATE,
          "开运算": cv2.MORPH_OPEN,
          "闭运算": cv2.MORPH_CLOSE,
          "梯度": cv2.MORPH_GRADIENT,       # 膨胀 - 腐蚀，勾出轮廓
          "顶帽": cv2.MORPH_TOPHAT,         # 原图 - 开运算，挑出比周围亮的细节
          "黑帽": cv2.MORPH_BLACKHAT}.get(op_name, cv2.MORPH_ERODE)  # 闭运算 - 原图

    def _do(patch):
        kernel = cv2.getStructuringElement(shape, (ksize, ksize))
        return cv2.morphologyEx(to_bgr(patch), op, kernel, iterations=iterations)

    return apply_to_roi(img, roi, _do)


def _run_morphology(detector, img, roi, params):
    return morphology(img, roi, params), []


def validate_morphology(params):
    """形态学：核大小取 [1,31] 内的奇数、迭代次数夹进 [1,10]"""
    fixed, notes = dict(params), []
    fixed["morph_ksize"] = force_odd(
        read_int(fixed, "morph_ksize", 3, "核大小", notes), 1, 31, "核大小", notes)
    fixed["morph_iterations"] = clamp_int(
        read_int(fixed, "morph_iterations", 1, "迭代次数", notes), 1, 10, "迭代次数", notes)
    return fixed, notes, []


# 声明表（kind = KIND_PROCESS）
MORPHOLOGY_SPECS = [
    {
        "name": "形态学",
        "run": _run_morphology,
        "format_result": lambda results: "执行成功（图像已处理，下游可见）",
        "validate": validate_morphology,
        "param_specs": [
            ("morph_op", "运算", "combo",
             {"options": ["腐蚀", "膨胀", "开运算", "闭运算", "梯度", "顶帽", "黑帽"],
              "default": "腐蚀"}),
            ("morph_shape", "核形状", "combo",
             {"options": ["矩形", "椭圆", "十字"], "default": "矩形"}),
            ("morph_ksize", "核大小", "int",
             {"min": 1, "max": 31, "default": 3, "odd": True}),
            ("morph_iterations", "迭代次数", "int", {"min": 1, "max": 10, "default": 1}),
        ],
    },
]
