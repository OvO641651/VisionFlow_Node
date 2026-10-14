# -*- coding: utf-8 -*-
"""M3 第三版：视频帧的"画面键"整段共用（修：播放时画面一大一小 + 滚轮缩放被覆盖）"""
import os
import sys
import tempfile
import shutil

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


class FakeMB(object):
    warning = information = staticmethod(lambda *a, **k: None)
    question = staticmethod(lambda *a, **k: 0)


m.QMessageBox = FakeMB
FlowPages.QMessageBox = FakeMB

fails = []


def check(name, cond, extra=""):
    print(("PASS  " if cond else "FAIL  ") + name + (("   <- " + str(extra)) if extra else ""))
    if not cond:
        fails.append(name)


tmp = tempfile.mkdtemp(prefix="vf_m3c_")
video = os.path.join(tmp, "t.avi")
img = os.path.join(tmp, "a.png")
cv2.imwrite(img, np.full((48, 64, 3), 90, np.uint8))
writer = cv2.VideoWriter(video, cv2.VideoWriter_fourcc(*'MJPG'), 25.0, (64, 48))
for i in range(6):
    writer.write(np.full((48, 64, 3), i * 40, np.uint8))
writer.release()


class FakeFD(object):
    getOpenFileNames = staticmethod(lambda *a, **k: ([img], ""))
    getOpenFileName = staticmethod(lambda *a, **k: (video, ""))
    getExistingDirectory = staticmethod(lambda *a, **k: tmp)


m.QFileDialog = FakeFD
w = m.MainWindow()
w.main_window.show()
gw = w.gallery_widget
n_video = w.add_flow_node("视频源", QPointF(20, 20))
n_video.params["video_path"] = video
n_inv = w.add_flow_node("取反", QPointF(20, 160))
w.add_edge(n_video, n_inv)
w.selected_node = n_video
gw.auto_switch_box.setChecked(False)
w.btn_step.click()          # 第 0 帧

view = w.image_view
keys = []


def display_keys():
    return [k for k in view._zoom_states if isinstance(k, str) and k.startswith("video:")]



# 记住当前缩放，再走几帧，看缩放会不会被复位
before_t = view.transform().m11()
view.scale(1.5, 1.5)
zoom_t = view.transform().m11()
for _ in range(3):
    w.btn_step.click()      # 逐帧前进
after_t = view.transform().m11()
check("播放/逐帧时画面缩放不再被复位（滚轮缩放保留）", abs(after_t - zoom_t) < 1e-6,
      (before_t, zoom_t, after_t))
check("三帧之后画面键仍是视频那一个（没有每帧换成新键）",
      view._current_key == "video:" + video, view._current_key)

# 图片（来自文件）仍然各用各的键，缩放互不影响
gw.add_button.click()
frame_img = gw.item_frame(gw.gallery_list.item(0))
check("来自文件的图仍然用自己的路径当画面键", w._display_key_of(frame_img) == img,
      w._display_key_of(frame_img))

shutil.rmtree(tmp, ignore_errors=True)
print()
print("失败项：", fails if fails else "无")
sys.exit(1 if fails else 0)
