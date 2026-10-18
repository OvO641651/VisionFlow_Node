# -*- coding: utf-8 -*-
"""
圆（检测类算子）—— **一个节点一个文件**（与 `LineDetectOps.py` 同构）。

2026.10.14（批次5 目标1 补做）：原先把"圆"拆在两处（算法在 `core/Detector.py`、
声明在 `core/NodeRegistry.py` 手写），现在收进本文件：算法类 `CircleDetector` +
引擎入口 `_run_circle` + 显示层绘制 `_draw_circle` + 日志文案 `_format_circle` +
参数校验 `validate_circle` + 声明表 `CIRCLE_SPECS`。
"""
from core import log_texts as T
import cv2
import numpy as np

from core.ParamRules import clamp_float, read_float, read_int


class CircleDetector:
    """圆检测算法（HoughCircles）。"""

    def circle_detector(self, img, method=cv2.HOUGH_GRADIENT, dp=1.0,
                        min_dist=150.0, param1=100.0, param2=80.0,
                        min_radius=20, max_radius=0,
                        roi_offset_x=0, roi_offset_y=0):
        """
        检测图像中的圆形，并在原图上绘制红色圆。

        参数:
            img: 输入图像（BGR格式）
            method: 检测方法，目前仅支持 cv2.HOUGH_GRADIENT
            dp: 累加器分辨率与图像分辨率的反比（dp=1时分辨率相同）
            min_dist: 圆心之间的最小距离，避免检测到相邻的圆
            param1: Canny边缘检测的高阈值（低阈值为它的一半）
            param2: 圆心检测的累加器阈值，越小检测到的圆越多（可能包含假圆）
            min_radius: 最小圆半径
            max_radius: 最大圆半径（0表示无限制）
            roi_offset_x: 圆检测区域的 x轴偏移量
            roi_offset_y: 圆检测区域的 y轴偏移量

        返回:
            (绘制了圆形的图像, 圆数据列表)
            圆数据是 (cx, cy, r)，坐标已经加上偏移量、换回主图坐标
        """
        if len(img.shape) == 2:
            gray = img
        else:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        circles = cv2.HoughCircles(gray, method, dp, min_dist, param1=param1,
                                   param2=param2, minRadius=min_radius,
                                   maxRadius=max_radius)
        circle_data = []
        if circles is not None:
            circles = np.round(circles[0, :]).astype(int)
            for (x, y, r) in circles:
                cv2.circle(img, (x, y), r, (0, 0, 255), 2)  # 红色圆
                cv2.circle(img, (x, y), 2, (0, 0, 255), 3)  # 圆心
                circle_data.append((x + roi_offset_x, y + roi_offset_y, r))
        return img, circle_data


def _run_circle(detector, img, roi, params):
    """圆（检测类）：和直线同理，只在 ROI 副本上跑，数据层图像透传"""
    x, y, w, h = roi
    patch = img[y:y + h, x:x + w].copy()
    _ignored, results = CircleDetector().circle_detector(
        patch,
        roi_offset_x=x,
        roi_offset_y=y,
        dp=params.get("dp", 1.0),
        min_dist=params.get("min_dist", 150.0),
        param1=params.get("param1", 100.0),
        param2=params.get("param2", 80.0),
        min_radius=params.get("min_radius", 20),
        max_radius=params.get("max_radius", 0),
    )
    return img, results


def _draw_circle(display_img, results, params):
    """把圆结果画到显示层（红色圆 + 红色圆心，和算法里的画法一致）"""
    for item in results:
        if len(item) == 3:
            x, y, r = item
            cv2.circle(display_img, (int(x), int(y)), int(r), (0, 0, 255), 2)   # 红色圆
            cv2.circle(display_img, (int(x), int(y)), 2, (0, 0, 255), 3)        # 圆心


def _format_circle(results):
    return T.CIRCLE_COUNT.format(n=len(results))


# ----------------------------------------------------------------------
# 参数校验规则（批次4 目标4；2026.10.14 从 core/NodeRegistry.py 搬来）
#
# 实测依据（cv2 4.13 / 2026.10.7）：
#     · HoughCircles 的 param1 / param2 = 0 **会抛异常**，而圆窗口原先 setRange(0, 1000)
#       ⇒ 下限就是 0、**界面就能调到**（唯一"界面可达且会崩"的参数）；窗口下限已改成 1，
#       引擎侧这一层仍然保留 —— 挡的是"方案文件里手改出来的 0"；
#     · dp=0 / minDist<=0 也抛异常，界面上够不到（0.1~10 / 10~10000），同样由引擎侧兜。
# ----------------------------------------------------------------------
def validate_circle(params):
    """圆：param1 / param2（必须 ≥ 1）、dp、min_dist（界面上够不到，挡方案文件）"""
    fixed, notes = dict(params), []

    for key, label, default in (("param1", "Canny 高阈值（param1）", 100),
                                ("param2", "圆心累加器阈值（param2）", 80)):
        value = read_int(fixed, key, default, label, notes)
        if value < 1:
            notes.append("{0}已纠正为 1（原 {1}：OpenCV 要求大于 0，原先会直接报错）".format(label, value))
            value = 1
        fixed[key] = value

    dp = clamp_float(read_float(fixed, "dp", 1.0, "累加器分辨率 dp", notes),
                     0.1, 10.0, "累加器分辨率 dp", notes)
    fixed["dp"] = dp

    min_dist = read_int(fixed, "min_dist", 150, "圆心最小距离", notes)
    if min_dist < 1:
        notes.append("圆心最小距离已纠正为 1（原 {0}）".format(min_dist))
        min_dist = 1
    fixed["min_dist"] = min_dist

    return fixed, notes, []


# 声明表（注册表 core/NodeRegistry.py 按它登记；kind = KIND_DETECT）
CIRCLE_SPECS = [
    {
        "name": "圆识别",
        "run": _run_circle,
        "draw": _draw_circle,
        "format_result": _format_circle,
        "validate": validate_circle,
    },
]
