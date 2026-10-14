# -*- coding: utf-8 -*-
"""
`DetectorShape` = **兼容门面**（2026.10.14 批次5 目标1 补做拆分之后）。

直线 / 圆的算法与声明已经各自搬进"**一个节点一个文件**"：
    · 直线 → `ops/detect/LineDetectOps.py`（`LineDetector` + `LINE_SPECS`）
    · 圆   → `ops/detect/CircleDetectOps.py`（`CircleDetector` + `CIRCLE_SPECS`）

本文件只保留两件事：
    1. `DetectorShape`：把上面两个算法类拼成一个对象，供引擎的统一签名
       `run(detector, img, roi, params)` 使用（`main.py` 里 `self.detector = DetectorShape()`）。
       **方法签名与拆分前完全一致** ⇒ 老调用点（`w.detector.line_detector(...)` 等）不用改。
    2. `make_test_image()`：图片源节点的"测试图"、几个参数窗口的占位图与若干用例都用它。

注意（2026.10.2 数据流引擎之后的老口径仍然有效）：
    检测函数只负责"算"；它们顺手画在传入数组上的绿线、红圆只是副作用，会被引擎丢掉
    （`_run_line` / `_run_circle` 传的是 ROI 的副本）。真正给用户看的叠加绘制由
    `ops/detect/*Ops.py` 的 `_draw_line()` / `_draw_circle()` 在显示层完成。
"""
import cv2
import numpy as np

from ops.detect.CircleDetectOps import CircleDetector
from ops.detect.LineDetectOps import LineDetector


class DetectorShape:
    """直线 / 圆算法的**门面**（真正的算法在 `ops/detect/*Ops.py`）。"""

    def __init__(self):
        self.line = LineDetector()
        self.circle = CircleDetector()

    def line_detector(self, *args, **kwargs):
        """直线检测 → 转发给 `ops/detect/LineDetectOps.py` 的 `LineDetector`。"""
        return self.line.line_detector(*args, **kwargs)

    def circle_detector(self, *args, **kwargs):
        """圆检测 → 转发给 `ops/detect/CircleDetectOps.py` 的 `CircleDetector`。"""
        return self.circle.circle_detector(*args, **kwargs)


def make_test_image():
    """造一张带矩形、圆和一条长横线的测试图，供单独运行本文件 / 其它自检使用"""
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.rectangle(img, (100, 100), (500, 400), (255, 255, 255), 2)
    cv2.circle(img, (300, 250), 80, (255, 255, 255), 2)
    cv2.line(img, (120, 430), (520, 430), (255, 255, 255), 3)
    return img


def main():
    """
    独立测试：优先读 image/lena.png，读不到就自己造一张
    （工程里没有 image 目录时也能正常跑，不会再直接崩）
    """
    detector = DetectorShape()

    img = cv2.imread('image/lena.png')
    if img is None:
        print("没找到 image/lena.png，改用自动生成的测试图")
        img = make_test_image()

    canvas, line_data = detector.line_detector(img)
    canvas, circle_data = detector.circle_detector(img)
    print("检测到直线：", line_data)
    print("检测到圆：", circle_data)

    cv2.imshow('img', canvas)
    cv2.waitKey(0)


if __name__ == '__main__':
    main()
