# -*- coding: utf-8 -*-
"""
批次4 目标5-M2 验证②：通用参数窗口的两项新能力 + 颜色提取节点

    python dsh_m2_ctrl_check.py

判据要点：
    · **`slider_int`**（用户 2026.10.12 要求，界面 = 参数名 ──进度条── 数值）：
      颜色提取的 12 个阈值都是"进度条 + 微调框"，两者**双向联动**；
      滑块 = 真范围（拖不出界），微调框 = 软范围（越界值先打进去、提交时夹回）；
      存量 `int` 参数（滤波的核大小等）**一个字不动**（还是纯微调框）。
    · **`visible_when`**（行联动）：选 HSV 只显示 HSV 那 6 行、RGB 那 6 行隐藏；切过去反过来；
      来回切**不丢值**（两套阈值都写进 `node.params`）。
    · **颜色提取**：阈值内保留原色、阈值外**置黑**；只处理 ROI、ROI 外原样；
      校验：H 上限夹到 179、下限 > 上限自动互换、另一套（没显示的）不动；结果文案带像素计数。
    · 窗口宽度：新增滑块**不许把窗口顶宽**（与其它通用窗口同为 274px 量级）。
"""
import os
import sys

PROJ = r"E:\opencv_python_3_8\PySide\VisionFlowNoed"
os.chdir(PROJ)
sys.path.insert(0, PROJ)

import numpy as np
from PySide2.QtWidgets import QApplication, QSlider
from PySide2.QtCore import QPoint, QPointF

app = QApplication([])
import main as m
import widgets.FlowPages as FlowPages
import ui.GenericProcessDialog as GPD
from core.NodeRegistry import get_spec

SHOT_DIR = r'E:\opencv_python_3_8\backups\_ui_preview'


class FakeMB(object):
    warning = information = staticmethod(lambda *a, **k: None)
    question = staticmethod(lambda *a, **k: 0)


class FakeFD(object):
    getOpenFileNames = staticmethod(lambda *a, **k: ([], ""))
    getOpenFileName = staticmethod(lambda *a, **k: ("", ""))
    getSaveFileName = staticmethod(lambda *a, **k: ("", ""))
    getExistingDirectory = staticmethod(lambda *a, **k: "")


m.QMessageBox = FakeMB
FlowPages.QMessageBox = FakeMB
GPD.QMessageBox = FakeMB
m.QFileDialog = FakeFD
GPD.QFileDialog = FakeFD

fails = []


def check(name, cond, extra=''):
    print(('PASS  ' if cond else 'FAIL  ') + name + (('   <- ' + str(extra)) if extra else ''))
    if not cond:
        fails.append(name)


def row_visible(dlg, widget):
    return widget.isVisibleTo(dlg)


def param_sliders(dlg):
    """只数"参数行里的进度条"——基本参数页本来就有一个 pos_correction_slider（位置修正）"""
    return [s for s in dlg.findChildren(QSlider) if s.objectName().startswith("param_")]


w = m.MainWindow()
w.main_window.show()
w.current_static_image = np.full((120, 160, 3), 60, np.uint8)


def open_dialog(name):
    node = w.add_flow_node(name, QPointF(20, 20))
    dlg = GPD.GenericProcessDialog(w.main_window, node=node, main_window=w)
    dlg.ui.tabWidget.setCurrentIndex(1)      # 必须切到"运行参数"页，否则非当前页被显式隐藏
    dlg.show()
    app.processEvents()
    return node, dlg


# ======================================================================
# ① slider_int：进度条 + 微调框，双向联动
# ======================================================================
node, dlg = open_dialog("颜色提取")
spec = get_spec("颜色提取")
slider_keys = [s[0] for s in spec.param_specs if s[2] == "slider_int"]
check('① 颜色提取声明了 12 个「进度条 + 微调框」参数', len(slider_keys) == 12, len(slider_keys))

pairs = [(k, dlg.param_controls[k]) for k in slider_keys]
check('① 每个都是 QSlider + QSpinBox 的组合',
      all(hasattr(c, "slider") and hasattr(c, "spin") for _, c in pairs), None)
check('① 控件名字是 param_<键名>（排查问题用）',
      all(c.objectName() == "param_" + k for k, c in pairs),
      [c.objectName() for _, c in pairs][:3])

h_low = dlg.param_controls["hsv_h_low"]
check('① 滑块范围 = 真范围（H 是 0~179，OpenCV 口径）',
      (h_low.slider.minimum(), h_low.slider.maximum()) == (0, 179),
      (h_low.slider.minimum(), h_low.slider.maximum()))
check('① 微调框的"真范围"记在 _soft_min / _soft_max 上（软范围机制）',
      (h_low.spin.property("_soft_min"), h_low.spin.property("_soft_max")) == (0, 179),
      (h_low.spin.property("_soft_min"), h_low.spin.property("_soft_max")))

h_low.slider.setValue(120)
check('① 拖进度条 ⇒ 数值框跟着变（滑块 → 框）', h_low.spin.value() == 120, h_low.spin.value())
h_low.spin.setValue(35)
check('① 改数值框 ⇒ 进度条跟着走（框 → 滑块）', h_low.slider.value() == 35, h_low.slider.value())

# ★ "进度条 + 微调框"整行必须完整落在视口里：横向滚动条是被**禁用**的，
#   一旦内容比视口宽，多出来的部分会被静默裁掉（第一版滑块最小宽 90 就是这样把
#   微调框右侧的上下箭头切掉的，靠这条断言抓出来）。
vp = dlg.run_params_scroll.viewport()
right_edges = [c.spin.mapTo(vp, QPoint(c.spin.width(), 0)).x() for _, c in pairs]
check('① 每行微调框的右缘都在视口内（右侧箭头没被裁掉）',
      all(x <= vp.width() for x in right_edges),
      (vp.width(), sorted(set(right_edges))))
check('① 内容最小宽 ≤ 视口宽（没有横向溢出）',
      dlg.run_params_scroll.widget().minimumSizeHint().width() <= vp.width(),
      (dlg.run_params_scroll.widget().minimumSizeHint().width(), vp.width()))

s_high = dlg.param_controls["hsv_s_high"]
s_high.spin.setValue(999)          # 越界：软范围允许先打进去，提交时夹回真范围
check('① 越界值提交后夹回上限，并且**滑块也同步**（S 上限 255）',
      s_high.spin.value() == 255 and s_high.slider.value() == 255,
      (s_high.spin.value(), s_high.slider.value()))
s_high.spin.setValue(-50)
check('① 越界值提交后夹回下限，滑块同步（S 上限 → 0）',
      s_high.spin.value() == 0 and s_high.slider.value() == 0,
      (s_high.spin.value(), s_high.slider.value()))
s_high.spin.setValue(200)
s_high.slider.setValue(77)
check('① 联动后两边始终一致', s_high.spin.value() == s_high.slider.value() == 77,
      (s_high.spin.value(), s_high.slider.value()))

# ======================================================================
# ② visible_when：选哪个模型只显示哪一套阈值
# ======================================================================
hsv_keys = [k for k in slider_keys if k.startswith("hsv_")]
rgb_keys = [k for k in slider_keys if k.startswith("rgb_")]
combo = dlg.param_controls["color_model"]
check('② 默认模型 = HSV', combo.currentText() == "HSV", combo.currentText())
check('② 默认：HSV 那 6 行可见、RGB 那 6 行隐藏',
      all(row_visible(dlg, dlg.param_controls[k]) for k in hsv_keys)
      and not any(row_visible(dlg, dlg.param_controls[k]) for k in rgb_keys),
      ([row_visible(dlg, dlg.param_controls[k]) for k in hsv_keys],
       [row_visible(dlg, dlg.param_controls[k]) for k in rgb_keys]))
dlg.grab().save(os.path.join(SHOT_DIR, 'm2_color_hsv.png'))

dlg.param_controls["hsv_s_high"].spin.setValue(200)     # 先改一个值，等会儿验证"切回来不丢"
combo.setCurrentText("RGB")
app.processEvents()
check('② 切到 RGB：RGB 那 6 行可见、HSV 那 6 行隐藏',
      all(row_visible(dlg, dlg.param_controls[k]) for k in rgb_keys)
      and not any(row_visible(dlg, dlg.param_controls[k]) for k in hsv_keys),
      None)
dlg.grab().save(os.path.join(SHOT_DIR, 'm2_color_rgb.png'))

combo.setCurrentText("HSV")
app.processEvents()
check('② 切回 HSV：值没丢（S 上限还是 200）',
      dlg.param_controls["hsv_s_high"].spin.value() == 200,
      dlg.param_controls["hsv_s_high"].spin.value())
dlg._update_params()
check('② 两套阈值**都**写进了 node.params（来回切不丢值）',
      node.params.get("hsv_s_high") == 200 and "rgb_r_high" in node.params
      and node.params.get("rgb_r_high") == 255,
      {k: v for k, v in node.params.items() if k.startswith(("hsv_", "rgb_", "color_"))})

# ======================================================================
# ③ 不许顶宽窗口 + 存量 int 参数界面没被动过
# ======================================================================
check('③ 颜色提取窗口宽度与其它通用窗口一致（未被进度条顶宽，274px 量级）',
      abs(dlg.width() - 274) <= 8, (dlg.width(), dlg.height()))
dlg.close()

node_b, dlg_b = open_dialog("滤波")
check('③ 存量 int 参数（滤波的核大小）**还是纯微调框**，没被换成进度条',
      dlg_b.param_controls["blur_ksize"].findChild(QSlider) is None
      and dlg_b.param_controls["blur_ksize"].__class__.__name__ == "QSpinBox",
      dlg_b.param_controls["blur_ksize"].__class__.__name__)
check('③ 滤波窗口里没有一个"参数进度条"（存量参数界面没被动过）', param_sliders(dlg_b) == [],
      param_sliders(dlg_b))
check('③ 滤波窗口宽度仍是 274px 量级（存量界面零回归）',
      abs(dlg_b.width() - 274) <= 8, (dlg_b.width(), dlg_b.height()))
dlg_b.close()

# 人脸窗口：3 个数值参数按用户要求**不上滑块**
node_f, dlg_f = open_dialog("人脸识别")
check('③ 人脸那 3 个数值参数没上滑块（用户 2026.10.12 拍板：保持微调框）',
      param_sliders(dlg_f) == [], param_sliders(dlg_f))
dlg_f.close()

print('-' * 70)
if fails:
    print('失败项：%d' % len(fails))
    for name in fails:
        print('   - ' + name)
else:
    print('失败项：无')
sys.exit(1 if fails else 0)
