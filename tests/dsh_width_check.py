# -*- coding: utf-8 -*-
"""量一下各算子参数窗口的宽度，找出"取反窗口偏宽"的来源"""
import os
import sys

PROJ = r"E:\opencv_python_3_8\PySide\VisionFlowNoed"
os.chdir(PROJ)
sys.path.insert(0, PROJ)

from PySide2 import QtWidgets
from PySide2.QtWidgets import QApplication
from PySide2.QtCore import QPointF

app = QApplication([])
import main as m

w = m.MainWindow()
w.main_window.show()

DIALOGS = {
    "灰度": m.GrayParamsDialog,
    "直线识别": m.LineParamsDialog,
    "圆识别": m.CircleParamsDialog,
}
NAMES = ["灰度", "取反", "滤波", "二值化", "形态学", "边缘提取", "直线识别", "圆识别", "图片源"]

for i, name in enumerate(NAMES):
    node = w.add_flow_node(name, QPointF(20 + i * 10, 20 + i * 10))
    cls = DIALOGS.get(name, m.GenericProcessDialog)
    dlg = cls(w.main_window, node=node, main_window=w)
    dlg.show()
    for _ in range(3):
        app.processEvents()
    pages = []
    tw = dlg.ui.tabWidget
    for j in range(tw.count()):
        page = tw.widget(j)
        pages.append("{0}:{1}".format(tw.tabText(j), page.sizeHint().width()))
    kids = [c for c in dlg.findChildren(QtWidgets.QWidget)
            if c is not dlg and c.objectName() and c.isVisibleTo(dlg)]
    kids.sort(key=lambda c: c.sizeHint().width(), reverse=True)
    top = ["{0}({1})={2}".format(c.objectName(), type(c).__name__, c.sizeHint().width())
           for c in kids[:3]]
    print("{0:6s} 宽={1:4d} sizeHint={2:4d} minimumHint={3:4d} | 页 {4} | 最宽控件 {5}".format(
        name, dlg.width(), dlg.sizeHint().width(), dlg.minimumSizeHint().width(),
        " ".join(pages), " ".join(top)))
    dlg.close()
