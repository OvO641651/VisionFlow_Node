# -*- coding: utf-8 -*-
"""
取反（处理类算子）—— **一个节点一个文件**。

2026.10.14（批次5 目标1）：原先处理类 6 个节点都挤在 `ops/process/ProcessOps.py`
一个大类文件里；现在每个节点独占一个文件：算法 + 引擎入口 `_run_*` + 日志文案 +
参数校验 + 声明表 `*_SPECS` 都在本文件里（与 `ops/detect/` 下三个检测节点同构）。
公共零件（`to_bgr` / `apply_to_roi` / `odd_kernel`）在 `core/ImageOps.py`。
"""
import cv2

from core.ImageOps import apply_to_roi


def invert(img, roi, params):
    """反色：ROI 内 255 - x"""
    return apply_to_roi(img, roi, lambda patch: cv2.bitwise_not(patch))


def _run_invert(detector, img, roi, params):
    return invert(img, roi, params), []


# 声明表（kind = KIND_PROCESS）
INVERT_SPECS = [
    {
        "name": "取反",
        "run": _run_invert,
        "format_result": lambda results: "执行成功（图像已处理，下游可见）",
        "param_specs": [],            # 没有可调参数，只按 ROI / 继承处理
    },
]
