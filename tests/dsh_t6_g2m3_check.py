# -*- coding: utf-8 -*-
"""批次6 目标2-M3 判据：**左面板折叠 / 展开** + **树干（非节点项）不许建节点**。

用户 2026.10.18 拍板：
  ① 折叠把手 = 甲（左面板**右边缘**贴一条细把手 14px、垂直拉伸、箭头 `<`/`>` 随状态变）；
  ② 折叠后**留窄条把手**（它是唯一的展开入口）；
  ③ **不记忆**折叠状态（每次启动展开）；
  ④ 树干不许建节点 = **判顶层 + 判注册表 双保险**。

★ 关键口径：画布要取 **当前页的 live view**（`flow_page_mgr.current_page["view"]`）——
  `main.ui` 里的 `flowView` 只是占位，不是运行时那个（本项目规矩：`.ui` 摆占位、真源在运行时）。
"""
import os
import sys
import time

PROJ = r"E:\opencv_python_3_8\PySide\VisionFlowNoed"
os.chdir(PROJ)
sys.path.insert(0, PROJ)

from PySide2.QtWidgets import QApplication, QTabWidget, QToolButton   # noqa: E402
from PySide2.QtCore import Qt, QMimeData, QPoint, QPointF             # noqa: E402
from PySide2.QtGui import QDropEvent                                  # noqa: E402

app = QApplication([])
import main as m                                                      # noqa: E402

_pass = [0]
_fails = []


def check(title, cond, actual=None):
    if cond:
        _pass[0] += 1
        print("PASS  " + title)
    else:
        _fails.append(title)
        print("FAIL  " + title + "   <- " + repr(actual))


def pump(ms=80):
    t0 = time.time()
    while (time.time() - t0) * 1000 < ms:
        app.processEvents()


w = m.MainWindow()
mw = w.main_window
tree = mw.tree
mw.show()
pump(120)

panel = mw.findChild(QTabWidget, "tool_tab_widget")
button = mw.findChild(QToolButton, "btn_collapse_toolbox")
live = w.flow_page_mgr.current_page.get("view")

check("工具箱子控件存在（tool_tab_widget）", panel is not None, panel)
check("折叠把手存在（btn_collapse_toolbox）", button is not None, button)
check("折叠把手宽度 14px（细条）", button is not None and button.maximumWidth() == 14,
      button.maximumWidth() if button is not None else None)

# ---------- ① 折叠 ----------
w0 = live.viewport().width()
t0 = button.text()
button.click()
pump(120)
w1 = live.viewport().width()
check("点折叠 ⇒ 工具箱隐藏", panel.isVisible() is False, panel.isVisible())
check("点折叠 ⇒ 画布变宽（差 > 100px）", (w1 - w0) > 100, "%d -> %d" % (w0, w1))
check("折叠后把手仍可见（唯一展开入口）", button.isVisible() is True, button.isVisible())
check("折叠后箭头变 '>'", button.text() == ">", button.text())

# ---------- ② 展开 ----------
button.click()
pump(120)
w2 = live.viewport().width()
check("再点 ⇒ 工具箱恢复可见", panel.isVisible() is True, panel.isVisible())
check("再点 ⇒ 画布宽度回到折叠前（差 ≤2px）", abs(w2 - w0) <= 2, "%d vs %d" % (w2, w0))
check("展开后箭头变回 '<'", button.text() == "<", button.text())


# ---------- ③ 双击：树干 / 非节点项不许建节点 ----------
def dbl(text):
    items = tree.findItems(text, Qt.MatchExactly | Qt.MatchRecursive)
    if not items:
        return None
    it = items[0]
    tree.setCurrentItem(it)
    n0 = len(w.flow_nodes)
    tree.itemDoubleClicked.emit(it, 0)
    pump(80)
    return len(w.flow_nodes) - n0


n_before = len(w.flow_nodes)
for trunk in ("采集", "处理", "检测识别", "颜色处理", "测试", "新建项目"):
    d = dbl(trunk)
    check("双击树干「%s」不建节点" % trunk, d == 0, d)
check("双击树干之后节点总数不变", len(w.flow_nodes) == n_before, len(w.flow_nodes) - n_before)

d_gray = dbl("灰度")
check("双击真实节点「灰度」仍会建节点（+1）", d_gray == 1, d_gray)

d_src = dbl("图片源")
check("双击真实节点「图片源」仍会建节点（+1）", d_src == 1, d_src)

# ---------- ③b 拖拽：树干 / 非节点项也不许建节点（★ 2.3.2 第 2 次修改）----------
def drop_to_canvas(text):
    """模拟“从树拖到画布松手”：先选中该项，再构造 QDropEvent 走 view.dropEvent。"""
    items = tree.findItems(text, Qt.MatchExactly | Qt.MatchRecursive)
    if not items:
        return None
    tree.setCurrentItem(items[0])
    md = QMimeData()
    md.setText(text)
    pos = QPoint(live.viewport().width() // 2, live.viewport().height() // 2)
    ev = QDropEvent(QPointF(pos), Qt.CopyAction, md, Qt.LeftButton, Qt.NoModifier)
    n0 = len(w.flow_nodes)
    live.dropEvent(ev)
    pump(40)
    return len(w.flow_nodes) - n0


d_drop_trunk = drop_to_canvas("采集")
check("拖拽树干「采集」到画布不建节点", d_drop_trunk == 0, d_drop_trunk)
d_drop_item = drop_to_canvas("新建项目")
check("拖拽非节点项「新建项目」到画布不建节点", d_drop_item == 0, d_drop_item)
d_drop_gray = drop_to_canvas("灰度")
check("拖拽真实节点「灰度」到画布仍会建节点（+1）", d_drop_gray == 1, d_drop_gray)

# 树侧：顶层项摘掉 ItemIsDragEnabled（从源头拖不动）
trunk_item = tree.findItems("采集", Qt.MatchExactly | Qt.MatchRecursive)[0]
node_item = tree.findItems("灰度", Qt.MatchExactly | Qt.MatchRecursive)[0]
check("树干项已摘掉“可拖拽”标志（ItemIsDragEnabled = False）",
      not bool(trunk_item.flags() & Qt.ItemIsDragEnabled), trunk_item.flags())
check("真实节点项仍可拖拽（ItemIsDragEnabled = True）",
      bool(node_item.flags() & Qt.ItemIsDragEnabled), node_item.flags())

# ---------- ③c 折叠把手高度 = 左面板高度（★ 2.3.2）----------
check("折叠把手高度与左面板一致（差 ≤2px）",
      abs(panel.height() - button.height()) <= 2,
      "%d vs %d" % (panel.height(), button.height()))

# ---------- ④ _create_node_from_name 也拦住未注册名 ----------
n0 = len(w.flow_nodes)
r_bad = w._create_node_from_name("采集")
r_ghost = w._create_node_from_name("不存在的节点")
check("_create_node_from_name('采集') 返回 None 且不建节点",
      r_bad is None and len(w.flow_nodes) == n0, (r_bad, len(w.flow_nodes) - n0))
check("_create_node_from_name('不存在的节点') 返回 None",
      r_ghost is None and len(w.flow_nodes) == n0, (r_ghost, len(w.flow_nodes) - n0))

print("")
print("通过 %d 项，失败 %d 项" % (_pass[0], len(_fails)))
if _fails:
    for f in _fails:
        print("  失败: " + f)
sys.exit(0 if not _fails else 1)
