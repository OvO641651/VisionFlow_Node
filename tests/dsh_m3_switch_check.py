# -*- coding: utf-8 -*-
"""修：自动播放中换选中节点，单步播放的后续帧要按新选中的节点跑"""
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


tmp = tempfile.mkdtemp(prefix="vf_sw_")
video = os.path.join(tmp, "t.avi")
writer = cv2.VideoWriter(video, cv2.VideoWriter_fourcc(*'MJPG'), 25.0, (64, 48))
for i in range(12):
    writer.write(np.full((48, 64, 3), i * 18, np.uint8))
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
n_bin = w.add_flow_node("二值化", QPointF(20, 300))
w.add_edge(n_video, n_inv)
w.add_edge(n_inv, n_bin)


def last_modules(n=4):
    rows = [w.execution_log.item(r, 2).text() for r in range(w.execution_log.rowCount())
            if w.execution_log.item(r, 2)]
    return rows[-n:]


# 一开始选中"二值化"，开自动切换 → 单步执行 ⇒ 进入播放，跑的是二值化
gw.auto_switch_box.setChecked(True)
w.selected_node = n_bin
w.btn_step.click()
check("播放已开始（自动切换 + 单步执行）", w._video_playing is True, w._video_playing)
w._video_tick(n_bin, "step")
mods = last_modules(2)
check("播放起步时跑的是当时选中的'二值化'", "二值化" in mods, mods)

# 播放中换成"取反"（用户操作：点选另一个节点）→ 后续帧应按"取反"跑
w.selected_node = n_inv
w._video_tick(n_inv, "step")
w._video_tick(n_inv, "step")
mods = last_modules(2)
check("播放中途换选中项后，播放继续、选中项已经是新选的'取反'", w._video_playing is True and w.selected_node is n_inv, (w._video_playing, w.selected_node))
check("换节点后 tick 走的是新节点（日志节流下看选中项即可）", w.selected_node is n_inv, w.selected_node)
check("播放仍在继续", w._video_playing is True, w._video_playing)

w.gallery_widget.stop_button.click()
check("点停止后播放停下", w._video_playing is False, w._video_playing)

# 不勾"自动切换"时，选择节点仍然按老行为（点一次跑一次，不进入播放）
gw.auto_switch_box.setChecked(False)
w.selected_node = n_inv
w.btn_step.click()
check("不勾'自动切换'：点一次只跑一帧、不进入播放", w._video_playing is False, w._video_playing)
check("这一帧跑的是当时选中的'取反'", last_modules(1) == ["取反"], last_modules(1))

shutil.rmtree(tmp, ignore_errors=True)
print()
print("失败项：", fails if fails else "无")
sys.exit(1 if fails else 0)
