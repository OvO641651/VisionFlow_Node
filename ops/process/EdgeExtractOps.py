# -*- coding: utf-8 -*-
"""
边缘提取（处理类算子）—— **一个节点一个文件**。

2026.10.14（批次5 目标1）：原先处理类 6 个节点都挤在 `ops/process/ProcessOps.py`
一个大类文件里；现在每个节点独占一个文件：算法 + 引擎入口 `_run_*` + 日志文案 +
参数校验 + 声明表 `*_SPECS` 都在本文件里（与 `ops/detect/` 下三个检测节点同构）。
公共零件（`to_bgr` / `apply_to_roi` / `odd_kernel`）在 `core/ImageOps.py`。
"""
import cv2

from core.ImageOps import apply_to_roi, odd_kernel, to_bgr

from core.ParamRules import clamp_int, force_odd, read_int


def edge(img, roi, params):
    """边缘提取：Canny / Sobel / Laplacian"""
    method = params.get("edge_method", "Canny")
    low = max(0, int(params.get("edge_low", 50)))
    high = max(0, int(params.get("edge_high", 150)))
    ksize = odd_kernel(params.get("edge_ksize", 3), 1, 31)

    def _do(patch):
        gray = cv2.cvtColor(to_bgr(patch), cv2.COLOR_BGR2GRAY)
        if method == "Sobel":
            gx = cv2.convertScaleAbs(cv2.Sobel(gray, cv2.CV_16S, 1, 0, ksize=ksize))
            gy = cv2.convertScaleAbs(cv2.Sobel(gray, cv2.CV_16S, 0, 1, ksize=ksize))
            return cv2.addWeighted(gx, 0.5, gy, 0.5, 0)
        if method == "Laplacian":
            return cv2.convertScaleAbs(cv2.Laplacian(gray, cv2.CV_16S, ksize=ksize))
        return cv2.Canny(gray, low, high)

    return apply_to_roi(img, roi, _do)


def _run_edge(detector, img, roi, params):
    return edge(img, roi, params), []


def validate_edge(params):
    """边缘提取：核大小取 [1,31] 内的奇数；Canny 的低/高阈值夹 0~500 并在填反时互换

    低/高阈值这两条 2026.10.7 晚追加（用户实测报"填 500/150 也能跑、效果和 150/500 一样、
    却看不到任何提示"）。为什么它值得管：`cv2.Canny` 内部**自己会交换** low/high（实测），
    所以结果不受影响 —— 但"参数框里写着 500/150、实际按 150/500 跑"这件事用户看不到，
    正是本项目要消灭的那种"静默"。互换之后"参数值 = 实际生效值"，并且会出黄字提示。
    注意：只有"方法 = Canny"才用这两个值（Sobel / Laplacian 只看核大小）。
    """
    fixed, notes = dict(params), []
    fixed["edge_ksize"] = force_odd(
        read_int(fixed, "edge_ksize", 3, "核大小", notes), 1, 31, "核大小", notes)

    low = clamp_int(read_int(fixed, "edge_low", 50, "低阈值", notes), 0, 500, "低阈值", notes)
    high = clamp_int(read_int(fixed, "edge_high", 150, "高阈值", notes), 0, 500, "高阈值", notes)
    if low > high:
        notes.append("Canny 低/高阈值已互换（{0}/{1} → {2}/{3}）".format(low, high, high, low))
        low, high = high, low
    fixed["edge_low"], fixed["edge_high"] = low, high
    return fixed, notes, []


# 声明表（kind = KIND_PROCESS）
EDGE_SPECS = [
    {
        "name": "边缘提取",
        "run": _run_edge,
        "format_result": lambda results: "执行成功（图像已处理，下游可见）",
        "validate": validate_edge,
        "param_specs": [
            ("edge_method", "方法", "combo",
             {"options": ["Canny", "Sobel", "Laplacian"], "default": "Canny"}),
            ("edge_low", "低阈值", "int", {"min": 0, "max": 500, "default": 50}),
            ("edge_high", "高阈值", "int", {"min": 0, "max": 500, "default": 150}),
            ("edge_ksize", "核大小", "int",
             {"min": 1, "max": 31, "default": 3, "odd": True}),
        ],
    },
]
