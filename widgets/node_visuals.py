# -*- coding: utf-8 -*-
"""节点图标的"占位画法"（批次6 目标1-M2a）。

★ 本批**不使用任何图片素材**（用户 2026.10.17："图标先占位"）——
   全部用 `QPainter` 画极简几何：零素材、零授权、任意 DPI 都清晰、大小自适应。
   将来换真图标（M5）只需要改 `core/icon_keys.py` 的映射 + 这里的一个分支。

约定：`draw_icon(painter, key, rect, color)` 在 `rect` 区域内用 `color` 画线/填充，
       失败/未知 key ⇒ 画一个通用方块（保证永远画得出来）。
"""
from PySide2.QtCore import QPointF, QRectF, Qt
from PySide2.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

# ★ 批次6 目标2-M2：树的图标缓存 ((key, color, size) → QIcon)，避免每次建树都重画
_ICON_CACHE = {}
_ICON_DEFAULT_COLOR = QColor(90, 90, 90)   # 统一中性深灰（用户 2026.10.18 拍板）

# `draw_icon()` 认识的键（make_icon 用它区分“已解析的键”与“算子名/分组名”）
_KNOWN_ICON_KEYS = frozenset((
    "gray", "invert", "blur", "threshold", "morph", "edge",
    "line", "circle", "face", "color",
    "image", "video", "camera", "save", "warn",
    "group_source", "group_process", "group_detect", "group_color", "group_test",
    "add", "generic",
))


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
        elif key == "group_source":          # 分组·采集：箭头流入方框
            painter.drawRect(QRectF(x + w * 0.4, y + h * 0.3, w * 0.56, h * 0.58))
            painter.drawLine(QPointF(x, cy), QPointF(x + w * 0.34, cy))
            painter.drawPolyline([QPointF(x + w * 0.2, cy - h * 0.12),
                                  QPointF(x + w * 0.34, cy),
                                  QPointF(x + w * 0.2, cy + h * 0.12)])
        elif key == "group_process":         # 分组·处理：方框内一条折线
            painter.drawRect(QRectF(x + w * 0.12, y + h * 0.12, w * 0.76, h * 0.76))
            painter.drawPolyline([QPointF(x + w * 0.26, y + h * 0.7),
                                  QPointF(x + w * 0.44, y + h * 0.36),
                                  QPointF(x + w * 0.62, y + h * 0.6),
                                  QPointF(x + w * 0.76, y + h * 0.4)])
        elif key == "group_detect":          # 分组·检测识别：方框 + 内部圆
            painter.drawRect(QRectF(x + w * 0.1, y + h * 0.1, w * 0.8, h * 0.8))
            painter.drawEllipse(QPointF(cx, cy), u * 0.2, u * 0.2)
        elif key == "group_color":           # 分组·颜色处理：三条竖色带
            for i in range(3):
                xx = x + w * (0.24 + 0.26 * i)
                painter.drawLine(QPointF(xx, y + h * 0.16), QPointF(xx, y + h * 0.84))
        elif key == "group_test":            # 分组·测试：方框 + 内部小方
            painter.drawRect(QRectF(x + w * 0.1, y + h * 0.1, w * 0.8, h * 0.8))
            painter.drawRect(QRectF(x + w * 0.38, y + h * 0.38, w * 0.24, h * 0.24))
        elif key == "add":                   # 新建项目：加号
            painter.drawLine(QPointF(cx, y + h * 0.12), QPointF(cx, y + h * 0.88))
            painter.drawLine(QPointF(x + w * 0.12, cy), QPointF(x + w * 0.88, cy))
        else:                                # generic / 未知：一个圆角方框
            painter.drawRoundedRect(QRectF(x + w * 0.12, y + h * 0.12, w * 0.76, h * 0.76), 2, 2)
    finally:
        painter.restore()


def make_icon(key, color=None, size=16):
    """把一个 `draw_icon()` 图案变成 `QIcon`（批次6 目标2-M2，树控件用）。

    · ★ **复用 `draw_icon()`** —— 画布与树同一个图案源，不重复实现；
    · ★ **2 倍画布 + setDevicePixelRatio(2)** ⇒ 高分屏不糊；
    · ★ 未知 key ⇒ `generic`（保证画得出来）；任何异常 ⇒ 返回空 QIcon（**不崩**）；
    · 结果按 (key, color, size) 缓存 ⇒ 建树时反复取也不重画。
    """
    try:
        size = max(8, int(size))
    except Exception:
        size = 16
    key = str(key)
    if key not in _KNOWN_ICON_KEYS:          # 传进来的是“算子名/分组名”⇒ 先查映射表
        try:
            from core import icon_keys
            key = icon_keys.icon_key_for(key)
        except Exception:
            key = "generic"
    if key not in _KNOWN_ICON_KEYS:
        key = "generic"
    cache_key = (key, str(color), size)
    cached = _ICON_CACHE.get(cache_key)
    if cached is not None:
        return cached
    icon = QIcon()
    try:
        dpr = 2
        pm = QPixmap(size * dpr, size * dpr)
        pm.setDevicePixelRatio(dpr)
        pm.fill(Qt.transparent)
        painter = QPainter(pm)
        try:
            col = QColor(color) if color is not None else QColor(_ICON_DEFAULT_COLOR)
            if not col.isValid():
                col = QColor(_ICON_DEFAULT_COLOR)
            draw_icon(painter, str(key), QRectF(0, 0, size, size), col)
        finally:
            painter.end()
        icon = QIcon(pm)
    except Exception:
        icon = QIcon()          # 画不出来就给空图标（不崩）
    _ICON_CACHE[cache_key] = icon
    return icon


def install_tree_icons(tree):
    """★ 批次6 目标2-M2：给树里每一项装 16×16 图标（节点 / 分组 / 测试 / 「新建项目」）。

    · 树项是在 `main.ui` 里声明的（用户可自行增删测试树干）⇒ 只能**遍历现有项**来装；
      遍历时**当场 setIcon**、**不保存任何 item 引用**（`QTreeWidgetItem` 可能是临时对象，
      存下来延后使用会随机 RuntimeException）；
    · ★ **画布右键菜单不加图标**（菜单在 `FlowChart.build_create_menu()`，本函数不碰它）；
    · 全程 try/except 兜底 ⇒ 画不出来最多没图标，**绝不影响启动**。
    返回装了图标的项数（供探针 / 判据用）。
    """
    count = [0]

    def _apply(item):
        try:
            text = item.text(0)
        except Exception:
            return
        if not text:
            return
        try:
            from core import icon_keys
            item.setIcon(0, make_icon(icon_keys.icon_key_for(text)))
            count[0] += 1
        except Exception:
            pass

    try:
        for i in range(tree.topLevelItemCount()):
            top = tree.topLevelItem(i)
            if top is None:
                continue
            _apply(top)
            try:
                for j in range(top.childCount()):
                    child = top.child(j)
                    if child is not None:
                        _apply(child)
            except Exception:
                continue
    except Exception:
        pass
    return count[0]
