# -*- coding: utf-8 -*-
"""节点图标：**SVG 为主 + 灰方块兜底**（批次6 目标5-M2b，2026.10.27）。

演变：目标1-M2a 用 `QPainter` 画极简几何占位 → 目标5-M2 接用户提供的 `icons/*.svg`
      → 目标5-M2b（本版）**退役 `draw_icon`**，全部改由 SVG 渲染：
      · `make_icon(key, color, size)` —— 树 / 窗口 / 顶部按钮用（`QIcon`）；
      · `render_svg(key, color, size)` —— **画布节点**用（返回 `QPixmap`，可染色）；
      · 缺 SVG / 渲染失败 ⇒ `_fallback_pixmap()` 画**灰方块**（**绝不空白、绝不抛异常**）。
"""
import os

from PySide2.QtCore import QRectF, Qt
from PySide2.QtGui import QColor, QIcon, QPainter, QPixmap

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

# ======================================================================
# ★ 批次6 目标5-M2：SVG 图标（用户 2026.10.27 提供的 icons/ 素材）
#   设计：**SVG 优先 → 缺文件回退 QPainter 自绘**（绝不返回空白、绝不抛异常）。
#   · 路径按**工程根**定位（不依赖当前工作目录）⇒ 从任何目录启动都能找到；
#   · 顶部按钮 key 走 `SVG_BUTTON`；节点/分组 key 与文件名同名 ⇒ node_icons/<key>.svg；
#   · 颜色：SVG 内颜色写死（黑/深色），`color` 参数只对回退的 QPainter 生效。
# ======================================================================
_SVG_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "icons")

# 顶部 8 个按钮（★ 2026.10.27 实测清单，别猜；start/stop/undo_gray/redo_gray 已不使用）
SVG_BUTTON = {
    "menu": "button_icons/menu.svg",
    "import_image": "button_icons/import.svg",
    "step_run": "button_icons/step.svg",
    "run_all": "button_icons/run.svg",
    "save_project": "button_icons/save.svg",
    "load_project": "button_icons/open_file.svg",
    "undo": "button_icons/undo.svg",
    "redo": "button_icons/redo.svg",
}
SVG_NODE_DIR = "node_icons"


def svg_path_for(key):
    """key → icons/ 下 SVG 的绝对路径；文件不存在 ⇒ None（**不抛异常**）。"""
    try:
        rel = SVG_BUTTON.get(str(key))
        if not rel:
            rel = os.path.join(SVG_NODE_DIR, str(key) + ".svg")
        path = os.path.join(_SVG_ROOT, rel.replace("/", os.sep))
        return path if os.path.isfile(path) else None
    except Exception:
        return None


def _fallback_pixmap(size=16):
    """★ 目标5-M2b：**极简兜底** —— 缺 SVG / 渲染失败时画一个灰方块（**绝不空白**）。"""
    try:
        size = max(8, int(size))
    except Exception:
        size = 16
    dpr = 2
    pm = QPixmap(size * dpr, size * dpr)
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    try:
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(_ICON_DEFAULT_COLOR))
        p.drawRoundedRect(QRectF(size * 0.18, size * 0.18, size * 0.64, size * 0.64), 2, 2)
    finally:
        p.end()
    return pm


_SVG_PIX_CACHE = {}


def render_svg(key, color=None, size=32):
    """SVG → **染色后的 QPixmap**（画布节点用；★ 缺文件 / 失败 ⇒ 灰方块兜底，绝不抛异常）。

    · 先 `QIcon(svg).pixmap(size, size)`；· `color` 不为 None 时用
      `CompositionMode_SourceIn` 把**非透明区域整体染色**（保留形状与抗锯齿）；
    · 结果按 (key, color, size) 缓存。
    """
    try:
        size = max(8, int(size))
    except Exception:
        size = 32
    col = None
    if color is not None:
        try:
            _c = QColor(color)
            if _c.isValid():
                col = _c
        except Exception:
            col = None
    ck = (str(key), col.name() if col is not None else "", size)
    cached = _SVG_PIX_CACHE.get(ck)
    if cached is not None:
        return cached
    pm = None
    try:
        path = svg_path_for(key)
        if path:
            base = QIcon(path).pixmap(size, size)
            if not base.isNull():
                pm = base
                if col is not None:
                    tinted = QPixmap(base.size())
                    tinted.fill(Qt.transparent)
                    p = QPainter(tinted)
                    try:
                        p.drawPixmap(0, 0, base)
                        p.setCompositionMode(QPainter.CompositionMode_SourceIn)
                        p.fillRect(tinted.rect(), col)
                    finally:
                        p.end()
                    pm = tinted
    except Exception:
        pm = None
    if pm is None or pm.isNull():
        pm = _fallback_pixmap(size)
    _SVG_PIX_CACHE[ck] = pm
    return pm

def make_icon(key, color=None, size=16):
    """把一个 `draw_icon()` 图案变成 `QIcon`（批次6 目标2-M2，树控件用）。

    · ★ **SVG 优先**（`icons/`），缺文件 ⇒ `_fallback_pixmap()` 灰方块兜底；
    · ★ **2 倍画布 + setDevicePixelRatio(2)** ⇒ 高分屏不糊；
    · ★ 未知 key ⇒ `generic`（保证画得出来）；任何异常 ⇒ 返回空 QIcon（**不崩**）；
    · 结果按 (key, color, size) 缓存 ⇒ 建树时反复取也不重画。
    """
    try:
        size = max(8, int(size))
    except Exception:
        size = 16
    key = str(key)
    is_button_key = key in SVG_BUTTON          # ★ 顶部按钮键（不属于节点图案）
    if not is_button_key and key not in _KNOWN_ICON_KEYS:   # 传进来的是“算子名/分组名”⇒ 先查映射表
        try:
            from core import icon_keys
            key = icon_keys.icon_key_for(key)
        except Exception:
            key = "generic"
    if not is_button_key and key not in _KNOWN_ICON_KEYS:
        key = "generic"
    cache_key = (key, str(color), size)
    cached = _ICON_CACHE.get(cache_key)
    if cached is not None:
        return cached
    icon = QIcon()
    # ★ 批次6 目标5-M2：SVG 优先（缺失/渲染失败 ⇒ 继续走下面的 QPainter 回退）
    try:
        _p = svg_path_for(key)
        if _p:
            _ic = QIcon(_p)
            if not _ic.isNull():
                icon = _ic
    except Exception:
        icon = QIcon()
    try:
        if not icon.isNull():
            _ICON_CACHE[cache_key] = icon
            return icon
        icon = QIcon(_fallback_pixmap(size))   # ★ 缺 SVG ⇒ 灰方块兜底（不再自绘图案）
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
