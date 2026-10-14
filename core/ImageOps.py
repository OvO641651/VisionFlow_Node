# -*- coding: utf-8 -*-
"""
图像处理的**公共零件**（处理类算子共用的"通用外壳"）。

2026.10.14（批次5 目标1）：原先它是处理类大类文件 `ops/process/ProcessOps.py` 里
`class ProcessOps` 的三个静态方法；"一个节点一个文件"之后被 6 个处理类节点 +
颜色提取（`ops/color/ColorExtractOps.py`）共用，所以提到 `core/` 当公共零件
（与 `ParamRules.py` / `ImageIO.py` 同类 —— 都是"零 GUI 依赖的纯逻辑"）。

三条硬规矩（沿用原来的注释，处理类算子都守）：
    1、**绝不就地改传进来的 img** —— 先 copy 一份再改。就地改会污染数据层，
       下游节点就会"看见"上游处理过的像素（历史上被绿线污染坑过一次）；
    2、输出必须是 **3 通道 BGR**：下游 cv2.line / cv2.circle / HoughCircles 都要求 3 通道，
       单通道图会把后面的算子弄崩，所以 `apply_to_roi()` 统一兜一层 `to_bgr()`；
    3、只处理 **ROI 那一块**，ROI 以外保持原样（"所见即所算"）。
"""
import cv2


def to_bgr(img):
    """保证是 3 通道 BGR（处理类算子的输出必须是 3 通道）"""
    if img.ndim == 2:
        return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    return img


def apply_to_roi(img, roi, func):
    """
    处理类通用外壳：copy 出新图 → 只在 ROI 上做变换 → 回填 → 保证 3 通道。

    :param func: func(patch) -> patch；patch 是 ROI 的视图（可以就地改），
                 返回值会被写回 ROI
    """
    out = to_bgr(img).copy()          # ① copy：绝不改传进来的 img
    x, y, w, h = roi
    if w <= 0 or h <= 0:
        # ROI 越界被裁成 0 尺寸时，原样返回（引擎已经按整图兜过一层，这里只防崩）
        return out
    patch = out[y:y + h, x:x + w]
    out[y:y + h, x:x + w] = to_bgr(func(patch))   # ② 回填时保证 3 通道
    return out


def odd_kernel(value, low, high):
    """把值夹进 [low, high] 并强制成奇数（卷积核尺寸必须奇数）"""
    value = max(low, min(high, int(value)))
    if value % 2 == 0:
        value = value + 1 if value < high else value - 1
    return max(low, min(high, value))
