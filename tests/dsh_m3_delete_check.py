# -*- coding: utf-8 -*-
"""删除清画布验收：列表为空时点删除应清空画布与视频源路径"""
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


tmp = tempfile.mkdtemp(prefix="vf_del_")
video = os.path.join(tmp, "t.avi")
writer = cv2.VideoWriter(video, cv2.VideoWriter_fourcc(*'MJPG'), 25.0, (64, 48))
for i in range(4):
    writer.write(np.full((48, 64, 3), i * 60, np.uint8))
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
w.selected_node = n_video
gw.auto_switch_box.setChecked(False)
w.btn_step.click()                       # 画布上出现一帧视频

check("准备：画布上有视频帧、图像列表为空", getattr(w.image_view, "pixmap_item", None) is not None and gw.count() == 0,
      (getattr(w.image_view, "pixmap_item", None) is not None, gw.count()))
gw.delete_button.click()                 # 点"删除"
check("点删除：画布被清空", getattr(w.image_view, "pixmap_item", None) is None)
check("点删除：current_static_image 也清了", w.current_static_image is None, w.current_static_image)
check("点删除：视频源节点里的路径被清空", (n_video.params.get("video_path") or "") == "",
      n_video.params.get("video_path"))
rows = [w.execution_log.item(r, 4).text() for r in range(w.execution_log.rowCount())
        if w.execution_log.item(r, 4)]
check("点删除：日志有说明", any("已清除画布内容" in t for t in rows), rows[-1:])

# 列表非空且没选中：仍然是"删不掉东西"，不应该误清画布
import numpy as np  # noqa: F811
pimg = os.path.join(tmp, "a.png")
cv2.imwrite(pimg, np.full((48, 64, 3), 120, np.uint8))
m.QFileDialog = type("FD2", (), {
    "getOpenFileNames": staticmethod(lambda *a, **k: ([pimg], "")),
    "getOpenFileName": staticmethod(lambda *a, **k: (pimg, "")),
    "getExistingDirectory": staticmethod(lambda *a, **k: tmp)})
gw.add_button.click()                    # 列表里有 1 张图（会自动选中）
w._show_static_image(gw.item_frame(gw.gallery_list.item(0)))
check("准备2：画布上有图片", getattr(w.image_view, "pixmap_item", None) is not None)
gw.delete_button.click()                 # 选中项存在 ⇒ 正常删除该条目
check("列表里有条目时：删除的是该条目（列表变空）", gw.count() == 0, gw.count())

shutil.rmtree(tmp, ignore_errors=True)
print()
print("失败项：", fails if fails else "无")
sys.exit(1 if fails else 0)
