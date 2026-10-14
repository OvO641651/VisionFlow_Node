# -*- coding: utf-8 -*-
"""
批次4 目标3-M5「输出图像」验证（三）：保存内容 = 数据层图像 / 带检测叠加（2026.10.7）

用户报的问题："图片保存时直线检测和圆检测的内容不能保存"。
根因：检测类算子按引擎铁律**不改图像**（只多产出一份结果数据），
所以"直线 / 圆"这种流程存"数据层图像"= 原始画面，看不到任何检测内容。

覆盖：
  ① 直线流程 + 带检测叠加 ⇒ 存出来的图里**有绿线**（0,255,0 像素 > 0）
  ② 圆流程 + 带检测叠加 ⇒ 存出来的图里**有红圆**（0,0,255 像素 > 0）
  ③ 同一流程改成"数据层图像" ⇒ 绿线 / 红圆像素为 0，且与数据层逐像素一致
  ④ 纯处理链（取反）+ 默认"带检测叠加" ⇒ 与数据层图像**逐像素一致**（默认不改变原有表现）
  ⑤ 叠加图**不含 ROI 辅助框**（黄色 0,255,255 / 洋红 255,0,255 像素为 0）
  ⑥ 单步执行选中输出节点 ⇒ 不叠检测（等于数据层起点原图）
  ⑦ 参数窗口里「保存内容」默认选中"带检测叠加"，两档都在
"""
import os
import shutil
import sys
import tempfile

PROJ = r"E:\opencv_python_3_8\PySide\VisionFlowNoed"
os.chdir(PROJ)
sys.path.insert(0, PROJ)

import numpy as np
import cv2
from PySide2.QtWidgets import QApplication
from PySide2.QtCore import QPointF

app = QApplication([])
import main as m
import widgets.FlowPages as FlowPages
import ops.sink.OutputOps as ops
from core.Detector import make_test_image


class FakeMB(object):
    warning = information = staticmethod(lambda *a, **k: None)
    question = staticmethod(lambda *a, **k: 0)


m.QMessageBox = FakeMB
FlowPages.QMessageBox = FakeMB
m.QFileDialog = type("F", (), {"getOpenFileNames": staticmethod(lambda *a, **k: ([], "")),
                               "getOpenFileName": staticmethod(lambda *a, **k: ("", "")),
                               "getSaveFileName": staticmethod(lambda *a, **k: ("", "")),
                               "getExistingDirectory": staticmethod(lambda *a, **k: "")})

fails = []


def check(name, cond, extra=""):
    print(("PASS  " if cond else "FAIL  ") + name + (("   <- " + str(extra)) if extra else ""))
    if not cond:
        fails.append(name)


TMP = tempfile.mkdtemp(prefix="vf_m5ov_")


def fresh_dir(name):
    d = os.path.join(TMP, name)
    if os.path.isdir(d):
        shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d, exist_ok=True)
    return d


def count_pixels(img, color, tol=10):
    """数一数图里有多少像素接近某个纯色（叠加上画的线是纯色，抗锯齿会有微小偏差）"""
    if img is None:
        return -1
    diff = np.abs(img.astype(int) - np.array(color, int))
    return int(np.all(diff <= tol, axis=2).sum())


def load_one(folder):
    files = sorted(os.listdir(folder))
    return (files[0], cv2.imread(os.path.join(folder, files[0]))) if files else (None, None)


def build_chain(names, out_dir, save_content=None, detect_params=None):
    """搭一条 起点(当前图) → ...names... 的链，最后一个必须是"输出图像"；返回 (window, 输出节点)"""
    win = m.MainWindow()
    win.main_window.show()
    nodes = [win.add_flow_node(n, QPointF(20, 20 + i * 140)) for i, n in enumerate(names)]
    for a, b in zip(nodes, nodes[1:]):
        win.add_edge(a, b)
    if detect_params:
        # 检测类节点的算法参数（例如圆的 param2：默认 80 在测试图上检不出那个圆，要调到 30）
        nodes[0].params.update(detect_params)
    sink = nodes[-1]
    sink.params["output_dir"] = out_dir
    sink.params["output_name"] = "shot"
    if save_content is not None:
        sink.params["save_content"] = save_content
    win.selected_node = sink            # 连续执行只跑到选中节点为止 ⇒ 选它才会执行到它
    win._show_static_image(make_test_image())
    win.btn_continuous.click()
    return win, sink


IMG = make_test_image()
GREEN = (0, 255, 0)        # 直线结果的颜色（_draw_line）
RED = (0, 0, 255)          # 圆结果的颜色（_draw_circle）
YELLOW = (0, 255, 255)     # 手画 ROI 框
MAGENTA = (255, 0, 255)    # 继承来的 ROI 框

# ----------------------------------------------------------------------
# ① 直线 + 叠加
# ----------------------------------------------------------------------
d1 = fresh_dir("line")
_, sink1 = build_chain(["直线识别", "输出图像"], d1)
name1, img1 = load_one(d1)
check("① 直线流程：文件写出来了", img1 is not None, os.listdir(d1))
green1 = count_pixels(img1, GREEN)
check("① 直线流程 + 带检测叠加 ⇒ 存出来的图里**有绿线**（用户报的问题已修）", green1 > 0,
      "绿线像素 = {0}".format(green1))

# ----------------------------------------------------------------------
# ② 圆 + 叠加
# ----------------------------------------------------------------------
d2 = fresh_dir("circle")
# 测试图上那个圆的半径 80：检测默认 param2=80 检不出来（0 个），调到 30 能检出 1 个
_, sink2 = build_chain(["圆识别", "输出图像"], d2, detect_params={"param2": 30.0})
name2, img2 = load_one(d2)
red2 = count_pixels(img2, RED)
check("② 圆流程 + 带检测叠加 ⇒ 存出来的图里**有红圆**", red2 > 0, "红色像素 = {0}".format(red2))

# ----------------------------------------------------------------------
# ③ 同一流程改成"数据层图像"
# ----------------------------------------------------------------------
d3 = fresh_dir("line_layer")
_, sink3 = build_chain(["直线识别", "输出图像"], d3, save_content=ops.SAVE_LAYER)
name3, img3 = load_one(d3)
check("③ 选「数据层图像」⇒ 没有绿线（检测类不改图 ⇒ 存的是原画面）",
      count_pixels(img3, GREEN) == 0, "绿线像素 = {0}".format(count_pixels(img3, GREEN)))
check("③ 「数据层图像」存出来的就是原图（与输入逐像素一致）",
      img3 is not None and float(np.mean(np.abs(img3.astype(int) - IMG.astype(int)))) == 0.0,
      None if img3 is None else float(np.mean(img3)))

# ----------------------------------------------------------------------
# ④ 纯处理链 + 默认叠加 ⇒ 与数据层一模一样
# ----------------------------------------------------------------------
d4 = fresh_dir("invert_overlay")
_, sink4 = build_chain(["取反", "输出图像"], d4)          # 不传 save_content ⇒ 用默认（叠加）
name4, img4 = load_one(d4)
expected4 = cv2.bitwise_not(IMG)
check("④ 纯处理链（取反）+ 默认叠加 ⇒ 与数据层图像**逐像素一致**（默认不改变原有表现）",
      img4 is not None and
      float(np.mean(np.abs(img4.astype(int) - expected4.astype(int)))) == 0.0,
      None if img4 is None else (float(np.mean(img4)), float(np.mean(expected4))))

d4b = fresh_dir("invert_layer")
build_chain(["取反", "输出图像"], d4b, save_content=ops.SAVE_LAYER)
_, img4b = load_one(d4b)
check("④ 同一流程选「数据层图像」⇒ 两张文件字节级一致（证明默认值确实等价）",
      img4 is not None and img4b is not None and
      float(np.mean(np.abs(img4.astype(int) - img4b.astype(int)))) == 0.0, None)

# ----------------------------------------------------------------------
# ⑤ 叠加图里没有 ROI 辅助框
# ----------------------------------------------------------------------
check("⑤ 叠加图**不含**手画 ROI 黄框（辅助线不进文件）", count_pixels(img1, YELLOW) == 0,
      "黄色像素 = {0}".format(count_pixels(img1, YELLOW)))
check("⑤ 叠加图**不含**继承 ROI 洋红框", count_pixels(img1, MAGENTA) == 0,
      "洋红像素 = {0}".format(count_pixels(img1, MAGENTA)))

# ----------------------------------------------------------------------
# ⑥ 单步执行选中输出节点 ⇒ 不叠检测
# ----------------------------------------------------------------------
d6 = fresh_dir("step")
w6 = m.MainWindow()
w6.main_window.show()
n_line = w6.add_flow_node("直线识别", QPointF(20, 20))
n_out6 = w6.add_flow_node("输出图像", QPointF(20, 180))
w6.add_edge(n_line, n_out6)
n_out6.params["output_dir"] = d6
n_out6.params["output_name"] = "single"
w6.selected_node = n_out6
w6._show_static_image(IMG)
w6.btn_step.click()
_, img6 = load_one(d6)
check("⑥ 单步执行选中输出节点 ⇒ 无检测叠加（等于数据层起点原图，与连续执行口径一致）",
      img6 is not None and count_pixels(img6, GREEN) == 0 and
      float(np.mean(np.abs(img6.astype(int) - IMG.astype(int)))) == 0.0,
      None if img6 is None else count_pixels(img6, GREEN))

# ----------------------------------------------------------------------
# ⑦ 参数窗口里的「保存内容」
# ----------------------------------------------------------------------
from ui.GenericProcessDialog import GenericProcessDialog

w7 = m.MainWindow()
w7.main_window.show()
n7 = w7.add_flow_node("输出图像", QPointF(20, 20))
dlg = GenericProcessDialog(w7.main_window, node=n7, main_window=w7)
combo = dlg.param_controls.get("save_content")
check("⑦ 参数窗口里有「保存内容」下拉框", combo is not None)
options = [combo.itemText(i) for i in range(combo.count())] if combo is not None else []
check("⑦ 两档都在：数据层图像 / 带检测叠加",
      options == [ops.SAVE_LAYER, ops.SAVE_OVERLAY], options)
check("⑦ 默认选中「带检测叠加」（否则检测内容默认还是存不下来）",
      combo is not None and combo.currentText() == ops.SAVE_OVERLAY,
      None if combo is None else combo.currentText())
dlg.close()
dlg.deleteLater()

shutil.rmtree(TMP, ignore_errors=True)
print()
print("失败项：", fails if fails else "无")
sys.exit(1 if fails else 0)
