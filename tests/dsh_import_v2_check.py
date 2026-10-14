# -*- coding: utf-8 -*-
"""本轮要求验证（图片与文件夹彻底分开、对话框回到原生）：
1、"打开文件"只负责选图片（不再管文件夹）；
2、图片源节点的"图像来源"多一条"文件夹"；
   来源=图片 → "浏览…"弹系统原生的"选择图片"；来源=文件夹 → 弹"选择文件夹"，
   且文件夹里所有图片都会静默进图库；
3、来源=文件夹时，节点取文件夹里按文件名排序的第一张；
4、导入全程不弹任何提示。
"""
import os
import sys
import inspect
import tempfile
import shutil

PROJ = r"E:\opencv_python_3_8\PySide\VisionFlowNoed"
os.chdir(PROJ)
sys.path.insert(0, PROJ)

import numpy as np
import cv2
from PySide2 import QtWidgets
from PySide2.QtWidgets import QApplication, QDialog, QPushButton, QLineEdit
from PySide2.QtCore import QPointF

app = QApplication([])

import main as m
import widgets.FlowPages as FlowPages
import ui.GenericProcessDialog as GPD

fails = []
warnings = []
infos = []


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
        infos.append(text)

    @staticmethod
    def question(*a, **k):
        return 0


m.QMessageBox = FakeMB
FlowPages.QMessageBox = FakeMB

P_HOUGH = os.path.join("image", "HoughLines.jpg")
P_LENA = os.path.join("image", "lena.png")
HOUGH = cv2.imread(P_HOUGH)
LENA = cv2.imread(P_LENA)

# 文件夹：两张好图（文件名排序后 a_ 在前）+ 一个坏 png
tmp = tempfile.mkdtemp(prefix="vf_v2_")
f_a = os.path.join(tmp, "a_hough.png")     # 用 png：无损，便于逐像素比对
f_b = os.path.join(tmp, "b_lena.png")
f_bad = os.path.join(tmp, "c_bad.png")
cv2.imwrite(f_a, HOUGH)
cv2.imwrite(f_b, LENA)
with open(f_bad, "wb") as fp:
    fp.write(b"not an image")

# 记录原生对话框被怎么调用
calls = []


class FakeFD(object):
    @staticmethod
    def getOpenFileNames(*a, **k):
        calls.append("getOpenFileNames")
        return [P_LENA], ""

    @staticmethod
    def getOpenFileName(parent=None, title="", dir="", filters=""):
        calls.append(("getOpenFileName", title))
        return P_HOUGH, ""

    @staticmethod
    def getExistingDirectory(parent=None, title="", dir=""):
        calls.append(("getExistingDirectory", title))
        return tmp


m.QFileDialog = FakeFD
GPD.QFileDialog = FakeFD     # 参数窗口模块自己 import 了 QFileDialog，也要换替身

w = m.MainWindow()
w.main_window.show()
w.flow_page_mgr.tab_widget.setTabText(0, "图片与文件夹分开")
gw = w.gallery_widget

# ============ 1、"打开文件"只选图片 ============
warnings[:] = []
infos[:] = []
calls[:] = []
w.open_file()
check("1 '打开文件'用的是原生多选文件对话框（getOpenFileNames）",
      calls and calls[0] == "getOpenFileNames", calls)
check("1 选中的图片进了图库", gw.has_path(P_LENA) and gw.gallery_list.count() == 1,
      gw.gallery_list.count())
check("1 没有任何提示窗口", warnings == [] and infos == [], (warnings, infos))

# 就算 str 里混进一个文件夹路径，也会被当成"不是图片文件"忽略掉
gw.gallery_list.clear()
m.QFileDialog = type("FD2", (), {
    # 注意：真正的 getOpenFileNames 返回 (路径列表, 选中的过滤器)，替身必须同形状
    "getOpenFileNames": staticmethod(lambda *a, **k: ([tmp, P_HOUGH], "")),
    "getOpenFileName": staticmethod(lambda *a, **k: ("", "")),
    "getExistingDirectory": staticmethod(lambda *a, **k: ""),
})
warnings[:] = []
w.open_file()
check("1 '打开文件'不会把文件夹里的图片导进来（文件夹路径被当成非图片忽略）",
      not gw.has_path(f_a), (gw.gallery_list.count(), gw.has_path(f_a)))
check("1 同一批里的图片照常导入（文件夹被忽略、图片不受影响）",
      gw.has_path(P_HOUGH), (gw.gallery_list.count(), gw.has_path(P_HOUGH)))
m.QFileDialog = FakeFD

# ============ 2、来源多了"文件夹"这一档 ============
n_src = w.add_flow_node("图片源", QPointF(20, 20))
n_gray = w.add_flow_node("灰度", QPointF(20, 200))
w.add_edge(n_src, n_gray)
n_src.params.update({"source_type": "图片", "source_path": P_HOUGH})

dlg = m.GenericProcessDialog(w.main_window, node=n_src, main_window=w)
combo = dlg.param_controls["source_type"]
check("2 来源下拉 = 图片 / 文件夹 / 测试图",
      [combo.itemText(i) for i in range(combo.count())] == ["图片", "文件夹", "测试图"],
      [combo.itemText(i) for i in range(combo.count())])
check("2 路径那一行的标签改成了通用的'路径'",
      any(lbl == "路径" for _k, lbl, _t, _o in m.get_spec("图片源").param_specs),
      [p[1] for p in m.get_spec("图片源").param_specs])

# ============ 3、来源=图片 → 原生"选择图片"；选了就静默进图库 ============
gw.gallery_list.clear()
widget = dlg.param_controls["source_path"]
edit = widget.findChild(QLineEdit)
browse = widget.findChild(QPushButton)
calls[:] = []
warnings[:] = []
combo.setCurrentText("图片")
browse.click()
check("3 来源=图片：弹的是原生'选择图片'对话框",
      calls and calls[0][0] == "getOpenFileName" and "选择图片" in calls[0][1], calls)
check("3 选完路径 = 那张图片", os.path.normcase(os.path.abspath(edit.text()))
      == os.path.normcase(os.path.abspath(P_HOUGH)), edit.text())
check("3 那张图片被静默放进图库", gw.has_path(P_HOUGH) and gw.gallery_list.count() == 1,
      gw.gallery_list.count())
check("3 全程无提示", warnings == [] and infos == [], (warnings, infos))

# ============ 4、来源=文件夹 → 原生"选择文件夹"；文件夹里图片静默进图库 ============
gw.gallery_list.clear()
calls[:] = []
warnings[:] = []
combo.setCurrentText("文件夹")
browse.click()
check("4 来源=文件夹：弹的是原生'选择文件夹'对话框",
      calls and calls[0][0] == "getExistingDirectory" and "选择文件夹" in calls[0][1], calls)
check("4 选完路径 = 这个文件夹（不是里面的某张图）",
      os.path.normcase(os.path.abspath(edit.text())) == os.path.normcase(os.path.abspath(tmp)),
      edit.text())
check("4 文件夹里的 2 张图片都静默进了图库（坏文件跳过）",
      gw.gallery_list.count() == 2 and gw.has_path(f_a) and gw.has_path(f_b),
      gw.gallery_list.count())
check("4 全程无提示", warnings == [] and infos == [], (warnings, infos))

# 点"确定" → 入库（不执行）且仍然静默
before_rows = w.execution_log.rowCount()
warnings[:] = []
dlg.on_ok()
check("4 点确定后仍然是静默的、且不执行流程",
      warnings == [] and infos == [] and w.execution_log.rowCount() == before_rows,
      (warnings, infos))

# ============ 5、来源=文件夹时，节点取"文件夹里排序第一张" ============
spec = m.get_spec("图片源")
out, res = spec.run(w.detector, None, (0, 0, 0, 0), {"source_type": "文件夹", "source_path": tmp})
check("5 文件夹来源：输出 = 排序第一张（a_hough.jpg）",
      out is not None and np.array_equal(out, HOUGH), spec.format_result(res))
check("5 日志文案写清了是第 1 张", "第 1 张" in spec.format_result(res), spec.format_result(res))
out2, res2 = spec.run(w.detector, LENA, (0, 0, 0, 0),
                      {"source_type": "文件夹", "source_path": P_HOUGH})
check("5 来源=文件夹但路径其实是图片：直接用这张（容错）", np.array_equal(out2, HOUGH),
      spec.format_result(res2))
out3, res3 = spec.run(w.detector, LENA, (0, 0, 0, 0), {"source_type": "文件夹", "source_path": ""})
check("5 来源=文件夹但没填路径：原样透传 + 日志说明原因",
      out3 is LENA and "文件夹里没有图片" in spec.format_result(res3), spec.format_result(res3))
empty_dir = tempfile.mkdtemp(prefix="vf_empty_")
out4, res4 = spec.run(w.detector, LENA, (0, 0, 0, 0),
                      {"source_type": "文件夹", "source_path": empty_dir})
check("5 空文件夹：原样透传 + 日志说明原因",
      out4 is LENA and "文件夹里没有图片" in spec.format_result(res4), spec.format_result(res4))

# 执行一次，确认"文件夹来源"能把整个文件夹的图带进图库
gw.gallery_list.clear()
n_src.params.update({"source_type": "文件夹", "source_path": tmp})
w.selected_node = n_gray
w.btn_step.click()
check("5 执行后：文件夹里的图片都进了图库", gw.gallery_list.count() == 2, gw.gallery_list.count())

# ============ 6、静态检查：不再有"非原生二合一对话框" ============
check("6 pick_images_or_folder 已经删除", not hasattr(w, "pick_images_or_folder"))
check("6 '打开文件'源码里用的是 getOpenFileNames",
      "getOpenFileNames" in inspect.getsource(w.open_file))
src_browse = inspect.getsource(m.GenericProcessDialog._browse_file)
check("6 '浏览…'源码里同时有 getOpenFileName 与 getExistingDirectory（按来源分开弹）",
      "getOpenFileName" in src_browse and "getExistingDirectory" in src_browse)
check("6 代码里不再用非原生对话框（没有 DontUseNativeDialog）",
      "DontUseNativeDialog" not in inspect.getsource(m.MainWindow)
      and "DontUseNativeDialog" not in inspect.getsource(m.GenericProcessDialog))

shutil.rmtree(tmp, ignore_errors=True)
shutil.rmtree(empty_dir, ignore_errors=True)
print()
print("失败项：", fails if fails else "无")
sys.exit(1 if fails else 0)
