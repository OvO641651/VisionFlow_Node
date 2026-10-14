# -*- coding: utf-8 -*-
"""M3 视频源节点（第一版）：注册 / 单步取帧与前进一帧 / auto_next / loop / 容错 / 不进图库"""
import os
import sys
import tempfile
import shutil

PROJ = r"E:\opencv_python_3_8\PySide\VisionFlowNoed"
os.chdir(PROJ)
sys.path.insert(0, PROJ)

import numpy as np
import cv2
from PySide2.QtWidgets import QApplication, QTreeWidget
from PySide2.QtCore import QPointF

app = QApplication([])
import main as m
import widgets.FlowPages as FlowPages
import core.NodeRegistry as NodeRegistry

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


tmp = tempfile.mkdtemp(prefix="vf_m3_")
video = os.path.join(tmp, "t.avi")
# 造一段 8 帧测试视频：每帧一个固定灰度（0/32/…/224），便于逐帧核对
writer = cv2.VideoWriter(video, cv2.VideoWriter_fourcc(*'MJPG'), 25.0, (64, 48))
for i in range(8):
    writer.write(np.full((48, 64, 3), i * 32, np.uint8))
writer.release()
check("测试视频造好了（8 帧）", os.path.exists(video) and os.path.getsize(video) > 0)


class FakeFD(object):
    getOpenFileNames = staticmethod(lambda *a, **k: ([], ""))
    getOpenFileName = staticmethod(lambda *a, **k: (video, ""))
    getExistingDirectory = staticmethod(lambda *a, **k: tmp)


m.QFileDialog = FakeFD
w = m.MainWindow()
w.main_window.show()
gw = w.gallery_widget

# ---------- 一、注册与树 ----------
spec = NodeRegistry.get_spec("视频源")
check("注册表里有'视频源'，且是起点类（KIND_SOURCE）", spec is not None and spec.kind == m.KIND_SOURCE,
      None if spec is None else spec.kind)
keys = [p[0] for p in spec.param_specs] if spec is not None else []
check("参数 = 视频路径 / 当前帧号 / 执行后前进一帧 / 到末尾回到开头",
      keys == ["video_path", "frame_index", "auto_next", "loop"], keys)
tree = w.main_window.findChild(QTreeWidget, "tree")
collect = tree.topLevelItem(0)
names = [collect.child(i).text(0) for i in range(collect.childCount())]
_known_collect = ["图片源", "视频源", "相机源", "输出图像"]
check("树里'采集'下按顺序含 图片源 / 视频源 / 相机源 / 输出图像（允许以后再往后加）",
      [x for x in names if x in _known_collect] == _known_collect, names)

# ---------- 二、单步执行：取当前帧 + 前进一帧 ----------
n_video = w.add_flow_node("视频源", QPointF(20, 20))
n_video.params["video_path"] = video
n_video.params["frame_index"] = 0
n_inv = w.add_flow_node("取反", QPointF(20, 160))
w.add_edge(n_video, n_inv)
w.selected_node = n_video


def shown_mean():
    # 视频帧来自起点节点，不会被记成主窗口的"当前图片"，看最近一次执行的缓存更准
    if not w.result_cache:
        return None
    return float(np.mean(w.result_cache[list(w.result_cache)[-1]]["frame"]))


w.btn_step.click()                       # 单步执行：选中的是视频源
check("单步①：取到第 0 帧（均值 0）", shown_mean() is not None and abs(shown_mean() - 0) < 2, shown_mean())
check("单步①：帧号前进到 1（auto_next 默认开）", n_video.params["frame_index"] == 1,
      n_video.params["frame_index"])
w.btn_step.click()
check("单步②：取到第 1 帧（均值 32）", abs(shown_mean() - 32) < 2, shown_mean())
check("单步②：帧号前进到 2", n_video.params["frame_index"] == 2, n_video.params["frame_index"])
check("视频源执行日志写的是'第 N 帧 / 共 M 帧'",
      any("帧 / 共" in (w.execution_log.item(r, 4).text() if w.execution_log.item(r, 4) else "")
          for r in range(w.execution_log.rowCount())))

# 不依赖视频源的节点：单步它不该吃掉一帧
before = n_video.params["frame_index"]
w.selected_node = n_inv
w.btn_step.click()                       # 取反的父节点是视频源 → 其实会用到它
check("单步下游节点（父链里有视频源）也会用掉一帧", n_video.params["frame_index"] == before + 1,
      n_video.params["frame_index"])
n_free = w.add_flow_node("滤波", QPointF(300, 20))     # 孤立节点：跟视频源无关
w.selected_node = n_free
before = n_video.params["frame_index"]
w.btn_step.click()
check("单步一个与视频源无关的节点：帧号不动", n_video.params["frame_index"] == before,
      n_video.params["frame_index"])

# ---------- 三、auto_next 关掉 → 停在原帧 ----------
n_video.params["auto_next"] = False
w.selected_node = n_video
fixed = n_video.params["frame_index"]
w.btn_step.click()
w.btn_step.click()
check("关掉'执行后前进一帧'后，反复执行都停在原帧", n_video.params["frame_index"] == fixed,
      n_video.params["frame_index"])
n_video.params["auto_next"] = True

# ---------- 四、越界 + loop ----------
n_video.params["frame_index"] = 999
w.selected_node = n_video
w.btn_step.click()
rows = [w.execution_log.item(r, 4).text() for r in range(w.execution_log.rowCount())
        if w.execution_log.item(r, 4)]
check("帧号越界且没开 loop：不崩、给出提示", bool(warns) and "视频源" in warns[-1], warns[-1:])
check("取不到帧的那一轮不算执行、帧号不动", n_video.params["frame_index"] == 999, n_video.params["frame_index"])
n_video.params["frame_index"] = 999
n_video.params["loop"] = True
w.btn_step.click()
check("开了 loop：越界后回到第 0 帧", abs(shown_mean() - 0) < 2, shown_mean())

# ---------- 五、坏文件 / 空路径：静默透传 ----------
warns[:] = []
n_video.params["video_path"] = os.path.join(tmp, "not_exist.mp4")
w.btn_step.click()
check("坏文件：不崩、给出提示", bool(warns) and "视频源" in warns[-1], warns[-1:])
n_video.params["video_path"] = ""
w.btn_step.click()
check("空路径：不崩、同样给出提示", bool(warns) and "视频源" in warns[-1], warns[-1:])
n_video.params["video_path"] = video

# ---------- 六、帧不进图库 ----------
check("执行视频源后，图库仍然是空的（帧不进图库）", gw.count() == 0, gw.count())

shutil.rmtree(tmp, ignore_errors=True)
print()
print("失败项：", fails if fails else "无")
sys.exit(1 if fails else 0)
