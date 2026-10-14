# -*- coding: utf-8 -*-
"""
灰度（处理类算子）—— **一个节点一个文件**。

2026.10.14（批次5 目标1）：原先处理类 6 个节点都挤在 `ops/process/ProcessOps.py`
一个大类文件里；现在每个节点独占一个文件：算法 + 引擎入口 `_run_*` + 日志文案 +
参数校验 + 声明表 `*_SPECS` 都在本文件里（与 `ops/detect/` 下三个检测节点同构）。
公共零件（`to_bgr` / `apply_to_roi` / `odd_kernel`）在 `core/ImageOps.py`。
"""
import cv2

from core.ImageOps import apply_to_roi, to_bgr


def to_gray(img):
    """
    灰度化（"数据层"版本）：始终返回 3 通道 BGR 图。

    数据流引擎里灰度是"处理类"算子，输出图像要交给下游继续算，而下游的
    cv2.line / cv2.circle / HoughCircles 都要求 3 通道，所以不能返回单通道：
    先转灰度、再补回 3 通道——图像没颜色了，但通道数和彩色图一致，下游不会报错。
    """
    if img is None or img.size == 0:
        return img
    if len(img.shape) == 2:
        # 本来就是单通道，补成 3 通道即可
        return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)


def gray(img, roi, params):
    """灰度：ROI 内转 3 通道灰度；params["gray_full_image"] 为真时整幅图都转"""
    if params.get("gray_full_image", False):
        # "作用于整图"：忽略 ROI（引擎那边也会把 ROI 当成整图，做到"所见即所算"）
        return to_gray(to_bgr(img).copy())
    return apply_to_roi(img, roi, to_gray)


def _run_gray(detector, img, roi, params):
    # 灰度算法就在本文件里，不再需要 detector（引擎调用签名统一，参数照旧保留）
    return gray(img, roi, params), []


# 声明表（注册表 core/NodeRegistry.py 按它登记；kind = KIND_PROCESS）
GRAY_SPECS = [
    {
        "name": "灰度",
        "run": _run_gray,
        "format_result": lambda results: "执行成功（图像已灰度化，下游模块可见）",
        "param_specs": None,          # 灰度有自己的专用窗口（带"作用于整图"开关）
        "whole_image_param": "gray_full_image",
    },
]
