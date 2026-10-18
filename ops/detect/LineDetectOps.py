# -*- coding: utf-8 -*-
"""
直线（检测类算子）—— **一个节点一个文件**。

2026.10.14（批次5 目标1 补做）：原先"直线"被拆在两处 —— 算法在 `core/Detector.py`、
节点声明在 `core/NodeRegistry.py` 里手写；现在把**这个节点该有的东西**收进本文件：
    · 算法类 `LineDetector`（Canny + HoughLinesP）
    · 引擎入口 `_run_line`（只算、不改数据层）
    · 显示层绘制 `_draw_line`（绿线，画在显示层）
    · 日志文案 `_format_line`
    · 参数校验 `validate_line`（批次4 目标4 的规则，从 NodeRegistry 搬来）
    · 声明表 `LINE_SPECS`（注册表按它登记，与 ProcessOps / FaceDetectOps 等一致）

数据层 / 渲染层分离（口径没变）：
    `LineDetector.line_detector()` 会顺手把绿线画进**传进去的数组**，那是副作用；
    `_run_line` 传给它的始终是 ROI 的一份 `.copy()` ⇒ 绿线**永远不进数据层**，
    用户看到的绿线由 `_draw_line()` 在显示层画。
"""
from core import log_texts as T
import cv2
import numpy as np

from core.ParamRules import clamp_int, read_int


class LineDetector:
    """直线检测算法（Canny 找边 + HoughLinesP 找线段）。"""

    def line_detector(self, img, rho=1.0, theta=np.pi / 180,
                      threshold=100, min_line_length=100.0,
                      max_line_gap=10.0, canny_low=50,
                      canny_high=150, aperture=3,
                      roi_offset_x=0, roi_offset_y=0):
        """
        检测图像中的直线段，并在原图上绘制绿色线段。

        参数:
            img: 输入图像（BGR格式）
            rho: 距离分辨率（像素）
            theta: 角度分辨率（弧度）
            threshold: 累加器阈值，值越小检测到的线段越多
            min_line_length: 最小线段长度，短于此值的线段被丢弃
            max_line_gap: 同一线段上允许的最大间断间隔（像素）
            canny_low: Canny边缘检测的低阈值
            canny_high: Canny边缘检测的高阈值
            aperture: Sobel算子的大小
            roi_offset_x: 直线检测区域的 x轴偏移量
            roi_offset_y: 直线检测区域的 y轴偏移量

        返回:
            (绘制了线段的图像, 直线数据列表)
            直线数据是 (x1, y1, x2, y2)，坐标已经加上偏移量、换回主图坐标
        """
        if len(img.shape) == 2:
            gray = img
        else:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        edges = cv2.Canny(gray, canny_low, canny_high, apertureSize=aperture)
        lines = cv2.HoughLinesP(edges, rho=rho, theta=theta, threshold=threshold,
                                minLineLength=min_line_length, maxLineGap=max_line_gap)
        line_data = []
        if lines is not None:
            for line in lines:
                x1, y1, x2, y2 = line[0]
                cv2.line(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
                # 把相对于子图的坐标，加上偏移量，转化为主图的真实坐标
                x1 += roi_offset_x
                y1 += roi_offset_y
                x2 += roi_offset_x
                y2 += roi_offset_y
                line_data.append((x1, y1, x2, y2))
        return img, line_data


def _run_line(detector, img, roi, params):
    """
    直线（检测类）：只在 ROI 的一份副本上跑算法，结果数据按原图坐标返回。

    算法就在本文件里，不再需要引擎传进来的 `detector`（引擎调用签名统一，参数照旧保留）。
    注意 patch 后面的 .copy()：
        line_detector() 会顺手把绿线画进传进去的数组里，那是它的"副作用"。
        这里给的是副本，画完直接丢掉，绿线不会进数据层；
        真正的绘制交给 _draw_line() 在显示层做。
        如果忘了 copy()，画绿线时会把数据层图像改掉，下游就又"看见"绿线了。
    """
    x, y, w, h = roi
    patch = img[y:y + h, x:x + w].copy()
    _ignored, results = LineDetector().line_detector(
        patch,
        roi_offset_x=x,
        roi_offset_y=y,
        canny_low=params.get("canny_low", 50),
        canny_high=params.get("canny_high", 150),
        threshold=params.get("hough_threshold", 100),
        min_line_length=params.get("min_line_length", 100.0),
        max_line_gap=params.get("max_line_gap", 10.0),
    )
    # 数据层图像原样透传（同一个对象，不复制）
    return img, results


def _draw_line(display_img, results, params):
    """把直线结果画到显示层（绿色，和算法里的画法一致）"""
    for item in results:
        if len(item) == 4:
            x1, y1, x2, y2 = item
            cv2.line(display_img, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)


def _format_line(results):
    return T.LINE_COUNT.format(n=len(results))


# ----------------------------------------------------------------------
# 参数校验规则（批次4 目标4；2026.10.14 从 core/NodeRegistry.py 搬来）
#
# 实测依据（cv2 4.13 / 2026.10.7）：
#     · Canny 低 > 高**不会崩**（OpenCV 内部自己交换）⇒ 我们互换只为让"参数值"与"实际生效值"一致；
#     · HoughLinesP 的 threshold=0 / minLineLength=0 **不崩**，但结果会暴增（实测 45 条 vs 正常）
#       ⇒ 纠正为 1 并写进说明。
# ----------------------------------------------------------------------
def validate_line(params):
    """直线：Canny 高低阈值（夹范围 + 互换）、累加器阈值、最小线段长度、最大线段间隙"""
    fixed, notes = dict(params), []

    low = clamp_int(read_int(fixed, "canny_low", 50, "Canny 低阈值", notes),
                    0, 500, "Canny 低阈值", notes)
    high = clamp_int(read_int(fixed, "canny_high", 150, "Canny 高阈值", notes),
                     0, 500, "Canny 高阈值", notes)
    if low > high:
        notes.append("Canny 低/高阈值已互换（{0}/{1} → {2}/{3}）".format(low, high, high, low))
        low, high = high, low
    fixed["canny_low"], fixed["canny_high"] = low, high

    threshold = read_int(fixed, "hough_threshold", 100, "累加器阈值", notes)
    if threshold < 1:
        notes.append("累加器阈值已纠正为 1（原 {0}：阈值越小检出的线段越多、噪声也多）".format(threshold))
        threshold = 1
    fixed["hough_threshold"] = threshold

    min_len = read_int(fixed, "min_line_length", 100, "最小线段长度", notes)
    if min_len < 1:
        notes.append("最小线段长度已纠正为 1（原 {0}）".format(min_len))
        min_len = 1
    fixed["min_line_length"] = min_len

    gap = read_int(fixed, "max_line_gap", 10, "最大线段间隙", notes)
    if gap < 0:
        notes.append("最大线段间隙已纠正为 0（原 {0}）".format(gap))
        gap = 0
    fixed["max_line_gap"] = gap

    return fixed, notes, []


# 声明表（注册表 core/NodeRegistry.py 按它登记；kind 由注册表那边给 = KIND_DETECT）
LINE_SPECS = [
    {
        "name": "直线识别",
        "run": _run_line,
        "draw": _draw_line,
        "format_result": _format_line,
        "validate": validate_line,
    },
]
