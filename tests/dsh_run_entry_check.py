# -*- coding: utf-8 -*-
"""执行入口修复验证：图库为空 + 流程里有"图片源"时，点按钮能跑、能看图

这个脚本专门走 UI 按钮路径（btn_step_execute / btn_continuous_execute / 参数窗口按钮），
不直接调内部函数——上一版就是只验了内部函数，漏了按钮的前置检查。
"""
import os
import sys

PROJ = r"E:\opencv_python_3_8\PySide\VisionFlowNoed"
OUT = r"E:\opencv_python_3_8\backups\_ui_preview"
os.chdir(PROJ)
sys.path.insert(0, PROJ)

import numpy as np
import cv2
from PySide2 import QtWidgets
from PySide2.QtWidgets import QApplication
from PySide2.QtCore import QPointF

app = QApplication([])

import main as m
import widgets.FlowPages as FlowPages

fails = []
warnings = []


def check(name, cond, extra=""):
    print(("PASS  " if cond else "FAIL  ") + name + (("   <- " + str(extra)) if extra else ""))
    if not cond:
        fails.append(name)


class FakeMB(object):
    @staticmethod
    def warning(parent, title, text):
        warnings.append(text)

    @staticmethod
    def information(parent, title, text):
        pass

    @staticmethod
    def question(*a, **k):
        return 0


m.QMessageBox = FakeMB
FlowPages.QMessageBox = FakeMB

lena = cv2.imread(os.path.join("image", "lena.png"))
other = np.zeros((240, 320, 3), dtype=np.uint8)
other[:, :] = (0, 0, 255)
path = os.path.join("image", "lena.png")

w = m.MainWindow()
if getattr(w, 'gallery_widget', None) is not None:
    w.gallery_widget.set_scope_all(False)   # 本套假设'只跑当前这一张'
check("构造成功，且当前没有打开任何图片 / 视频 / 摄像头",
      w.current_static_image is None and w.cap is None)

tabs = w.flow_page_mgr.tab_widget

# ===================== 1、图库为空 + 流程里有图片源 → 单步执行能跑 =====================
tabs.setTabText(0, "图片源页")
n_src = w.add_flow_node("图片源", QPointF(20, 20))
n_gray = w.add_flow_node("灰度", QPointF(20, 200))
n_bin = w.add_flow_node("二值化", QPointF(20, 380))
n_src.params.update({"source_type": "单张图片", "source_path": path})
n_gray.params["gray_full_image"] = True
w.add_edge(n_src, n_gray)
w.add_edge(n_gray, n_bin)

w.selected_node = n_gray
warnings[:] = []
w.btn_step.click()
check("图库为空也能点'单步执行'：没有弹任何提示", warnings == [], warnings)
rows = {}
for r in range(w.execution_log.rowCount()):
    item = w.execution_log.item(r, 2)
    if item is not None:
        rows[item.text()] = w.execution_log.item(r, 3).text()
check("单步执行真的跑了（日志里有 灰度 这一行）", rows.get("灰度") is not None, rows)
check("单步执行只跑选中的那个节点，输入按它声明的图像源取（不再是图库那张）",
      rows.get("灰度") == "节点：图片源（单步：只跑本节点）", rows)
check("单步执行只记一行日志（上游不跟着跑）",
      len(rows) == 1, rows)
check("图库为空时用图片源兜底，不会把这张图记成'当前图'（避免换了文件还用旧图）",
      w.current_static_image is None,
      None if w.current_static_image is None else w.current_static_image.shape)

# ===================== 2、连续执行（按钮）=====================
# 注意（2026.10.7 起）：连续执行 = "执行到**当前选中节点**为止"，
# 想让它把 图片源→灰度→二值化 整条跑完，就必须选中**最后一个**节点（二值化）。
w.selected_node = n_bin
warnings[:] = []
w.btn_continuous.click()
check("图库为空也能点'连续执行'：没有弹提示", warnings == [], warnings)
rows = {}
for r in range(w.execution_log.rowCount()):
    item = w.execution_log.item(r, 2)
    if item is not None:
        rows[item.text()] = w.execution_log.item(r, 3).text()
check("连续执行跑完 3 个节点，图像源列都对",
      rows.get("图片源") == "全局图像源" and rows.get("灰度") == "节点：图片源"
      and rows.get("二值化") == "节点：灰度", rows)
check("结果缓存里留下了这次执行（显示层用它渲染）",
      len(w.result_cache) > 0, list(w.result_cache)[:3])

# 顺手把主窗口截图，人工确认画布上显示的是处理后的图
shot = os.path.join(OUT, "source_run_no_gallery.png")
w.main_window.grab().save(shot)
print("saved:", shot)

# ===================== 3、参数窗口里的按钮也能跑 =====================
# 注意：引擎只跑"有连线"的节点，所以这里给 取反 接一个下游，让它成为一条能跑的链
dlg_node = w.add_flow_node("取反", QPointF(300, 20))
dlg_tail = w.add_flow_node("边缘提取", QPointF(300, 200))
w.add_edge(dlg_node, dlg_tail)
dlg = m.GenericProcessDialog(w.main_window, node=dlg_node, main_window=w)
# 注意（2026.10.7 深夜·目标5-M1）：参数窗口的"连续执行"走的是主窗口那条入口，
# 执行范围 = **当前选中节点 + 它的上游**（决策 e）。真实使用里是双击节点打开的窗口，
# 那时它已经是选中项；这里是自己 new 出来的窗口，所以要显式选中它，场景才和真实一致。
w.selected_node = dlg_node
warnings[:] = []
dlg.on_cont_click()
check("参数窗口的'连续执行'也能跑（没有弹提示）", warnings == [], warnings)
check("参数窗口执行后日志里出现了 取反 这一行",
      any(w.execution_log.item(r, 2) is not None and w.execution_log.item(r, 2).text() == "取反"
          for r in range(w.execution_log.rowCount())))
warnings[:] = []
dlg.on_step_click()
check("参数窗口的'执行'（单步）也能跑（没有弹提示）", warnings == [], warnings)

# ===================== 4、没有图片源、也没有图 → 仍然拦住（老行为）=====================
w.flow_page_mgr.add_page()
tabs.setTabText(tabs.count() - 2, "空页")
n_plain = w.add_flow_node("取反", QPointF(20, 20))
w.current_static_image = None          # 模拟"图库为空"
w.selected_node = n_plain
warnings[:] = []
before_rows = w.execution_log.rowCount()
w.btn_step.click()
check("没有图片源也没打开图：仍然弹提示（不静默、不崩）",
      len(warnings) == 1 and "图片源" in warnings[0], warnings)
check("提示里说清了两种办法（导入图片 / 放图片源节点）",
      "导入图片" in warnings[0] and "图片源" in warnings[0], warnings)

warnings[:] = []
w.btn_continuous.click()
check("连续执行同样被拦住并提示", len(warnings) == 1, warnings)

# ===================== 5、图片源来源选"当前图像"、又没有图 → 也拦住 =====================
w.flow_page_mgr.tab_widget.setCurrentIndex(0)
n_src.params["source_type"] = "当前图像"
w.current_static_image = None
warnings[:] = []
w.btn_continuous.click()
check("来源='当前图像'但没打开图：拦住并提示", len(warnings) == 1, warnings)

# ===================== 6、有当前图时老行为不变 =====================
n_src.params["source_type"] = "单张图片"
w._show_static_image(other)            # 模拟"打开了另一张图"
# 这条断言要看的是"图片源那条支路（图片源→灰度→二值化）"，所以选中那条链的**末节点**：
# 决策 e 之后执行范围 = 选中节点 + 它的上游，选中别处就看不到 灰度 这一行了。
w.selected_node = n_bin
warnings[:] = []
w.btn_continuous.click()
check("打开图片后点连续执行：不弹提示、照常跑", warnings == [], warnings)
rows = {}
for r in range(w.execution_log.rowCount()):
    item = w.execution_log.item(r, 2)
    if item is not None:
        rows[item.text()] = w.execution_log.item(r, 3).text()
check("有当前图时：连图片源那条支路仍然吃图片源的文件（并存）",
      rows.get("灰度") == "节点：图片源", rows)

print()
print("失败项：", fails if fails else "无")
sys.exit(1 if fails else 0)
