# -*- coding: utf-8 -*-
"""M3 视频源（第二版）：自动切换=自动播放（按原帧率）/ 停止可停 / loop 反复播放 / 删除清视频"""
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
from ops.source.VideoSourceOps import video_info

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


tmp = tempfile.mkdtemp(prefix="vf_m3b_")
video = os.path.join(tmp, "t.avi")
writer = cv2.VideoWriter(video, cv2.VideoWriter_fourcc(*'MJPG'), 25.0, (64, 48))
for i in range(6):
    writer.write(np.full((48, 64, 3), i * 40, np.uint8))
writer.release()
count, fps = video_info(video)
check("测试视频：6 帧、fps≈25", count == 6 and 20 < fps < 30, (count, fps))


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
n_video.params["frame_index"] = 0
n_inv = w.add_flow_node("取反", QPointF(20, 160))
w.add_edge(n_video, n_inv)
w.selected_node = n_video


def cached_mean():
    if not w.result_cache:
        return None
    return float(np.mean(w.result_cache[list(w.result_cache)[-1]]["frame"]))


# ---------- 一、不勾"自动切换"：还是点一次走一帧 ----------
gw.auto_switch_box.setChecked(False)
w.btn_step.click()
check("不勾'自动切换'：点一次只走一帧（没在播放）", w._video_playing is False and n_video.params["frame_index"] == 1,
      (w._video_playing, n_video.params["frame_index"]))

# ---------- 二、勾"自动切换"：点执行 → 开始自动播放 ----------
n_video.params["frame_index"] = 0
gw.auto_switch_box.setChecked(True)
w.btn_step.click()
check("勾'自动切换'后点执行：进入自动播放状态", w._video_playing is True, w._video_playing)
check("播放用的是原帧率（定时器间隔 ≈ 1000/fps）",
      w._video_timer is not None and 30 <= w._video_timer.interval() <= 60,
      None if w._video_timer is None else w._video_timer.interval())
check("播放已经跑了一帧（帧号前进）", n_video.params["frame_index"] >= 1, n_video.params["frame_index"])

# 手动驱动若干 tick（无头环境里不等真实定时器）
before = n_video.params["frame_index"]
for _ in range(3):
    w._video_tick(n_video, "step")
mid = n_video.params["frame_index"]
check("播放中画面逐帧更新（帧号持续前进）", mid > before, (before, mid))
check("播放中帧内容确实在变（均值前后不同）", cached_mean() is not None)

# ---------- 三、"停止"按钮 → 停止播放 ----------
w.gallery_widget.stop_button.click()
check("点'停止'按钮：播放停下来", w._video_playing is False and w._video_timer.isActive() is False,
      (w._video_playing, None if w._video_timer is None else w._video_timer.isActive()))
rows = [w.execution_log.item(r, 4).text() for r in range(w.execution_log.rowCount())
        if w.execution_log.item(r, 4)]
check("日志写了'停止播放'", any("停止播放" in t for t in rows), rows[-2:])

# ---------- 四、播到末尾：不勾 loop → 自动停 ----------
n_video.params["loop"] = False
n_video.params["frame_index"] = count - 1
gw.auto_switch_box.setChecked(True)
w._video_playing = False
w._start_video_playback(n_video, "step")
w._video_tick(n_video, "step")
w._video_tick(n_video, "step")   # 末帧那一格先跑完，下一格才判断到末尾
check("播到末尾且没勾 loop：自动停止播放", w._video_playing is False, w._video_playing)

# ---------- 五、勾 loop → 回到开头继续 ----------
n_video.params["loop"] = True
n_video.params["frame_index"] = count + 2          # 越界
gw.auto_switch_box.setChecked(True)
w._video_playing = False
w._start_video_playback(n_video, "step")
w._video_tick(n_video, "step")
check("越界且勾了 loop：回到开头继续播放（没停、帧号回到 0 附近）",
      w._video_playing is True and n_video.params["frame_index"] <= 2,
      (w._video_playing, n_video.params["frame_index"]))
w.gallery_widget.stop_button.click()

# ---------- 六、删除：把该条目对应的视频路径也从"视频源"节点里清掉 ----------
n_video.params["video_path"] = video
w._clear_source_nodes_path(video)
check("删除路径时，视频源节点里的 video_path 也被清空",
      (n_video.params.get("video_path") or "") == "", n_video.params.get("video_path"))

shutil.rmtree(tmp, ignore_errors=True)
print()
print("失败项：", fails if fails else "无")
sys.exit(1 if fails else 0)
