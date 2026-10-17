# -*- coding: utf-8 -*-
"""节点图标的"占位画法"（批次6 目标1-M2a）。

★ 本批**不使用任何图片素材**（用户 2026.10.17："图标先占位"）——
   全部用 `QPainter` 画极简几何：零素材、零授权、任意 DPI 都清晰、大小自适应。
   将来换真图标（M5）只需要改 `core/icon_keys.py` 的映射 + 这里的一个分支。

约定：`draw_icon(painter, key, rect, color)` 在 `rect` 区域内用 `color` 画线/填充，
       失败/未知 key ⇒ 画一个通用方块（保证永远画得出来）。
"""
from PySide2.QtCore import QPointF, QRectF, Qt
from PySide2.QtGui import QPainterPath, QPen


def _pen(color, width=1.6):
    pen = QPen(color, width)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    return pen


def draw_icon(painter, key, rect, color):
    """在 rect（QRectF）里画一个极简几何图标。"""
    painter.save()
    try:
        painter.setPen(_pen(color, 1.6))
        painter.setBrush(Qt.NoBrush)
        r = QRectF(rect)
        x, y, w, h = r.left(), r.top(), r.width(), r.height()
        cx, cy = x + w / 2.0, y + h / 2.0
        u = min(w, h)                       # 图标基准尺寸
        half = u / 2.0

        if key == "gray":                    # 灰度：一半实心、一半空心的圆
            painter.drawEllipse(QPointF(cx, cy), half, half)
            painter.setBrush(color)
            painter.drawPie(QRectF(cx - half, cy - half, u, u), 90 * 16, 180 * 16)
        elif key == "invert":                # 取反：两个对调的黑白三角
            painter.setBrush(color)
            painter.drawPolygon([QPointF(x, y + h), QPointF(x + w, y + h), QPointF(x, y)])
            painter.setBrush(Qt.NoBrush)
            painter.drawPolygon([QPointF(x + w, y), QPointF(x + w, y + h), QPointF(x, y)])
        elif key == "blur":                  # 滤波：三道波纹
            for i in range(3):
                yy = y + h * (0.25 + 0.25 * i)
                path = QPainterPath(QPointF(x, yy))
                path.cubicTo(QPointF(cx - w * 0.15, yy - h * 0.18),
                             QPointF(cx + w * 0.15, yy + h * 0.18),
                             QPointF(x + w, yy))
                painter.drawPath(path)
        elif key == "threshold":             # 二值化：阶梯
            painter.drawPolyline([QPointF(x, y + h), QPointF(x + w * 0.4, y + h),
                                  QPointF(x + w * 0.4, cy), QPointF(x + w, cy),
                                  QPointF(x + w, y)])
        elif key == "morph":                 # 形态学：圆 + 方
            painter.drawEllipse(QPointF(cx - w * 0.15, cy), u * 0.32, u * 0.32)
            painter.drawRect(QRectF(cx + w * 0.02, cy - u * 0.32, u * 0.32, u * 0.32))
        elif key == "edge":                  # 边缘提取：方框轮廓
            painter.drawRect(QRectF(x + w * 0.1, y + h * 0.1, w * 0.8, h * 0.8))
            painter.drawRect(QRectF(x + w * 0.32, y + h * 0.32, w * 0.36, h * 0.36))
        elif key == "line":                  # 直线识别：一条斜线
            painter.drawLine(QPointF(x + w * 0.1, y + h * 0.85), QPointF(x + w * 0.9, y + h * 0.15))
        elif key == "circle":                # 圆识别：一个圆
            painter.drawEllipse(QPointF(cx, cy), half * 0.85, half * 0.85)
        elif key == "face":                  # 人脸识别：脸轮廓 + 双眼
            painter.drawEllipse(QPointF(cx, cy), half * 0.8, half)
            painter.setBrush(color)
            painter.drawEllipse(QPointF(cx - u * 0.18, cy - u * 0.18), u * 0.07, u * 0.07)
            painter.drawEllipse(QPointF(cx + u * 0.18, cy - u * 0.18), u * 0.07, u * 0.07)
        elif key == "color":                 # 颜色提取：三条色带
            for i in range(3):
                yy = y + h * (0.2 + 0.3 * i)
                painter.drawLine(QPointF(x, yy), QPointF(x + w, yy))
        elif key == "image":                 # 图片源：相框 + 山
            painter.drawRect(QRectF(x + w * 0.08, y + h * 0.15, w * 0.84, h * 0.7))
            painter.drawPolyline([QPointF(x + w * 0.2, y + h * 0.7),
                                  QPointF(x + w * 0.45, y + h * 0.4),
                                  QPointF(x + w * 0.65, y + h * 0.6),
                                  QPointF(x + w * 0.8, y + h * 0.45)])
        elif key == "video":                 # 视频源：胶片
            painter.drawRect(QRectF(x + w * 0.08, y + h * 0.2, w * 0.84, h * 0.6))
            for i in range(3):
                xx = x + w * (0.2 + 0.25 * i)
                painter.drawLine(QPointF(xx, y + h * 0.08), QPointF(xx, y + h * 0.2))
                painter.drawLine(QPointF(xx, y + h * 0.8), QPointF(xx, y + h * 0.92))
        elif key == "camera":                # 相机源：机身 + 镜头
            painter.drawRect(QRectF(x + w * 0.06, y + h * 0.28, w * 0.88, h * 0.5))
            painter.drawEllipse(QPointF(cx, y + h * 0.55), u * 0.18, u * 0.18)
            painter.drawLine(QPointF(x + w * 0.3, y + h * 0.28), QPointF(x + w * 0.38, y + h * 0.16))
        elif key == "save":                  # 输出图像：下箭头 + 底线
            painter.drawLine(QPointF(cx, y + h * 0.12), QPointF(cx, y + h * 0.62))
            painter.drawPolyline([QPointF(cx - u * 0.22, y + h * 0.42),
                                  QPointF(cx, y + h * 0.64),
                                  QPointF(cx + u * 0.22, y + h * 0.42)])
            painter.drawLine(QPointF(x + w * 0.15, y + h * 0.85), QPointF(x + w * 0.85, y + h * 0.85))
        elif key == "warn":                  # 警告（测试用）：感叹号
            painter.drawPolyline([QPointF(cx, y + h * 0.1),
                                  QPointF(x + w * 0.88, y + h * 0.88),
                                  QPointF(x + w * 0.12, y + h * 0.88),
                                  QPointF(cx, y + h * 0.1)])
            painter.drawLine(QPointF(cx, y + h * 0.36), QPointF(cx, y + h * 0.62))
            painter.setBrush(color)
            painter.drawEllipse(QPointF(cx, y + h * 0.74), u * 0.045, u * 0.045)
        else:                                # generic / 分组 / 未知：一个圆角方框
            painter.drawRoundedRect(QRectF(x + w * 0.12, y + h * 0.12, w * 0.76, h * 0.76), 2, 2)
    finally:
        painter.restore()
