# -*- coding: utf-8 -*-
"""
批次4 目标5-M2 验证⑥：**所有参数窗口在任何宽度下都不许把控件裁掉**（通用护栏）

为什么要有这一套（用户 2026.10.12 实测报"输出图像节点窗口被遮挡"）：
    "运行参数"页整页在 `QScrollArea` 里、而**横向滚动条被禁用**（用户 2026.10.7 定的"横向条永不出现"）
    ⇒ 一旦内容的**最小宽**超过视口，右边就会被**静默裁掉**（连滚动条都没有）。
    第一次是滑块最小宽 90（把微调框箭头切掉），这次是 `QComboBox` 的 minimumSizeHint
    默认按**最长那一项**算（"MP4（mp4v，体积小，推荐）"这种长项把整行顶出去），
    而且**用户机器上的字体比无头环境更宽**，所以我在无头里量着"还有余量"、他那儿已经被切了。

判据（按真实路由把每个窗口都开一遍，**两种宽度 × 每个行联动档位**）：
    · 内容最小宽 ≤ 视口宽；
    · 每一行里**每个可见控件**的右缘 ≤ 视口宽；
    · 横向滚动条 maximum == 0（它被禁用，"不裁掉"就等于它没有可滚动的量）。
"""
import os
import sys

PROJ = r"E:\opencv_python_3_8\PySide\VisionFlowNoed"
os.chdir(PROJ)
sys.path.insert(0, PROJ)

import numpy as np
from PySide2.QtWidgets import QApplication, QComboBox, QLabel, QVBoxLayout, QWidget
from PySide2.QtCore import QPoint, QPointF

app = QApplication([])
import main as m
import widgets.FlowPages as FlowPages
import ui.GenericProcessDialog as GPD
from ui.LineParamsDialog import LineParamsDialog
from ui.CircleParamsDialog import CircleParamsDialog
from ui.GrayParamsDialog import GrayParamsDialog
from core.NodeRegistry import get_spec


class FakeMB(object):
    warning = information = staticmethod(lambda *a, **k: None)
    question = staticmethod(lambda *a, **k: 0)


class FakeFD(object):
    getOpenFileNames = staticmethod(lambda *a, **k: ([], ""))
    getOpenFileName = staticmethod(lambda *a, **k: ("", ""))
    getSaveFileName = staticmethod(lambda *a, **k: ("", ""))
    getExistingDirectory = staticmethod(lambda *a, **k: "")


m.QMessageBox = FakeMB
FlowPages.QMessageBox = FakeMB
GPD.QMessageBox = FakeMB
m.QFileDialog = FakeFD
GPD.QFileDialog = FakeFD

fails = []


def check(name, cond, extra=None):
    text = '' if extra is None else '   <- ' + str(extra)
    print(('PASS  ' if cond else 'FAIL  ') + name + text)
    if not cond:
        fails.append(name)


SPECIAL = {"直线识别": LineParamsDialog, "圆识别": CircleParamsDialog, "灰度": GrayParamsDialog}


def dialog_for(main_window, name):
    """按 `on_node_double_clicked()` 的同一条路由拿窗口类（顺带把路由也验了）"""
    node = main_window.add_flow_node(name, QPointF(20, 20))
    cls = SPECIAL.get(name)
    if cls is None:
        spec = get_spec(name)
        if spec is None or spec.param_specs is None:
            return None, None
        cls = GPD.GenericProcessDialog
    return node, cls(main_window.main_window, node=node, main_window=main_window)


def row_widgets(dlg):
    """"运行参数"页里每一行的所有控件（含容器内部的），只挑可见的"""
    layout = getattr(dlg, "param_layout", None)
    if layout is None:
        layout = dlg.ui.findChild(QVBoxLayout, "verticalLayout_8")
    out = []
    if layout is None:
        return out
    for i in range(layout.count()):
        item = layout.itemAt(i)
        row = item.layout() if item is not None else None
        if row is None:
            continue
        for j in range(row.count()):
            widget = row.itemAt(j).widget()
            if widget is None:
                continue
            out.append(widget)
            out.extend(widget.findChildren(QWidget))
    return out


def measure(dlg, tag):
    """返回 (标签, 问题列表)。问题列表空 = 这一档没问题"""
    scroll = getattr(dlg, "run_params_scroll", None)
    if scroll is None:
        return tag, ['没有滚动区']
    vp = scroll.viewport()
    problems = []
    content_min = scroll.widget().minimumSizeHint().width()
    if content_min > vp.width():
        problems.append('内容最小宽 %d > 视口 %d' % (content_min, vp.width()))
    if scroll.horizontalScrollBar().maximum() != 0:
        problems.append('横向可滚 %d' % scroll.horizontalScrollBar().maximum())
    for widget in row_widgets(dlg):
        if not widget.isVisibleTo(dlg):
            continue
        right = widget.mapTo(vp, QPoint(widget.width(), 0)).x()
        if right > vp.width():
            problems.append('%s(%s) 右缘 %d > 视口 %d' % (
                widget.objectName() or widget.__class__.__name__,
                widget.__class__.__name__, right, vp.width()))
    return tag, problems


w = m.MainWindow()
w.main_window.show()
w.current_static_image = np.full((120, 160, 3), 60, np.uint8)

# 树上所有叶子（= 所有算子），逐个按真实路由开窗口
tree_names = []
import xml.etree.ElementTree as ET
root = ET.parse("main.ui").getroot()
for top in root.iter("item"):
    text = top.find("property[@name='text']/string")
    if text is not None and text.text:
        tree_names.append(text.text)
# 只保留"有算子的叶子"（顶层分组名与"新建项目"会被 dialog_for 过滤掉）
candidates = [n for n in tree_names if get_spec(n) is not None or n in SPECIAL]

checked = 0
for name in candidates:
    node, dlg = dialog_for(w, name)
    if dlg is None:
        continue
    checked += 1
    # 运行参数页（起点节点没有"基本参数"页，索引 0 就是运行参数页；其余切到它）
    pages = [dlg.ui.tabWidget.tabText(i) for i in range(dlg.ui.tabWidget.count())]
    if "运行参数" in pages:
        dlg.ui.tabWidget.setCurrentIndex(pages.index("运行参数"))
    dlg.show()
    app.processEvents()

    for width in (274, 390):
        dlg.resize(width, 560)
        app.processEvents()
        tag, problems = measure(dlg, '%s@%d' % (name, width))
        check('窗口「%s」在 %dpx 宽下不裁掉控件' % (name, width), problems == [], problems)

    # 行联动的每一档都要试（颜色提取：HSV / RGB 两套阈值都要装得下）
    deps = sorted({dep for _row, dep, _allowed in getattr(dlg, "_linked_rows", []) or []})
    for dep in deps:
        combo = dlg.param_controls.get(dep)
        if not isinstance(combo, QComboBox):
            continue
        for index in range(combo.count()):
            combo.setCurrentIndex(index)
            app.processEvents()
            tag, problems = measure(dlg, '%s@274/%s' % (name, combo.itemText(index)))
            check('窗口「%s」在 %dpx 宽 + 「%s = %s」档下不裁掉控件' % (
                name, 274, dep, combo.itemText(index)), problems == [], problems)
        combo.setCurrentIndex(0)
        app.processEvents()

    dlg.close()

check('前置：确实逐个开过所有参数窗口（不是空跑）', checked >= 12, checked)

print('-' * 70)
if fails:
    print('失败项：%d' % len(fails))
    for name in fails:
        print('   - ' + name)
else:
    print('失败项：无')
sys.exit(1 if fails else 0)
