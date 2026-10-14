# -*- coding: utf-8 -*-
"""修：播放中点删除 -> 先停播、不弹窗（原来每格都弹一次"请先导入图片/视频"）"""
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

warns = []


class FakeMB(object):
    warning = staticmethod(lambda parent, title, text: warns.append(text))
    information = staticmethod(lambda *a, **k: None)
    question = staticmethod(lambda *a, **k: 0)


m.QMessageBox = FakeMB
FlowPages.QMessageBox = FakeMB

fails = []


def check(name, cond, extra=""):
    print(("PASS  " if cond else "FAIL  ") + name + (("   <- " + str(extra)) if extra else ""))
    if not cond:
        fails.append(name)


tmp = tempfile.mkdtemp(prefix="vf_delp_")
video = os.path.join(tmp, "t.avi")
writer = cv2.VideoWriter(video, cv2.VideoWriter_fourcc(*'MJPG'), 25.0, (64, 48))
for i in range(20):
    writer.write(np.full((48, 64, 3), i * 12, np.uint8))
writer.release()


class FakeFD(object):
    getOpenFileNames = staticmethod(lambda *a, **k: ([], ""))
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

# 开自动播放
gw.auto_switch_box.setChecked(True)
w.selected_node = n_inv
w.btn_step.click()
check("准备：视频正在自动播放", w._video_playing is True, w._video_playing)

# 播放中点"删除"
warns[:] = []
gw.delete_button.click()
check("点删除：播放立即停止", w._video_playing is False, w._video_playing)
check("点删除：画布被清空", getattr(w.image_view, "pixmap_item", None) is None)
check("点删除：视频源路径被清空", (n_video.params.get("video_path") or "") == "",
      n_video.params.get("video_path"))
check("点删除：**没有弹出任何提示窗**", warns == [], warns)

# 就算还有 tick 在跑（模拟定时器残余），也不该再弹窗
warns[:] = []
w._video_tick(n_inv, "step")
check("残余 tick 也不会弹窗（不会再出现导入提示）", warns == [], warns)

# 列表为空时反复点删除也不弹窗
for _ in range(3):
    gw.delete_button.click()
check("反复点删除仍然不弹窗", warns == [], warns)

shutil.rmtree(tmp, ignore_errors=True)
print()
print("失败项：", fails if fails else "无")
sys.exit(1 if fails else 0)
