# -*- coding: utf-8 -*-
"""批次6 目标4-M1 判据：**图片信息条**（方案 §3.2.4 目标4-M1 / §十三 第 64 条）。

用户 2026.10.26 拍板（参考海康 VM）：
  · 信息条 = **通栏横条**，位于**图片视图下方、图库工具栏上方**（不是浮层）；
  · 内容只有三项：`W * H | X:.... Y:.... | R:... G:... B:...`（**文字靠右**）；
  · 坐标 = **原图像素**坐标（缩放/平移时按比例反算）；颜色 = 该像素值（内部 BGR）；
  · 单通道图显示 `V:..`；鼠标移出 / 点在图外 ⇒ 坐标与颜色显示 `--`；无图 ⇒ 尺寸也 `--`；
  · ★ **不显示**文件名 / 格式 / 文件大小 / **缩放百分比**。
"""
import os
import sys

PROJ = r"E:\opencv_python_3_8\PySide\VisionFlowNoed"
os.chdir(PROJ)
sys.path.insert(0, PROJ)

import numpy as np                                                         # noqa: E402
from PySide2.QtCore import QEvent, QPoint, QPointF, Qt                     # noqa: E402
from PySide2.QtGui import QMouseEvent                                      # noqa: E402
from PySide2.QtWidgets import QApplication, QLabel, QWidget                # noqa: E402

app = QApplication([])
import main as m                                                           # noqa: E402
from widgets import image_info_bar as ib                                   # noqa: E402

_pass = [0]
_fails = []


def check(title, cond, actual=None):
    if cond:
        _pass[0] += 1
        print("PASS  " + title)
    else:
        _fails.append(title)
        print("FAIL  " + title + "   <- " + repr(actual))


def pump(n=4):
    for _ in range(n):
        app.processEvents()


def vp_for_pixel(view, px, py):
    """找一个视口坐标，使 mapToScene 后取整正好落在原图像素 (px, py) 上。

    （直接 mapFromScene(20.5, 10.5) 会因为取整落到隔壁像素，所以 ±几个像素里试一遍。）
    """
    base = view.mapFromScene(QPointF(px + 0.5, py + 0.5))
    for dx in (0, -1, 1, -2, 2):
        for dy in (0, -1, 1, -2, 2):
            vp = QPoint(base.x() + dx, base.y() + dy)
            sp = view.mapToScene(vp)
            if int(sp.x()) == px and int(sp.y()) == py:
                return vp
    return base


# ===================== ① format_info 纯函数（逐字符） =====================
want = "2448 * 2048 | X:0488 Y:0077 | R:255 G:255 B:255"
got = ib.format_info(2448, 2048, 488, 77, (255, 255, 255))
check("① format_info 彩色样例逐字符一致", got == want, got)

got = ib.format_info(640, 480, 10, 20, (128,))
check("② 单通道显示 V: 且不含 R:/G:/B:",
      "V:128" in got and "R:" not in got and "G:" not in got, got)

got = ib.format_info(2448, 2048, None, None, None)
check("③ 无坐标 ⇒ X:-- Y:--", "X:-- Y:--" in got, got)

got = ib.format_info(None, None, None, None, None)
check("④ 无图 ⇒ 尺寸也是 --", got.startswith("--"), got)

# ===================== ② 界面上的信息条 =====================
w = m.MainWindow()
w.main_window.resize(1400, 900)
w.main_window.show()
pump(8)

bar = w.main_window.findChild(QWidget, "image_info_bar")
label = w.main_window.findChild(QLabel, "lbl_image_info")
check("⑤ 信息条控件存在", bar is not None, None)
check("⑥ 信息条高度 = 24", bar is not None and bar.height() == 24,
      None if bar is None else bar.height())
check("⑦ 文本靠右（含 AlignRight）",
      label is not None and bool(int(label.alignment()) & int(Qt.AlignRight)),
      None if label is None else label.alignment())

# 挂一张小图（左上角像素故意给不同值，便于验证 BGR -> RGB 的转换）
img = np.zeros((100, 200, 3), np.uint8)
img[10, 20] = (10, 20, 30)          # numpy 里是 BGR ⇒ 应显示 R:30 G:20 B:10
w._display_image(img)
pump(4)

text = label.text() if label is not None else ""
check("⑧ 显示尺寸 = 原图 200 * 100", "200 * 100" in text, text)
check("⑨ 文本里没有 %% （不显示缩放百分比）", "%" not in text, text)

# 鼠标移到 (20,10) 这个原图像素上
view = w.image_view
vp = vp_for_pixel(view, 20, 10)
ev = QMouseEvent(QEvent.MouseMove, QPoint(vp), Qt.NoButton, Qt.NoButton, Qt.NoModifier)
view.mouseMoveEvent(ev)
pump(2)
text = label.text()
check("⑩ 鼠标在图上 ⇒ 原图坐标 X:0020 Y:0010", "X:0020 Y:0010" in text, text)
check("⑪ 像素颜色按 RGB 显示（R:30 G:20 B:10）",
      "R:30 G:20 B:10" in text, text)

# 鼠标移出视图
view.leaveEvent(QEvent(QEvent.Leave))
pump(2)
text = label.text()
check("⑫ 鼠标移出 ⇒ 坐标/颜色清空", "X:-- Y:--" in text, text)

# 点在图片外（黑边）
outside = QPoint(view.mapFromScene(QPointF(-50.0, -50.0)))
view.mouseMoveEvent(QMouseEvent(QEvent.MouseMove, outside,
                                Qt.NoButton, Qt.NoButton, Qt.NoModifier))
pump(2)
text = label.text()
check("⑬ 点在图外黑边 ⇒ 视为无坐标", "X:-- Y:--" in text, text)

# 单通道图 ⇒ V:
gray = np.full((60, 80), 77, np.uint8)
w._display_image(gray)
pump(4)
text = label.text()
check("⑭ 单通道图 ⇒ 尺寸 80 * 60 且颜色位显示 V:--",
      "80 * 60" in text and "V:--" in text and "R:--" not in text, text)

# 清空画面
w._display_image(None)
pump(4)
text = label.text()
check("⑮ 无图 ⇒ 尺寸显示 --", text.startswith("--"), text)

# 原有控件都在（结构没被破坏）
names = ["gallery_toolbar", "image_gallery", "result_tab", "tool_tab_widget",
         "flowWidget", "execution_log"]
missing = [n for n in names if w.main_window.findChild(QWidget, n) is None]
check("⑯ 关键控件仍可 findChild", not missing, missing)

# ===================== ③ 4.1.2：中键拖动 + 鼠标跟踪 + 浮层信息条 =====================
from PySide2.QtWidgets import QGraphicsView                                   # noqa: E402

# 换一张**大图**（4000×3000）⇒ 滚动条有范围，才能验证中键拖动
big = np.zeros((3000, 4000, 3), np.uint8)
big[77, 488] = (10, 20, 30)          # BGR ⇒ 应显示 R:30 G:20 B:10
w._display_image(big)
pump(6)
vp = view.viewport()

# ⑰ 鼠标跟踪（本次 bug 的根因：没开跟踪 ⇒ 不按键时 Qt 不发 mouseMoveEvent）
check("⑰ 鼠标跟踪已开启（view + viewport）",
      view.hasMouseTracking() and vp.hasMouseTracking(),
      (view.hasMouseTracking(), vp.hasMouseTracking()))

# ⑱ 不按键的 MouseMove **经 viewport 投递**（真实路径）⇒ 信息条更新
view.horizontalScrollBar().setValue(0)
view.verticalScrollBar().setValue(0)
pump(3)
q = vp_for_pixel(view, 488, 77)
QApplication.sendEvent(vp, QMouseEvent(QEvent.MouseMove, QPoint(q),
                                       Qt.NoButton, Qt.NoButton, Qt.NoModifier))
pump(3)
text = label.text()
check("⑱ 不按键移动鼠标 ⇒ 坐标/颜色实时更新（经 viewport 投递）",
      "X:0488 Y:0077" in text and "R:30 G:20 B:10" in text, text)

# ⑲ 中键拖动 ⇒ 平移；左键拖动 ⇒ 不平移；光标随中键变抓手
h0 = view.horizontalScrollBar().value()
view.mousePressEvent(QMouseEvent(QEvent.MouseButtonPress, QPoint(300, 200),
                                 Qt.MiddleButton, Qt.MiddleButton, Qt.NoModifier))
cursor_mid = int(view.cursor().shape())
view.mouseMoveEvent(QMouseEvent(QEvent.MouseMove, QPoint(260, 190),
                                Qt.NoButton, Qt.MiddleButton, Qt.NoModifier))
h1 = view.horizontalScrollBar().value()
view.mouseReleaseEvent(QMouseEvent(QEvent.MouseButtonRelease, QPoint(260, 190),
                                   Qt.MiddleButton, Qt.NoButton, Qt.NoModifier))
cursor_after = int(view.cursor().shape())
h_before_left = view.horizontalScrollBar().value()
view.mousePressEvent(QMouseEvent(QEvent.MouseButtonPress, QPoint(300, 200),
                                 Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))
view.mouseMoveEvent(QMouseEvent(QEvent.MouseMove, QPoint(240, 160),
                                Qt.NoButton, Qt.LeftButton, Qt.NoModifier))
view.mouseReleaseEvent(QMouseEvent(QEvent.MouseButtonRelease, QPoint(240, 160),
                                   Qt.LeftButton, Qt.NoButton, Qt.NoModifier))
h_after_left = view.horizontalScrollBar().value()
check("⑲ 中键拖动平移 / 左键不平移 / 光标变抓手",
      h1 != h0 and h_after_left == h_before_left
      and cursor_mid == int(Qt.ClosedHandCursor)
      and cursor_after == int(Qt.ArrowCursor),
      (h0, h1, h_before_left, h_after_left, cursor_mid, cursor_after))

# ⑳ 信息条是**画布内浮层**：挂在 viewport 上、贴底横满、半透明、鼠标穿透
bar2 = vp.findChild(QWidget, "image_info_bar")
geo_ok = (bar2 is not None and bar2.parent() is vp
          and bar2.y() == vp.height() - 24 and bar2.width() == vp.width()
          and bar2.height() == 24)
check("⑳ 信息条嵌在画布内（贴底横满/半透明/鼠标穿透）",
      geo_ok
      and bar2 is not None
      and bar2.testAttribute(Qt.WA_StyledBackground)
      and bar2.testAttribute(Qt.WA_TransparentForMouseEvents),
      None if bar2 is None else (bar2.geometry().getRect(), vp.size().toTuple()))

# ㉑ ★ 参数窗口用的新实例：类默认行为一个字节没改（ROI 左键画框仍可用）
from widgets.ImageGraphicsView import ImageGraphicsView                      # noqa: E402
fresh = ImageGraphicsView()
check("㉑ 新实例默认行为未改（ScrollHandDrag + 未启用中键拖动）",
      fresh.dragMode() == QGraphicsView.ScrollHandDrag
      and fresh.enable_middle_pan is False,
      (int(fresh.dragMode()), fresh.enable_middle_pan))

print("")
print("通过 %d 项，失败 %d 项" % (_pass[0], len(_fails)))
if _fails:
    for f in _fails:
        print("  FAILED: " + f)
sys.exit(0 if not _fails else 1)
