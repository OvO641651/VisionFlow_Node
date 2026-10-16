# -*- coding: utf-8 -*-
"""
dsh_t5g5_m2_check.py —— 批次5 目标5-M2 的判据（**含并入的 M3**）

四条（用户 2026.10.16 拍板"全部取推荐"）：
  M2-a 删除语义：**播放 / 相机开着时，点「删除」只停播 + 关相机，不删图库条目**（再点一次才删）。
  M2-b 取图来源：**这一轮真用到视频 / 相机源 ⇒ 不展开成批量**（批量只对纯静态图流程生效），
        修"画布同时播图库图片和视频"与"图库有图时点连续执行不开摄像头"（单步本来就不展开 ⇒ 两条入口一致）。
  M2-c 相机收尾：随 M2-b（不再"顺手开、顺手关"）。
  M2-d 日志表格：`ScrollPerItem` → `ScrollPerPixel`（= 原 M3 并入本 M）。

运行：`python tests\dsh_t5g5_m2_check.py`（无头；退出码 0 = 全过）
"""
import os
import sys
import tempfile                                                 # ⑭⑮ 要造一个真 .avi

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

import numpy as np
import cv2                                                      # ⑭⑮ 要造一个真 .avi

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(PROJ)
sys.path.insert(0, PROJ)

from PySide2.QtWidgets import QApplication, QAbstractItemView   # noqa: E402
from PySide2.QtCore import QPointF                              # noqa: E402

app = QApplication([])

import main as m                                                # noqa: E402

_ok = [0]
_bad = [0]


def check(title, ok, extra=None):
    if ok:
        _ok[0] += 1
        print("PASS  {0}{1}".format(title, "" if extra is None else "   <- {0}".format(extra)))
    else:
        _bad[0] += 1
        print("FAIL  {0}{1}".format(title, "" if extra is None else "   <- {0}".format(extra)))


def img(shape, value=0):
    return np.full(shape, value, np.uint8)


class FakeMB(object):                       # 挡掉"没有可用的图"之类的提示框
    Yes = 0x4000
    No = 0x10000
    Ok = 0x400
    question = staticmethod(lambda *a, **k: 0x4000)
    information = staticmethod(lambda *a, **k: 0x400)
    warning = staticmethod(lambda *a, **k: 0x400)
    critical = staticmethod(lambda *a, **k: 0x400)


class FakeCap(object):                      # 假相机：只满足"开着 / 能关"
    def __init__(self):
        self.released = False

    def isOpened(self):
        return True

    def release(self):
        self.released = True

    def read(self):
        return False, None


_real_mb = m.QMessageBox
m.QMessageBox = FakeMB

LENA = os.path.abspath(os.path.join("image", "lena.png"))
HOUGH = os.path.abspath(os.path.join("image", "HoughLines.jpg"))

print("=" * 70)
print("批次5 目标5-M2：删除 / 执行优先级 + 相机收尾 + 日志按像素滚动（含并入的 M3）")
print("=" * 70)

# ======================================================================
# ① M2-d：日志表格按像素滚动
# ======================================================================
w = m.MainWindow()
w.main_window.show()
check("① 日志表格**按像素滚动**（修前 = `ScrollPerItem`，一滚一行；M2-d）",
      w.execution_log.verticalScrollMode() == QAbstractItemView.ScrollPerPixel
      and w.execution_log.horizontalScrollMode() == QAbstractItemView.ScrollPerPixel,
      (w.execution_log.verticalScrollMode(), w.execution_log.horizontalScrollMode()))

# ======================================================================
# ② ~ ⑤ M2-a：删除语义（播放 / 相机开着 ⇒ 只停播关相机，不删条目）
# ======================================================================
gw = w.gallery_widget
w.import_image_path(LENA)
w.import_image_path(HOUGH)
n_before = gw.count()
check("② 前置：图库里有两张图", n_before == 2, n_before)

w._video_playing = True                      # 模拟"正在播视频"
w.delete_gallery_item(gw.gallery_list.item(0))
check("③ [回归钉] **播放中点「删除」：只停播、不删条目**（修前会顺手把这张删掉 —— ⑥(1)）",
      gw.count() == n_before and w._is_playing() is False,
      (n_before, gw.count(), w._is_playing()))
w.delete_gallery_item(gw.gallery_list.item(0))
check("④ 停播之后再点一次「删除」：这一张才真被删掉", gw.count() == n_before - 1, gw.count())

cap = FakeCap()
w.cap = cap
w.add_flow_node("相机源", QPointF(20, 20))
n2 = gw.count()
w.delete_gallery_item(gw.gallery_list.item(0))
check("⑤ [回归钉] **相机开着点「删除」：只关相机、不删条目**（修前「图片和相机同时删」 —— ⑦(3)）",
      cap.released is True and gw.count() == n2, (cap.released, n2, gw.count()))
w.delete_gallery_item(gw.gallery_list.item(0))
check("⑥ 相机已关后再点「删除」：条目被删（老行为不变）", gw.count() == n2 - 1, gw.count())

# ======================================================================
# ⑦ ~ ⑫ M2-b / M2-c：取图来源（活源 ⇒ 不展开成批量）
# ======================================================================
w2 = m.MainWindow()
w2.main_window.show()
gw2 = w2.gallery_widget
for i in range(3):
    gw2.add_image(img((80, 120, 3), i * 20), "m2_{0}.png".format(i))
gw2.set_scope_all(True)                       # 运行模式 = 运行全部
n_inv = w2.add_flow_node("取反", QPointF(20, 20))
n_bin = w2.add_flow_node("二值化", QPointF(20, 200))
w2.add_edge(n_inv, n_bin)

calls = []
flow_calls = []
real_run_all = w2.run_all_images
real_flow = w2.run_flow_continuous
# 两条路都打桩：只判"走了哪条路"，不让真的执行（避免用例自己造出假的图/视频数据）
w2.run_all_images = lambda *a, **k: (calls.append(a), 1)[1]
w2.run_flow_continuous = lambda *a, **k: (flow_calls.append(1), True)[1]

check("⑦ 活源判定：都不播、也没有视频/相机源 ⇒ 假（纯静态图流程）",
      w2._uses_live_source() is False, w2._uses_live_source())
w2.on_continuous_execute()
check("⑧ 纯静态图流程 + 图库有图 + 运行全部 ⇒ **仍然展开成批量**（老行为保护）",
      len(calls) == 1 and flow_calls == [], (len(calls), flow_calls))

calls[:] = []
flow_calls[:] = []
w2._video_playing = True                      # = "播放视频时点连续执行"
w2.on_continuous_execute()
check("⑨ [回归钉] **视频在播**时点连续执行 ⇒ **不展开成批量、走活源那条路**（修前：批量刷画布 + 视频抢画布）",
      calls == [] and flow_calls == [1], (calls, flow_calls))
w2._video_playing = False

vnode = w2.add_flow_node("视频源", QPointF(20, 380))
vnode.params["video_path"] = LENA              # 只求"配了视频"（不真播）
check("⑩ 活源判定：流程里有**配了视频的视频源** ⇒ 真", w2._uses_live_source() is True)
calls[:] = []
flow_calls[:] = []
w2.on_continuous_execute()
check("⑪ [回归钉] 视频源流程点连续执行 ⇒ **不展开成批量**（修前：图库有图就去处理图库、而不是走视频）",
      calls == [] and flow_calls == [1], (calls, flow_calls))

cam2 = w2.add_flow_node("相机源", QPointF(20, 560))
w2.add_edge(cam2, n_inv)                      # 相机源有下游 ⇒ 这一轮真会用到它
check("⑫ 活源判定：流程里有**相机源且真会用到**（有下游）⇒ 真（⑦(1) 的判据）",
      w2._uses_live_source() is True, w2._uses_live_source())
calls[:] = []
flow_calls[:] = []
w2.on_continuous_execute()
check("⑬ [回归钉] 相机源流程点连续执行 ⇒ **不展开成批量、走活源那条路**（修 ⑦(1)「图库有图时不开摄像头」；M2-c 同此判据）",
      calls == [] and flow_calls == [1], (calls, flow_calls))

# ======================================================================
# ⑭ ~ ⑮ 用户 2026.10.16 复测报的第 ② 条：活源（视频）轮的结果**不能记在"启动那张静态图"的缓存键下**
#         （修前：切走再切回那张图，画布显示的是**视频帧的结果** ⇒ 看着像"列表里的图被换成了视频帧"）
# ======================================================================
w3 = m.MainWindow()
w3.main_window.show()
gw3 = w3.gallery_widget
for i in range(3):
    gw3.add_image(img((48, 64, 3), 200 - i * 20), "mx{0}.png".format(i))
vid = os.path.join(tempfile.mkdtemp(), "m2.avi")
vw = cv2.VideoWriter(vid, cv2.VideoWriter_fourcc(*"MJPG"), 10, (64, 48))
for i in range(5):
    vw.write(img((48, 64, 3), 40 + i * 30))
vw.release()

gw3.set_current_index(1)
n_inv2 = w3.add_flow_node("取反", QPointF(20, 20))
vs3 = w3.add_flow_node("视频源", QPointF(20, 200))
w3.add_edge(vs3, n_inv2)
vs3.params["video_path"] = vid
w3.selected_node = n_inv2
w3._show_static_image(gw3.item_frame(gw3.gallery_list.item(1)))
w3.run_flow_continuous()                       # = 点"连续执行"（活源轮）

keys = [k[0] if isinstance(k, tuple) else k for k in w3.result_cache.keys()]
check("⑭ [回归钉] 活源（视频）轮：结果记在**视频帧键**下（带 `#`）、**不记在**启动那张静态图的键下",
      any("#" in str(k) for k in keys) and all("mx1.png" not in str(k) for k in keys), keys)
check("⑭-补 活源轮后标签写着**视频帧计数**（`视频帧 (n/总数)`，用户 2026.10.16 要求恢复）",
      "视频帧 (" in gw3.count_label.text() and "/" in gw3.count_label.text(), gw3.count_label.text())

before = float(np.mean(gw3.item_frame(gw3.gallery_list.item(1))))
gw3.set_current_index(0)
w3._show_static_image(gw3.item_frame(gw3.gallery_list.item(0)))      # 切走
gw3.set_current_index(1)
w3._show_static_image(gw3.item_frame(gw3.gallery_list.item(1)))      # 再切回来
check("⑮ [回归钉] 切走再切回那张静态图 ⇒ 画布是**它自己的原图**（修前是视频帧的结果）",
      w3.current_static_image is not None
      and abs(float(np.mean(w3.current_static_image)) - before) < 1,
      (None if w3.current_static_image is None else float(np.mean(w3.current_static_image)), before))

# ======================================================================
# ⑯ ~ ⑰ §8.2.7（甲修法）：**流程里有视频源节点 ⇒ 连续执行不展开成批量**
#         修前：删除视频后 `video_path` 变空 ⇒ "活源"判据变假 ⇒ 去跑图库里的图片当检测对象
# ======================================================================
w4 = m.MainWindow()
w4.main_window.show()
gw4 = w4.gallery_widget
for i in range(3):
    gw4.add_image(img((48, 64, 3), 120 - i * 10), "kz{0}.png".format(i))
gw4.set_scope_all(True)
vs4 = w4.add_flow_node("视频源", QPointF(20, 20))
w4.add_flow_node("取反", QPointF(20, 200))
calls4 = []
w4.run_all_images = lambda *a, **k: (calls4.append(a), 1)[1]

check("⑯ 活源判定：视频源节点在（哪怕还没配视频）⇒ 算活源流程",
      w4._uses_live_source() is True, w4._uses_live_source())

vs4.params["video_path"] = ""                 # = 用户点了「删除」之后的状态
warns4 = []


def _warn4(*a, **k):
    warns4.append(a[2] if len(a) > 2 else "")
    return 0x400


m.QMessageBox.warning = staticmethod(_warn4)
rows_before4 = w4.execution_log.rowCount()
w4.on_continuous_execute()
check("⑰ [回归钉] 删掉视频后再点连续执行 ⇒ **不跑图库的图**，而是如实提示（修前：图库图被当检测对象执行）",
      calls4 == [] and w4.execution_log.rowCount() == rows_before4 and bool(warns4),
      (calls4, w4.execution_log.rowCount(), rows_before4, warns4[:1]))

# ======================================================================
# ⑱ ~ ⑲ 2026.10.16 用户实测：不勾「自动切换」连点单步执行 ⇒ 帧号**一直涨过总帧数**、画面停在第一帧
#         （单步那条 `_advance_video_cursor()` 原来只 +1、没有处理末尾）
# ======================================================================
w5 = m.MainWindow()
w5.main_window.show()
vid5 = os.path.join(tempfile.mkdtemp(), "m2b.avi")
vw5 = cv2.VideoWriter(vid5, cv2.VideoWriter_fourcc(*"MJPG"), 10, (64, 48))
for i in range(4):
    vw5.write(img((48, 64, 3), 30 + i * 40))
vw5.release()
vs5 = w5.add_flow_node("视频源", QPointF(20, 20))
n_inv5 = w5.add_flow_node("取反", QPointF(20, 200))
w5.add_edge(vs5, n_inv5)
vs5.params["video_path"] = vid5
vs5.params["frame_index"] = 0
vs5.params["loop"] = True                # 勾了「循环」⇒ 到头应回卷到 0
w5.selected_node = n_inv5
for _ in range(8):                       # 远超总帧数（4 帧）
    w5.run_flow_step(n_inv5)
idx_loop = int(vs5.params.get("frame_index") or 0)
check("⑱ [回归钉] 单步连点超过总帧数 ⇒ **回卷**（勾了「循环」⇒帧号落在 0..总帧数-1，不再涨到 49/36）",
      vs5.params.get("loop") is True and 0 <= idx_loop < 4, (vs5.params.get("loop"), idx_loop))

vs5.params["loop"] = False
vs5.params["frame_index"] = 0
w5.selected_node = n_inv5
for _ in range(8):
    w5.run_flow_step(n_inv5)
idx_noloop = int(vs5.params.get("frame_index") or 0)
check("⑲ [回归钉] 不勾「循环」：到头就**停在最后一帧**（不再继续涨过总帧数）",
      idx_noloop == 3, idx_noloop)

# ======================================================================
# ⑳ ~ ㉑ 2026.10.16 用户实测 + 桌面探针定案：**活源（视频 / 相机）轮不"补图库"**
#         修前那一栈：相机流程执行 ⇒ `_ensure_source_images_in_gallery()` 把当前页「图片源」节点
#         指定的那张图塞进**空图库**（用户看到"首次执行突然多出一张图"，误以为是相机第一帧）
# ======================================================================
w6 = m.MainWindow()
w6.main_window.show()
gw6 = w6.gallery_widget
src6 = w6.add_flow_node("图片源", QPointF(20, 20))
src6.params["source_path"] = LENA
src6.params["source_type"] = "图片"
vid6 = os.path.join(tempfile.mkdtemp(), "m2c.avi")
vw6 = cv2.VideoWriter(vid6, cv2.VideoWriter_fourcc(*"MJPG"), 10, (64, 48))
for i in range(4):
    vw6.write(img((48, 64, 3), 60 + i * 30))
vw6.release()
vs6 = w6.add_flow_node("视频源", QPointF(20, 200))
w6.add_edge(vs6, src6)
vs6.params["video_path"] = vid6
check("⑳ 前置：图库是空的", gw6.count() == 0, gw6.count())
w6.run_flow_continuous()                     # 活源轮（流程里有视频源 = 活源流程）
check("⑳ [回归钉] **活源轮不往图库里补图**（修前：当前页「图片源」那张图被塞进空图库 ⇒ 图库 1 张）",
      gw6.count() == 0, (gw6.count(), [gw6.item_path(gw6.gallery_list.item(i)) for i in range(gw6.count())]))

w7 = m.MainWindow()                          # 对照：纯静态流程 ⇒ 2026.10.5 的"图库里看得见"仍然成立
w7.main_window.show()
gw7 = w7.gallery_widget
src7 = w7.add_flow_node("图片源", QPointF(20, 20))
src7.params["source_path"] = LENA
src7.params["source_type"] = "图片"
w7._show_static_image(np.full((48, 64, 3), 90, np.uint8))
w7.run_flow_continuous()
check("㉑ **静态流程保留** 2026.10.5 的行为：图片源指定的图**仍然进图库**（1 张）",
      gw7.count() == 1 and gw7.has_path(LENA), (gw7.count(), gw7.has_path(LENA)))

w2.run_all_images = real_run_all
w2.run_flow_continuous = real_flow
m.QMessageBox = _real_mb

print("-" * 70)
print("通过 {0} 项，失败 {1} 项".format(_ok[0], _bad[0]))
if _bad[0]:
    print("失败项：{0} 项".format(_bad[0]))
    sys.exit(1)
print("失败项：无")
sys.exit(0)
