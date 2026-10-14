# -*- coding: utf-8 -*-
"""
二值化（处理类算子）—— **一个节点一个文件**。

2026.10.14（批次5 目标1）：原先处理类 6 个节点都挤在 `ops/process/ProcessOps.py`
一个大类文件里；现在每个节点独占一个文件：算法 + 引擎入口 `_run_*` + 日志文案 +
参数校验 + 声明表 `*_SPECS` 都在本文件里（与 `ops/detect/` 下三个检测节点同构）。
公共零件（`to_bgr` / `apply_to_roi` / `odd_kernel`）在 `core/ImageOps.py`。
"""
import cv2

from core.ImageOps import apply_to_roi, to_bgr

from core.ParamRules import clamp_int, read_int


def threshold(img, roi, params):
    """二值化：固定阈值 / Otsu / 自适应（先转灰度再算，结果补回 3 通道）"""
    mode = params.get("thresh_mode", "固定阈值")
    thresh = int(params.get("thresh_value", 127))
    maxval = int(params.get("thresh_maxval", 255))
    flag = (cv2.THRESH_BINARY_INV if params.get("thresh_type", "二值") == "反二值"
            else cv2.THRESH_BINARY)

    def _do(patch):
        gray = cv2.cvtColor(to_bgr(patch), cv2.COLOR_BGR2GRAY)
        if mode == "Otsu":
            # Otsu 自己算阈值，传进去的 thresh 会被忽略
            _used, out = cv2.threshold(gray, 0, maxval, flag | cv2.THRESH_OTSU)
            return out
        if mode == "自适应":
            # 自适应阈值：blockSize 必须是 > 1 的奇数
            return cv2.adaptiveThreshold(gray, maxval, cv2.ADAPTIVE_THRESH_MEAN_C,
                                         flag, 11, 2)
        _used, out = cv2.threshold(gray, thresh, maxval, flag)
        return out

    return apply_to_roi(img, roi, _do)


def _run_threshold(detector, img, roi, params):
    return threshold(img, roi, params), []


def validate_threshold(params):
    """二值化：阈值 / 最大值夹进 [0,255]（越界时 OpenCV 不报错、只是静默饱和，用户看不出来）"""
    fixed, notes = dict(params), []
    fixed["thresh_value"] = clamp_int(
        read_int(fixed, "thresh_value", 127, "阈值", notes), 0, 255, "阈值", notes)
    fixed["thresh_maxval"] = clamp_int(
        read_int(fixed, "thresh_maxval", 255, "最大值", notes), 0, 255, "最大值", notes)
    return fixed, notes, []


# 声明表（kind = KIND_PROCESS）
THRESHOLD_SPECS = [
    {
        "name": "二值化",
        "run": _run_threshold,
        "format_result": lambda results: "执行成功（图像已处理，下游可见）",
        "validate": validate_threshold,
        "param_specs": [
            ("thresh_mode", "阈值方式", "combo",
             {"options": ["固定阈值", "Otsu", "自适应"], "default": "固定阈值"}),
            ("thresh_value", "阈值", "int", {"min": 0, "max": 255, "default": 127}),
            ("thresh_maxval", "最大值", "int", {"min": 0, "max": 255, "default": 255}),
            ("thresh_type", "类型", "combo",
             {"options": ["二值", "反二值"], "default": "二值"}),
        ],
    },
]
