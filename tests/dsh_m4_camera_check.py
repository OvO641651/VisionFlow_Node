# -*- coding: utf-8 -*-
"""
批次4 目标3-M4「相机源节点」验证（2026.10.7）——不需要真摄像头：
把 cv2.VideoCapture 换成假设备，按"用户会点的那个按钮"走真实路径。

覆盖：
  ① 注册（kind=source / 四项参数 / 预留类型置灰）
  ② 相机没开 + 勾着"执行时自动打开" ⇒ 点连续执行**自动打开相机**（用的正是节点里的编号）
  ③ 相机帧真的进了流程（数据层 取反 后 = 255 - 相机值，逐像素）
  ④ 相机帧**不进结果缓存**
  ⑤ 相机帧"画面键"整段共用（camera:编号），逐帧执行缩放不被复位
  ⑥ 相机开着时再点执行**仍然走引擎**（修：别被主窗口"老摄像头预览"分支接走）
  ⑦ 勾"自动切换"+执行 ⇒ 自动出画面；「停止」= **不关相机**、最后一帧留在画布上
  ⑧ 「删除」= **关相机** + 清画布，但**不动相机源节点里的参数**
  ⑨ 参数复用视频槽（VIDEO_ROI_KEY）
  ⑩ 分辨率"只存不生效"
  ⑪ open_on_run 不勾 ⇒ 不自动开设备；取不到帧就原样透传 + 日志写说明
  ⑫ 旧路径回归：主窗口"打开摄像头 / 关闭"按钮行为不变
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


# ----------------------------------------------------------------------
# 假相机设备：read() 返回一整张填充 value 的图（像素级可核对）
# ----------------------------------------------------------------------
CAM_W, CAM_H = 64, 48


class FakeCapture(object):
    value = [200]          # 当前"画面内容"（灰度值）
    reads = [0]
    opened = []            # 被打开过的编号
    releases = [0]

    def __init__(self, index=0):
        self.index = int(index)
        self._open = True
        FakeCapture.opened.append(self.index)

    def isOpened(self):
        return self._open

    def read(self):
        if not self._open:
            return False, None
        FakeCapture.reads[0] += 1
        return True, np.full((CAM_H, CAM_W, 3), FakeCapture.value[0], np.uint8)

    def get(self, prop):
        return 30.0

    def release(self):
        if self._open:
            FakeCapture.releases[0] += 1
        self._open = False


cv2.VideoCapture = FakeCapture


# ----------------------------------------------------------------------
# 搭窗口（真实路径：add_flow_node / add_edge / 点按钮）
# ----------------------------------------------------------------------
class FakeFD(object):
    getOpenFileNames = staticmethod(lambda *a, **k: ([], ""))
    getOpenFileName = staticmethod(lambda *a, **k: ("", ""))
    getExistingDirectory = staticmethod(lambda *a, **k: "")


m.QFileDialog = FakeFD
w = m.MainWindow()
w.main_window.show()
gw = w.gallery_widget
gw.auto_switch_box.setChecked(False)

# 截住两处真实产物：① 交给显示层的那张图 + 画面键；② 数据层底图（画叠加之前）
shown = []
_orig_display = w._display_image


def _spy(img, image_key=None):
    shown.append((img.copy(), image_key))
    return _orig_display(img, image_key)


w._display_image = _spy

base_imgs = []
_orig_render = w._render_display


def _render_spy(base_img, executed):
    base_imgs.append(None if base_img is None else base_img.copy())
    return _orig_render(base_img, executed)


w._render_display = _render_spy


def last_key():
    return shown[-1][1] if shown else None


def last_base_mean():
    return float(np.mean(base_imgs[-1])) if base_imgs and base_imgs[-1] is not None else None


# ----------------------------------------------------------------------
# ① 注册 + 预留类型置灰
# ----------------------------------------------------------------------
spec = m.get_spec("相机源")
check("① 相机源已注册", spec is not None)
check("① 相机源是「图像源类」（kind=source，起点节点只留“运行参数”页）",
      spec is not None and spec.kind == m.KIND_SOURCE, getattr(spec, "kind", None))
names = [p[0] for p in (spec.param_specs if spec else [])]
check("① 四项参数（相机类型/编号/分辨率/执行时自动打开）",
      names == ["camera_type", "camera_id", "resolution", "open_on_run"], names)

n_cam = w.add_flow_node("相机源", QPointF(20, 20))
from ui.GenericProcessDialog import GenericProcessDialog
dlg = GenericProcessDialog(w.main_window, node=n_cam, main_window=w)
combo = dlg.param_controls.get("camera_type")
model = combo.model() if combo is not None else None
check("① 参数窗口里确实有「相机类型」下拉框", combo is not None)
check("① 相机类型：USB 相机可选",
      model is not None and model.item(0).isEnabled() and model.item(0).text() == "USB 相机")
check("① 相机类型：网络相机 / 工业相机**置灰不可选**（用户要求：预留项置灰）",
      model is not None and not model.item(1).isEnabled() and not model.item(2).isEnabled(),
      None if model is None else [(model.item(i).text(), model.item(i).isEnabled())
                                  for i in range(model.rowCount())])
dlg.close()
dlg.deleteLater()

# ----------------------------------------------------------------------
# ②③④⑤ 搭流程：相机源 → 取反（看像素）、相机源 → 二值化（看参数）
# ----------------------------------------------------------------------
n_cam.params["camera_id"] = 0
n_inv = w.add_flow_node("取反", QPointF(20, 170))
n_bin = w.add_flow_node("二值化", QPointF(20, 320))
n_bin.params["thresh_value"] = 100          # 给一个有参数的节点，验证"参数共用视频槽"
w.add_edge(n_cam, n_inv)
w.add_edge(n_cam, n_bin)
w.selected_node = n_inv

check("② 执行前相机是关的", w.cap is None)
FakeCapture.value[0] = 200

w.btn_continuous.click()

check("② 点连续执行 ⇒ 相机**自动打开**（用的是节点里的编号）",
      w.cap is not None and FakeCapture.opened and FakeCapture.opened[-1] == 0,
      (w.cap is not None, list(FakeCapture.opened)))
check("② 打开的是同一台时不会重复开设备（复用，方案 A）",
      len(FakeCapture.opened) == 1, list(FakeCapture.opened))
check("③ 相机帧真的进了流程：数据层 取反 后 = 255-200 = 55（逐像素）",
      last_base_mean() is not None and abs(last_base_mean() - 55) < 1e-6, last_base_mean())

FakeCapture.value[0] = 60
w.btn_continuous.click()
check("③ 换一张相机画面 ⇒ 流程跟着变（255-60 = 195）",
      last_base_mean() is not None and abs(last_base_mean() - 195) < 1e-6, last_base_mean())
FakeCapture.value[0] = 200

check("④ 相机帧**不进结果缓存**（result_cache 保持空）", len(w.result_cache) == 0,
      list(w.result_cache))
check("⑤ 相机帧的画面键整段共用 = camera:0", last_key() == "camera:0", last_key())

# ⑥ 相机已经开着，再点执行也必须走引擎（曾经被"老摄像头预览"分支接走）
before_n = len(shown)
w.btn_continuous.click()
check("⑥ 相机开着时再点连续执行**仍然走引擎**（不是老 update_frame 分支）",
      len(shown) == before_n + 1 and last_key() == "camera:0",
      (len(shown), last_key()))
check("⑥ 「老预览」判定要求 timer 在跑（相机源自动打开的没有 timer）",
      w.timer is None and w._legacy_camera_preview_active() is False,
      (w.timer, w._legacy_camera_preview_active()))

# ⑤ 缩放：逐帧跑不该被复位
view = w.image_view
view.scale(1.4, 1.4)
z1 = view.transform().m11()
w.btn_continuous.click()
w.btn_continuous.click()
check("⑤ 逐帧执行时画面缩放不被复位（画面键没变）",
      abs(view.transform().m11() - z1) < 1e-6, (z1, view.transform().m11()))
check("⑤ 显示层当前记的画面键就是 camera:0（整段共用，没被每帧换成新键）",
      view._current_key == "camera:0", view._current_key)
check("⑤ 逐帧执行期间不会堆积新的画面键（_zoom_states 里没有相机键）",
      not [k for k in view._zoom_states if isinstance(k, str) and k.startswith("camera:")],
      list(view._zoom_states.keys()))

# ⑨ 参数复用视频槽
store = getattr(n_bin, "params_per_image", None) or {}
check("⑨ 下游节点的参数存进了「视频槽」（与视频共用一份）",
      m.VIDEO_ROI_KEY in store and store[m.VIDEO_ROI_KEY].get("thresh_value") == 100,
      {k: v.get("thresh_value") for k, v in store.items()})

# ⑩ 分辨率只存不生效
n_cam.params["resolution"] = "1920×1080"
w.btn_continuous.click()
check("⑩ 分辨率只存不生效：改 1920×1080 后实际仍是设备给的 64×48",
      shown[-1][0].shape[:2] == (CAM_H, CAM_W), shown[-1][0].shape)
check("⑩ 分辨率参数照样存下来了", n_cam.params.get("resolution") == "1920×1080")
n_cam.params["resolution"] = "默认"

# ----------------------------------------------------------------------
# ⑦ 自动出画面 + 「停止」= 不关相机、留最后一帧
# ----------------------------------------------------------------------
gw.auto_switch_box.setChecked(True)
shown[:] = []
w.btn_continuous.click()
check("⑦ 勾「自动切换」+执行 ⇒ 自动出画面（定时器开着）",
      w._video_playing and w._camera_playing and w._video_timer is not None
      and w._video_timer.isActive(),
      (w._video_playing, w._camera_playing))
check("⑦ 相机仍开着（出画面期间不关设备）", w.cap is not None and w.cap.isOpened())

FakeCapture.value[0] = 120
for _ in range(3):
    w._video_timer.timeout.emit()
check("⑦ 自动出画面的每一格都按最新画面算（255-120 = 135）",
      last_base_mean() is not None and abs(last_base_mean() - 135) < 1e-6, last_base_mean())

view_before = getattr(view, "pixmap_item", None)
gw.stop_button.click()
check("⑦ 「停止」= 停播但**不关相机**（用户定：停止不关、删除才关）",
      (not w._video_playing) and (not w._camera_playing) and w.cap is not None
      and w.cap.isOpened(), (w._video_playing, w.cap))
check("⑦ 「停止」后最后一帧仍留在画布上（不清画布）",
      view.pixmap_item is not None and view.pixmap_item is view_before,
      view.pixmap_item is not None)
check("⑦ 「停止」后画面键还在（缩放不会被复位）", last_key() == "camera:0", last_key())

# ----------------------------------------------------------------------
# ⑧ 「删除」= 关相机 + 清画布，但不动节点参数
# ----------------------------------------------------------------------
before_params = dict(n_cam.params)
releases_before = FakeCapture.releases[0]
gw.delete_button.click()
check("⑧ 「删除」= **关掉相机**（cap.release，内部 API 真被调用）",
      w.cap is None and FakeCapture.releases[0] == releases_before + 1,
      (w.cap, FakeCapture.releases[0]))
check("⑧ 「删除」= 清画布（pixmap_item 被摘掉）", view.pixmap_item is None,
      view.pixmap_item is not None)
check("⑧ 「删除」**不动相机源节点里的参数**（编号/分辨率都留着）",
      dict(n_cam.params) == before_params, (before_params, dict(n_cam.params)))
w.btn_continuous.click()
check("⑧ 删完再点执行 ⇒ 相机会重新自动打开（参数还在）",
      w.cap is not None and w.cap.isOpened(), w.cap)

# ----------------------------------------------------------------------
# ⑪ open_on_run 不勾 ⇒ 不自动开设备；取不到帧就原样透传 + 日志写说明
# ----------------------------------------------------------------------
gw.delete_button.click()
check("⑪ 前置：相机已关", w.cap is None)
n_cam.params["open_on_run"] = False
w.current_static_image = np.full((CAM_H, CAM_W, 3), 30, np.uint8)   # 有"当前图"才跑得起来
opened_before = len(FakeCapture.opened)
w.btn_continuous.click()
check("⑪ 没勾「执行时自动打开」⇒ 不自动开设备",
      w.cap is None and len(FakeCapture.opened) == opened_before,
      (w.cap, len(FakeCapture.opened)))
texts = []
for r in range(w.execution_log.rowCount()):
    item = w.execution_log.item(r, 4)
    if item is not None:
        texts.append(item.text())
check("⑪ 取不到画面时日志写明原因（不弹窗）",
      any("没有可用的相机画面" in t for t in texts), texts)
check("⑪ 取不到帧时**原样透传**（取反后 = 255-30 = 225，不是 0/黑图）",
      last_base_mean() is not None and abs(last_base_mean() - 225) < 1e-6, last_base_mean())
n_cam.params["open_on_run"] = True
w.current_static_image = None

# ----------------------------------------------------------------------
# ⑫ 旧路径回归：主窗口「打开摄像头 / 关闭」按钮
# ----------------------------------------------------------------------
w.flow_nodes.remove(n_cam)          # 模拟"这一页没有相机源节点"⇒ 老预览分支该生效
check("⑫ 无相机源节点时，老预览判定才成立（需要 timer 在跑）",
      w._legacy_camera_preview_active() is False)
w.camera_id = 1
w.open_camera()
check("⑫ 老按钮「打开摄像头」照旧能开（编号取设置里的 camera_id=1）",
      w.cap is not None and w.cap.isOpened() and FakeCapture.opened[-1] == 1,
      list(FakeCapture.opened[-3:]))
check("⑫ 老按钮会起它自己那个 30ms 刷新定时器", w.timer is not None and w.timer.isActive())
check("⑫ 老按钮顺带把参数切到视频槽", w.current_image_key == m.VIDEO_ROI_KEY,
      w.current_image_key)
check("⑫ 此时老预览判定成立 ⇒ 单步/连续走 update_frame（老行为不变）",
      w._legacy_camera_preview_active() is True)
w.close_camera()
check("⑫ 老按钮「关闭」照旧：定时器停、设备释放、画布清空",
      w.timer is None and w.cap is None and view.pixmap_item is None)

print()
print("失败项：", fails if fails else "无")
sys.exit(1 if fails else 0)
