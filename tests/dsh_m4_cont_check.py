# -*- coding: utf-8 -*-
"""
M4 修复回归（2026.10.7，用户实测报的 bug）：
"使用相机源节点后，在画布上没有图片时，点连续执行会弹'请先导入图片/视频…'、打不开摄像头；
 点单步执行却能截一幅图到画布上、不弹窗。"

根因：连续执行走 `_ensure_camera_open_for_run()`，它的判据是"这一轮**真用到**相机源"
（= 相机源要有一条下游连线）⇒ 画布上只有一个"相机源"、又没连线时判成"没用到" ⇒ 设备压根没开
⇒ `_source_node_frame()` 问它要图只能拿到 None ⇒ 弹提示。而单步执行选中相机源时，
`_camera_used_by(cam, "step")` 的 `node is camera` 分支直接成立 ⇒ 正常打开。
修法：把"轮到相机源取图时顺手开设备"放进 `_source_node_frame(allow_camera_open=True)`
（只有执行路径传 True），判据从"有没有连线"变成"是不是轮到它取图"。
"""
import os
import sys

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

warnings = []


class FakeMB(object):
    warning = staticmethod(lambda *a, **k: warnings.append(a[2] if len(a) > 2 else ""))
    information = staticmethod(lambda *a, **k: None)
    question = staticmethod(lambda *a, **k: 0)


m.QMessageBox = FakeMB
FlowPages.QMessageBox = FakeMB

fails = []


def check(name, cond, extra=""):
    print(("PASS  " if cond else "FAIL  ") + name + (("   <- " + str(extra)) if extra else ""))
    if not cond:
        fails.append(name)


class FakeCapture(object):
    value = [200]
    opened = []

    def __init__(self, index=0):
        self.index = int(index)
        self._open = True
        FakeCapture.opened.append(self.index)

    def isOpened(self):
        return self._open

    def read(self):
        return True, np.full((48, 64, 3), FakeCapture.value[0], np.uint8)

    def get(self, p):
        return 30.0

    def release(self):
        self._open = False


cv2.VideoCapture = FakeCapture
m.QFileDialog = type("F", (), {"getOpenFileNames": staticmethod(lambda *a, **k: ([], "")),
                               "getOpenFileName": staticmethod(lambda *a, **k: ("", "")),
                               "getExistingDirectory": staticmethod(lambda *a, **k: "")})

shown = []
base_imgs = []


def new_window(with_edge=False):
    """每个场景都新建一个窗口（干净状态），返回 (w, 相机源节点)"""
    FakeCapture.opened[:] = []
    del warnings[:]
    del shown[:]
    del base_imgs[:]
    win = m.MainWindow()
    win.main_window.show()
    orig_display = win._display_image

    def spy_display(img, image_key=None):
        shown.append((img.copy(), image_key))
        return orig_display(img, image_key)

    win._display_image = spy_display
    orig_render = win._render_display

    def spy_render(base_img, executed):
        base_imgs.append(None if base_img is None else base_img.copy())
        return orig_render(base_img, executed)

    win._render_display = spy_render
    cam = win.add_flow_node("相机源", QPointF(20, 20))
    if with_edge:
        inv = win.add_flow_node("取反", QPointF(20, 170))
        win.add_edge(cam, inv)
        win.selected_node = inv
    else:
        win.selected_node = cam
    return win, cam


# ----------------------------------------------------------------------
# ① 用户报的那一条：画布上只有"相机源"、没有连线、画布上没图片 ⇒ 连续执行
# ----------------------------------------------------------------------
w, cam = new_window(with_edge=False)
check("① 前置：相机是关的、画布上没有图片",
      w.cap is None and w.current_static_image is None, (w.cap, w.current_static_image))
w.btn_continuous.click()
check("① 【连续执行】画布上只有相机源（没连线）时**自动打开相机**（用户报的 bug 回归）",
      w.cap is not None and w.cap.isOpened(), w.cap)
check("① 不弹「请先导入图片/视频…」窗口", len(warnings) == 0, warnings)
check("① 画布上确实出了画面", len(shown) == 1, len(shown))
check("① 日志如实提示「没有可执行的流程」（孤立节点不执行，但相机已经打开、画面有了）",
      any("没有可执行的流程" in (w.execution_log.item(r, 4).text()
                                if w.execution_log.item(r, 4) else "")
          for r in range(w.execution_log.rowCount())),
      [w.execution_log.item(r, 4).text() for r in range(w.execution_log.rowCount())
       if w.execution_log.item(r, 4)])

# ----------------------------------------------------------------------
# ② 同一场景点"单步执行"：两条入口表现要一致
# ----------------------------------------------------------------------
w2, cam2 = new_window(with_edge=False)
w2.btn_step.click()
check("② 【单步执行】同一场景也正常（两条入口表现一致）",
      w2.cap is not None and w2.cap.isOpened() and len(warnings) == 0 and len(shown) == 1,
      (w2.cap is not None, len(warnings), len(shown)))

# ----------------------------------------------------------------------
# ③ 有连线时照旧：相机帧真的进流程
# ----------------------------------------------------------------------
w3, cam3 = new_window(with_edge=True)
FakeCapture.value[0] = 200
w3.btn_continuous.click()
check("③ 有连线时照旧打开相机、不弹窗", w3.cap is not None and len(warnings) == 0,
      (w3.cap is not None, warnings))
check("③ 相机帧真的进了流程（数据层取反后 = 255-200 = 55）",
      base_imgs and abs(float(np.mean(base_imgs[-1])) - 55) < 1e-6,
      float(np.mean(base_imgs[-1])) if base_imgs else None)
check("③ 同一台相机不会重复开设备", FakeCapture.opened == [0], list(FakeCapture.opened))

# ----------------------------------------------------------------------
# ④ 守卫：参数窗口 / 取上游尺寸时**绝不能**顺手把相机打开
# ----------------------------------------------------------------------
w4, cam4 = new_window(with_edge=False)
check("④ 前置：相机还没开", w4.cap is None)
probe = w4._node_input_frame(cam4)
check("④ _node_input_frame()（对话框取默认 ROI 尺寸）不会开相机",
      w4.cap is None and FakeCapture.opened == [], (w4.cap, list(FakeCapture.opened)))
check("④ 相机没开时它如实返回 None（不崩）", probe is None, probe)
check("④ _source_node_frame() 默认也不开相机（只有执行路径才传 allow_camera_open=True）",
      w4._source_node_frame() is None and w4.cap is None, w4.cap)

# ----------------------------------------------------------------------
# ⑤ 守卫：画布上有图片时，"孤立"的相机源不该被顺手打开
# ----------------------------------------------------------------------
w5, cam5 = new_window(with_edge=False)
w5.current_static_image = np.full((48, 64, 3), 30, np.uint8)
w5.btn_continuous.click()
check("⑤ 画布上已经有图片、相机源又没连线 ⇒ **不**打开相机（不白占设备）",
      w5.cap is None and FakeCapture.opened == [] and len(warnings) == 0,
      (w5.cap, list(FakeCapture.opened), warnings))

# ----------------------------------------------------------------------
# ⑥ "执行时自动打开相机"没勾 ⇒ 孤立相机源也不开设备、只如实提示
# ----------------------------------------------------------------------
w6, cam6 = new_window(with_edge=False)
cam6.params["open_on_run"] = False
w6.btn_continuous.click()
check("⑥ 没勾「执行时自动打开相机」⇒ 不开设备",
      w6.cap is None and FakeCapture.opened == [], (w6.cap, list(FakeCapture.opened)))
check("⑥ 这种情况才允许弹提示（如实告诉用户没图可用）", len(warnings) == 1, warnings)

print()
print("失败项：", fails if fails else "无")
sys.exit(1 if fails else 0)
