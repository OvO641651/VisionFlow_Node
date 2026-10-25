# -*- coding: utf-8 -*-
"""图片信息条（批次6 目标4-M1；第 2 次修改 4.1.2 起改为**画布内浮层**）。

形态（用户 2026.10.26 定，参考海康 VM 图 2 红框）：
    · **嵌在图像画布内部**，贴在视口**最底部**、**横向拉满**、高 24px，**半透明**、**不占布局高度**；
    · **鼠标穿透**（条上点不到图 ⇒ 坐标显示 `--`，但底部的图仍可拖动/缩放）；
    · 文字**靠右**。

内容（只有三项）：
    `W * H | X:.... Y:.... | R:... G:... B:...`
    · 尺寸 = **原图**像素尺寸；坐标 = 鼠标所指的**原图像素**坐标；颜色 = 该像素值（内部 BGR ⇒ 显示 R/G/B）；
    · 单通道图显示 `V:`；鼠标移出 / 点在图外黑边 ⇒ 坐标与颜色 `--`；无图 ⇒ 尺寸也 `--`；
    · ★ 不显示文件名 / 格式 / 文件大小 / **缩放百分比**。

本模块只放"控件 + 文案 + 接线"，**不新增 MainWindow 方法**（门禁白名单要求）。
"""

from PySide2.QtCore import QEvent, QObject, Qt
from PySide2.QtWidgets import QHBoxLayout, QLabel, QWidget

#: 信息条高度（与 .ui 时代一致）
BAR_HEIGHT = 24

#: 信息条样式：半透明黑底 + 白字（整条贴底横满，所以不加圆角）
BAR_STYLE = (
    "QWidget#image_info_bar{"
    "background-color:rgba(0,0,0,140);"
    "}"
    "QLabel#lbl_image_info{"
    "color:#e8e8e8;"
    "font-size:11px;"
    "padding:0px 6px;"
    "background:transparent;"
    "}"
)

#: 无内容时的占位
EMPTY = "--"


def _fmt4(value):
    """坐标补零到 4 位（2448 宽的图也够用）。"""
    try:
        return "%04d" % int(value)
    except Exception:
        return EMPTY


def format_info(w, h, x=None, y=None, rgb=None, single=False):
    """把尺寸 / 坐标 / 颜色拼成一行文本（**纯函数**，便于用例直接断言）。

    :param w: 原图宽（None ⇒ 显示 `--`）
    :param h: 原图高
    :param x: 原图像素 x（None ⇒ 坐标显示 `X:--`）
    :param y: 原图像素 y
    :param rgb: 颜色元组。三元组 (r,g,b) ⇒ `R:/G:/B:`；单元素 (v,) ⇒ `V:`
    :param single: 这张图是不是单通道（灰度/二值）⇒ 没有坐标时也显示 `V:--`
    """
    size_text = EMPTY if (w is None or h is None) else "%d * %d" % (int(w), int(h))

    if x is None or y is None:
        pos_text = "X:-- Y:--"
    else:
        pos_text = "X:%s Y:%s" % (_fmt4(x), _fmt4(y))

    one_channel = bool(single) or (rgb is not None and len(rgb) == 1)
    if x is None or y is None or rgb is None:
        col_text = "V:--" if one_channel else "R:-- G:-- B:--"
    elif one_channel:
        col_text = "V:%d" % int(rgb[0])
    else:
        col_text = "R:%d G:%d B:%d" % (int(rgb[0]), int(rgb[1]), int(rgb[2]))

    return "%s | %s | %s" % (size_text, pos_text, col_text)


def _state_of(host):
    """当前记住的 (w, h, single)。"""
    state = getattr(host, "_image_info_state", None)
    if not state or len(state) != 3:
        return (None, None, False)
    return state


def update_info(host, payload=None):
    """刷新信息条文本。

    :param payload: `(w, h, x, y, rgb, single)`；传 None 表示"鼠标移出图片" ⇒ 坐标/颜色清空
    """
    label = getattr(host, "_image_info_label", None)
    if label is None:
        return

    w, h, single = _state_of(host)
    x = y = rgb = None
    if payload:
        try:
            w, h, x, y, rgb, single = payload
        except Exception:
            return
        if single is None:
            single = bool(rgb is not None and len(rgb) == 1)
        host._image_info_state = (w, h, bool(single))

    try:
        label.setText(format_info(w, h, x, y, rgb, single))
    except Exception:
        pass


def update_image_size(host, img):
    """换图时更新尺寸（由图片视图在 `set_image` 里回调）。"""
    try:
        if img is None:
            host._image_info_state = (None, None, False)
        else:
            h = int(img.shape[0])
            w = int(img.shape[1])
            single = (len(img.shape) == 2 or
                      (len(img.shape) == 3 and img.shape[2] == 1))
            host._image_info_state = (w, h, bool(single))
    except Exception:
        host._image_info_state = (None, None, False)
    update_info(host)


def relayout(host, view=None):
    """把信息条摆到视口**最底部、横向拉满**（视口尺寸变化时也要调）。"""
    bar = getattr(host, "_image_info_bar", None)
    if bar is None:
        return
    if view is None:
        view = getattr(host, "image_view", None)
    if view is None:
        return
    try:
        vp = view.viewport()
        if vp is None:
            return
        bar.setGeometry(0, max(0, vp.height() - BAR_HEIGHT), vp.width(), BAR_HEIGHT)
        bar.raise_()
    except Exception:
        pass


class _InfoBarHost(QObject):
    """把"视图回调 + 视口尺寸变化"接到"信息条刷新/重摆"上。

    ★ 用 QObject 子对象 + 绑定方法接线（不用 lambda / 闭包，避免生命周期问题）。
    """

    def __init__(self, host, parent=None, view=None):
        super(_InfoBarHost, self).__init__(parent)
        self._host = host
        self._view = view

    def on_mouse(self, payload):
        update_info(self._host, payload)

    def on_image_changed(self, img):
        update_image_size(self._host, img)

    def eventFilter(self, obj, event):
        """视口尺寸变化 ⇒ 重新贴底（信息条是浮层，不参与布局）。"""
        try:
            if (self._view is not None and obj is self._view.viewport()
                    and event.type() == QEvent.Resize):
                relayout(self._host, self._view)
        except Exception:
            pass
        return False


def _find(host, cls, name):
    try:
        return host.main_window.findChild(cls, name)
    except Exception:
        return None


def _create_bar(view):
    """运行时创建信息条（parent = 图片视图的 viewport ⇒ 嵌在画布内部）。"""
    vp = view.viewport()
    bar = QWidget(vp)
    bar.setObjectName("image_info_bar")
    # QWidget 想要 styleSheet 生效必须开 WA_StyledBackground，否则半透明底画不出来
    bar.setAttribute(Qt.WA_StyledBackground, True)
    # ★ 鼠标穿透：条不挡图（底部 24px 的图仍然可以拖动 / 缩放）
    bar.setAttribute(Qt.WA_TransparentForMouseEvents, True)
    bar.setStyleSheet(BAR_STYLE)

    lay = QHBoxLayout(bar)
    lay.setContentsMargins(6, 0, 6, 0)
    lay.setSpacing(6)

    label = QLabel(bar)
    label.setObjectName("lbl_image_info")
    label.setText(EMPTY)
    label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
    lay.addWidget(label)
    return bar, label


def install_image_info_bar(host, view=None):
    """创建/找到信息条、上样式、把图片视图的鼠标/换图回调与视口 resize 接上。

    :return: 信息条控件（失败时返回 None）
    """
    try:
        if view is None:
            view = getattr(host, "image_view", None)
        if view is None:
            return None

        # 兼容：若 .ui 里还留着旧控件就用它；否则运行时新建（4.1.2 起走这条）
        bar = _find(host, QWidget, "image_info_bar")
        label = _find(host, QLabel, "lbl_image_info")
        if bar is None or label is None:
            bar, label = _create_bar(view)
        else:
            bar.setAttribute(Qt.WA_StyledBackground, True)
            bar.setStyleSheet(BAR_STYLE)
            label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        host._image_info_bar = bar
        host._image_info_label = label
        if not hasattr(host, "_image_info_state"):
            host._image_info_state = (None, None, False)

        # 视图回调（鼠标移动 / 换图）
        if hasattr(view, "set_info_callbacks"):
            cb_host = _InfoBarHost(host, parent=view, view=view)
            host._image_info_cb_host = cb_host      # 保住引用，别被回收
            view.set_info_callbacks(cb_host.on_mouse, cb_host.on_image_changed)
            # 视口尺寸变化 ⇒ 信息条重新贴底
            try:
                view.viewport().installEventFilter(cb_host)
                host._image_info_filter_host = cb_host
            except Exception:
                pass

        relayout(host, view)
        update_info(host)
        return bar
    except Exception:
        return None
