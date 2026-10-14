# -*- coding: utf-8 -*-
"""本轮 4 项修改的验证（走按钮 / 窗口槽函数的真实路径）

1、单步执行 ≠ 连续执行（单步只跑选中的那个节点，输入取它声明的图像源那张图）
2、图库为空、只有"图片源"时，"框选"按钮也能用（用图片源那张图，不弹提示）
3、图库与图片源统一：图片源的图会进图库；点图库会把图片源路径同步过去；支持导入文件夹
4、图片源窗口：来源合并成 图片 / 测试图；去掉执行 / 连续执行；只留确定
"""
import os
import sys
import tempfile
import shutil

PROJ = r"E:\opencv_python_3_8\PySide\VisionFlowNoed"
os.chdir(PROJ)
sys.path.insert(0, PROJ)

import numpy as np
import cv2
from PySide2 import QtWidgets
from PySide2.QtWidgets import QApplication, QDialog, QComboBox
from PySide2.QtCore import QPointF

app = QApplication([])

import main as m
import widgets.FlowPages as FlowPages
import ui.LineParamsDialog as LPD

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
LPD.QMessageBox = FakeMB

# ROISelectDialog 是模态的 exec_()，测试里换成替身：只记录"传进来的图"和"形状"
roi_calls = []


class FakeRoiDialog(object):
    def __init__(self, img, parent=None, shape="矩形"):
        roi_calls.append((img.shape, shape))
        self.img = img

    def exec_(self):
        return QDialog.Rejected

    def get_roi(self):
        return (0, 0, 0, 0)


LPD.ROISelectDialog = FakeRoiDialog

P_HOUGH = os.path.join("image", "HoughLines.jpg")
P_LENA = os.path.join("image", "lena.png")
HOUGH = cv2.imread(P_HOUGH)
LENA = cv2.imread(P_LENA)

w = m.MainWindow()
if getattr(w, 'gallery_widget', None) is not None:
    w.gallery_widget.set_scope_all(False)   # 本套假设'只跑当前这一张'
tabs = w.flow_page_mgr.tab_widget
tabs.setTabText(0, "本轮验证")


def cached_frames():
    return [v["frame"] for v in w.result_cache.values()]


def log_rows():
    rows = []
    for r in range(w.execution_log.rowCount()):
        name = w.execution_log.item(r, 2)
        src = w.execution_log.item(r, 3)
        rows.append((name.text() if name else "", src.text() if src else ""))
    return rows


# 流程：图片源(HoughLines) → 取反 → 二值化
n_src = w.add_flow_node("图片源", QPointF(20, 20))
n_inv = w.add_flow_node("取反", QPointF(20, 160))
n_bin = w.add_flow_node("二值化", QPointF(20, 300))
n_src.params.update({"source_type": "图片", "source_path": P_HOUGH})
n_bin.params["threshold_value"] = 128
w.add_edge(n_src, n_inv)
w.add_edge(n_inv, n_bin)

# ===================== 1、单步执行 ≠ 连续执行 =====================
w.result_cache.clear()
w.selected_node = n_bin
warnings[:] = []
w.btn_step.click()
step_frames = cached_frames()
check("1 单步执行(选中二值化)：没有弹提示", warnings == [], warnings)
rows_step = log_rows()
check("1 单步执行只记录选中的那一个节点（只有一行）", len(rows_step) == 1, rows_step)
check("1 单步执行的日志写明：只跑本节点、输入来自图片源",
      rows_step and "单步：只跑本节点" in rows_step[0][1] and "图片源" in rows_step[0][1], rows_step)

# 变量链的关系：单步的二值化输入 = 图片源原图（不经过取反）
# 注意：缓存里存的是**显示图**（数据层输出 + 画上去的 ROI 框），所以这里也按渲染层算一遍来比
_out_e, _res_e, _roi_e, _spec_e = w._execute_node(n_bin, HOUGH.copy(), None)
expect_step = w._render_display(_out_e, [(n_bin, _res_e, _roi_e, _spec_e)])
check("1 单步执行的输入 = 图片源那张**原图**（未经取反），结果逐像素一致",
      step_frames and step_frames[0].shape == expect_step.shape
      and np.array_equal(step_frames[0], expect_step), None if not step_frames else step_frames[0].shape)

w.result_cache.clear()
w.selected_node = n_bin
warnings[:] = []
w.btn_continuous.click()
cont_frames = cached_frames()
check("1 连续执行(选中二值化)：没有弹提示", warnings == [], warnings)
rows_cont = log_rows()
check("1 连续执行跑了整条链（3 行日志）", len(rows_cont) == 3, rows_cont)
check("1 **单步执行的结果 ≠ 连续执行的结果**（用户报的致命问题）",
      step_frames and cont_frames and not np.array_equal(step_frames[0], cont_frames[0]),
      (step_frames[0].shape if step_frames else None, cont_frames[0].shape if cont_frames else None))

# ===================== 2、框选：图库为空也能用图片源的图 =====================
w.result_cache.clear()
roi_calls[:] = []
warnings[:] = []
w.current_static_image = None            # 图库为空 / 没打开图片
w.current_image_key = None
n_bin.input_source = n_src
dlg_bin = m.GenericProcessDialog(w.main_window, node=n_bin, main_window=w)
dlg_bin.on_select_click()
check("2 图库为空点'框选'：不弹'请先导入图片'提示", warnings == [], warnings)
check("2 框选窗口拿到的是图片源那张图（897×708）",
      roi_calls and roi_calls[0][0] == HOUGH.shape, roi_calls)

# ===================== 3、图库与图片源统一 =====================
gw = w.gallery_widget
check("3 前面执行过之后，图库里已经有图片源那一张（不重复加）",
      gw.gallery_list.count() == 1 and gw.has_path(P_HOUGH), gw.gallery_list.count())

w.result_cache.clear()
w.selected_node = n_bin
w.btn_continuous.click()                 # 跑一次 → 图片源那张图应该进图库
check("3 执行后，图片源指定的图自动进了图库列表",
      gw.gallery_list.count() == 1 and gw.has_path(P_HOUGH), gw.gallery_list.count())

# 再往图库放一张别的图（模拟"打开文件"导入的第二张），点它 → 图片源的路径应该跟着变
gw.add_image(LENA, P_LENA)
item2 = gw.gallery_list.item(gw.gallery_list.count() - 1)
gw._on_item_clicked(item2)
check("3 点图库里第二张图后，图片源节点的路径同步成了它",
      n_src.params.get("source_path") == P_LENA and n_src.params.get("source_type") == "图片",
      (n_src.params.get("source_type"), n_src.params.get("source_path")))
check("3 同步后这一页被标成'有改动'（不会被当成没改过）",
      w.flow_page_mgr.current_page.get("dirty") is True, w.flow_page_mgr.current_page.get("dirty"))
check("3 图库点选后主体显示的也是那张图（当前图 = lena）",
      w.current_static_image is LENA, None if w.current_static_image is None else w.current_static_image.shape)

# 打开文件：应该把路径一起带进图库（不重复加）
tmpdir = tempfile.mkdtemp(prefix="vf_import_")
p_a = os.path.join(tmpdir, "a.png")
p_b = os.path.join(tmpdir, "b.png")
cv2.imwrite(p_a, HOUGH)
cv2.imwrite(p_b, LENA)


class FakeFileDialog(object):
    @staticmethod
    def getOpenFileNames(*a, **k):
        return [p_a, p_b], ""

    @staticmethod
    def getExistingDirectory(*a, **k):
        return tmpdir


m.QFileDialog = FakeFileDialog
before = gw.gallery_list.count()
warnings[:] = []
w.open_file()
check("3 打开文件（多选）把新图片都加进图库，并且带上了路径",
      gw.gallery_list.count() == before + 2 and gw.has_path(p_a) and gw.has_path(p_b),
      gw.gallery_list.count())

# 重复导入同一批：不重复加缩略图、也不弹提示
warnings[:] = []
infos[:] = []
w.open_file()
check("3 打开文件重复导入同一批图片：不重复加缩略图、也不弹提示",
      warnings == [] and infos == [] and gw.gallery_list.count() == before + 2,
      (warnings, infos, gw.gallery_list.count()))

# ===================== 4、图片源窗口 =====================
n_src.params["source_path"] = P_HOUGH
dlg_src = m.GenericProcessDialog(w.main_window, node=n_src, main_window=w)
titles = [dlg_src.ui.tabWidget.tabText(i) for i in range(dlg_src.ui.tabWidget.count())]
check("4 图片源窗口：只剩'运行参数'一页", titles == ["运行参数"], titles)
combo = dlg_src.param_controls["source_type"]
check("4 来源下拉 = 图片 / 文件夹 / 测试图（本轮把'文件夹'单独拆出来）",
      [combo.itemText(i) for i in range(combo.count())] == ["图片", "文件夹", "测试图"],
      [combo.itemText(i) for i in range(combo.count())])
btn_run = dlg_src.ui.findChild(QtWidgets.QPushButton, "btn_run")
btn_cont = dlg_src.ui.findChild(QtWidgets.QPushButton, "btn_cont")
check("4 执行 / 连续执行 两个按钮已隐藏",
      btn_run is not None and not btn_run.isVisibleTo(dlg_src.ui)
      and btn_cont is not None and not btn_cont.isVisibleTo(dlg_src.ui))
btn_ok = dlg_src.ui.findChild(QtWidgets.QPushButton, "btn_ok")
check("4 确定按钮还在", btn_ok is not None and btn_ok.isVisibleTo(dlg_src.ui))

before_rows = w.execution_log.rowCount()
dlg_src.on_ok()
check("4 点确定 = 只保存参数并关窗（不会执行流程）",
      dlg_src.result() == QDialog.Accepted and w.execution_log.rowCount() == before_rows,
      (dlg_src.result(), before_rows, w.execution_log.rowCount()))

# 来源三分支
spec_src = m.get_spec("图片源")
out_file, res_file = spec_src.run(w.detector, None, (0, 0, 0, 0),
                                  {"source_type": "图片", "source_path": P_HOUGH})
check("4 来源'图片'+路径：读那个文件", np.array_equal(out_file, HOUGH), spec_src.format_result(res_file))
out_cur, res_cur = spec_src.run(w.detector, LENA, (0, 0, 0, 0), {"source_type": "图片", "source_path": ""})
check("4 来源'图片'但没填路径：跟'当前图像'一样（原样透传，同一对象）", out_cur is LENA,
      spec_src.format_result(res_cur))
out_old, _r = spec_src.run(w.detector, None, (0, 0, 0, 0),
                           {"source_type": "单张图片", "source_path": P_HOUGH})
check("4 兼容旧方案文件里的来源值'单张图片'", np.array_equal(out_old, HOUGH))
out_test, _r2 = spec_src.run(w.detector, None, (0, 0, 0, 0), {"source_type": "测试图"})
check("4 来源'测试图'仍可用", out_test is not None and out_test.ndim == 3)

shutil.rmtree(tmpdir, ignore_errors=True)
print()
print("失败项：", fails if fails else "无")
sys.exit(1 if fails else 0)
