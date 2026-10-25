# -*- coding: utf-8 -*-
"""批次6 目标3-M3 判据：**可拖分界线（QSplitter）**（方案 §3.2.3 / §十三 第 62 条）。

用户 2026.10.19 拍板：
  · 只做**左中右三个区域**（左边树 / 中间画布 / 右边图像+日志），上下不做；
  · 分界线宽 **23**、**禁止拖成 0**、拖动比例**不记忆**、**双击 handle 复位**；
  · **折叠树后仍保持「中 : 右 = 1 : 1」**；
  · 左侧允许新建容器（工具箱 + 14px 折叠把手），**折叠后把手仍在**。
"""
import os
import sys

PROJ = r"E:\opencv_python_3_8\PySide\VisionFlowNoed"
os.chdir(PROJ)
sys.path.insert(0, PROJ)

from PySide2.QtCore import QEvent, QPoint, QPointF, Qt                    # noqa: E402
from PySide2.QtGui import QMouseEvent                                     # noqa: E402
from PySide2.QtWidgets import (QApplication, QLabel, QLineEdit, QListWidget,  # noqa: E402
                               QSlider, QSplitter, QTableWidget, QTabWidget,
                               QTextEdit, QToolButton, QTreeWidget, QWidget)

app = QApplication([])
import main as m                                                          # noqa: E402
from widgets.FlowPages import (MAIN_SPLITTER_NAME, RIGHT_SPLITTER_NAME,   # noqa: E402
                               capture_splitter_defaults, reset_splitters,
                               SPLITTER_HANDLE_WIDTH)

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


w = m.MainWindow()
w.main_window.resize(1400, 900)
w.main_window.show()
pump(8)

ms = w.main_window.findChild(QSplitter, MAIN_SPLITTER_NAME)
rs = w.main_window.findChild(QSplitter, RIGHT_SPLITTER_NAME)

# ===================== ① 两个 splitter 的基本属性 =====================
check("① 主分界线 main_splitter 存在且 3 个面板", ms is not None and ms.count() == 3,
      None if ms is None else ms.count())
check("① 右侧纵向分界线 right_splitter 存在且 2 个面板", rs is not None and rs.count() == 2,
      None if rs is None else rs.count())
check("① 主分界线 handle 宽 == SPLITTER_HANDLE_WIDTH", ms is not None and ms.handleWidth() == SPLITTER_HANDLE_WIDTH,
      None if ms is None else ms.handleWidth())
check("① 右侧分界线 handle 宽 == SPLITTER_HANDLE_WIDTH", rs is not None and rs.handleWidth() == SPLITTER_HANDLE_WIDTH,
      None if rs is None else rs.handleWidth())
check("① 两条分界线都禁止拖成 0（childrenCollapsible False）",
      ms is not None and rs is not None
      and ms.childrenCollapsible() is False and rs.childrenCollapsible() is False,
      (None if ms is None else ms.childrenCollapsible(), None if rs is None else rs.childrenCollapsible()))

# ★ 记录初始尺寸（后面双击复位要跟它比）
defaults_main = list(ms.sizes())
defaults_right = list(rs.sizes())
capture_splitter_defaults(w)
print("    初始 main sizes =", defaults_main, " right sizes =", defaults_right)

# ===================== ② 拖动主分界线（左|中） =====================
before = list(ms.sizes())
x0 = ms.handle(1).mapTo(ms, QPoint(0, 0)).x()
ms.moveSplitter(ms.handle(1).x() + 40, 1)
pump(3)
after = list(ms.sizes())
check("② 拖动左|中分界线 ⇒ 左侧与中间尺寸都变了（各 > 20px）",
      abs(after[0] - before[0]) > 20 and abs(after[1] - before[1]) > 20,
      (before, after))

# ===================== ③ 双击 handle ⇒ 复位默认 =====================
for i in range(1, ms.count()):
    handle = ms.handle(i)
    if handle is not None:
        app.sendEvent(handle, QMouseEvent(QEvent.MouseButtonDblClick, QPointF(2.0, 2.0),
                                          Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))
pump(3)
reset_main = list(ms.sizes())
check("③ 双击分界线 ⇒ 主分界线回到初始尺寸（差 ≤2px）",
      all(abs(reset_main[i] - defaults_main[i]) <= 2 for i in range(len(defaults_main))),
      (defaults_main, reset_main))

# ===================== ④ 拖动右侧纵向分界线 =====================
before_r = list(rs.sizes())
y0 = rs.handle(1).mapTo(rs, QPoint(0, 0)).y()
rs.moveSplitter(rs.handle(1).x() + 40, 1)
pump(3)
after_r = list(rs.sizes())
check("④ 拖动右侧上|下分界线 ⇒ 上下尺寸都变了（各 > 20px）",
      abs(after_r[0] - before_r[0]) > 20 and abs(after_r[1] - before_r[1]) > 20,
      (before_r, after_r))

# ===================== ⑤ 折叠后 中 : 右 = 1 : 1，展开还原 =====================
flow_view = w.flow_page_mgr.current_page["view"]
log = w.main_window.findChild(QTableWidget, "execution_log")
panel = w.main_window.findChild(QTabWidget, "tool_tab_widget")
btn = w.main_window.findChild(QToolButton, "btn_collapse_toolbox")
w_before = flow_view.viewport().width()
btn.click()
pump(6)
w_collapsed = flow_view.viewport().width()
log_collapsed = log.width()
ratio = float(w_collapsed) / max(1, log_collapsed)
check("⑤ 折叠后工具箱隐藏", panel.isVisible() is False, panel.isVisible())
check("⑤ 折叠后 画布 : 右侧 ≈ 1 : 1（0.85~1.15）", 0.85 <= ratio <= 1.15, round(ratio, 3))
check("⑤ 折叠后把手仍可见（唯一展开入口）", btn.isVisible() is True, btn.isVisible())
check("⑤ 折叠后画布明显变宽（> 折叠前 + 100px）", w_collapsed > w_before + 100,
      (w_before, w_collapsed))
btn.click()
pump(6)
check("⑤ 展开后画布宽度还原（差 ≤2px）",
      panel.isVisible() is True and abs(flow_view.viewport().width() - w_before) <= 2,
      (panel.isVisible(), flow_view.viewport().width(), w_before))

# ===================== ⑥ 关键控件仍在（对象名一个没改） =====================
targets = [("tool_tab_widget", QTabWidget), ("flowWidget", QTabWidget), ("result_tab", QTabWidget),
           ("tree", QTreeWidget), ("execution_log", QTableWidget), ("left_panel", QWidget),
           ("right_top_panel", QWidget), ("btn_collapse_toolbox", QToolButton),
           ("btn_tree_expand", QToolButton), ("edit_tree_search", QLineEdit),
           ("text_help_body", QTextEdit), ("lbl_help_title", QLabel),
           ("lbl_current_node", QLabel), ("zoom_slider", QSlider),
           ("image_gallery", QListWidget), ("gallery_toolbar", QWidget)]
missing = [nm for nm, cls in targets if w.main_window.findChild(cls, nm) is None]
check("⑥ 关键控件全部仍可 findChild 到（%d 个）" % len(targets), not missing, missing)
check("⑥ 折叠把手对象名仍是 btn_collapse_toolbox",
      btn is not None and btn.objectName() == "btn_collapse_toolbox",
      None if btn is None else btn.objectName())

print("")
print("通过 %d 项，失败 %d 项" % (_pass[0], len(_fails)))
if _fails:
    print("失败项：" + " / ".join(_fails))
sys.exit(1 if _fails else 0)
