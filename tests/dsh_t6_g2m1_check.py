# -*- coding: utf-8 -*-
"""批次6 目标2-M1 判据：**树状图搜索 + 展开/折叠**（方案 §五 的 M1）。

用户 2026.10.18 拍板：
  · 「展开/折叠」用**一个按钮切换**（文字随状态变）；
  · 搜索**不区分大小写**、**子串匹配节点名 + 分组名**（不做拼音）；
  · **过滤状态中双击命中项仍能建节点**。
"""
import os
import sys
import time

PROJ = r"E:\opencv_python_3_8\PySide\VisionFlowNoed"
os.chdir(PROJ)
sys.path.insert(0, PROJ)

from PySide2.QtCore import QPoint
from PySide2.QtWidgets import QApplication, QLineEdit, QToolButton, QLabel, QTabWidget, QWidget   # noqa: E402

app = QApplication([])
import main as m                                                             # noqa: E402

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


def new_window():
    win = m.MainWindow()
    win.main_window.resize(1400, 900)
    win.main_window.show()
    pump(6)
    return win


def visible_names(tree):
    out = []
    for i in range(tree.topLevelItemCount()):
        g = tree.topLevelItem(i)
        for j in range(g.childCount()):
            c = g.child(j)
            if not c.isHidden():
                out.append(c.text(0))
    return out


def group_named(tree, name):
    for i in range(tree.topLevelItemCount()):
        g = tree.topLevelItem(i)
        if g.text(0) == name:
            return g
    return None


def search(edit, text):
    edit.setText(text)
    pump(3)


win = new_window()
tree = win.tree
edit = win.main_window.findChild(QLineEdit, "edit_tree_search")
button = win.main_window.findChild(QToolButton, "btn_tree_expand")
hint = win.main_window.findChild(QLabel, "lbl_tree_search_hint")     # ★ M1c：应为 None

# ① 控件都在，且原树对象没变
check("① 搜索框 / 展开折叠按钮 都在（★ M1c：提示控件已删除）", edit is not None and button is not None,
      (edit, button))
check("① ★ 无匹配提示控件已彻底删除（不存在）", hint is None, hint)
check("① 原树控件对象仍是 self.tree（对象名未改）", win.main_window.findChild(type(tree), "tree") is tree, None)

# ② 搜「边缘」⇒ 只剩「边缘提取」，且「处理」组自动展开
search(edit, "边缘")
names = visible_names(tree)
proc = group_named(tree, "处理")
check("② 搜「边缘」只剩「边缘提取」", names == ["边缘提取"], names)
check("② 命中节点名 ⇒ 其分组自动展开", proc is not None and proc.isExpanded(), None if proc is None else proc.isExpanded())

# ③ 搜分组名「处理」⇒ 该组 6 项全可见
search(edit, "处理")
proc_names = []
if proc is not None:
    for j in range(proc.childCount()):
        c = proc.child(j)
        if not c.isHidden():
            proc_names.append(c.text(0))
check("③ 搜分组名「处理」⇒ 该组 6 项全可见",
      proc_names == ["灰度", "取反", "滤波", "二值化", "形态学", "边缘提取"], proc_names)

# ④ 子串：搜「图片」⇒ 「图片源」（且「输出图像」不含「图片」，不应出现）
search(edit, "图片")
names = visible_names(tree)
check("④ 子串匹配：搜「图片」只有「图片源」", names == ["图片源"], names)

# ⑤ 无匹配 ⇒ 全部隐藏、★ 不提示、且窗口宽度不变形（M1c 的量化指标）
_w0 = win.main_window.width()
search(edit, "zzz")
check("⑤ 无匹配：树全空", visible_names(tree) == [], visible_names(tree))
_w1 = win.main_window.width()
check("⑤ ★ 无匹配时主窗口宽度不变（不再被提示文字挤变形）", abs(_w1 - _w0) <= 1, (_w0, _w1))
check("⑤ ★ 无匹配时没有任何提示控件", hint is None, hint)

# ⑥ 清空 ⇒ 全部恢复 + 折叠状态回到搜索前（先把「采集」折叠作为对照）
proc2 = group_named(tree, "采集")
if proc2 is not None:
    proc2.setExpanded(False)
search(edit, "边缘")
search(edit, "")
total = sum(tree.topLevelItem(i).childCount() for i in range(tree.topLevelItemCount()))
check("⑥ 清空后全部节点恢复可见", len(visible_names(tree)) == total, (len(visible_names(tree)), total))
check("⑥ 清空后折叠状态回到搜索前（「采集」仍折叠）", proc2 is not None and not proc2.isExpanded(),
      None if proc2 is None else proc2.isExpanded())

# ⑦ 一个按钮切换：点一次全展开（文字变「展开」），再点全折叠
groups = [tree.topLevelItem(i) for i in range(tree.topLevelItemCount())]
button.click()
pump(2)
check("⑦ 点一次 ⇒ 全部分组展开", all(g.isExpanded() for g in groups), [g.isExpanded() for g in groups])
check("⑦ 展开后按钮文字为「展开」", button.text() == "展开", button.text())
button.click()
pump(2)
check("⑦ 再点一次 ⇒ 全部分组折叠", all(not g.isExpanded() for g in groups), [g.isExpanded() for g in groups])
check("⑦ 折叠后按钮文字为「折叠」", button.text() == "折叠", button.text())

# ⑧ ★ 过滤状态中双击命中项仍能建节点（真实双击信号 + 等 QTimer.singleShot(1)）
search(edit, "灰度")
target = group_named(tree, "处理").child(0) if group_named(tree, "处理") is not None else None
before = len(win.flow_nodes)
if target is not None:
    tree.setCurrentItem(target)
    tree.itemDoubleClicked.emit(target, 0)
    time.sleep(0.06)
    pump(6)
check("⑧ 过滤中双击命中项仍能建节点", len(win.flow_nodes) == before + 1, (before, len(win.flow_nodes)))

search(edit, "")
pump(2)

# ⑨ 工具箱 Tab：存在 · 标题「工具箱」· 树在这一页里
tab = win.main_window.findChild(QTabWidget, "tool_tab_widget")
check("⑨ 左侧存在 tool_tab_widget（工具箱 Tab）", tab is not None, tab)
check("⑨ 工具箱页标题 == 「工具箱」", tab is not None and tab.tabText(0) == "工具箱", tab.tabText(0) if tab else None)
check("⑨ 树在工具箱页内", tab is not None and tab.widget(0) is tree.parent(), None)

# ⑩ 三个控件**来自 main.ui**（文本里声明 + 运行时 parent 链挂在该页）
ui_text = open(os.path.join(PROJ, "main.ui"), encoding="utf-8").read()
declared = all(("name=" + chr(34) + n + chr(34)) in ui_text for n in ("btn_tree_expand", "edit_tree_search"))
check("⑩ main.ui 里声明了两个控件", declared, declared)
box = win.main_window.findChild(QWidget, "tab_toolbox")
_ok = box is not None and all(box.isAncestorOf(w) for w in (button, edit))
check("⑩ 两个控件的祖先链包含 tab_toolbox", _ok, None)

# ⑪ ★ 树按**像素平滑滚动**（与执行日志一致）
try:
    from PySide2.QtWidgets import QAbstractItemView as _AIV
    _vm = tree.verticalScrollMode()
    _hm = tree.horizontalScrollMode()
    check("⑪ ★ 树垂直滚动 = ScrollPerPixel", _vm == _AIV.ScrollPerPixel, _vm)
    check("⑪ ★ 树水平滚动 = ScrollPerPixel", _hm == _AIV.ScrollPerPixel, _hm)
except Exception as _e:
    check("⑪ 树滚动模式读取", False, _e)

print("=" * 60)
print("通过 %d 项，失败 %d 项" % (_pass[0], len(_fails)))
if _fails:
    for t in _fails:
        print("  FAIL: " + t)
    sys.exit(1)
sys.exit(0)
